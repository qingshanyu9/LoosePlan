# app/services/onboarding_finalizer.py
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot, Property, QStandardPaths


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today_date() -> str:
    return datetime.now().date().isoformat()


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


_BRACKET_CHARS_RE = re.compile(r"[（）\(\)\[\]【】{}<>《》]")
_SPACES_RE = re.compile(r"\s+")


def _compact_text(s: str) -> str:
    s = _BRACKET_CHARS_RE.sub("", s or "")
    s = _SPACES_RE.sub("", s)
    return s.strip()


def _limit_chars(s: str, max_len: int) -> str:
    t = _compact_text(s)
    return t[:max_len] if max_len > 0 else ""


def _sanitize_mbti(s: str) -> str:
    t = (s or "").upper()
    m = re.search(r"\b([IE][NS][TF][JP])\b", t)
    if m:
        return m.group(1)
    return _compact_text(t)[:4]


def _default_memory_graph(personality: str, ts: str) -> dict[str, Any]:
    def empty():
        return {"content": "", "memory_time": "", "source": ""}

    return {
        "updated_at": ts,
        "sections": {
            "用户面板": {
                "基本信息": empty(),
                "性格特征": {
                    "content": personality,
                    "memory_time": ts if personality else "",
                    "source": "初始化设定" if personality else "",
                },
                "兴趣爱好": empty(),
                "健康与身体状态": empty(),
                "羁绊网络": empty(),
            },
            "日程看板": {
                "工作时间": empty(),
                "休息习惯": empty(),
                "限定活动": empty(),
                "餐饮与运动规律": empty(),
                "免打扰时段": empty(),
            },
            "行为图鉴": {
                "沟通习惯": empty(),
                "消费习惯": empty(),
                "使用习惯": empty(),
                "学习习惯": empty(),
                "出行习惯": empty(),
            },
            "特殊规则": {
                "隐私规则": empty(),
                "回复规则": empty(),
                "题型规划": empty(),
                "格式规则": empty(),
            },
        },
    }


class OnboardingFinalizer(QObject):
    busyChanged = Signal()
    lastErrorChanged = Signal()

    def __init__(self, project_root: Path, draft: QObject, parent: QObject | None = None):
        super().__init__(parent)
        self._root = Path(project_root).resolve()
        self._draft = draft
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

    def _cleanup_onboarding_tmp(self) -> None:
        """完成后清理向导临时文件，避免下次启动误判仍在 onboarding。"""
        try:
            tmp_dir = self._root / ".tmp"
            state = tmp_dir / "onboarding_state.json"
            if state.exists():
                state.unlink()
            # 如果 .tmp 空了就删
            if tmp_dir.exists():
                try:
                    next(tmp_dir.iterdir())
                except StopIteration:
                    tmp_dir.rmdir()
        except Exception:
            pass

    def _persist_runtime_last_data_dir(self, data_dir: Path) -> None:
        """将 data_dir 持久化到 AppDataLocation/runtime.json，供下次启动/托盘判定使用。"""
        try:
            loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
            if not loc:
                return
            runtime_file = (Path(loc).resolve() / "runtime.json")
            obj: dict[str, Any] = {}
            try:
                if runtime_file.exists():
                    obj = json.loads(runtime_file.read_text(encoding="utf-8"))
            except Exception:
                obj = {}

            obj["last_data_dir"] = str(data_dir.expanduser().resolve())

            runtime_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = runtime_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(runtime_file)
        except Exception:
            pass

    @Slot(result=bool)
    def finalizeFromDraft(self) -> bool:
        if self._busy:
            return False

        self._set_last_error("")
        self._set_busy(True)
        try:
            try:
                self._draft.loadDraft()
            except Exception:
                pass

            data_dir = Path(str(getattr(self._draft, "getDraftDataDir")() or "")).expanduser().resolve()
            if not str(data_dir):
                self._set_last_error("数据目录为空")
                return False
            data_dir.mkdir(parents=True, exist_ok=True)

            for rel in ["chat", "schedule", "pending", "reviews/weekly", "notifications"]:
                (data_dir / rel).mkdir(parents=True, exist_ok=True)

            ts = _now_iso()
            today = _today_date()

            config = {
                "data_dir": str(data_dir),
                "user_display_name": str(getattr(self._draft, "getDraftUserDisplayName")() or ""),
                "assistant_name": str(getattr(self._draft, "getDraftAssistantName")() or ""),
                "kimi": {
                    "api_key": str(getattr(self._draft, "getDraftKimiApiKey")() or ""),
                    "base_url": str(getattr(self._draft, "getDraftKimiBaseUrl")() or ""),
                    "model": str(getattr(self._draft, "getDraftKimiModel")() or ""),
                },
                "feishu": {
                    "enabled": bool(getattr(self._draft, "getDraftFeishuEnabled")()),
                    "app_id": str(getattr(self._draft, "getDraftFeishuAppId")() or ""),
                    "app_secret": str(getattr(self._draft, "getDraftFeishuAppSecret")() or ""),
                    "bound_receive_id": str(getattr(self._draft, "getDraftFeishuBoundReceiveId")() or ""),
                    "bound_receive_type": str(getattr(self._draft, "getDraftFeishuBoundReceiveType")() or "chat_id"),
                    "last_connected_at": str(getattr(self._draft, "getDraftFeishuLastConnectedAt")() or ""),
                },
                "push": {
                    "weekly_review": {"enabled": True, "weekday": 0, "sync_feishu": True},
                    "schedule_reminder": {"enabled": True, "default_remind_before_min": 15},
                },
                "runtime": {
                    "last_daily_refresh_date": today,
                    "last_weekly_review_key": "",
                },
            }
            _atomic_write_json(data_dir / "config.json", config)

            # ✅ 关键：写入 runtime.json 的 last_data_dir，确保重启后可正确识别已完成初始化
            self._persist_runtime_last_data_dir(data_dir)

            try:
                answers = list(getattr(self._draft, "getDraftQuizAnswers")() or [])
            except Exception:
                answers = []

            profile_answers = {
                "generated_at": ts,
                "naming": {
                    "user_calling": config["user_display_name"],
                    "assistant_name": config["assistant_name"],
                },
                "answers": answers,
            }
            _atomic_write_json(data_dir / "profile_answers.json", profile_answers)

            try:
                pr = dict(getattr(self._draft, "getDraftProfileResult")() or {})
            except Exception:
                pr = {}

            profile = pr.get("profile") if isinstance(pr.get("profile"), dict) else {}
            labels = profile.get("labels") if isinstance(profile.get("labels"), dict) else {}

            profile_out = {
                "generated_at": ts,
                "labels": {
                    "mbti": _sanitize_mbti(str(labels.get("mbti", "") or "")),
                    "time_personality": _limit_chars(str(labels.get("time_personality", "") or ""), 5),
                    "industry": _limit_chars(str(labels.get("industry", "") or ""), 5),
                    "schedule_style": _limit_chars(str(labels.get("schedule_style", "") or ""), 5),
                    "strength": _limit_chars(str(labels.get("strength", "") or ""), 5),
                    "rhythm": _limit_chars(str(labels.get("rhythm", "") or ""), 5),
                    "energy_peak": _limit_chars(str(labels.get("energy_peak", "") or ""), 5),
                    "task_preference": _limit_chars(str(labels.get("task_preference", "") or ""), 5),
                },
                "summary": str(profile.get("summary", "") or "").strip() or "已生成你的工作画像。",
            }
            _atomic_write_json(data_dir / "profile.json", profile_out)

            personality = ""
            mg = pr.get("memory_graph_init") if isinstance(pr.get("memory_graph_init"), dict) else {}
            content = mg.get("content")
            if isinstance(content, str):
                personality = content.strip()
            _atomic_write_json(data_dir / "memory_graph.json", _default_memory_graph(personality, ts))

            qb_dst = data_dir / "question_bank.json"
            if not qb_dst.exists():
                qb_src = self._root / "data" / "question_bank.json"
                if not qb_src.exists():
                    qb_src = self._root / "question_bank.json"
                if qb_src.exists():
                    qb_dst.write_text(qb_src.read_text(encoding="utf-8"), encoding="utf-8")

            pa = data_dir / "pending" / "pending_action.json"
            if not pa.exists():
                _atomic_write_json(pa, {})

            month_key = datetime.now().strftime("%Y-%m")
            sched = data_dir / "schedule" / f"{month_key}.json"
            if not sched.exists():
                _atomic_write_json(
                    sched,
                    {
                        "month": month_key,
                        "events": [],
                        "todos": [],
                        "derived": {
                            "last_derived_at": "",
                            "today_date": today,
                            "today_plan_lines": [],
                            "month_achievements": "",
                            "last_month_achievements_at": "",
                        },
                        "change_log": [],
                    },
                )

            # ✅ 新增：完成后清理 onboarding 临时文件
            self._cleanup_onboarding_tmp()

            return True
        except Exception as ex:
            self._set_last_error(f"保存失败：{ex}")
            return False
        finally:
            self._set_busy(False)
