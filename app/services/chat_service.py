from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any, Callable, Optional

import requests
from PySide6.QtCore import QObject, Property, Signal, Slot

from .schedule_service import ScheduleService


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _today() -> str:
    return _now().date().isoformat()


def _atomic_write_append_jsonl(path: Path, obj: dict[str, Any], lock: threading.Lock) -> None:
    line = json.dumps(obj, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _normalize_base_url(u: str) -> str:
    s = (u or "").strip()
    while s.endswith("/"):
        s = s[:-1]
    return s


def _extract_first_json(text: str) -> Optional[dict[str, Any]]:
    s = (text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


class ChatService(QObject):
    messagesChanged = Signal(str)
    pendingChanged = Signal()
    dateAutoSwitched = Signal(str)
    toastRequested = Signal(str)
    scheduleChanged = Signal(str, str)
    kimiConnectedChanged = Signal()
    feishuConnectedChanged = Signal()
    namesChanged = Signal()

    def __init__(
        self,
        *,
        get_data_dir: Callable[[], Path],
        schedule_service: ScheduleService,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._get_data_dir = get_data_dir
        self._schedule = schedule_service
        self._http = requests.Session()
        self._http.trust_env = False
        self._io_lock = threading.Lock()
        self._http_lock = threading.Lock()
        self._recent_input_lock = threading.Lock()
        self._recent_inputs: dict[str, dict[str, Any]] = {}
        self._proposal_lock = threading.Lock()
        self._recent_proposals: dict[str, dict[str, Any]] = {}

        self._messages: list[dict[str, Any]] = []
        self._selected_date = _today()
        self._kimi_connected = False
        self._feishu_connected = False
        self._user_display_name = "我"
        self._assistant_name = "助手"

        try:
            self._schedule.pendingChanged.connect(self.pendingChanged.emit)
            self._schedule.monthDataChanged.connect(self._on_month_changed)
            self._schedule.toastRequested.connect(self.toastRequested.emit)
        except Exception:
            pass

        self._refresh_names()
        if self._is_configured():
            self.loadMessages(self._selected_date)

    def _on_month_changed(self, month: str) -> None:
        self.scheduleChanged.emit(str(month or ""), self._selected_date)

    def _data_dir(self) -> Path:
        return self._get_data_dir().resolve()

    def _is_configured(self) -> bool:
        return (self._data_dir() / "config.json").exists()

    def _chat_dir(self) -> Path:
        d = self._data_dir() / "chat"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _chat_file(self, date_str: str) -> Path:
        return self._chat_dir() / f"{date_str}.jsonl"

    def _schedule_file(self, month: str) -> Path:
        return self._data_dir() / "schedule" / f"{month}.json"

    def _read_config(self) -> dict[str, Any]:
        p = self._data_dir() / "config.json"
        try:
            if p.exists():
                obj = json.loads(p.read_text(encoding="utf-8"))
                return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
        return {}

    def _refresh_names(self) -> None:
        cfg = self._read_config()
        user_name = str(cfg.get("user_display_name", "") or "我").strip() or "我"
        assistant_name = str(cfg.get("assistant_name", "") or "助手").strip() or "助手"
        if self._user_display_name != user_name or self._assistant_name != assistant_name:
            self._user_display_name = user_name
            self._assistant_name = assistant_name
            self.namesChanged.emit()

    def _append_message(
        self,
        *,
        role: str,
        text: str,
        channel: str,
        intent: str = "",
        chat_id: str = "",
        sender_open_id: str = "",
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        obj = {
            "id": str(uuid.uuid4()),
            "ts": _now_iso(),
            "role": role,
            "channel": channel,
            "text": text,
        }
        if intent:
            obj["intent"] = intent
        if chat_id:
            obj["chat_id"] = chat_id
        if sender_open_id:
            obj["sender_open_id"] = sender_open_id
        if isinstance(extra, dict):
            for k, v in extra.items():
                if isinstance(k, str) and k and v is not None:
                    obj[k] = v
        _atomic_write_append_jsonl(self._chat_file(_today()), obj, self._io_lock)
        return obj

    def _proposal_scope(self, *, channel: str, chat_id: str = "", open_id: str = "") -> str:
        return f"{channel}:{(chat_id or '').strip()}:{(open_id or '').strip()}"

    def _remember_proposal(
        self,
        *,
        channel: str,
        confirm_text: str,
        ops: list[dict[str, Any]],
        chat_id: str = "",
        open_id: str = "",
    ) -> None:
        scope = self._proposal_scope(channel=channel, chat_id=chat_id, open_id=open_id)
        item = {
            "at": monotonic(),
            "channel": channel,
            "chat_id": (chat_id or "").strip(),
            "open_id": (open_id or "").strip(),
            "confirm_text": str(confirm_text or "").strip(),
            "ops": list(ops or []),
        }
        with self._proposal_lock:
            self._recent_proposals[scope] = item

    def _get_recent_proposal(
        self,
        *,
        channel: str,
        chat_id: str = "",
        open_id: str = "",
        max_age_seconds: float = 600.0,
    ) -> dict[str, Any]:
        scope = self._proposal_scope(channel=channel, chat_id=chat_id, open_id=open_id)
        now = monotonic()
        with self._proposal_lock:
            item = self._recent_proposals.get(scope)
            if not item:
                return {}
            if (now - float(item.get("at", 0.0) or 0.0)) > max_age_seconds:
                self._recent_proposals.pop(scope, None)
                return {}
            return dict(item)

    def _clear_recent_proposal(self, *, channel: str, chat_id: str = "", open_id: str = "") -> None:
        scope = self._proposal_scope(channel=channel, chat_id=chat_id, open_id=open_id)
        with self._proposal_lock:
            self._recent_proposals.pop(scope, None)

    def _message_matches_scope(self, msg: dict[str, Any], *, channel: str, chat_id: str = "", open_id: str = "") -> bool:
        if not isinstance(msg, dict):
            return False
        if str(msg.get("channel", "") or "").strip() != channel:
            return False
        if channel == "feishu":
            if (chat_id or "").strip() and str(msg.get("chat_id", "") or "").strip() != (chat_id or "").strip():
                return False
            if (open_id or "").strip() and str(msg.get("sender_open_id", "") or "").strip() != (open_id or "").strip():
                return False
        return True

    def _proposal_from_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(msg, dict):
            return {}
        ops = msg.get("proposal_ops") if isinstance(msg.get("proposal_ops"), list) else []
        confirm_text = str(msg.get("proposal_confirm_text", "") or msg.get("text", "") or "").strip()
        if ops:
            return {"ops": ops, "confirm_text": confirm_text}
        inferred = self._infer_ops_from_confirm_text(confirm_text)
        if inferred:
            return {"ops": inferred, "confirm_text": confirm_text}
        return {}

    def _recover_recent_proposal_from_history(
        self,
        *,
        channel: str,
        chat_id: str = "",
        open_id: str = "",
        max_age_seconds: float = 1800.0,
    ) -> dict[str, Any]:
        messages = self._read_messages_for_date(_today())
        now = _now()
        for msg in reversed(messages):
            if not self._message_matches_scope(msg, channel=channel, chat_id=chat_id, open_id=open_id):
                continue
            ts = str(msg.get("ts", "") or "").strip()
            try:
                msg_dt = datetime.fromisoformat(ts)
            except Exception:
                msg_dt = None
            if msg_dt is not None and (now - msg_dt).total_seconds() > max_age_seconds:
                break
            if str(msg.get("role", "") or "") != "assistant":
                continue
            intent = str(msg.get("intent", "") or "").strip()
            if intent not in {"schedule_propose", "schedule_waiting"}:
                continue
            proposal = self._proposal_from_message(msg)
            if proposal:
                return proposal
        return {}

    def _is_duplicate_input(
        self,
        *,
        channel: str,
        text: str,
        chat_id: str = "",
        open_id: str = "",
        within_seconds: float = 1.2,
    ) -> bool:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if not normalized:
            return False
        scope = f"{channel}:{(chat_id or '').strip()}:{(open_id or '').strip()}"
        now = monotonic()
        with self._recent_input_lock:
            recent = self._recent_inputs.get(scope)
            self._recent_inputs[scope] = {"text": normalized, "at": now}
        return bool(recent) and recent.get("text") == normalized and (now - float(recent.get("at", 0.0) or 0.0)) <= within_seconds

    def _read_messages_for_date(self, date_str: str) -> list[dict[str, Any]]:
        p = self._chat_file(date_str)
        out: list[dict[str, Any]] = []
        try:
            if not p.exists():
                return []
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
        except Exception:
            return []
        out.sort(key=lambda x: str(x.get("ts", "")))
        return out

    def _load_recent_context(self, limit: int = 200) -> list[dict[str, Any]]:
        files = sorted(self._chat_dir().glob("*.jsonl"), key=lambda x: x.name, reverse=True)
        out: list[dict[str, Any]] = []
        for fp in files:
            try:
                lines = fp.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
                    if len(out) >= limit:
                        break
            if len(out) >= limit:
                break
        out.reverse()
        return out

    def _list_chat_dates(self) -> list[str]:
        try:
            files = sorted(self._chat_dir().glob("*.jsonl"), key=lambda x: x.name)
        except Exception:
            return []
        return [fp.stem for fp in files if fp.stem]

    def _schedule_snapshot(self) -> dict[str, Any]:
        month_data = self._schedule.monthData if isinstance(self._schedule.monthData, dict) else {}
        pending = self._schedule.pendingAction if isinstance(self._schedule.pendingAction, dict) else {}
        return {
            "selected_date": str(month_data.get("selected_date", "") or self._selected_date),
            "todos": list(month_data.get("todos", []) if isinstance(month_data.get("todos"), list) else []),
            "events": list(month_data.get("events", []) if isinstance(month_data.get("events"), list) else []),
            "pending_confirm_text": str(pending.get("confirm_text", "") or ""),
        }

    def _resolve_names(self) -> tuple[str, str]:
        self._refresh_names()
        return self._user_display_name, self._assistant_name

    def _build_kimi_messages(self, user_text: str, context: list[dict[str, Any]]) -> list[dict[str, Any]]:
        user_name, assistant_name = self._resolve_names()
        msgs: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    f"你是 {assistant_name}，服务对象是 {user_name}。"
                    "必须只输出 JSON 对象，不允许输出 Markdown 或解释。"
                    "JSON 字段固定：reply,intent,needs_confirmation,confirm_text,followups,ops。"
                    "intent 只能是 chat|schedule_propose|schedule_followup|none。"
                    "涉及待办/日程新增、删除、修改时必须给出 ops。"
                    "如果用户是在查询、查看、列出、总结已有日程或待办，不是要新增或修改，则 intent 必须是 chat 且 ops 必须为空。"
                    "如果用户是在讨论较大的目标、想请你帮助规划、拆解任务、制定执行方案或安排一周节奏，这属于建议和规划，不是立刻写入单条日程；此时 intent 必须是 chat，ops 必须为空。"
                    "如果用户明显想新增或修改日程，但时间、日期或事项有歧义、缺失或疑似错字，请优先结合上下文理解并纠正常见错字；如果仍不够确定，就把 intent 设为 schedule_followup，并在 followups 中给出一句简短追问。"
                    "不要在信息不完整时只回复“收到”。如果 intent 是 schedule_propose，就必须提供可执行 ops；否则请改成 schedule_followup。"
                    "确认文案里要明确提示用户回复“确定”或“取消”。"
                    "delete_todo/update_todo/toggle_todo payload 优先给 id，没有 id 时给 text。"
                    "delete_event/update_event payload 优先给 id，没有 id 时给 title，并尽量补 date/time。"
                    "add_todo payload 使用 text。"
                    "add_event payload 使用 date,time,title,duration,tags,location,remind_before_min。"
                ),
            },
            {
                "role": "system",
                "content": json.dumps(
                    {
                        "today": _today(),
                        "current_schedule_snapshot": self._schedule_snapshot(),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        for it in context[-80:]:
            role = str(it.get("role", "user"))
            txt = str(it.get("text", "") or "")
            if txt:
                msgs.append({"role": "assistant" if role == "assistant" else "user", "content": txt})
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def _call_kimi_json(self, user_text: str, context: list[dict[str, Any]]) -> dict[str, Any]:
        cfg = self._read_config()
        kimi = cfg.get("kimi") if isinstance(cfg.get("kimi"), dict) else {}
        api_key = str(kimi.get("api_key", "") or "").strip()
        base_url = _normalize_base_url(str(kimi.get("base_url", "") or "https://api.moonshot.cn/v1"))
        model = str(kimi.get("model", "") or "kimi-k2-thinking-turbo").strip()
        if not api_key:
            self._set_kimi_connected(False)
            return {
                "reply": "Kimi 未配置或 API Key 为空。",
                "intent": "none",
                "needs_confirmation": False,
                "confirm_text": "",
                "followups": [],
                "ops": [],
            }

        payload = {
            "model": model,
            "messages": self._build_kimi_messages(user_text, context),
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/chat/completions"
        try:
            with self._http_lock:
                resp = self._http.post(url, headers=headers, json=payload, timeout=35.0)
            raw = resp.text or ""
            if resp.status_code < 200 or resp.status_code >= 300:
                self._set_kimi_connected(False)
                return {
                    "reply": f"Kimi 请求失败（HTTP {resp.status_code}）。",
                    "intent": "none",
                    "needs_confirmation": False,
                    "confirm_text": "",
                    "followups": [],
                    "ops": [],
                }
            obj = json.loads(raw) if raw.strip() else {}
            choices = obj.get("choices") if isinstance(obj, dict) else None
            content = ""
            if isinstance(choices, list) and choices:
                message = choices[0].get("message") if isinstance(choices[0], dict) else {}
                content = str((message or {}).get("content", "") or "")
            parsed = _extract_first_json(content)
            if parsed is None:
                parsed = {
                    "reply": content.strip() or "收到。",
                    "intent": "chat",
                    "needs_confirmation": False,
                    "confirm_text": "",
                    "followups": [],
                    "ops": [],
                }
            parsed.setdefault("reply", "")
            parsed.setdefault("intent", "chat")
            parsed.setdefault("needs_confirmation", False)
            parsed.setdefault("confirm_text", "")
            parsed.setdefault("followups", [])
            parsed.setdefault("ops", [])
            self._set_kimi_connected(True)
            return parsed
        except Exception:
            self._set_kimi_connected(False)
            return {
                "reply": "网络异常，稍后再试。",
                "intent": "none",
                "needs_confirmation": False,
                "confirm_text": "",
                "followups": [],
                "ops": [],
            }

    def _call_kimi_chat_only(self, user_text: str, context: list[dict[str, Any]]) -> str:
        cfg = self._read_config()
        kimi = cfg.get("kimi") if isinstance(cfg.get("kimi"), dict) else {}
        api_key = str(kimi.get("api_key", "") or "").strip()
        base_url = _normalize_base_url(str(kimi.get("base_url", "") or "https://api.moonshot.cn/v1"))
        model = str(kimi.get("model", "") or "kimi-k2-thinking-turbo").strip()
        if not api_key:
            self._set_kimi_connected(False)
            return ""

        user_name, assistant_name = self._resolve_names()
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    f"You are {assistant_name}, talking to {user_name}. "
                    "The current user message is normal conversation, not a schedule or todo command. "
                    "Reply naturally in Simplified Chinese. "
                    "Do not suggest adding, updating, confirming, or cancelling schedule or todo items. "
                    "Return a JSON object with keys reply and intent only. "
                    "intent must be 'chat'."
                ),
            }
        ]
        for it in context[-40:]:
            role = str(it.get("role", "user"))
            txt = str(it.get("text", "") or "")
            if txt:
                messages.append({"role": "assistant" if role == "assistant" else "user", "content": txt})
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.5,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url}/chat/completions"
        try:
            with self._http_lock:
                resp = self._http.post(url, headers=headers, json=payload, timeout=35.0)
            if resp.status_code < 200 or resp.status_code >= 300:
                self._set_kimi_connected(False)
                return ""
            obj = json.loads(resp.text or "{}")
            choices = obj.get("choices") if isinstance(obj, dict) else None
            content = ""
            if isinstance(choices, list) and choices:
                message = choices[0].get("message") if isinstance(choices[0], dict) else {}
                content = str((message or {}).get("content", "") or "")
            parsed = _extract_first_json(content)
            reply = str((parsed or {}).get("reply", "") or content or "").strip()
            self._set_kimi_connected(True)
            return reply
        except Exception:
            self._set_kimi_connected(False)
            return ""

    def _set_kimi_connected(self, value: bool) -> None:
        v = bool(value)
        if self._kimi_connected != v:
            self._kimi_connected = v
            self.kimiConnectedChanged.emit()

    def _normalize_user_text(self, text: str) -> str:
        s = (text or "").strip()
        if not s:
            return ""
        replacements = {
            "中文": "中午",
            "种午": "中午",
            "下无": "下午",
            "高鉄": "高铁",
            "髙铁": "高铁",
        }
        for src, dst in replacements.items():
            s = s.replace(src, dst)
        return s

    def _parse_cn_number(self, token: str) -> int:
        t = str(token or "").strip()
        if not t:
            return -1
        digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if t == "十":
            return 10
        if t.startswith("十"):
            return 10 + digits.get(t[1:], -100)
        if t.endswith("十"):
            return digits.get(t[:-1], -100) * 10
        if "十" in t:
            left, right = t.split("十", 1)
            return digits.get(left, -100) * 10 + digits.get(right, -100)
        return digits.get(t, -1)

    def _parse_date_hint(self, text: str) -> str:
        t = self._normalize_user_text(text)
        today = _now().date()
        if "后天" in t:
            return (today + timedelta(days=2)).isoformat()
        if "明天" in t:
            return (today + timedelta(days=1)).isoformat()
        if "今天" in t:
            return today.isoformat()

        m = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})", t)
        if m:
            return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        m = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", t)
        if m:
            return f"{today.year:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

        return today.isoformat()

    def _parse_time_hint(self, text: str) -> str:
        t = self._normalize_user_text(text)
        if not t:
            return ""

        def _apply_period(hour: int, period: str) -> int:
            p = str(period or "")
            if p in {"凌晨"}:
                return 0 if hour == 24 else hour % 24
            if p in {"早上", "上午", "清晨"}:
                return hour if hour <= 11 else hour % 12
            if p == "中午":
                if hour == 12:
                    return 12
                return hour + 12 if 1 <= hour <= 6 else hour
            if p in {"下午", "傍晚", "晚上", "今晚"}:
                if hour == 12:
                    return 12
                return hour + 12 if 1 <= hour <= 11 else hour
            return hour % 24

        m = re.search(r"(凌晨|早上|上午|中午|下午|傍晚|晚上|今晚)?\s*(\d{1,2})\s*[:：]\s*(\d{1,2})", t)
        if m:
            hour = _apply_period(int(m.group(2)), str(m.group(1) or ""))
            return f"{hour:02d}:{int(m.group(3)):02d}"
        m = re.search(r"(凌晨|早上|上午|中午|下午|傍晚|晚上|今晚)?\s*(\d{1,2})点(?:(\d{1,2})分?)?", t)
        if m:
            hour = _apply_period(int(m.group(2)), str(m.group(1) or ""))
            return f"{hour:02d}:{int(m.group(3) or 0):02d}"
        m = re.search(r"(凌晨|早上|上午|中午|下午|傍晚|晚上|今晚)?\s*([零一二两三四五六七八九十]{1,3})点(?:(?:([零一二三四五六七八九十]{1,3})分?))?", t)
        if m:
            hour_raw = self._parse_cn_number(m.group(2))
            minute_raw = self._parse_cn_number(m.group(3) or "")
            if 0 <= hour_raw <= 24:
                hour = _apply_period(hour_raw, str(m.group(1) or ""))
                minute = minute_raw if 0 <= minute_raw <= 59 else 0
                return f"{hour:02d}:{minute:02d}"
        return ""

    def _has_explicit_date_or_time_hint(self, text: str) -> bool:
        t = self._normalize_user_text(text)
        if not t:
            return False
        if self._parse_time_hint(t):
            return True
        return bool(
            re.search(
                r"(\u4eca\u5929|\u660e\u5929|\u540e\u5929|\u5468[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u65e5\u5929]|"
                r"\u661f\u671f[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u65e5\u5929]|\d{4}[-/\u5e74]\d{1,2}[-/\u6708]\d{1,2}|"
                r"\d{1,2}\u6708\d{1,2}[\u65e5\u53f7]?)",
                t,
            )
        )

    def _looks_like_schedule_request(
        self,
        text: str,
        *,
        intent: str = "",
        ops: Optional[list[dict[str, Any]]] = None,
    ) -> bool:
        t = self._normalize_user_text(text)
        if not t:
            return False
        if self._looks_like_schedule_lookup(t) or self._looks_like_planning_request(t):
            return False

        has_datetime = self._has_explicit_date_or_time_hint(t)
        has_todo_keyword = bool(re.search(r"(\u5f85\u529e|todo|to do|\u4efb\u52a1)", t, flags=re.I))
        has_schedule_keyword = bool(re.search(r"(\u65e5\u7a0b|\u884c\u7a0b|\u63d0\u9192)", t))
        has_event_keyword = bool(
            re.search(
                r"(\u4f1a\u8bae|\u5f00\u4f1a|\u6d3b\u52a8|\u9762\u8bd5|\u8003\u8bd5|\u4e0a\u8bfe|"
                r"\u8bfe\u7a0b|\u51fa\u5dee|\u9ad8\u94c1|\u822a\u73ed|\u706b\u8f66|\u76f4\u64ad|"
                r"\u62dc\u8bbf|\u6c47\u62a5|\u805a\u9910)",
                t,
            )
        )
        has_mutation = bool(
            re.search(
                r"(\u6dfb\u52a0|\u65b0\u589e|\u52a0\u5165|\u521b\u5efa|\u65b0\u5efa|"
                r"\u5220\u9664|\u53d6\u6d88|\u5220\u6389|\u79fb\u9664|"
                r"\u6539\u6210|\u6539\u5230|\u6539\u4e3a|\u8c03\u6574|\u4fee\u6539|\u66f4\u65b0|"
                r"\u8bbe\u4e3a|\u6807\u8bb0|\u5b8c\u6210|\u5b89\u6392|"
                r"\u8bb0\u4e00\u4e0b|\u5e2e\u6211\u8bb0|\u8bbe\u4e2a\u63d0\u9192|\u63d0\u9192\u6211)",
                t,
            )
        )
        has_chatty_marker = bool(
            re.search(
                r"(\u8bed\u6c14|\u6e29\u67d4|\u54c4|\u804a\u5929|\u8c22\u8c22|\u54c8\u54c8|\u4f60\u662f\u8c01|"
                r"\u4ec0\u4e48\u610f\u601d|\u4e3a\u4ec0\u4e48|\u611f\u89c9|\u89c9\u5f97|\u60f3\u804a)",
                t,
            )
        )
        op_names = {
            str(item.get("op", "") or "").strip()
            for item in (ops or [])
            if isinstance(item, dict)
        }

        if has_chatty_marker and not (has_mutation or has_todo_keyword or has_schedule_keyword):
            return False
        if has_todo_keyword and (has_mutation or op_names & {"add_todo", "delete_todo", "update_todo", "toggle_todo"}):
            return True
        if has_schedule_keyword and (has_mutation or has_datetime or has_event_keyword):
            return True
        if has_datetime and (has_event_keyword or has_mutation):
            return True
        if op_names & {"add_event", "delete_event", "update_event"} and (
            has_datetime or has_schedule_keyword or has_event_keyword or has_mutation
        ):
            return True
        if intent in {"schedule_propose", "schedule_followup", "schedule_waiting"} and (
            has_mutation or (has_datetime and (has_schedule_keyword or has_event_keyword or has_todo_keyword))
        ):
            return True
        return False

    def _cleanup_subject(self, text: str) -> str:
        s = self._normalize_user_text(text)
        s = re.sub(r"(今天|明天|后天)", "", s)
        s = re.sub(r"\d{4}[年/-]\d{1,2}[月/-]\d{1,2}[日号]?", "", s)
        s = re.sub(r"\d{1,2}月\d{1,2}[日号]?", "", s)
        s = re.sub(r"(凌晨|早上|上午|中午|下午|傍晚|晚上|今晚)?\s*\d{1,2}\s*[:：]\s*\d{2}", "", s)
        s = re.sub(r"(凌晨|早上|上午|中午|下午|傍晚|晚上|今晚)?\s*\d{1,2}点(\d{1,2}分?)?", "", s)
        s = re.sub(r"(凌晨|早上|上午|中午|下午|傍晚|晚上|今晚)?\s*[零一二两三四五六七八九十]{1,3}点([零一二三四五六七八九十]{1,3}分?)?", "", s)
        s = re.sub(r"(添加|新增|加入|安排|创建|删除|取消|删掉|改成|改到|改为|调整到|把|有一个|有个|一个|日程|待办|事项|任务)", " ", s)
        s = re.sub(r"[，。,.：:？?！!、\s]+", " ", s)
        return s.strip()

    def _infer_ops_from_confirm_text(self, text: str) -> list[dict[str, Any]]:
        t = self._normalize_user_text(text)
        if not t:
            return []

        m = re.search(r"确认新增日程[:：]\s*(\d{4}-\d{2}-\d{2})\s+(待定|\d{2}:\d{2})\s+(.+?)(?:[？?]\s*)?(?:请回复|$)", t, flags=re.S)
        if m:
            title = re.sub(r"\s+", " ", m.group(3)).strip()
            return [{
                "op": "add_event",
                "payload": {
                    "date": m.group(1),
                    "time": m.group(2),
                    "title": title,
                    "duration": "01:00",
                    "tags": [],
                    "location": "",
                    "remind_before_min": 0,
                },
            }]

        m = re.search(r"确认新增待办[:：]\s*(.+?)(?:[？?]\s*)?(?:请回复|$)", t, flags=re.S)
        if m:
            todo_text = re.sub(r"\s+", " ", m.group(1)).strip()
            if todo_text:
                return [{"op": "add_todo", "payload": {"text": todo_text, "done": False}}]
        batch = self._infer_plan_ops_from_text(t)
        if batch:
            return batch
        return []

    def _year_for_month_day(self, month: int, day: int) -> int:
        today = _now().date()
        year = today.year
        try:
            picked = datetime(year, month, day).date()
        except Exception:
            return year
        if picked < today - timedelta(days=45):
            return year + 1
        return year

    def _duration_to_hhmm(self, minutes: int) -> str:
        mins = max(30, int(minutes))
        hours = mins // 60
        remain = mins % 60
        return f"{hours:02d}:{remain:02d}"

    def _ops_confirm_text(self, ops: list[dict[str, Any]]) -> str:
        if not ops:
            return self._ensure_confirm_prompt("")
        if len(ops) == 1:
            return self._ensure_confirm_prompt(self._default_confirm_text_from_ops(ops))

        lines = []
        for idx, op_obj in enumerate(ops[:8], start=1):
            payload = op_obj.get("payload") if isinstance(op_obj.get("payload"), dict) else {}
            date = str(payload.get("date", "") or "").strip()
            time = str(payload.get("time", "") or "待定").strip() or "待定"
            title = str(payload.get("title", "") or "").strip()
            lines.append(f"{idx}. {date} {time} {title}".strip())
        if len(ops) > 8:
            lines.append(f"……共 {len(ops)} 项")
        body = "确认将以下任务写入日程：\n" + "\n".join(lines)
        return self._ensure_confirm_prompt(body)

    def _recent_plan_offer_reply(self, text: str) -> str:
        normalized = re.sub(r"[\W_]+", "", str(text or "").strip(), flags=re.UNICODE)
        if not normalized:
            return ""

        reject_prefixes = (
            "\u4e0d\u7528",
            "\u4e0d\u8981",
            "\u4e0d\u9700\u8981",
            "\u5148\u4e0d\u7528",
            "\u5148\u4e0d\u8981",
            "\u7b97\u4e86",
        )
        accept_prefixes = (
            "\u9700\u8981",
            "\u8981",
            "\u597d",
            "\u597d\u7684",
            "\u884c",
            "\u53ef\u4ee5",
            "\u662f",
            "\u662f\u7684",
            "\u55ef",
            "\u55ef\u55ef",
        )
        if any(normalized.startswith(prefix) for prefix in reject_prefixes):
            return "reject"
        if any(normalized.startswith(prefix) for prefix in accept_prefixes):
            return "accept"
        return ""

    def _is_recent_plan_offer_text(self, text: str) -> bool:
        t = self._normalize_user_text(text)
        if not t:
            return False
        return bool(
            re.search(
                r"(添加到.*日程|加入.*日程|写入.*日程|写进.*日程|同步到.*日程|加到.*日程|"
                r"需要我帮.*(这些|这份|上述)?.*(任务|步骤|安排).*(日程|日程里))",
                t,
            )
        )

    def _propose_plan_ops(
        self,
        *,
        ops: list[dict[str, Any]],
        channel: str,
        chat_id: str = "",
        open_id: str = "",
    ) -> tuple[str, str, Optional[dict[str, Any]]]:
        confirm_text = self._ops_confirm_text(ops)
        proposal = self._schedule.proposeFromChat(channel=channel, confirm_text=confirm_text, ops=ops)
        status = str(proposal.get("status", "") or "")
        if status == "already_applied":
            return "这些任务对应的日程已经存在，无需重复添加。", "none", None

        reply = str(proposal.get("confirm_text", "") or confirm_text)
        intent = "schedule_propose" if status == "proposed" else "schedule_waiting"
        proposal_ops = list(proposal.get("ops", []) if isinstance(proposal.get("ops"), list) else ops)
        self._remember_proposal(
            channel=channel,
            confirm_text=reply,
            ops=proposal_ops,
            chat_id=chat_id,
            open_id=open_id,
        )
        self.pendingChanged.emit()
        return reply, intent, {
            "proposal_confirm_text": reply,
            "proposal_ops": proposal_ops,
        }

    def _infer_plan_ops_from_text(self, text: str) -> list[dict[str, Any]]:
        t = self._normalize_user_text(text)
        if not t:
            return []

        ops: list[dict[str, Any]] = []
        numbered_pattern = re.compile(
            r"(?:^|\n)\s*\d+[.、]\s*(\d{1,2})月(\d{1,2})日(?:\([^)]*\)|（[^）]*）)?\s*(\d{1,2}:\d{2})\s*[-—~～]\s*(\d{1,2}:\d{2})\s+([^\n]+)"
        )
        weekday_pattern = re.compile(
            r"(?:^|\n)\s*(?:周[一二三四五六日天]|星期[一二三四五六日天])(?:\s*[（(](\d{1,2})月(\d{1,2})日[)）])?[:：]\s*([^\n]+)"
        )

        for m in numbered_pattern.finditer(t):
            month = int(m.group(1))
            day = int(m.group(2))
            start = str(m.group(3) or "").strip()
            end = str(m.group(4) or "").strip()
            title = re.sub(r"\s+", " ", str(m.group(5) or "")).strip()
            if not title:
                continue
            try:
                start_dt = datetime.strptime(start, "%H:%M")
                end_dt = datetime.strptime(end, "%H:%M")
                delta = int((end_dt - start_dt).total_seconds() // 60)
            except Exception:
                delta = 120
            ops.append(
                {
                    "op": "add_event",
                    "payload": {
                        "date": f"{self._year_for_month_day(month, day):04d}-{month:02d}-{day:02d}",
                        "time": start,
                        "title": title,
                        "duration": self._duration_to_hhmm(delta),
                        "tags": [],
                        "location": "",
                        "remind_before_min": 0,
                    },
                }
            )

        if ops:
            return ops

        current_month_day: tuple[int, int] | None = None
        heading_pattern = re.compile(r"(\d{1,2})月(\d{1,2})日")
        bullet_pattern = re.compile(r"^\s*(?:[-*•]\s*)?(\d{1,2}:\d{2})\s*[-–—~～]\s*(\d{1,2}:\d{2})\s+(.+?)\s*$")
        for raw_line in t.splitlines():
            line = re.sub(r"[*_`#>\[\]()]", " ", raw_line).strip()
            if not line:
                continue
            heading_match = heading_pattern.search(line)
            if heading_match:
                current_month_day = (int(heading_match.group(1)), int(heading_match.group(2)))
                continue
            if current_month_day is None:
                continue
            bullet_match = bullet_pattern.match(line)
            if not bullet_match:
                continue

            month, day = current_month_day
            start = bullet_match.group(1)
            end = bullet_match.group(2)
            title = re.sub(r"\s+", " ", bullet_match.group(3)).strip(" -:：")
            if not title:
                continue
            try:
                start_dt = datetime.strptime(start, "%H:%M")
                end_dt = datetime.strptime(end, "%H:%M")
                delta = int((end_dt - start_dt).total_seconds() // 60)
            except Exception:
                delta = 120
            ops.append(
                {
                    "op": "add_event",
                    "payload": {
                        "date": f"{self._year_for_month_day(month, day):04d}-{month:02d}-{day:02d}",
                        "time": start,
                        "title": title,
                        "duration": self._duration_to_hhmm(delta),
                        "tags": [],
                        "location": "",
                        "remind_before_min": 0,
                    },
                }
            )

        if ops:
            return ops

        for m in weekday_pattern.finditer(t):
            if not m.group(1) or not m.group(2):
                continue
            month = int(m.group(1))
            day = int(m.group(2))
            desc = re.sub(r"\s+", " ", str(m.group(3) or "")).strip()
            if not desc:
                continue
            hours_m = re.search(r"约\s*(\d+(?:\.\d+)?)\s*小时", desc)
            duration = "02:00"
            if hours_m:
                try:
                    duration = self._duration_to_hhmm(int(float(hours_m.group(1)) * 60))
                except Exception:
                    duration = "02:00"
            title = re.sub(r"[，,]\s*约\s*\d+(?:\.\d+)?\s*小时.*$", "", desc).strip()
            title = re.sub(r"^完成", "完成", title).strip()
            if not title:
                continue
            ops.append(
                {
                    "op": "add_event",
                    "payload": {
                        "date": f"{self._year_for_month_day(month, day):04d}-{month:02d}-{day:02d}",
                        "time": "09:00",
                        "title": title,
                        "duration": duration,
                        "tags": [],
                        "location": "",
                        "remind_before_min": 0,
                    },
                }
            )
        return ops

    def _contains_schedule_mutation(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        if re.search(r"(添加|新增|加入|创建|新建|删除|取消|删掉|移除|改成|改为|改到|调整到|调整为|修改|更新|设为|标记|完成)", t):
            return True
        if re.search(r"安排(一个|一下|下|在|到)", t):
            return True
        return False

    def _looks_like_planning_request(self, text: str) -> bool:
        t = self._normalize_user_text(text)
        if not t:
            return False
        ask_pattern = r"(怎么安排|怎么样安排|怎样安排|如何安排|怎么计划|怎么样计划|怎样计划|如何计划|怎么规划|怎么样规划|怎样规划|如何规划|帮我安排|帮我规划|规划一下|安排一下|拆解|分解|制定计划|给我建议|怎么办|怎么做更合适)"
        goal_pattern = r"(完成|写完|推进|准备|复习|备考|赶完|做完|交付|论文|项目|初稿|报告|作业|考试|答辩|面试)"
        horizon_pattern = r"(今天|明天|后天|这周|本周|下周|本月|这个月|下个月|月底|月初|近期)"
        has_planning = bool(re.search(r"(安排|规划|计划|拆解|分解|建议)", t))
        has_ask = bool(re.search(ask_pattern, t) or "?" in t or "？" in t)
        return bool(has_planning and has_ask and (re.search(goal_pattern, t) or re.search(horizon_pattern, t)))

    def _reply_for_goal_planning(self, text: str) -> str:
        t = self._normalize_user_text(text)
        if not self._looks_like_planning_request(t):
            return ""

        if "论文" in t and ("初稿" in t or "论文" in t):
            return (
                "可以先不要急着写成一条日程，先把目标拆成 4 块：\n"
                "1. 明确初稿范围：今天先定提纲、章节和参考资料。\n"
                "2. 拆成 3 个写作块：比如文献综述、主体分析、结论与摘要。\n"
                "3. 每天安排 2 到 3 个专注时段，每个时段只推进一个小块。\n"
                "4. 最后预留半天到一天做通读、补引用和格式检查。\n\n"
                "如果你愿意，我可以继续把“下周完成论文初稿”拆成按天安排。"
            )

        return (
            "这类目标更适合先拆解再写入日程。可以先按这个顺序推进：\n"
            "1. 先明确最终交付物和截止时间。\n"
            "2. 把目标拆成 3 到 5 个可独立完成的小任务。\n"
            "3. 先安排最关键、最费脑的部分，再安排整理和收尾。\n"
            "4. 预留一段缓冲时间，避免最后一天堆在一起。\n\n"
            "如果你愿意，我可以继续按天帮你拆解。"
        )

    def _next_week_monday(self) -> datetime.date:
        today = _now().date()
        days_until_next_monday = (7 - today.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7
        return today + timedelta(days=days_until_next_monday)

    def _planning_payload_for_goal(self, text: str) -> dict[str, Any]:
        t = self._normalize_user_text(text)
        if not self._looks_like_planning_request(t):
            return {}

        if "论文" in t and ("初稿" in t or "论文" in t):
            start = self._next_week_monday()
            plan_rows = [
                (0, "09:00", "12:00", "完成大纲和文献综述框架"),
                (1, "09:00", "11:30", "撰写引言部分"),
                (2, "09:00", "12:00", "完成研究方法章节"),
                (3, "09:00", "12:30", "撰写结果分析部分"),
                (4, "09:00", "12:00", "完成讨论和结论"),
                (5, "09:00", "13:30", "整合修改论文初稿"),
            ]
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            ops: list[dict[str, Any]] = []
            lines = ["建议将论文初稿拆解为每日任务："]
            for idx, (offset, start_time, end_time, title) in enumerate(plan_rows, start=1):
                current = start + timedelta(days=offset)
                duration_min = int((datetime.strptime(end_time, "%H:%M") - datetime.strptime(start_time, "%H:%M")).total_seconds() // 60)
                lines.append(
                    f"{idx}. {current.month}月{current.day}日({weekday_names[current.weekday()]})"
                    f"{start_time}-{end_time} {title}"
                )
                ops.append(
                    {
                        "op": "add_event",
                        "payload": {
                            "date": current.isoformat(),
                            "time": start_time,
                            "title": title,
                            "duration": self._duration_to_hhmm(duration_min),
                            "tags": [],
                            "location": "",
                            "remind_before_min": 0,
                        },
                    }
                )
            lines.append("")
            lines.append("需要我帮您将这些任务添加到日程中吗？")
            return {"reply": "\n".join(lines), "plan_ops": ops}

        reply = self._reply_for_goal_planning(t)
        plan_ops = self._infer_plan_ops_from_text(reply) if reply else []
        return {"reply": reply, "plan_ops": plan_ops}

    def _looks_like_apply_recent_plan(self, text: str) -> bool:
        t = self._normalize_user_text(text)
        if not t:
            return False
        refer_pattern = r"(这些|这个|上面|刚才|刚刚|上述)"
        apply_pattern = r"(添加到日程|加入日程|写进日程|写入日程|放进日程|同步到日程|加到日程)"
        return bool(re.search(apply_pattern, t) and (re.search(refer_pattern, t) or "任务" in t or "安排" in t))

    def _recover_recent_plan_from_history(
        self,
        *,
        channel: str,
        chat_id: str = "",
        open_id: str = "",
        max_age_seconds: float = 3600.0,
    ) -> dict[str, Any]:
        messages = self._read_messages_for_date(_today())
        now = _now()
        for msg in reversed(messages):
            if not self._message_matches_scope(msg, channel=channel, chat_id=chat_id, open_id=open_id):
                continue
            ts = str(msg.get("ts", "") or "").strip()
            try:
                msg_dt = datetime.fromisoformat(ts)
            except Exception:
                msg_dt = None
            if msg_dt is not None and (now - msg_dt).total_seconds() > max_age_seconds:
                break
            if str(msg.get("role", "") or "") != "assistant":
                continue
            ops = msg.get("plan_ops") if isinstance(msg.get("plan_ops"), list) else []
            if not ops:
                ops = self._infer_plan_ops_from_text(str(msg.get("text", "") or ""))
            if ops:
                return {"ops": ops, "source_text": str(msg.get("text", "") or "").strip()}
        return {}

    def _looks_like_schedule_lookup(self, text: str) -> bool:
        t = (text or "").strip()
        if not t or self._contains_schedule_mutation(t) or self._looks_like_planning_request(t):
            return False

        has_topic = bool(re.search(r"(日程|安排|计划|行程|会议|待办|任务)", t))
        has_question = (
            ("?" in t)
            or ("？" in t)
            or bool(re.search(r"(什么|啥|哪些|几项|多少|有吗|有没有|查看|看看|查询|列出|告诉我|帮我看|帮我查)", t))
        )
        has_date_hint = bool(re.search(r"(今天|明天|后天|\d{4}[-/年]\d{1,2}[-/月]\d{1,2}|\d{1,2}月\d{1,2}[日号]?)", t))
        return (has_topic and has_question) or (has_topic and has_date_hint and has_question)

    def _load_schedule_month(self, month: str) -> dict[str, Any]:
        p = self._schedule_file(month)
        try:
            if p.exists():
                obj = json.loads(p.read_text(encoding="utf-8"))
                return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
        return {}

    def _events_for_date(self, date_str: str) -> list[dict[str, Any]]:
        raw = self._load_schedule_month(date_str[:7])
        events = raw.get("events") if isinstance(raw.get("events"), list) else []
        picked: list[dict[str, Any]] = []
        for item in events:
            if not isinstance(item, dict):
                continue
            if str(item.get("date", "") or "").strip() != date_str:
                continue
            picked.append(item)

        def _sort_key(x: dict[str, Any]) -> tuple[int, str]:
            time_text = str(x.get("time", "") or "").strip()
            if not time_text or time_text == "待定":
                return (1, "99:99")
            return (0, time_text)

        picked.sort(key=_sort_key)
        return picked

    def _open_todos(self, month: str) -> list[dict[str, Any]]:
        raw = self._load_schedule_month(month)
        todos = raw.get("todos") if isinstance(raw.get("todos"), list) else []
        out: list[dict[str, Any]] = []
        for item in todos:
            if not isinstance(item, dict):
                continue
            if bool(item.get("done", False)):
                continue
            out.append(item)
        return out

    def _date_label(self, date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return date_str
        today = _now().date()
        if dt == today:
            return f"今天（{date_str}）"
        if dt == today + timedelta(days=1):
            return f"明天（{date_str}）"
        if dt == today + timedelta(days=2):
            return f"后天（{date_str}）"
        return date_str

    def _reply_for_schedule_lookup(self, text: str) -> str:
        if not self._looks_like_schedule_lookup(text):
            return ""

        t = (text or "").strip()
        date_str = self._parse_date_hint(t)
        date_label = self._date_label(date_str)
        events = self._events_for_date(date_str)
        include_events = bool(re.search(r"(日程|安排|计划|行程|会议)", t))
        include_todos = bool(re.search(r"(待办|任务)", t))
        todos = self._open_todos(date_str[:7]) if include_todos else []

        parts: list[str] = []
        if include_events and events:
            lines = []
            for item in events:
                time_text = str(item.get("time", "") or "待定").strip() or "待定"
                title = str(item.get("title", "") or "").strip()
                lines.append(f"{time_text} {title}".strip())
            parts.append(f"{date_label}的日程：\n" + "\n".join(lines))
        elif include_events and not include_todos:
            parts.append(f"{date_label}还没有安排日程。")

        if include_todos:
            todo_lines = [f"- {str(item.get('text', '') or '').strip()}" for item in todos[:5] if str(item.get("text", "") or "").strip()]
            if todo_lines:
                parts.append("当前待办：\n" + "\n".join(todo_lines))
            else:
                parts.append("当前没有待办。")

        return "\n\n".join([x for x in parts if x.strip()])

    def _fallback_ops_from_text(self, text: str) -> list[dict[str, Any]]:
        t = self._normalize_user_text(text)
        if not t:
            return []
        if self._looks_like_schedule_lookup(t) or self._looks_like_planning_request(t):
            return []
        if not self._looks_like_schedule_request(t):
            return []

        date_hint = self._parse_date_hint(t)
        time_hint = self._parse_time_hint(t)
        subject = self._cleanup_subject(t)

        if "待办" in t and re.search(r"(添加|新增|加入|创建)", t):
            return [{"op": "add_todo", "payload": {"text": subject or t, "done": False}}]

        if "待办" in t and re.search(r"(删除|取消|删掉)", t):
            return [{"op": "delete_todo", "payload": {"text": subject or t}}]

        if "待办" in t and re.search(r"(完成|做完)", t):
            return [{"op": "update_todo", "payload": {"from_text": subject or t, "done": True}}]

        if re.search(r"(删除|取消|删掉)", t) and re.search(r"(日程|会议|活动|行程)", t):
            payload: dict[str, Any] = {"title": subject or t}
            if date_hint:
                payload["date"] = date_hint
            if time_hint:
                payload["time"] = time_hint
            return [{"op": "delete_event", "payload": payload}]

        if re.search(r"(改到|改成|改为|调整到)", t) and time_hint:
            payload = {"title": subject or t, "time": time_hint}
            if date_hint:
                payload["date"] = date_hint
            return [{"op": "update_event", "payload": payload}]

        if time_hint or re.search(r"(今天|明天|后天|\d{1,2}月\d{1,2}[日号]?|日程|会议|活动|行程)", t):
            return [{
                "op": "add_event",
                "payload": {
                    "date": date_hint,
                    "time": time_hint or "待定",
                    "title": subject or "事件",
                    "duration": "01:00",
                    "tags": [],
                    "location": "",
                    "remind_before_min": 0,
                },
            }]

        return []

    def _pick_followup(self, result: dict[str, Any]) -> str:
        followups = result.get("followups") if isinstance(result.get("followups"), list) else []
        for item in followups:
            text = str(item or "").strip()
            if text:
                return text
        return ""

    def _ensure_confirm_prompt(self, text: str) -> str:
        base = str(text or "").strip()
        prompt = '请回复“确定”执行，或者回复“取消”放弃。'
        if not base:
            return prompt
        if prompt in base:
            return base
        return f"{base}\n{prompt}"

    def _default_confirm_text_from_ops(self, ops: list[dict[str, Any]]) -> str:
        if not ops:
            return "请回复“确定”执行，或回复“取消”放弃。"
        op_obj = ops[0] if isinstance(ops[0], dict) else {}
        op = str(op_obj.get("op", "") or "")
        payload = op_obj.get("payload") if isinstance(op_obj.get("payload"), dict) else {}
        if op == "add_todo":
            return f"确认新增待办：{payload.get('text', '')}？"
        if op == "delete_todo":
            return f"确认删除待办：{payload.get('text', '')}？"
        if op == "update_todo":
            return f"确认更新待办：{payload.get('text', '') or payload.get('from_text', '')}？"
        if op == "add_event":
            return f"确认新增日程：{payload.get('date', '')} {payload.get('time', '')} {payload.get('title', '')}？"
        if op == "delete_event":
            return f"确认删除日程：{payload.get('title', '')}？"
        if op == "update_event":
            return f"确认更新日程：{payload.get('title', '')}？"
        return "请回复“确定”执行，或回复“取消”放弃。"

    def _pending_command(self, text: str) -> str:
        t = (text or "").strip()
        normalized = re.sub(r"[\W_]+", "", t, flags=re.UNICODE)
        if normalized.startswith("\u786e\u5b9a") or normalized.startswith("\u786e\u8ba4"):
            return "confirm"
        if normalized.startswith("\u53d6\u6d88"):
            return "cancel"
        return ""


    def _process_user_message(self, *, text: str, channel: str, chat_id: str = "", open_id: str = "") -> str:
        t = (text or "").strip()
        if not t:
            return ""

        pending_cmd = self._pending_command(t)
        if pending_cmd:
            has_pending = self._schedule.hasPending()
            if has_pending:
                if pending_cmd == "confirm":
                    _ok, msg = self._schedule.confirmPendingFromChannel(channel=channel, source="chat")
                else:
                    _ok, msg = self._schedule.cancelPendingFromChannel()
                self._clear_recent_proposal(channel=channel, chat_id=chat_id, open_id=open_id)
            else:
                recent = self._get_recent_proposal(channel=channel, chat_id=chat_id, open_id=open_id)
                if not recent:
                    recent = self._recover_recent_proposal_from_history(channel=channel, chat_id=chat_id, open_id=open_id)
                    if recent:
                        self._remember_proposal(
                            channel=channel,
                            confirm_text=str(recent.get("confirm_text", "") or ""),
                            ops=list(recent.get("ops", []) if isinstance(recent.get("ops"), list) else []),
                            chat_id=chat_id,
                            open_id=open_id,
                        )
                if pending_cmd == "cancel":
                    if recent:
                        self._clear_recent_proposal(channel=channel, chat_id=chat_id, open_id=open_id)
                        msg = "????????"
                    else:
                        msg = "?????????"
                elif recent:
                    reproposal = self._schedule.proposeFromChat(
                        channel=channel,
                        confirm_text=str(recent.get("confirm_text", "") or ""),
                        ops=list(recent.get("ops", []) if isinstance(recent.get("ops"), list) else []),
                    )
                    reproposal_status = str(reproposal.get("status", "") or "")
                    if reproposal_status in {"proposed", "already_pending"}:
                        _ok, msg = self._schedule.confirmPendingFromChannel(channel=channel, source="chat")
                        self._clear_recent_proposal(channel=channel, chat_id=chat_id, open_id=open_id)
                    elif reproposal_status == "already_applied":
                        msg = "????????????????"
                        self._clear_recent_proposal(channel=channel, chat_id=chat_id, open_id=open_id)
                    else:
                        msg = "?????????"
                else:
                    msg = "?????????"
            self._append_message(
                role="assistant",
                text=msg,
                channel=channel,
                intent="none",
                chat_id=chat_id,
                sender_open_id=open_id,
            )
            self.pendingChanged.emit()
            self.loadMessages(_today())
            return msg

        plan_offer_cmd = self._recent_plan_offer_reply(t)
        if plan_offer_cmd:
            plan = self._recover_recent_plan_from_history(channel=channel, chat_id=chat_id, open_id=open_id)
            plan_ops = list(plan.get("ops", []) if isinstance(plan.get("ops"), list) else [])
            source_text = str(plan.get("source_text", "") or "").strip()
            if plan_ops and self._is_recent_plan_offer_text(source_text):
                if plan_offer_cmd == "reject":
                    reply = "?????????????????????????????????"
                    intent = "chat"
                    proposal_meta = None
                else:
                    reply, intent, proposal_meta = self._propose_plan_ops(
                        ops=plan_ops,
                        channel=channel,
                        chat_id=chat_id,
                        open_id=open_id,
                    )
                self._append_message(
                    role="assistant",
                    text=reply,
                    channel=channel,
                    intent=intent,
                    chat_id=chat_id,
                    sender_open_id=open_id,
                    extra=proposal_meta,
                )
                self.loadMessages(_today())
                return reply

        if self._looks_like_apply_recent_plan(t):
            plan = self._recover_recent_plan_from_history(channel=channel, chat_id=chat_id, open_id=open_id)
            plan_ops = list(plan.get("ops", []) if isinstance(plan.get("ops"), list) else [])
            if plan_ops:
                reply, intent, proposal_meta = self._propose_plan_ops(
                    ops=plan_ops,
                    channel=channel,
                    chat_id=chat_id,
                    open_id=open_id,
                )
                self._append_message(
                    role="assistant",
                    text=reply,
                    channel=channel,
                    intent=intent,
                    chat_id=chat_id,
                    sender_open_id=open_id,
                    extra=proposal_meta,
                )
                self.loadMessages(_today())
                return reply

            reply = "????????????????????????????????????????????????????"
            self._append_message(
                role="assistant",
                text=reply,
                channel=channel,
                intent="chat",
                chat_id=chat_id,
                sender_open_id=open_id,
            )
            self.loadMessages(_today())
            return reply

        lookup_reply = self._reply_for_schedule_lookup(t)
        if lookup_reply:
            self._append_message(
                role="assistant",
                text=lookup_reply,
                channel=channel,
                intent="chat",
                chat_id=chat_id,
                sender_open_id=open_id,
            )
            self.loadMessages(_today())
            return lookup_reply

        context = self._load_recent_context(limit=200)
        result = self._call_kimi_json(t, context)
        reply = str(result.get("reply", "") or "").strip() or "???"
        intent = str(result.get("intent", "chat") or "chat")
        ops = result.get("ops") if isinstance(result.get("ops"), list) else []

        planning_payload = self._planning_payload_for_goal(t)
        planning_reply = str(planning_payload.get("reply", "") or "").strip()
        planning_ops = list(planning_payload.get("plan_ops", []) if isinstance(planning_payload.get("plan_ops"), list) else [])
        if not planning_ops and self._looks_like_planning_request(t):
            planning_ops = self._infer_plan_ops_from_text(reply)

        route_to_schedule = self._looks_like_schedule_request(t, intent=intent, ops=ops)
        if not ops and route_to_schedule:
            ops = self._fallback_ops_from_text(t)
        elif self._looks_like_schedule_lookup(t):
            ops = []
            result["needs_confirmation"] = False
            result["intent"] = "chat"
            intent = "chat"
        elif not route_to_schedule and (
            ops or intent in {"schedule_propose", "schedule_followup", "schedule_waiting"} or bool(result.get("needs_confirmation", False))
        ):
            ops = []
            result["needs_confirmation"] = False
            result["intent"] = "chat"
            intent = "chat"
            repaired_reply = self._call_kimi_chat_only(t, context)
            if repaired_reply:
                reply = repaired_reply

        if planning_reply:
            ops = []
            result["needs_confirmation"] = False
            if str(result.get("intent", "") or "") != "chat" or reply in {"", "???"} or reply.startswith("Kimi "):
                reply = planning_reply
            result["intent"] = "chat"
            intent = "chat"

        need_confirm = bool(result.get("needs_confirmation", False)) or bool(ops)
        intent = str(result.get("intent", intent) or intent)
        proposal_meta: Optional[dict[str, Any]] = None
        followup_reply = self._pick_followup(result)

        if intent == "schedule_followup" and not ops:
            reply = followup_reply or reply or "??????????????????????"
            need_confirm = False
            ops = []
        elif intent == "schedule_propose" and not ops:
            if followup_reply:
                reply = followup_reply
                intent = "schedule_followup"
            else:
                reply = "???????????????????????????????????"
                intent = "schedule_followup"
            need_confirm = False

        if need_confirm and ops:
            confirm_text = str(result.get("confirm_text", "") or "").strip() or self._default_confirm_text_from_ops(ops)
            confirm_text = self._ensure_confirm_prompt(confirm_text)
            proposal = self._schedule.proposeFromChat(channel=channel, confirm_text=confirm_text, ops=ops)
            status = str(proposal.get("status", "") or "")
            if status == "already_pending":
                reply = self._ensure_confirm_prompt("????????????")
                intent = "schedule_waiting"
                proposal_meta = {
                    "proposal_confirm_text": confirm_text,
                    "proposal_ops": list(ops),
                }
            elif status == "already_applied":
                reply = "????????????????"
                intent = "schedule_duplicate"
            elif status == "proposed":
                reply = str(proposal.get("confirm_text", "") or confirm_text)
                intent = "schedule_propose"
                proposal_ops = list(proposal.get("ops", []) if isinstance(proposal.get("ops"), list) else ops)
                self._remember_proposal(
                    channel=channel,
                    confirm_text=reply,
                    ops=proposal_ops,
                    chat_id=chat_id,
                    open_id=open_id,
                )
                proposal_meta = {
                    "proposal_confirm_text": reply,
                    "proposal_ops": proposal_ops,
                }
                self.pendingChanged.emit()

        self._append_message(
            role="assistant",
            text=reply,
            channel=channel,
            intent=intent,
            chat_id=chat_id,
            sender_open_id=open_id,
            extra=proposal_meta or ({"plan_ops": planning_ops} if planning_ops and intent == "chat" else None),
        )
        self.loadMessages(_today())
        return reply

    @Property("QVariantList", notify=messagesChanged)

    def messages(self) -> list:
        return list(self._messages)

    @Property(bool, notify=kimiConnectedChanged)
    def kimiConnected(self) -> bool:
        return bool(self._kimi_connected)

    @Property(bool, notify=feishuConnectedChanged)
    def feishuConnected(self) -> bool:
        return bool(self._feishu_connected)

    @Property(str, notify=namesChanged)
    def assistantName(self) -> str:
        self._refresh_names()
        return self._assistant_name

    @Property(str, notify=namesChanged)
    def userDisplayName(self) -> str:
        self._refresh_names()
        return self._user_display_name

    @Slot(bool)
    def setKimiConnected(self, value: bool) -> None:
        self._set_kimi_connected(value)

    @Slot(bool)
    def setFeishuConnected(self, value: bool) -> None:
        v = bool(value)
        if self._feishu_connected != v:
            self._feishu_connected = v
            self.feishuConnectedChanged.emit()

    @Slot(str)
    def loadMessages(self, date: str) -> None:
        self._refresh_names()
        d = (date or "").strip() or _today()
        self._selected_date = d
        self._messages = self._read_messages_for_date(d)
        self.messagesChanged.emit(d)

    @Slot(str, str)
    def sendMessage(self, text: str, selectedDate: str) -> None:
        t = (text or "").strip()
        if not t:
            return
        if self._is_duplicate_input(channel="desktop", text=t):
            self.toastRequested.emit("检测到重复发送，已忽略相同消息")
            return
        date = (selectedDate or "").strip() or _today()
        if date != _today():
            self.dateAutoSwitched.emit(_today())
            self.toastRequested.emit("历史日期不可补写，已切回今天发送")

        self._append_message(role="user", text=t, channel="desktop")
        self.loadMessages(_today())

        def _worker() -> None:
            self._process_user_message(text=t, channel="desktop")

        threading.Thread(target=_worker, name="ChatDesktop", daemon=True).start()

    @Slot()
    def confirmPending(self) -> None:
        if not self._schedule.hasPending():
            self.toastRequested.emit("当前没有待确认操作")
            return
        _ok, msg = self._schedule.confirmPendingFromChannel(channel="desktop", source="chat")
        self._append_message(role="assistant", text=msg, channel="desktop")
        self.pendingChanged.emit()
        self.loadMessages(_today())
        self.toastRequested.emit(msg)

    @Slot()
    def cancelPending(self) -> None:
        _ok, msg = self._schedule.cancelPendingFromChannel()
        self._append_message(role="assistant", text=msg, channel="desktop")
        self.pendingChanged.emit()
        self.loadMessages(_today())
        self.toastRequested.emit(msg)

    @Slot(result="QVariantList")
    def availableChatDates(self) -> list:
        dates = self._list_chat_dates()
        today = _today()
        if today not in dates:
            dates.append(today)
        return sorted(set(dates))

    @Slot(result=str)
    def forceTodayDate(self) -> str:
        td = _today()
        self.loadMessages(td)
        return td

    def handleFeishuText(self, chat_id: str, open_id: str, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        if self._is_duplicate_input(channel="feishu", text=t, chat_id=chat_id, open_id=open_id):
            return "检测到重复消息，已忽略相同内容。"
        self._append_message(
            role="user",
            text=t,
            channel="feishu",
            chat_id=(chat_id or "").strip(),
            sender_open_id=(open_id or "").strip(),
        )
        return self._process_user_message(
            text=t,
            channel="feishu",
            chat_id=(chat_id or "").strip(),
            open_id=(open_id or "").strip(),
        )
