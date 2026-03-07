from __future__ import annotations

import html
import json
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import requests
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _today() -> date:
    return _now().date()


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _safe_date(value: str) -> date | None:
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _date_range(start: date, end: date) -> list[date]:
    out: list[date] = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _month_keys_between(start: date, end: date) -> list[str]:
    out: list[str] = []
    cur = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cur <= last:
        out.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return out


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _iso_week_key(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _review_key(start_day: date, end_day: date) -> str:
    return f"{_iso_week_key(start_day)}_to_{end_day.isoformat()}"


def _format_dot_range(start_text: str, end_text: str) -> str:
    start_day = _safe_date(start_text)
    end_day = _safe_date(end_text)
    if not start_day or not end_day:
        return f"{start_text} - {end_text}".strip()
    if start_day.year == end_day.year:
        return f"{start_day:%Y.%m.%d} - {end_day:%m.%d}"
    return f"{start_day:%Y.%m.%d} - {end_day:%Y.%m.%d}"


def _human_ts(value: str) -> str:
    try:
        dt = datetime.fromisoformat((value or "").strip())
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return (value or "").strip()


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _clean_lines(value: Any, *, limit: int, fallback: list[str] | None = None) -> list[str]:
    fallback = fallback or []
    out: list[str] = []
    if isinstance(value, list):
        for item in value:
            text = _clean_text(item)
            if text and text not in out:
                out.append(text)
            if len(out) >= limit:
                break
    return out if out else list(fallback[:limit])


def _extract_first_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    low = (text or "").lower()
    return any(k.lower() in low for k in keywords)


def _clip(items: list[str], limit: int) -> list[str]:
    return [str(x) for x in items[:limit]]


class ReviewService(QObject):
    reportListChanged = Signal()
    selectedReportChanged = Signal()
    loadingChanged = Signal()
    toastRequested = Signal(str)
    desktopNotify = Signal(str)
    feishuNotify = Signal(str)
    _workerFinished = Signal(object)

    def __init__(self, *, get_data_dir: Callable[[], Path], parent: QObject | None = None):
        super().__init__(parent)
        self._get_data_dir = get_data_dir
        self._lock = threading.Lock()
        self._report_list: list[dict[str, Any]] = []
        self._selected_report: dict[str, Any] = {}
        self._loading = False
        self._active_keys: set[str] = set()
        self._workerFinished.connect(self._on_worker_finished)
        self.reloadReports()

    def _data_dir(self) -> Path:
        return self._get_data_dir().resolve()

    def _config_path(self) -> Path:
        return self._data_dir() / "config.json"

    def _config(self) -> dict[str, Any]:
        return _read_json(self._config_path(), {})

    def _save_config(self, cfg: dict[str, Any]) -> None:
        _atomic_write_json(self._config_path(), cfg)

    def _weekly_dir(self) -> Path:
        path = self._data_dir() / "reviews" / "weekly"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _exports_dir(self) -> Path:
        path = self._data_dir() / "reviews" / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _review_path(self, key: str) -> Path:
        return self._weekly_dir() / f"{key}.json"

    def _set_loading(self, value: bool) -> None:
        v = bool(value)
        if self._loading != v:
            self._loading = v
            self.loadingChanged.emit()

    def _current_week_period(self) -> tuple[date, date]:
        end_day = _today()
        return _week_start(end_day), end_day

    def _read_review_obj(self, path: Path) -> dict[str, Any]:
        obj = _read_json(path, {})
        if not isinstance(obj, dict):
            obj = {}
        start_text = str(obj.get("period_start", "") or "").strip()
        end_text = str(obj.get("period_end", "") or "").strip()
        start_day = _safe_date(start_text)
        end_day = _safe_date(end_text)
        if not start_day or not end_day:
            name = path.stem
            if "_to_" in name:
                maybe_end = name.split("_to_")[-1]
                end_day = _safe_date(maybe_end)
                if end_day:
                    start_day = _week_start(end_day)
        if not start_day or not end_day:
            end_day = _today()
            start_day = _week_start(end_day)
        obj["period_start"] = start_day.isoformat()
        obj["period_end"] = end_day.isoformat()
        obj.setdefault("generated_at", "")
        obj.setdefault("summary", {})
        obj.setdefault("report", {})
        obj.setdefault("push", {})
        obj.setdefault("generation_source", "local")
        return obj

    def _review_sequence_no(self, review: dict[str, Any]) -> int:
        try:
            value = int(review.get("sequence_no", 0) or 0)
        except Exception:
            return 0
        return value if value > 0 else 0

    def _next_sequence_no(self) -> int:
        max_seq = 0
        for path in self._weekly_dir().glob("*.json"):
            review = self._read_review_obj(path)
            max_seq = max(max_seq, self._review_sequence_no(review))
        if max_seq > 0:
            return max_seq + 1
        return sum(1 for _ in self._weekly_dir().glob("*.json")) + 1

    def _ensure_review_sequence_numbers(self) -> dict[str, int]:
        records: list[dict[str, Any]] = []
        used: set[int] = set()
        assigned: dict[str, int] = {}

        for path in self._weekly_dir().glob("*.json"):
            review = self._read_review_obj(path)
            key = path.stem
            seq = self._review_sequence_no(review)
            record = {"path": path, "key": key, "review": review, "seq": seq}
            records.append(record)
            if seq > 0 and seq not in used:
                used.add(seq)
                assigned[key] = seq
            else:
                record["seq"] = 0

        pending = [record for record in records if int(record.get("seq", 0) or 0) <= 0]
        pending.sort(
            key=lambda record: (
                str(record["review"].get("generated_at", "") or ""),
                str(record["review"].get("period_end", "") or ""),
                str(record["key"]),
            )
        )

        next_seq = 1
        for record in pending:
            while next_seq in used:
                next_seq += 1
            seq = next_seq
            record["review"]["sequence_no"] = seq
            _atomic_write_json(record["path"], record["review"])
            used.add(seq)
            assigned[str(record["key"])] = seq
            next_seq += 1

        return assigned

    def _normalize_with_fallback(self, review: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        raw_summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
        raw_report = review.get("report") if isinstance(review.get("report"), dict) else {}
        raw_projects = raw_report.get("projects") if isinstance(raw_report.get("projects"), list) else []
        projects: list[dict[str, str]] = []
        for index, item in enumerate(raw_projects[:3]):
            if not isinstance(item, dict):
                continue
            title = _clean_text(item.get("title", "") or f"项目/任务 {chr(65 + index)}")
            content = _clean_text(item.get("content", ""))
            if title or content:
                projects.append({"title": title or f"项目/任务 {chr(65 + index)}", "content": content})
        if not projects:
            projects = list(fallback["report"]["projects"])

        retrospective = raw_report.get("retrospective") if isinstance(raw_report.get("retrospective"), dict) else {}
        learning_energy = raw_report.get("learning_and_energy") if isinstance(raw_report.get("learning_and_energy"), dict) else {}
        next_week_plan = raw_report.get("next_week_plan") if isinstance(raw_report.get("next_week_plan"), dict) else {}
        mood_interest = raw_report.get("mood_and_interest") if isinstance(raw_report.get("mood_and_interest"), dict) else {}

        summary = {
            "period": _clean_text(raw_summary.get("period", "")) or fallback["summary"]["period"],
            "core_progress": _clean_lines(
                raw_summary.get("core_progress"),
                limit=3,
                fallback=fallback["summary"]["core_progress"],
            ),
            "risks": _clean_lines(
                raw_summary.get("risks"),
                limit=3,
                fallback=fallback["summary"]["risks"],
            ),
            "next_week_focus": _clean_lines(
                raw_summary.get("next_week_focus"),
                limit=2,
                fallback=fallback["summary"]["next_week_focus"],
            ),
        }

        report_norm = {
            "projects": projects,
            "retrospective": {
                "difficulties": _clean_lines(
                    retrospective.get("difficulties"),
                    limit=3,
                    fallback=fallback["report"]["retrospective"]["difficulties"],
                ),
                "improvements": _clean_lines(
                    retrospective.get("improvements"),
                    limit=3,
                    fallback=fallback["report"]["retrospective"]["improvements"],
                ),
            },
            "learning_and_energy": {
                "learning": _clean_lines(
                    learning_energy.get("learning"),
                    limit=3,
                    fallback=fallback["report"]["learning_and_energy"]["learning"],
                ),
                "energy": _clean_text(learning_energy.get("energy", "")) or fallback["report"]["learning_and_energy"]["energy"],
            },
            "next_week_plan": {
                "key_tasks": _clean_lines(
                    next_week_plan.get("key_tasks"),
                    limit=3,
                    fallback=fallback["report"]["next_week_plan"]["key_tasks"],
                ),
                "routine": _clean_lines(
                    next_week_plan.get("routine"),
                    limit=3,
                    fallback=fallback["report"]["next_week_plan"]["routine"],
                ),
            },
            "mood_and_interest": {
                "mood": _clean_text(mood_interest.get("mood", "")) or fallback["report"]["mood_and_interest"]["mood"],
                "interest_shift": _clean_lines(
                    mood_interest.get("interest_shift"),
                    limit=4,
                    fallback=fallback["report"]["mood_and_interest"]["interest_shift"],
                ),
                "tags": _clean_lines(
                    mood_interest.get("tags"),
                    limit=4,
                    fallback=fallback["report"]["mood_and_interest"]["tags"],
                ),
            },
        }
        review["summary"] = summary
        review["report"] = report_norm
        return review

    def _chat_records_between(self, start_day: date, end_day: date) -> list[dict[str, Any]]:
        chat_dir = self._data_dir() / "chat"
        if not chat_dir.exists():
            return []
        out: list[dict[str, Any]] = []
        for day in _date_range(start_day, end_day):
            path = chat_dir / f"{day.isoformat()}.jsonl"
            if not path.exists():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
        out.sort(key=lambda item: str(item.get("ts", "") or ""))
        return out

    def _is_meaningful_user_dialogue(self, text: str) -> bool:
        raw = _clean_text(text)
        if len(raw) < 2:
            return False
        low = raw.lower()
        command_like = {
            "确认", "确定", "取消", "日程", "待办", "打开", "关闭", "导出", "分享",
            "每周回顾", "回顾", "设置", "ok", "okay", "好的", "收到"
        }
        if raw in command_like or low in command_like:
            return False
        if raw.startswith("/") or raw.startswith("add_") or raw.startswith("delete_") or raw.startswith("update_"):
            return False
        if raw.isdigit():
            return False
        return True

    def _user_dialogues_between(self, start_day: date, end_day: date) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for item in self._chat_records_between(start_day, end_day):
            if str(item.get("role", "") or "").strip() != "user":
                continue
            text = _clean_text(item.get("text", ""))
            if not self._is_meaningful_user_dialogue(text):
                continue
            out.append(
                {
                    "ts": str(item.get("ts", "") or ""),
                    "text": text,
                    "channel": str(item.get("channel", "") or ""),
                }
            )
        return out

    def _schedule_snapshot_between(self, start_day: date, end_day: date) -> dict[str, Any]:
        schedule_dir = self._data_dir() / "schedule"
        events: list[dict[str, Any]] = []
        todos: list[dict[str, Any]] = []
        logs: list[dict[str, Any]] = []
        if not schedule_dir.exists():
            return {"events": [], "todos": [], "change_log": []}
        for month in _month_keys_between(start_day, end_day):
            path = schedule_dir / f"{month}.json"
            month_obj = _read_json(path, {})
            if not isinstance(month_obj, dict):
                continue
            for item in month_obj.get("events", []):
                if not isinstance(item, dict):
                    continue
                day = _safe_date(str(item.get("date", "") or ""))
                if day and start_day <= day <= end_day:
                    events.append(item)
            for item in month_obj.get("todos", []):
                if isinstance(item, dict):
                    todos.append(item)
            for item in month_obj.get("change_log", []):
                if not isinstance(item, dict):
                    continue
                try:
                    ts = datetime.fromisoformat(str(item.get("ts", "") or ""))
                except Exception:
                    continue
                if start_day <= ts.date() <= end_day:
                    logs.append(item)
        events.sort(key=lambda item: f"{item.get('date', '')} {item.get('time', '')}")
        logs.sort(key=lambda item: str(item.get("ts", "") or ""))
        return {"events": events, "todos": todos, "change_log": logs}

    def _future_schedule_after(self, end_day: date, days: int = 7) -> dict[str, Any]:
        start_day = end_day + timedelta(days=1)
        return self._schedule_snapshot_between(start_day, end_day + timedelta(days=days))

    def _load_profile_summary(self) -> str:
        profile = _read_json(self._data_dir() / "profile.json", {})
        if not isinstance(profile, dict):
            return ""
        return _clean_text(profile.get("summary", ""))

    def _load_memory_sections(self) -> dict[str, Any]:
        memory = _read_json(self._data_dir() / "memory_graph.json", {})
        if not isinstance(memory, dict):
            return {}
        sections = memory.get("sections")
        return sections if isinstance(sections, dict) else {}

    def _extract_learning_lines(self, dialogues: list[dict[str, str]]) -> list[str]:
        keywords = ["学习", "阅读", "看完", "读完", "课程", "技能", "研究", "教程", "文章", "复盘"]
        lines: list[str] = []
        for item in dialogues:
            text = _clean_text(item.get("text", ""))
            if len(text) < 6:
                continue
            if _contains_any(text, keywords):
                lines.append(text)
        return _clip(lines, 3)

    def _extract_risk_lines(self, dialogues: list[dict[str, str]]) -> list[str]:
        keywords = ["风险", "阻碍", "困难", "卡住", "延期", "来不及", "疲惫", "焦虑", "压力", "低效", "问题"]
        lines: list[str] = []
        for item in dialogues:
            text = _clean_text(item.get("text", ""))
            if text and _contains_any(text, keywords):
                lines.append(text)
        return _clip(lines, 3)

    def _extract_interest_tags(self, dialogues: list[dict[str, str]]) -> list[str]:
        keywords = {
            "AI": ["ai", "kimi", "模型", "智能体"],
            "效率工具": ["效率", "工具", "飞书", "自动化", "整理"],
            "产品规划": ["产品", "需求", "版本", "规划"],
            "开发实现": ["开发", "代码", "qml", "python", "接口"],
            "数据分析": ["数据", "分析", "统计", "报表"],
            "学习成长": ["学习", "阅读", "课程", "知识"],
            "日程管理": ["日程", "提醒", "待办", "计划"],
        }
        counter: Counter[str] = Counter()
        samples = [str(x.get("text", "") or "") for x in dialogues]
        for sample in samples:
            low = sample.lower()
            for label, hits in keywords.items():
                if any(h.lower() in low for h in hits):
                    counter[label] += 1
        if not counter:
            return ["常规沟通", "信息整理"]
        return [item[0] for item in counter.most_common(4)]

    def _extract_core_progress_lines(self, dialogues: list[dict[str, str]]) -> list[str]:
        keywords = ["完成", "搞定", "推进", "实现", "写完", "解决", "已经", "上线", "提交", "测试"]
        lines: list[str] = []
        for item in dialogues:
            text = _clean_text(item.get("text", ""))
            if len(text) < 6:
                continue
            if _contains_any(text, keywords):
                lines.append(text)
        if not lines:
            for item in dialogues:
                text = _clean_text(item.get("text", ""))
                if len(text) >= 8:
                    lines.append(f"本周期主要围绕“{text[:28]}”展开讨论。")
        return _clip(lines, 3)

    def _extract_next_focus_lines(self, dialogues: list[dict[str, str]], tags: list[str]) -> list[str]:
        keywords = ["下周", "接下来", "准备", "计划", "打算", "下一步", "后续", "要做", "想要"]
        lines: list[str] = []
        for item in dialogues:
            text = _clean_text(item.get("text", ""))
            if len(text) < 6:
                continue
            if _contains_any(text, keywords):
                lines.append(text)
        if not lines:
            for tag in tags[:2]:
                lines.append(f"继续围绕“{tag}”相关议题推进更具体的执行安排。")
        return _clip(lines, 2)

    def _build_local_review(self, start_day: date, end_day: date) -> dict[str, Any]:
        dialogues = self._user_dialogues_between(start_day, end_day)
        core_progress = self._extract_core_progress_lines(dialogues)
        if not core_progress:
            core_progress = ["本周期暂无足够的用户对话内容，暂时无法提炼稳定的核心进展。"]

        risk_lines = self._extract_risk_lines(dialogues)
        if not risk_lines:
            risk_lines = ["用户对话中暂无明确风险表述，需继续观察是否出现卡点、压力或延期信号。"]

        interest_tags = self._extract_interest_tags(dialogues)
        next_week_focus = self._extract_next_focus_lines(dialogues, interest_tags)
        if not next_week_focus:
            next_week_focus = ["优先围绕本周期高频讨论主题继续推进，并补齐尚未形成结论的议题。"]

        projects: list[dict[str, str]] = []
        source_items = core_progress[:2]
        for index, text in enumerate(source_items):
            title = f"项目/任务 {chr(65 + index)}"
            content = f"本周期用户对话主要围绕「{text}」展开，可视为当前最核心的推进议题；建议下周继续聚焦这一主题并形成更明确的行动结果。"
            projects.append({"title": title, "content": content})
        while len(projects) < 2:
            title = f"项目/任务 {chr(65 + len(projects))}"
            projects.append({"title": title, "content": "本周期暂无更多可用的用户对话证据，建议后续补充更完整的表达内容后再做细化分析。"})

        learning_lines = self._extract_learning_lines(dialogues)
        if not learning_lines:
            learning_lines = ["用户对话中暂无明确的学习型表达，建议后续主动记录阅读、研究或技能练习内容。"]

        negative_hits = sum(1 for item in dialogues if _contains_any(str(item.get("text", "")), ["累", "疲惫", "焦虑", "压力", "烦"]))
        positive_hits = sum(1 for item in dialogues if _contains_any(str(item.get("text", "")), ["完成", "推进", "顺利", "开心", "不错"]))
        if negative_hits > positive_hits:
            mood = "本周期整体压力偏高，语气中出现了更多疲惫和阻塞信号，建议下周为高强度任务预留缓冲。"
            energy = "时间分配偏紧，恢复和专注切换成本较高，建议压缩并行事项并保留固定休息窗口。"
        elif positive_hits > 0:
            mood = "本周期整体状态相对平稳，推进语气偏积极，说明当前节奏基本可控。"
            energy = "时间分配总体可接受，重点任务有连续推进迹象，但仍需防止后段堆积。"
        else:
            mood = "本周期可用于判断情绪波动的用户对话证据有限，整体状态更接近常规沟通。"
            energy = "仅凭当前用户对话还不足以精确判断精力峰谷，建议后续持续表达任务压力和恢复状态。"

        interest_shift = [f"本周期对「{tag}」的关注频次相对更高。" for tag in interest_tags[:3]]
        if len(interest_shift) < 2:
            interest_shift.append("当前可见兴趣焦点仍较稳定，尚未从用户对话中看到明显的新方向迁移。")

        routine = ["继续记录更完整的需求、问题和计划表达，为后续回顾提供更稳定的语料。"]

        return {
            "period_start": start_day.isoformat(),
            "period_end": end_day.isoformat(),
            "generated_at": _now_iso(),
            "generation_source": "local",
            "summary": {
                "period": f"{start_day.isoformat()} 至 {end_day.isoformat()}",
                "core_progress": core_progress,
                "risks": risk_lines,
                "next_week_focus": next_week_focus,
            },
            "report": {
                "projects": projects,
                "retrospective": {
                    "difficulties": risk_lines,
                    "improvements": [
                        "把跨任务切换频率控制在更低水平，先完成关键闭环再扩展新事项。",
                        "为高优先级事项预留明确的缓冲时间，降低临时调整带来的连锁影响。",
                    ],
                },
                "learning_and_energy": {
                    "learning": learning_lines,
                    "energy": energy,
                },
                "next_week_plan": {
                    "key_tasks": next_week_focus,
                    "routine": routine,
                },
                "mood_and_interest": {
                    "mood": mood,
                    "interest_shift": interest_shift,
                    "tags": interest_tags,
                },
            },
            "push": {},
        }

    def _call_kimi_review(self, start_day: date, end_day: date) -> dict[str, Any] | None:
        cfg = self._config()
        kimi = cfg.get("kimi") if isinstance(cfg.get("kimi"), dict) else {}
        api_key = str(kimi.get("api_key", "") or "").strip()
        if not api_key:
            return None
        base_url = str(kimi.get("base_url", "") or "https://api.moonshot.cn/v1").strip().rstrip("/")
        model = str(kimi.get("model", "") or "kimi-k2-thinking-turbo").strip()

        dialogues = self._user_dialogues_between(start_day, end_day)
        if not dialogues:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 LoosePlan 的每周回顾分析器。"
                    "只能根据提供的用户对话内容生成内容，禁止引用日程、系统操作、待办变更或任何非用户对话信息。"
                    "必须只输出 JSON 对象，不要输出 Markdown 或解释。"
                    "JSON 结构固定为："
                    "{\"summary\":{\"period\":\"\",\"core_progress\":[],\"risks\":[],\"next_week_focus\":[]},"
                    "\"report\":{\"projects\":[{\"title\":\"\",\"content\":\"\"}],"
                    "\"retrospective\":{\"difficulties\":[],\"improvements\":[]},"
                    "\"learning_and_energy\":{\"learning\":[],\"energy\":\"\"},"
                    "\"next_week_plan\":{\"key_tasks\":[],\"routine\":[]},"
                    "\"mood_and_interest\":{\"mood\":\"\",\"interest_shift\":[],\"tags\":[]}}}"
                    "。"
                    "摘要版必须对应：1.时间周期 2.核心进展 3.存在风险 4.下周重点。"
                    "详细报告版必须对应：1.项目与工作回顾 2.问题与复盘 3.学习与状态评估 4.下周行动计划 5.状态与兴趣动态评估。"
                    "如果信息不足，明确写“暂无明确记录”或给出保守判断。"
                    "summary.core_progress 最多 3 条，summary.risks 最多 3 条，summary.next_week_focus 最多 2 条。"
                    "report.projects 输出 1 到 3 条，每条都要有 title 和 content，title 使用“项目/任务 A”这类格式。"
                    "输出语言使用简体中文。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "period_start": start_day.isoformat(),
                        "period_end": end_day.isoformat(),
                        "user_dialogues": dialogues[-120:],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=55.0,
            )
        except Exception:
            return None
        if response.status_code < 200 or response.status_code >= 300:
            return None
        try:
            resp_obj = response.json()
        except Exception:
            return None
        choices = resp_obj.get("choices") if isinstance(resp_obj, dict) else None
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = str((message or {}).get("content", "") or "")
        parsed = _extract_first_json(content)
        return parsed if isinstance(parsed, dict) else None

    def _build_review_object(self, start_day: date, end_day: date) -> dict[str, Any]:
        fallback = self._build_local_review(start_day, end_day)
        kimi = self._call_kimi_review(start_day, end_day)
        review = {
            "period_start": start_day.isoformat(),
            "period_end": end_day.isoformat(),
            "generated_at": _now_iso(),
            "generation_source": "kimi" if isinstance(kimi, dict) else "local",
            "summary": kimi.get("summary", {}) if isinstance(kimi, dict) else fallback["summary"],
            "report": kimi.get("report", {}) if isinstance(kimi, dict) else fallback["report"],
            "push": {},
        }
        return self._normalize_with_fallback(review, fallback)

    def _summary_text(self, review: dict[str, Any]) -> str:
        summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
        core_progress = summary.get("core_progress") if isinstance(summary.get("core_progress"), list) else []
        risks = summary.get("risks") if isinstance(summary.get("risks"), list) else []
        focus = summary.get("next_week_focus") if isinstance(summary.get("next_week_focus"), list) else []
        start_text = str(review.get("period_start", "") or "")
        end_text = str(review.get("period_end", "") or "")
        lines = [
            f"每周回顾摘要（{start_text} - {end_text}）",
            f"1. 时间周期：{start_text} 至 {end_text}",
            "2. 核心进展：" + ("；".join([str(x) for x in core_progress]) if core_progress else "暂无明确记录"),
            "3. 存在风险：" + ("；".join([str(x) for x in risks]) if risks else "暂无明确记录"),
            "4. 下周重点：" + ("；".join([str(x) for x in focus]) if focus else "暂无明确记录"),
        ]
        return "\n".join(lines)

    def _detail_markdown(self, review: dict[str, Any]) -> str:
        summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
        report = review.get("report") if isinstance(review.get("report"), dict) else {}
        projects = report.get("projects") if isinstance(report.get("projects"), list) else []
        retrospective = report.get("retrospective") if isinstance(report.get("retrospective"), dict) else {}
        learning_energy = report.get("learning_and_energy") if isinstance(report.get("learning_and_energy"), dict) else {}
        next_week_plan = report.get("next_week_plan") if isinstance(report.get("next_week_plan"), dict) else {}
        mood_interest = report.get("mood_and_interest") if isinstance(report.get("mood_and_interest"), dict) else {}
        tags = mood_interest.get("tags") if isinstance(mood_interest.get("tags"), list) else []

        lines = [
            f"# 每周回顾（{review.get('period_start', '')} - {review.get('period_end', '')})",
            "",
            "## 摘要版",
            f"1. 时间周期：{summary.get('period', '')}",
            "2. 核心进展：" + ("；".join([str(x) for x in summary.get("core_progress", [])]) or "暂无明确记录"),
            "3. 存在风险：" + ("；".join([str(x) for x in summary.get("risks", [])]) or "暂无明确记录"),
            "4. 下周重点：" + ("；".join([str(x) for x in summary.get("next_week_focus", [])]) or "暂无明确记录"),
            "",
            "## 详细报告版",
            "### 1. 项目与工作回顾",
        ]
        for item in projects:
            if isinstance(item, dict):
                lines.append(f"- {item.get('title', '')}：{item.get('content', '')}")
        lines.extend(
            [
                "",
                "### 2. 问题与复盘",
                "- 遇到的困难：" + ("；".join([str(x) for x in retrospective.get("difficulties", [])]) or "暂无明确记录"),
                "- 改进措施：" + ("；".join([str(x) for x in retrospective.get("improvements", [])]) or "暂无明确记录"),
                "",
                "### 3. 学习与状态评估",
                "- 知识获取：" + ("；".join([str(x) for x in learning_energy.get("learning", [])]) or "暂无明确记录"),
                f"- 精力管理：{learning_energy.get('energy', '') or '暂无明确记录'}",
                "",
                "### 4. 下周行动计划",
                "- 关键任务：" + ("；".join([str(x) for x in next_week_plan.get("key_tasks", [])]) or "暂无明确记录"),
                "- 常规推进：" + ("；".join([str(x) for x in next_week_plan.get("routine", [])]) or "暂无明确记录"),
                "",
                "### 5. 状态与兴趣动态评估",
                f"- 情绪与能量波动：{mood_interest.get('mood', '') or '暂无明确记录'}",
                "- 兴趣与关注点偏移：" + ("；".join([str(x) for x in mood_interest.get('interest_shift', [])]) or "暂无明确记录"),
            ]
        )
        if tags:
            lines.append("- 当前兴趣标签：" + " / ".join([str(x) for x in tags]))
        return "\n".join(lines).strip()

    def _detail_html(self, review: dict[str, Any]) -> str:
        report = review.get("report") if isinstance(review.get("report"), dict) else {}
        projects = report.get("projects") if isinstance(report.get("projects"), list) else []
        retrospective = report.get("retrospective") if isinstance(report.get("retrospective"), dict) else {}
        learning_energy = report.get("learning_and_energy") if isinstance(report.get("learning_and_energy"), dict) else {}
        next_week_plan = report.get("next_week_plan") if isinstance(report.get("next_week_plan"), dict) else {}
        mood_interest = report.get("mood_and_interest") if isinstance(report.get("mood_and_interest"), dict) else {}

        def p(label: str, content: str) -> str:
            return f"<p><b>{html.escape(label)}：</b>{html.escape(content or '暂无明确记录')}</p>"

        parts = ["<div style='font-size:13px; line-height:1.8; color:#111827;'>"]
        parts.append("<h3 style='font-size:14px; margin:0 0 12px 0; padding-bottom:8px; border-bottom:1px solid rgba(0,0,0,0.06);'>1. 项目与工作回顾</h3>")
        for item in projects:
            if not isinstance(item, dict):
                continue
            parts.append(p(str(item.get("title", "") or "项目/任务"), str(item.get("content", "") or "")))

        parts.append("<h3 style='font-size:14px; margin:22px 0 12px 0; padding-bottom:8px; border-bottom:1px solid rgba(0,0,0,0.06);'>2. 问题与复盘</h3>")
        parts.append(p("遇到的困难", "；".join([str(x) for x in retrospective.get("difficulties", [])]) or "暂无明确记录"))
        parts.append(p("改进措施", "；".join([str(x) for x in retrospective.get("improvements", [])]) or "暂无明确记录"))

        parts.append("<h3 style='font-size:14px; margin:22px 0 12px 0; padding-bottom:8px; border-bottom:1px solid rgba(0,0,0,0.06);'>3. 学习与状态评估</h3>")
        parts.append(p("知识获取", "；".join([str(x) for x in learning_energy.get("learning", [])]) or "暂无明确记录"))
        parts.append(p("精力管理", str(learning_energy.get("energy", "") or "暂无明确记录")))

        parts.append("<h3 style='font-size:14px; margin:22px 0 12px 0; padding-bottom:8px; border-bottom:1px solid rgba(0,0,0,0.06);'>4. 下周行动计划</h3>")
        parts.append(p("关键任务", "；".join([str(x) for x in next_week_plan.get("key_tasks", [])]) or "暂无明确记录"))
        parts.append(p("常规推进", "；".join([str(x) for x in next_week_plan.get("routine", [])]) or "暂无明确记录"))

        parts.append("<h3 style='font-size:14px; margin:22px 0 12px 0; padding-bottom:8px; border-bottom:1px solid rgba(0,0,0,0.06);'>5. 状态与兴趣动态评估</h3>")
        parts.append(p("情绪与能量波动", str(mood_interest.get("mood", "") or "暂无明确记录")))
        parts.append(p("兴趣与关注点偏移", "；".join([str(x) for x in mood_interest.get("interest_shift", [])]) or "暂无明确记录"))
        parts.append("</div>")
        return "".join(parts)

    def _display_item(self, review: dict[str, Any], key: str) -> dict[str, Any]:
        push = review.get("push") if isinstance(review.get("push"), dict) else {}
        generated_at = str(review.get("generated_at", "") or "")
        pushed_at = str(push.get("pushed_at", "") or "")
        period_start = str(review.get("period_start", "") or "")
        period_end = str(review.get("period_end", "") or "")
        end_day = _safe_date(period_end) or _today()
        week_no = end_day.isocalendar().week
        mood_interest = review.get("report", {}).get("mood_and_interest", {}) if isinstance(review.get("report"), dict) else {}
        tags = mood_interest.get("tags") if isinstance(mood_interest, dict) else []
        return {
            "key": key,
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": generated_at,
            "generated_at_text": _human_ts(generated_at),
            "range_text": _format_dot_range(period_start, period_end),
            "title": f"第 {week_no} 周回顾",
            "detail_title": f"第 {week_no} 周回顾 ({_format_dot_range(period_start, period_end)})",
            "status_label": "已推送" if pushed_at else "已生成",
            "status_time": _human_ts(pushed_at or generated_at),
            "generation_source": str(review.get("generation_source", "local") or "local"),
            "summary_text": self._summary_text(review),
            "detail_markdown": self._detail_markdown(review),
            "detail_html": self._detail_html(review),
            "interest_tags": list(tags if isinstance(tags, list) else []),
            "summary": review.get("summary", {}),
            "report": review.get("report", {}),
        }

    def _load_all_reports(self) -> list[dict[str, Any]]:
        sequence_map = self._ensure_review_sequence_numbers()
        out: list[dict[str, Any]] = []
        for path in self._weekly_dir().glob("*.json"):
            review = self._read_review_obj(path)
            key = path.stem
            item = self._display_item(review, key)
            sequence_no = sequence_map.get(key, self._review_sequence_no(review) or 1)
            item["sequence_no"] = sequence_no
            item["title"] = f"第 {sequence_no} 周回顾"
            item["detail_title"] = f"第 {sequence_no} 周回顾 ({_format_dot_range(item.get('period_start', ''), item.get('period_end', ''))})"
            out.append(item)
        out.sort(
            key=lambda item: (
                str(item.get("period_end", "") or ""),
                str(item.get("generated_at", "") or ""),
            ),
            reverse=True,
        )
        return out

    def _report_exists(self, key: str) -> bool:
        return self._review_path(key).exists()

    def _persist_review(self, start_day: date, end_day: date, review: dict[str, Any]) -> str:
        key = _review_key(start_day, end_day)
        path = self._review_path(key)
        existing = self._read_review_obj(path) if path.exists() else {}
        sequence_no = self._review_sequence_no(review) or self._review_sequence_no(existing)
        if sequence_no <= 0:
            sequence_no = self._next_sequence_no()
        data = {
            "sequence_no": sequence_no,
            "period_start": start_day.isoformat(),
            "period_end": end_day.isoformat(),
            "generated_at": review.get("generated_at", _now_iso()),
            "generation_source": review.get("generation_source", "local"),
            "summary": review.get("summary", {}),
            "report": review.get("report", {}),
            "push": review.get("push", {}),
        }
        _atomic_write_json(path, data)
        return key

    def _mark_pushed(self, key: str, *, sync_feishu: bool, trigger: str) -> None:
        path = self._review_path(key)
        review = self._read_review_obj(path)
        push = review.get("push") if isinstance(review.get("push"), dict) else {}
        push["pushed_at"] = _now_iso()
        push["desktop"] = True
        push["feishu"] = bool(sync_feishu)
        push["trigger"] = trigger
        review["push"] = push
        _atomic_write_json(path, review)

    def _set_last_weekly_review_key(self, key: str) -> None:
        cfg = self._config()
        meta = cfg.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            cfg["meta"] = meta
        meta["last_weekly_review_key"] = key
        self._save_config(cfg)

    def _last_weekly_review_key(self) -> str:
        cfg = self._config()
        meta = cfg.get("meta") if isinstance(cfg.get("meta"), dict) else {}
        return str(meta.get("last_weekly_review_key", "") or "").strip()

    def _start_generation(
        self,
        *,
        start_day: date,
        end_day: date,
        force: bool,
        notify: bool,
        scheduled: bool,
    ) -> None:
        key = _review_key(start_day, end_day)
        if key in self._active_keys:
            return
        self._active_keys.add(key)
        self._set_loading(True)

        def _worker() -> None:
            payload: dict[str, Any]
            try:
                if (not force) and self._report_exists(key):
                    payload = {
                        "ok": True,
                        "key": key,
                        "review_created": False,
                        "notify": notify,
                        "scheduled": scheduled,
                        "message": "已加载现有周回顾",
                    }
                else:
                    review = self._build_review_object(start_day, end_day)
                    saved_key = self._persist_review(start_day, end_day, review)
                    payload = {
                        "ok": True,
                        "key": saved_key,
                        "review_created": True,
                        "notify": notify,
                        "scheduled": scheduled,
                        "message": "已生成周回顾",
                    }
            except Exception as exc:
                payload = {"ok": False, "key": key, "message": f"生成周回顾失败：{exc}"}
            self._workerFinished.emit(payload)

        threading.Thread(target=_worker, name=f"ReviewGen-{key}", daemon=True).start()

    @Slot(object)
    def _on_worker_finished(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        key = str(data.get("key", "") or "")
        if key:
            self._active_keys.discard(key)
        self._set_loading(bool(self._active_keys))
        if not data.get("ok", False):
            self.toastRequested.emit(str(data.get("message", "生成周回顾失败") or "生成周回顾失败"))
            return
        self.reloadReports(select_key=key)
        if data.get("notify", False):
            report = self._selected_report if self._selected_report.get("key") == key else {}
            if report:
                sync_feishu = self.weeklySyncFeishu()
                message = str(report.get("summary_text", "") or "")
                self.desktopNotify.emit(message)
                if sync_feishu:
                    self.feishuNotify.emit(message)
                self._mark_pushed(key, sync_feishu=sync_feishu, trigger="scheduler" if data.get("scheduled", False) else "share")
                if data.get("scheduled", False):
                    self._set_last_weekly_review_key(key)
                self.reloadReports(select_key=key)
        self.toastRequested.emit(str(data.get("message", "已更新周回顾") or "已更新周回顾"))

    @Property("QVariantList", notify=reportListChanged)
    def reportList(self) -> list:
        return list(self._report_list)

    @Property("QVariantMap", notify=selectedReportChanged)
    def selectedReport(self) -> dict:
        return dict(self._selected_report)

    @Property(bool, notify=loadingChanged)
    def loading(self) -> bool:
        return bool(self._loading)

    def weeklySyncFeishu(self) -> bool:
        cfg = self._config()
        push = cfg.get("push") if isinstance(cfg.get("push"), dict) else {}
        weekly = push.get("weekly_review") if isinstance(push.get("weekly_review"), dict) else {}
        return bool(weekly.get("sync_feishu", True))

    def weeklyEnabled(self) -> bool:
        cfg = self._config()
        push = cfg.get("push") if isinstance(cfg.get("push"), dict) else {}
        weekly = push.get("weekly_review") if isinstance(push.get("weekly_review"), dict) else {}
        return bool(weekly.get("enabled", True))

    def weeklyWeekday(self) -> int:
        cfg = self._config()
        push = cfg.get("push") if isinstance(cfg.get("push"), dict) else {}
        weekly = push.get("weekly_review") if isinstance(push.get("weekly_review"), dict) else {}
        try:
            return max(0, min(int(weekly.get("weekday", 0) or 0), 6))
        except Exception:
            return 0

    @Slot()
    def reloadReports(self, select_key: str = "") -> None:
        current_key = str(select_key or self._selected_report.get("key", "") or "")
        self._report_list = self._load_all_reports()
        self.reportListChanged.emit()
        if not self._report_list:
            self._selected_report = {}
            self.selectedReportChanged.emit()
            return
        if current_key:
            for item in self._report_list:
                if str(item.get("key", "") or "") == current_key:
                    self._selected_report = dict(item)
                    self.selectedReportChanged.emit()
                    return
        self._selected_report = dict(self._report_list[0])
        self.selectedReportChanged.emit()

    @Slot(str)
    def selectReport(self, key: str) -> None:
        wanted = (key or "").strip()
        if not wanted:
            return
        for item in self._report_list:
            if str(item.get("key", "") or "") == wanted:
                self._selected_report = dict(item)
                self.selectedReportChanged.emit()
                break

    @Slot()
    def ensureCurrentWeekReview(self) -> None:
        start_day, end_day = self._current_week_period()
        key = _review_key(start_day, end_day)
        if self._report_exists(key):
            self.reloadReports(select_key=key)
            return
        self._start_generation(start_day=start_day, end_day=end_day, force=False, notify=False, scheduled=False)

    @Slot()
    def refreshSelectedReview(self) -> None:
        start_day = _safe_date(str(self._selected_report.get("period_start", "") or ""))
        end_day = _safe_date(str(self._selected_report.get("period_end", "") or ""))
        if not start_day or not end_day:
            start_day, end_day = self._current_week_period()
        self._start_generation(start_day=start_day, end_day=end_day, force=True, notify=False, scheduled=False)

    @Slot(str, str, bool)
    def generatePeriod(self, start_text: str, end_text: str, force: bool = False) -> None:
        start_day = _safe_date(start_text)
        end_day = _safe_date(end_text)
        if not start_day or not end_day:
            self.toastRequested.emit("请选择有效的起止日期")
            return
        if start_day > end_day:
            self.toastRequested.emit("起始日期不能晚于结束日期")
            return
        if (end_day - start_day).days > 30:
            self.toastRequested.emit("自定义周期最长支持 31 天")
            return
        key = _review_key(start_day, end_day)
        if (not force) and self._report_exists(key):
            self.reloadReports(select_key=key)
            return
        self._start_generation(start_day=start_day, end_day=end_day, force=bool(force), notify=False, scheduled=False)

    @Slot()
    def exportSelectedReport(self) -> None:
        if not self._selected_report:
            self.toastRequested.emit("当前没有可导出的周回顾")
            return
        key = str(self._selected_report.get("key", "") or "")
        if not key:
            self.toastRequested.emit("当前没有可导出的周回顾")
            return
        export_path = self._exports_dir() / f"{key}.md"
        export_path.write_text(str(self._selected_report.get("detail_markdown", "") or ""), encoding="utf-8")
        self.toastRequested.emit(f"已导出到 {export_path}")

    @Slot()
    def shareSelectedReport(self) -> None:
        if not self._selected_report:
            self.toastRequested.emit("当前没有可分享的周回顾")
            return
        key = str(self._selected_report.get("key", "") or "")
        message = str(self._selected_report.get("summary_text", "") or "")
        if not key or not message:
            self.toastRequested.emit("当前没有可分享的周回顾")
            return
        try:
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(message)
        except Exception:
            pass
        sync_feishu = self.weeklySyncFeishu()
        self.desktopNotify.emit(message)
        if sync_feishu:
            self.feishuNotify.emit(message)
        self._mark_pushed(key, sync_feishu=sync_feishu, trigger="share")
        self.reloadReports(select_key=key)
        self.toastRequested.emit("已分享摘要并复制到剪贴板")

    def maybePushScheduledReview(self) -> None:
        if not self.weeklyEnabled():
            return
        today = _today()
        current_weekday = (today.weekday() + 1) % 7
        if current_weekday != self.weeklyWeekday():
            return
        start_day = _week_start(today)
        key = _review_key(start_day, today)
        if self._last_weekly_review_key() == key:
            return
        self._start_generation(start_day=start_day, end_day=today, force=True, notify=True, scheduled=True)
