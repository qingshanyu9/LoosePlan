from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _today() -> str:
    return _now().date().isoformat()


def _month_of(date_str: str) -> str:
    return (date_str or "")[:7]


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _format_date_cn(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.year}年 {dt.month}月"
    except Exception:
        return date_str


def _format_display_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d %b / %Y").upper()
    except Exception:
        return date_str


def _human_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        return ts
    now = _now()
    if dt.date() == now.date():
        return f"今天 {dt.strftime('%H:%M')}"
    if dt.date() == (now.date() - timedelta(days=1)):
        return f"昨天 {dt.strftime('%H:%M')}"
    return dt.strftime("%m-%d %H:%M")


def _month_file_skeleton(month: str) -> dict[str, Any]:
    return {
        "month": month,
        "events": [],
        "todos": [],
        "derived": {
            "last_derived_at": "",
            "today_date": _today(),
            "today_plan_lines": [],
            "month_achievements": "",
            "last_month_achievements_at": "",
        },
        "change_log": [],
    }


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


@dataclass
class ScheduleOp:
    op: str
    month: str
    payload: dict[str, Any]


class ScheduleService(QObject):
    monthDataChanged = Signal(str)
    pendingChanged = Signal()
    toastRequested = Signal(str)

    def __init__(
        self,
        *,
        get_data_dir: Callable[[], Path],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._get_data_dir = get_data_dir
        self._lock = threading.Lock()

        self._month_data: dict[str, Any] = {}
        self._current_month: str = ""
        self._selected_date: str = _today()
        self._pending: dict[str, Any] = {}

        if self._is_configured():
            self._load_pending()
            self._rebuild_month_data()

    def _data_dir(self) -> Path:
        return self._get_data_dir().resolve()

    def _is_configured(self) -> bool:
        return (self._data_dir() / "config.json").exists()

    def _schedule_dir(self) -> Path:
        p = self._data_dir() / "schedule"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _pending_file(self) -> Path:
        p = self._data_dir() / "pending"
        p.mkdir(parents=True, exist_ok=True)
        return p / "pending_action.json"

    def _month_file(self, month: str) -> Path:
        return self._schedule_dir() / f"{month}.json"

    def _load_month_raw(self, month: str) -> dict[str, Any]:
        path = self._month_file(month)
        raw = _read_json(path, _month_file_skeleton(month))
        if not isinstance(raw, dict):
            raw = _month_file_skeleton(month)
        raw.setdefault("month", month)
        raw.setdefault("events", [])
        raw.setdefault("todos", [])
        raw.setdefault("derived", {})
        raw.setdefault("change_log", [])
        derived = raw["derived"] if isinstance(raw["derived"], dict) else {}
        derived.setdefault("last_derived_at", "")
        derived.setdefault("today_date", _today())
        derived.setdefault("today_plan_lines", [])
        derived.setdefault("month_achievements", "")
        derived.setdefault("last_month_achievements_at", "")
        raw["derived"] = derived
        return raw

    def _save_month_raw(self, month: str, obj: dict[str, Any]) -> None:
        _atomic_write_json(self._month_file(month), obj)

    def _load_pending(self) -> None:
        p = _read_json(self._pending_file(), {})
        self._pending = p if isinstance(p, dict) else {}

    def _save_pending(self, obj: dict[str, Any]) -> None:
        self._pending = obj if isinstance(obj, dict) else {}
        _atomic_write_json(self._pending_file(), self._pending)
        self.pendingChanged.emit()

    def _clear_pending(self) -> None:
        self._save_pending({})

    def _sorted_events_for_date(self, events: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
        picked: list[dict[str, Any]] = []
        for e in events:
            if not isinstance(e, dict):
                continue
            if str(e.get("date", "")).strip() != date_str:
                continue
            picked.append(e)

        def _sort_key(x: dict[str, Any]) -> tuple[int, str]:
            t = str(x.get("time", "") or "").strip()
            if t == "待定" or not t:
                return (1, "99:99")
            return (0, t)

        picked.sort(key=_sort_key)
        return picked

    def _rebuild_derived(self, month_obj: dict[str, Any]) -> None:
        today = _today()
        events = month_obj.get("events") if isinstance(month_obj.get("events"), list) else []
        lines: list[str] = []
        for e in self._sorted_events_for_date(events, today):
            t = str(e.get("time", "") or "").strip() or "待定"
            title = str(e.get("title", "") or "").strip()
            lines.append(f"{t}  {title}".strip())

        d = month_obj.get("derived") if isinstance(month_obj.get("derived"), dict) else {}
        d["today_date"] = today
        d["today_plan_lines"] = lines
        d["last_derived_at"] = _now_iso()
        month_obj["derived"] = d

    def _stats(self, todos: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(todos)
        done = sum(1 for x in todos if isinstance(x, dict) and bool(x.get("done", False)))
        pending = max(0, total - done)
        done_pct = (done / total * 100.0) if total else 0.0
        pending_pct = (pending / total * 100.0) if total else 0.0
        return {
            "done": done,
            "pending": pending,
            "total": total,
            "done_pct": round(done_pct, 1),
            "pending_pct": round(pending_pct, 1),
        }

    def _calendar_cells(self, selected_date: str) -> list[dict[str, Any]]:
        try:
            sel = datetime.strptime(selected_date, "%Y-%m-%d")
        except Exception:
            sel = _now()
        first = sel.replace(day=1)
        start_weekday = (first.weekday() + 1) % 7  # Sunday=0
        start = first - timedelta(days=start_weekday)
        today = _today()
        cells: list[dict[str, Any]] = []
        for i in range(42):
            d = start + timedelta(days=i)
            ds = d.date().isoformat()
            cells.append(
                {
                    "date": ds,
                    "day": d.day,
                    "in_month": d.month == sel.month,
                    "selected": ds == selected_date,
                    "today": ds == today,
                }
            )
        return cells

    def _history_rows(self, logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in reversed(logs[-20:]):
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "id": str(item.get("id", "") or ""),
                    "time_text": _human_time(str(item.get("ts", "") or "")),
                    "summary": str(item.get("summary", "") or ""),
                    "channel": str(item.get("channel", "") or ""),
                }
            )
        return out[:12]

    def _rebuild_month_data(self) -> None:
        month = self._current_month or _month_of(self._selected_date or _today()) or _month_of(_today())
        self._current_month = month
        if not self._selected_date:
            self._selected_date = f"{month}-01"

        raw = self._load_month_raw(month)
        todos = raw.get("todos") if isinstance(raw.get("todos"), list) else []
        events = raw.get("events") if isinstance(raw.get("events"), list) else []
        change_log = raw.get("change_log") if isinstance(raw.get("change_log"), list) else []
        derived = raw.get("derived") if isinstance(raw.get("derived"), dict) else {}

        todo_rows: list[dict[str, Any]] = []
        for idx, t in enumerate(todos, start=1):
            if not isinstance(t, dict):
                continue
            todo_rows.append(
                {
                    "id": str(t.get("id", "") or ""),
                    "num": f"{idx:02d}",
                    "text": str(t.get("text", "") or ""),
                    "done": bool(t.get("done", False)),
                }
            )

        event_rows: list[dict[str, Any]] = []
        for e in self._sorted_events_for_date(events, self._selected_date):
            event_rows.append(
                {
                    "id": str(e.get("id", "") or ""),
                    "time": str(e.get("time", "") or "待定"),
                    "title": str(e.get("title", "") or ""),
                    "tags": list(e.get("tags", []) if isinstance(e.get("tags"), list) else []),
                }
            )

        achv = str(derived.get("month_achievements", "") or "").strip()
        notes = [x.strip(" -•\t") for x in achv.splitlines() if x.strip()] if achv else []
        if not notes:
            notes = ["本月成果将在首次联网刷新后生成"]

        self._month_data = {
            "month": month,
            "selected_date": self._selected_date,
            "month_label": _format_date_cn(self._selected_date),
            "display_date": _format_display_date(self._selected_date),
            "calendar_cells": self._calendar_cells(self._selected_date),
            "todos": todo_rows,
            "events": event_rows,
            "notes": [{"text": x} for x in notes[:8]],
            "history": self._history_rows(change_log),
            "stats": self._stats(todos),
        }

        self.monthDataChanged.emit(month)

    def _generate_month_achievements_local(self, month_obj: dict[str, Any], month: str) -> str:
        todos = month_obj.get("todos") if isinstance(month_obj.get("todos"), list) else []
        done = sum(1 for t in todos if isinstance(t, dict) and bool(t.get("done", False)))
        total = len(todos)
        events = month_obj.get("events") if isinstance(month_obj.get("events"), list) else []
        lines = [
            f"{month} 计划进展：已完成待办 {done}/{total} 项。",
            f"本月已安排日程 {len(events)} 项。",
        ]
        if done > 0 and total > 0:
            pct = round(done / total * 100, 1)
            lines.append(f"完成率约 {pct}%。")
        return "\n".join(lines)

    def _ensure_month_for_selected(self) -> None:
        m = _month_of(self._selected_date or _today()) or _month_of(_today())
        if self._current_month != m:
            self._current_month = m

    def _new_pending(self, *, reason: str, confirm_text: str, ops: list[dict[str, Any]], channel: str) -> dict[str, Any]:
        return {
            "created_at": _now_iso(),
            "channel": channel,
            "reason": reason,
            "confirm_text": confirm_text,
            "ops": ops,
        }

    def _append_change_log(
        self,
        month_obj: dict[str, Any],
        *,
        channel: str,
        source: str,
        op: str,
        summary: str,
        before: Any,
        after: Any,
    ) -> None:
        logs = month_obj.get("change_log") if isinstance(month_obj.get("change_log"), list) else []
        logs.append(
            {
                "id": str(uuid.uuid4()),
                "ts": _now_iso(),
                "channel": channel,
                "source": source,
                "op": op,
                "summary": summary,
                "before": before,
                "after": after,
            }
        )
        month_obj["change_log"] = logs[-200:]

    def _match_text(self, source: str, target: str) -> bool:
        s = (source or "").strip().lower()
        t = (target or "").strip().lower()
        if not s or not t:
            return False
        return s == t or s in t or t in s

    def _normalize_event_value(self, value: str) -> str:
        s = str(value or "").strip().lower()
        return re.sub(r"\s+", " ", s)

    def _event_signature(self, obj: dict[str, Any]) -> tuple[str, str, str]:
        if not isinstance(obj, dict):
            return "", "", ""
        date = str(obj.get("date", "") or "").strip()
        time = str(obj.get("time", "") or "").strip()
        title = self._normalize_event_value(str(obj.get("title", "") or ""))
        return date, time, title

    def _ops_signature(self, ops: list[dict[str, Any]]) -> str:
        packed = self._build_ops_for_channel(ops)
        try:
            return json.dumps(packed, ensure_ascii=False, sort_keys=True)
        except Exception:
            return ""

    def _op_already_applied(self, op_obj: dict[str, Any]) -> bool:
        if not isinstance(op_obj, dict):
            return False
        op = str(op_obj.get("op", "") or "").strip()
        payload = op_obj.get("payload") if isinstance(op_obj.get("payload"), dict) else {}
        if op != "add_event":
            return False

        month = str(op_obj.get("month", "") or "").strip()
        if not month:
            month = _month_of(str(payload.get("date", "") or self._selected_date or _today())) or _month_of(_today())

        target_sig = self._event_signature(payload)
        if not all(target_sig):
            return False

        month_obj = self._load_month_raw(month)
        events = month_obj.get("events") if isinstance(month_obj.get("events"), list) else []
        for item in events:
            if not isinstance(item, dict):
                continue
            if self._event_signature(item) == target_sig:
                return True
        return False

    def _find_event_index(self, events: list[dict[str, Any]], payload: dict[str, Any]) -> int:
        event_id = str(payload.get("id", "") or "").strip()
        if event_id:
            return next((i for i, x in enumerate(events) if isinstance(x, dict) and str(x.get("id", "")) == event_id), -1)

        title = str(payload.get("match_title", "") or payload.get("from_title", "") or payload.get("title", "") or "").strip()
        date = str(payload.get("match_date", "") or payload.get("from_date", "") or "").strip()
        time = str(payload.get("match_time", "") or payload.get("from_time", "") or "").strip()
        if not title and not date and not time:
            date = str(payload.get("date", "") or "").strip()
            time = str(payload.get("time", "") or "").strip()
        for idx, item in enumerate(events):
            if not isinstance(item, dict):
                continue
            if title and not self._match_text(title, str(item.get("title", "") or "")):
                continue
            if date and date != str(item.get("date", "") or "").strip():
                continue
            if time and time != str(item.get("time", "") or "").strip():
                continue
            return idx
        return -1

    def _find_todo_index(self, todos: list[dict[str, Any]], payload: dict[str, Any]) -> int:
        todo_id = str(payload.get("id", "") or "").strip()
        if todo_id:
            return next((i for i, x in enumerate(todos) if isinstance(x, dict) and str(x.get("id", "")) == todo_id), -1)

        text = str(payload.get("text", "") or payload.get("from_text", "") or "").strip()
        for idx, item in enumerate(todos):
            if not isinstance(item, dict):
                continue
            if self._match_text(text, str(item.get("text", "") or "")):
                return idx
        return -1

    def _apply_op(self, month_obj: dict[str, Any], op_obj: dict[str, Any], *, channel: str, source: str) -> None:
        op = str(op_obj.get("op", "") or "").strip()
        payload = op_obj.get("payload") if isinstance(op_obj.get("payload"), dict) else {}
        if not op:
            return

        events = month_obj.get("events") if isinstance(month_obj.get("events"), list) else []
        todos = month_obj.get("todos") if isinstance(month_obj.get("todos"), list) else []
        now_iso = _now_iso()

        if op == "add_event":
            event = {
                "id": str(uuid.uuid4()),
                "date": str(payload.get("date", "") or self._selected_date or _today()),
                "time": str(payload.get("time", "") or "待定"),
                "title": str(payload.get("title", "") or "").strip(),
                "duration": str(payload.get("duration", "") or "01:00"),
                "tags": list(payload.get("tags", []) if isinstance(payload.get("tags"), list) else []),
                "location": str(payload.get("location", "") or ""),
                "remind_before_min": _to_int(payload.get("remind_before_min", 0) or 0, 0),
                "created_at": now_iso,
                "updated_at": now_iso,
                "source": source,
                "channel": channel,
            }
            events.append(event)
            month_obj["events"] = events
            self._append_change_log(
                month_obj,
                channel=channel,
                source=source,
                op=op,
                summary=f"新增：{event['date']} {event['time']} {event['title']}（{channel}）",
                before=None,
                after={"id": event["id"], "date": event["date"], "time": event["time"], "title": event["title"]},
            )
            return

        if op == "delete_event":
            idx = self._find_event_index(events, payload)
            if idx < 0:
                return
            before = events[idx]
            del events[idx]
            month_obj["events"] = events
            self._append_change_log(
                month_obj,
                channel=channel,
                source=source,
                op=op,
                summary=f"删除日程：{before.get('title', '')}（{channel}）",
                before=before,
                after=None,
            )
            return

        if op == "update_event":
            idx = self._find_event_index(events, payload)
            if idx < 0:
                return
            before = dict(events[idx])
            after = dict(events[idx])
            for k in ["date", "time", "title", "duration", "tags", "location", "remind_before_min"]:
                if k in payload:
                    after[k] = payload[k]
            after["updated_at"] = now_iso
            events[idx] = after
            month_obj["events"] = events
            self._append_change_log(
                month_obj,
                channel=channel,
                source=source,
                op=op,
                summary=f"更新日程：{after.get('title', '')}（{channel}）",
                before=before,
                after=after,
            )
            return

        if op == "add_todo":
            text = str(payload.get("text", "") or "").strip()
            if not text:
                return
            todo = {
                "id": str(uuid.uuid4()),
                "text": text,
                "done": bool(payload.get("done", False)),
                "created_at": now_iso,
                "updated_at": now_iso,
                "source": source,
                "channel": channel,
            }
            todos.append(todo)
            month_obj["todos"] = todos
            self._append_change_log(
                month_obj,
                channel=channel,
                source=source,
                op=op,
                summary=f"新增待办：{text}（{channel}）",
                before=None,
                after={"id": todo["id"], "text": todo["text"], "done": todo["done"]},
            )
            return

        if op in {"delete_todo", "toggle_todo", "update_todo"}:
            idx = self._find_todo_index(todos, payload)
            if idx < 0:
                return
            before = dict(todos[idx])
            after = dict(todos[idx])
            if op == "delete_todo":
                del todos[idx]
                month_obj["todos"] = todos
                self._append_change_log(
                    month_obj,
                    channel=channel,
                    source=source,
                    op=op,
                    summary=f"删除待办：{before.get('text', '')}（{channel}）",
                    before=before,
                    after=None,
                )
                return
            if op == "toggle_todo":
                after["done"] = not bool(before.get("done", False))
            if op == "update_todo":
                if "text" in payload:
                    after["text"] = str(payload.get("text", "") or "").strip() or after.get("text", "")
                if "done" in payload:
                    after["done"] = bool(payload.get("done", False))
            after["updated_at"] = now_iso
            todos[idx] = after
            month_obj["todos"] = todos
            self._append_change_log(
                month_obj,
                channel=channel,
                source=source,
                op=op,
                summary=f"更新待办：{after.get('text', '')}（{channel}）",
                before=before,
                after=after,
            )

    def _build_ops_for_channel(self, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for x in ops:
            if not isinstance(x, dict):
                continue
            op = str(x.get("op", "") or "").strip()
            month = str(x.get("month", "") or "").strip()
            payload = x.get("payload") if isinstance(x.get("payload"), dict) else {}
            if not op:
                continue
            if not month:
                date = str(payload.get("date", "") or self._selected_date or _today())
                month = _month_of(date) or self._current_month or _month_of(_today())
            out.append({"op": op, "month": month, "payload": payload})
        return out

    def _propose_ops(self, *, reason: str, confirm_text: str, ops: list[dict[str, Any]], channel: str) -> dict[str, Any]:
        packed = self._build_ops_for_channel(ops)
        if not packed:
            self.toastRequested.emit("未生成有效操作")
            return {"status": "invalid", "ops": []}

        with self._lock:
            self._load_pending()
            pending_ops = self._pending.get("ops") if isinstance(self._pending.get("ops"), list) else []
            if pending_ops and self._ops_signature(pending_ops) == self._ops_signature(packed):
                return {
                    "status": "already_pending",
                    "ops": packed,
                    "confirm_text": str(self._pending.get("confirm_text", "") or "").strip() or confirm_text,
                }

            filtered = [op_obj for op_obj in packed if not self._op_already_applied(op_obj)]
            if not filtered:
                return {"status": "already_applied", "ops": []}

            self._save_pending(self._new_pending(reason=reason, confirm_text=confirm_text, ops=filtered, channel=channel))
            return {"status": "proposed", "ops": filtered, "confirm_text": confirm_text}

    def _apply_pending(self, *, channel: str, source: str) -> tuple[bool, str, list[str]]:
        with self._lock:
            self._load_pending()
            pending = self._pending if isinstance(self._pending, dict) else {}
            ops = pending.get("ops") if isinstance(pending.get("ops"), list) else []
            if not ops:
                return False, "当前没有待确认操作", []

            touched_months: set[str] = set()
            summaries: list[str] = []
            for op_obj in ops:
                if not isinstance(op_obj, dict):
                    continue
                month = str(op_obj.get("month", "") or "").strip()
                if not month:
                    payload = op_obj.get("payload") if isinstance(op_obj.get("payload"), dict) else {}
                    month = _month_of(str(payload.get("date", "") or _today()))
                month = month or _month_of(_today())
                month_obj = self._load_month_raw(month)
                self._apply_op(month_obj, op_obj, channel=channel, source=source)
                self._rebuild_derived(month_obj)
                self._save_month_raw(month, month_obj)
                touched_months.add(month)
                summaries.append(str(op_obj.get("op", "") or ""))

            self._clear_pending()
            self._ensure_month_for_selected()
            self._rebuild_month_data()
            return True, "已确认并写入日程", sorted(touched_months)

    def _cancel_pending(self) -> bool:
        with self._lock:
            self._load_pending()
            ops = self._pending.get("ops") if isinstance(self._pending.get("ops"), list) else []
            if not ops:
                return False
            self._clear_pending()
            return True

    # ---------- Properties ----------
    @Property("QVariantMap", notify=monthDataChanged)
    def monthData(self) -> dict:
        return dict(self._month_data)

    @Property(str, notify=monthDataChanged)
    def currentMonth(self) -> str:
        return self._current_month

    @Property(str, notify=monthDataChanged)
    def selectedDate(self) -> str:
        return self._selected_date

    @Property("QVariantMap", notify=pendingChanged)
    def pendingAction(self) -> dict:
        return dict(self._pending)

    # ---------- QML API ----------
    @Slot(str, str)
    def loadMonth(self, month: str, selectedDate: str) -> None:
        m = (month or "").strip()
        d = (selectedDate or "").strip()
        if not d:
            d = _today()
        if not m:
            m = _month_of(d) or _month_of(_today())
        if not d.startswith(m):
            d = f"{m}-01"
        self._current_month = m
        self._selected_date = d
        self._load_pending()
        self._rebuild_month_data()

    @Slot(str)
    def requestAddTodo(self, text: str) -> None:
        t = (text or "").strip()
        if not t:
            self.toastRequested.emit("待办内容不能为空")
            return
        self._propose_ops(
            reason="schedule_update",
            confirm_text=f"确认新增待办：{t}？",
            ops=[{"op": "add_todo", "month": self._current_month, "payload": {"text": t, "done": False}}],
            channel="desktop",
        )

    @Slot(str)
    def requestDeleteTodo(self, todoId: str) -> None:
        tid = (todoId or "").strip()
        if not tid:
            return
        self._propose_ops(
            reason="schedule_update",
            confirm_text="确认删除该待办？",
            ops=[{"op": "delete_todo", "month": self._current_month, "payload": {"id": tid}}],
            channel="desktop",
        )

    @Slot(str, str, bool)
    def requestUpdateTodo(self, todoId: str, text: str, done: bool) -> None:
        tid = (todoId or "").strip()
        new_text = (text or "").strip()
        if not tid:
            return
        if not new_text:
            self.toastRequested.emit("待办内容不能为空")
            return
        self._propose_ops(
            reason="schedule_update",
            confirm_text=f"确认更新待办：{new_text}？",
            ops=[{"op": "update_todo", "month": self._current_month, "payload": {"id": tid, "text": new_text, "done": bool(done)}}],
            channel="desktop",
        )

    @Slot(str)
    def requestToggleTodo(self, todoId: str) -> None:
        tid = (todoId or "").strip()
        if not tid:
            return
        self._propose_ops(
            reason="schedule_update",
            confirm_text="确认更新该待办状态？",
            ops=[{"op": "toggle_todo", "month": self._current_month, "payload": {"id": tid}}],
            channel="desktop",
        )

    @Slot("QVariantMap")
    def requestAddEvent(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            payload = {}
        date = str(payload.get("date", "") or self._selected_date or _today())
        title = str(payload.get("title", "") or "").strip()
        if not title:
            self.toastRequested.emit("日程标题不能为空")
            return
        p = {
            "date": date,
            "time": str(payload.get("time", "") or "待定"),
            "title": title,
            "duration": str(payload.get("duration", "") or "01:00"),
            "tags": list(payload.get("tags", []) if isinstance(payload.get("tags"), list) else []),
            "location": str(payload.get("location", "") or ""),
            "remind_before_min": _to_int(payload.get("remind_before_min", 0) or 0, 0),
        }
        self._propose_ops(
            reason="schedule_update",
            confirm_text=f"确认新增日程：{date} {p['time']} {title}？",
            ops=[{"op": "add_event", "month": _month_of(date), "payload": p}],
            channel="desktop",
        )

    @Slot(str)
    def requestDeleteEvent(self, eventId: str) -> None:
        eid = (eventId or "").strip()
        if not eid:
            return
        self._propose_ops(
            reason="schedule_update",
            confirm_text="确认删除该日程？",
            ops=[{"op": "delete_event", "month": self._current_month, "payload": {"id": eid}}],
            channel="desktop",
        )

    @Slot(str, "QVariantMap")
    def requestUpdateEvent(self, eventId: str, payload: dict) -> None:
        eid = (eventId or "").strip()
        if not eid:
            return
        if not isinstance(payload, dict):
            payload = {}
        title = str(payload.get("title", "") or "").strip()
        if not title:
            self.toastRequested.emit("日程标题不能为空")
            return
        date = str(payload.get("date", "") or self._selected_date or _today())
        p = {
            "id": eid,
            "date": date,
            "time": str(payload.get("time", "") or "待定"),
            "title": title,
            "duration": str(payload.get("duration", "") or "01:00"),
            "tags": list(payload.get("tags", []) if isinstance(payload.get("tags"), list) else []),
            "location": str(payload.get("location", "") or ""),
            "remind_before_min": _to_int(payload.get("remind_before_min", 0) or 0, 0),
        }
        self._propose_ops(
            reason="schedule_update",
            confirm_text=f"确认更新日程：{date} {p['time']} {title}？",
            ops=[{"op": "update_event", "month": _month_of(date), "payload": p}],
            channel="desktop",
        )

    @Slot()
    def confirmPending(self) -> None:
        ok, msg, touched = self._apply_pending(channel="desktop", source="manual")
        self.toastRequested.emit(msg)
        if ok:
            for m in touched:
                self.monthDataChanged.emit(m)

    @Slot()
    def cancelPending(self) -> None:
        ok = self._cancel_pending()
        self.toastRequested.emit("已取消待确认操作" if ok else "当前没有待确认操作")

    @Slot(bool)
    def ensureDailyMonthAchievements(self, kimi_connected: bool) -> None:
        _ = bool(kimi_connected)
        month = self._current_month or _month_of(_today())
        if month != _month_of(_today()):
            return
        with self._lock:
            month_obj = self._load_month_raw(month)
            derived = month_obj.get("derived") if isinstance(month_obj.get("derived"), dict) else {}
            last = str(derived.get("last_month_achievements_at", "") or "")
            if last.startswith(_today()):
                return
            derived["month_achievements"] = self._generate_month_achievements_local(month_obj, month)
            derived["last_month_achievements_at"] = _now_iso()
            month_obj["derived"] = derived
            self._save_month_raw(month, month_obj)
        self._rebuild_month_data()

    # ---------- Python API ----------
    def proposeFromChat(self, *, channel: str, confirm_text: str, ops: list[dict[str, Any]]) -> dict[str, Any]:
        return self._propose_ops(reason="schedule_update", confirm_text=confirm_text, ops=ops, channel=channel)

    def hasPending(self) -> bool:
        self._load_pending()
        return bool(self._pending.get("ops")) if isinstance(self._pending, dict) else False

    def pendingConfirmText(self) -> str:
        self._load_pending()
        if not isinstance(self._pending, dict):
            return ""
        return str(self._pending.get("confirm_text", "") or "").strip()

    def confirmPendingFromChannel(self, channel: str, source: str = "chat") -> tuple[bool, str]:
        ok, msg, _ = self._apply_pending(channel=channel, source=source)
        return ok, msg

    def cancelPendingFromChannel(self) -> tuple[bool, str]:
        ok = self._cancel_pending()
        return (ok, "已取消待确认操作" if ok else "当前没有待确认操作")

    def listTodayReminders(self) -> list[dict[str, Any]]:
        month = _month_of(_today())
        month_obj = self._load_month_raw(month)
        out: list[dict[str, Any]] = []
        default_min = self._default_remind_before_min()
        for e in month_obj.get("events", []):
            if not isinstance(e, dict):
                continue
            if str(e.get("date", "")) != _today():
                continue
            t = str(e.get("time", "") or "").strip()
            if not t or t == "待定":
                continue
            try:
                dt = datetime.strptime(f"{e.get('date')} {t}", "%Y-%m-%d %H:%M")
            except Exception:
                continue
            remind = int(e.get("remind_before_min", 0) or 0)
            if remind <= 0:
                remind = default_min
            out.append(
                {
                    "event_id": str(e.get("id", "") or ""),
                    "title": str(e.get("title", "") or ""),
                    "time": t,
                    "date": str(e.get("date", "")),
                    "tags": list(e.get("tags", []) if isinstance(e.get("tags"), list) else []),
                    "remind_before_min": remind,
                    "event_at_iso": dt.isoformat(timespec="seconds"),
                    "remind_at_iso": (dt - timedelta(minutes=remind)).isoformat(timespec="seconds"),
                }
            )
        return out

    def _default_remind_before_min(self) -> int:
        cfg = _read_json(self._data_dir() / "config.json", {})
        push = cfg.get("push") if isinstance(cfg, dict) and isinstance(cfg.get("push"), dict) else {}
        sr = push.get("schedule_reminder") if isinstance(push.get("schedule_reminder"), dict) else {}
        v = _to_int(sr.get("default_remind_before_min", 10) or 10, 10)
        return max(0, min(v, 24 * 60))
