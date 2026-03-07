# app/services/profile_generator.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib import request, error

from PySide6.QtCore import QObject, Signal, Slot, Property, QThreadPool, QRunnable


def _normalize_base_url(u: str) -> str:
    s = (u or "").strip()
    while s.endswith("/"):
        s = s[:-1]
    return s


# --------- Sanitizers (labels <=5 chars, no brackets) ---------
_BRACKET_CHARS_RE = re.compile(r"[（）\(\)\[\]【】{}<>《》]")
_SPACES_RE = re.compile(r"\s+")


def _strip_brackets(s: str) -> str:
    return _BRACKET_CHARS_RE.sub("", s or "")


def _compact_text(s: str) -> str:
    s = _strip_brackets(s)
    s = _SPACES_RE.sub("", s)
    return s.strip()


def _limit_chars(s: str, max_len: int) -> str:
    s = _compact_text(s)
    if max_len <= 0:
        return ""
    return s[:max_len]


def _sanitize_mbti(s: str) -> str:
    # keep only 4-letter MBTI, e.g. INTJ
    t = (s or "").upper()
    m = re.search(r"\b([IE][NS][TF][JP])\b", t)
    if m:
        return m.group(1)
    # fallback
    t = _compact_text(t)
    return t[:4]


def _sanitize_summary(s: str, max_len: int = 80) -> str:
    # summary can be longer, but remove bracket chars; keep spaces minimal
    t = _strip_brackets(s)
    t = t.replace("\r", " ").replace("\n", " ").strip()
    t = re.sub(r"\s{2,}", " ", t)
    return t[:max_len]


def _safe_extract_json(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    if not t:
        raise ValueError("empty model output")

    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"```\s*$", "", t)
    t = t.strip()

    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    i = t.find("{")
    j = t.rfind("}")
    if i >= 0 and j > i:
        sub = t[i : j + 1]
        obj2 = json.loads(sub)
        if isinstance(obj2, dict):
            return obj2

    raise ValueError("model output is not valid JSON")


def _normalize_profile_payload(obj: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize to schema:
    {
      "profile": {
        "labels": {8 fields},
        "summary": str
      },
      "memory_graph_init": {"only_fill":"性格特征","content": str}
    }
    Additionally enforce:
    - labels values <= 5 chars
    - no () [] 【】 etc in labels
    - mbti is 4 letters
    - summary non-empty (fallback if empty)
    """
    # accept strict schema first
    prof = obj.get("profile") if isinstance(obj.get("profile"), dict) else {}
    labels = prof.get("labels") if isinstance(prof.get("labels"), dict) else {}

    # tolerant fallback: sometimes model may return top-level labels/summary
    if not labels and isinstance(obj.get("labels"), dict):
        labels = obj.get("labels")  # type: ignore[assignment]
    raw_summary = prof.get("summary", "")
    if (not raw_summary) and isinstance(obj.get("summary"), str):
        raw_summary = obj.get("summary")

    def _get_label(k: str) -> str:
        v = labels.get(k, "")
        s = str(v) if isinstance(v, (str, int, float)) else ""
        if k == "mbti":
            return _sanitize_mbti(s)
        return _limit_chars(s, 5)

    mbti = _get_label("mbti")
    time_personality = _get_label("time_personality")
    industry = _get_label("industry")
    schedule_style = _get_label("schedule_style")
    strength = _get_label("strength")
    rhythm = _get_label("rhythm")
    energy_peak = _get_label("energy_peak")
    task_preference = _get_label("task_preference")

    summary = _sanitize_summary(str(raw_summary or ""), max_len=90)

    # fallback summary if empty
    if not summary:
        parts = []
        if mbti:
            parts.append(f"{mbti}型")
        if industry:
            parts.append(industry)
        if schedule_style:
            parts.append(f"偏好{schedule_style}")
        if strength:
            parts.append(f"擅长{strength}")
        if energy_peak:
            parts.append(f"高峰{energy_peak}")
        if task_preference:
            parts.append(task_preference)
        summary = "，".join(parts) if parts else "已生成你的工作画像。"

    norm = {
        "profile": {
            "labels": {
                "mbti": mbti,
                "time_personality": time_personality,
                "industry": industry,
                "schedule_style": schedule_style,
                "strength": strength,
                "rhythm": rhythm,
                "energy_peak": energy_peak,
                "task_preference": task_preference,
            },
            "summary": summary,
        },
        "memory_graph_init": {
            "only_fill": "性格特征",
            "content": "",
        },
    }

    mg = obj.get("memory_graph_init") if isinstance(obj.get("memory_graph_init"), dict) else {}
    content = mg.get("content")
    if isinstance(content, str):
        norm["memory_graph_init"]["content"] = content.strip()

    return norm


def _post_json(url: str, api_key: str, payload: dict[str, Any], timeout_s: float = 60.0) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("Authorization", f"Bearer {api_key.strip()}")
    with request.urlopen(req, data=data, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        st = getattr(resp, "status", 0) or 0
        return st, raw


def _extract_error_message(raw: str) -> str:
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            err = obj.get("error")
            if isinstance(err, dict):
                msg = err.get("message")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
            msg2 = obj.get("message")
            if isinstance(msg2, str) and msg2.strip():
                return msg2.strip()
    except Exception:
        pass
    return raw.strip()[:400]


# 关键：要求每个标签 <=5 字，且不含括号；MBTI 只输出 4 字母
SYSTEM_PROMPT = (
    "你是“用户画像与记忆初始化助手”。"
    "你只输出 JSON，不要解释过程，不要包含 Markdown，不要输出多余文本。"
    "必须严格按以下 schema 输出，字段必须齐全："
    "{\"profile\":{\"labels\":{\"mbti\":\"\",\"time_personality\":\"\",\"industry\":\"\",\"schedule_style\":\"\","
    "\"strength\":\"\",\"rhythm\":\"\",\"energy_peak\":\"\",\"task_preference\":\"\"},\"summary\":\"\"},"
    "\"memory_graph_init\":{\"only_fill\":\"性格特征\",\"content\":\"\"}}"
    "输出约束："
    "1) labels 的每个值必须不超过 5 个汉字（或等价长度），不得包含任何括号字符（（）()[]【】等），不要出现“：”或“(xxx)”。"
    "2) mbti 只输出 4 个字母（例如 INTJ），不要加中文后缀。"
    "3) summary 必须给出一句话总结（20~30字），开头是“你是”，不要为空。"
)


@dataclass(frozen=True)
class _GenCfg:
    api_key: str
    base_url: str
    model: str


class _WorkerSignals(QObject):
    finished = Signal(bool, str, object)  # ok, errMsg, resultObj


class _GenWorker(QRunnable):
    def __init__(self, cfg: _GenCfg, user_prompt: str):
        super().__init__()
        self.signals = _WorkerSignals()
        self._cfg = cfg
        self._user_prompt = user_prompt

    def run(self) -> None:
        base = _normalize_base_url(self._cfg.base_url)
        if not base:
            self.signals.finished.emit(False, "Base URL 不能为空", {})
            return
        if not self._cfg.api_key.strip():
            self.signals.finished.emit(False, "请先配置 Kimi API Key", {})
            return
        if not self._cfg.model.strip():
            self.signals.finished.emit(False, "请先配置 Model", {})
            return

        url = f"{base}/chat/completions"
        payload = {
            "model": self._cfg.model.strip(),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._user_prompt},
            ],
            "temperature": 0.2,
        }

        try:
            st, raw = _post_json(url, self._cfg.api_key, payload, timeout_s=80.0)
            if not (200 <= st < 300):
                self.signals.finished.emit(False, _extract_error_message(raw) or f"HTTP {st}", {})
                return
            resp = json.loads(raw)
            content = ""
            if isinstance(resp, dict):
                choices = resp.get("choices")
                if isinstance(choices, list) and choices:
                    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                    if isinstance(msg, dict):
                        content = str(msg.get("content", "") or "")
            if not content:
                self.signals.finished.emit(False, "模型返回为空", {})
                return

            obj = _safe_extract_json(content)
            norm = _normalize_profile_payload(obj)
            self.signals.finished.emit(True, "", norm)
        except error.HTTPError as e:
            try:
                raw = e.read().decode("utf-8", errors="replace")
            except Exception:
                raw = ""
            self.signals.finished.emit(False, _extract_error_message(raw) or f"HTTP {getattr(e, 'code', '')}", {})
        except error.URLError:
            self.signals.finished.emit(False, "网络错误：请检查 Base URL / 网络 / 代理", {})
        except Exception as ex:
            self.signals.finished.emit(False, f"生成失败：{ex}", {})


class ProfileGenerator(QObject):
    busyChanged = Signal()
    lastErrorChanged = Signal()
    finished = Signal(bool, str)

    def __init__(self, draft: QObject, quiz: QObject, parent: QObject | None = None):
        super().__init__(parent)
        self._draft = draft
        self._quiz = quiz
        self._pool = QThreadPool.globalInstance()
        self._active_workers: set[_GenWorker] = set()

        self._busy = False
        self._last_error = ""

    def _get_busy(self) -> bool:
        return self._busy

    def _get_last_error(self) -> str:
        return self._last_error

    busy = Property(bool, _get_busy, notify=busyChanged)
    lastError = Property(str, _get_last_error, notify=lastErrorChanged)

    def _set_busy(self, v: bool) -> None:
        v = bool(v)
        if self._busy != v:
            self._busy = v
            self.busyChanged.emit()

    def _set_last_error(self, s: str) -> None:
        s = (s or "").strip()
        if self._last_error != s:
            self._last_error = s
            self.lastErrorChanged.emit()

    @Slot()
    def generateFromDraft(self) -> None:
        if self._busy:
            return
        try:
            self._draft.loadDraft()
        except Exception:
            pass

        cfg = _GenCfg(
            api_key=str(getattr(self._draft, "getDraftKimiApiKey")()),
            base_url=str(getattr(self._draft, "getDraftKimiBaseUrl")()),
            model=str(getattr(self._draft, "getDraftKimiModel")()),
        )

        assistant_name = str(getattr(self._draft, "getDraftAssistantName")() or "")
        user_calling = str(getattr(self._draft, "getDraftUserDisplayName")() or "")

        try:
            answers = self._quiz.exportAnswersForKimi()
        except Exception:
            answers = []

        lines: list[str] = []
        lines.append(f"称呼设定：assistant_name={assistant_name}；user_calling={user_calling}")
        lines.append("答题结果：")
        for a in answers:
            if not isinstance(a, dict):
                continue
            g = str(a.get("group_name", "") or a.get("group_id", ""))
            qid = str(a.get("qid", ""))
            title = str(a.get("title", ""))
            sel = a.get("selected_text")
            if isinstance(sel, list):
                sel_txt = " / ".join([str(x) for x in sel if str(x)])
            else:
                sel_txt = ""
            if sel_txt:
                lines.append(f"- [{g}] {qid} {title} => {sel_txt}")
            else:
                selected = a.get("selected")
                if isinstance(selected, list):
                    sel_k = "/".join([str(x) for x in selected if str(x)])
                else:
                    sel_k = ""
                lines.append(f"- [{g}] {qid} {title} => {sel_k}")

        user_prompt = "\n".join(lines)

        self._set_last_error("")
        self._set_busy(True)

        worker = _GenWorker(cfg, user_prompt)
        worker.setAutoDelete(False)
        self._active_workers.add(worker)
        worker.signals.finished.connect(
            lambda ok, err_msg, result_obj, worker=worker: self._handle_worker_finished(
                worker, ok, err_msg, result_obj
            )
        )
        self._pool.start(worker)

    def _handle_worker_finished(
        self, worker: _GenWorker, ok: bool, err_msg: str, result_obj: object
    ) -> None:
        self._active_workers.discard(worker)
        try:
            worker.signals.deleteLater()
        except Exception:
            pass
        self._on_finished(ok, err_msg, result_obj)

    @Slot(bool, str, object)
    def _on_finished(self, ok: bool, err_msg: str, result_obj: object) -> None:
        self._set_busy(False)
        if ok and isinstance(result_obj, dict):
            try:
                self._draft.setDraftProfileResult(result_obj)
                self._draft.saveDraft()
            except Exception:
                pass
            self._set_last_error("")
            self.finished.emit(True, "")
        else:
            self._set_last_error(err_msg or "生成失败")
            self.finished.emit(False, self._last_error)
