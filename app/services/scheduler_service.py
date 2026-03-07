from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .review_service import ReviewService
from .schedule_service import ScheduleService


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            obj = json.loads(path.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    return {}


@dataclass(frozen=True)
class ReminderKey:
    event_id: str
    remind_at_iso: str

    def as_string(self) -> str:
        return f"{self.event_id}@{self.remind_at_iso}"


class SchedulerService(QObject):
    desktopNotify = Signal(str)
    feishuNotify = Signal(str)
    toastRequested = Signal(str)

    def __init__(
        self,
        *,
        get_data_dir: Callable[[], Path],
        schedule_service: ScheduleService,
        review_service: ReviewService,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._get_data_dir = get_data_dir
        self._schedule = schedule_service
        self._review = review_service
        self._fired: set[str] = set()
        self._last_day: str = datetime.now().date().isoformat()
        self._timer = QTimer(self)
        self._timer.setInterval(30000)
        self._timer.timeout.connect(self._tick)

    @Slot()
    def start(self) -> None:
        if self._timer.isActive():
            return
        self._timer.start()
        self._tick()

    @Slot()
    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def _config(self) -> dict:
        return _read_json(self._get_data_dir().resolve() / "config.json")

    def _is_reminder_enabled(self) -> bool:
        cfg = self._config()
        push = cfg.get("push") if isinstance(cfg.get("push"), dict) else {}
        sr = push.get("schedule_reminder") if isinstance(push.get("schedule_reminder"), dict) else {}
        return bool(sr.get("enabled", True))

    def _tick(self) -> None:
        now = datetime.now()
        today = now.date().isoformat()
        if today != self._last_day:
            self._fired.clear()
            self._last_day = today

        try:
            self._review.maybePushScheduledReview()
        except Exception:
            pass

        if not self._is_reminder_enabled():
            return

        reminders = self._schedule.listTodayReminders()
        for r in reminders:
            event_id = str(r.get("event_id", "") or "").strip()
            remind_at_iso = str(r.get("remind_at_iso", "") or "").strip()
            event_at_iso = str(r.get("event_at_iso", "") or "").strip()
            if not event_id or not remind_at_iso or not event_at_iso:
                continue
            try:
                remind_at = datetime.fromisoformat(remind_at_iso)
                event_at = datetime.fromisoformat(event_at_iso)
            except Exception:
                continue
            if now < remind_at or now > event_at:
                continue

            rk = ReminderKey(event_id=event_id, remind_at_iso=remind_at_iso).as_string()
            if rk in self._fired:
                continue
            self._fired.add(rk)

            title = str(r.get("title", "") or "")
            t = str(r.get("time", "") or "")
            tags = r.get("tags") if isinstance(r.get("tags"), list) else []
            tag_text = f" [{', '.join([str(x) for x in tags if str(x).strip()])}]" if tags else ""
            msg = f"提醒：{title} {t}{tag_text}".strip()
            self.desktopNotify.emit(msg)
            self.feishuNotify.emit(msg)
