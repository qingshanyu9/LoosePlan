# app/core/onboarding_draft.py
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Slot

from app.core.app_paths import default_user_data_dir


@dataclass
class DraftState:
    """Onboarding draft state stored in .tmp/onboarding_state.json.

    v4 rule: during onboarding only write temporary state; user clicks "完成" on profile result
    page then write final files.
    """

    step: int = 1
    data_dir: str = ""  # local path (not file:// URL)

    # Step 2: Kimi
    kimi_api_key: str = ""
    kimi_base_url: str = ""
    kimi_model: str = ""

    # Step 3: Feishu
    feishu_enabled: bool = True
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bound_receive_type: str = "open_id"
    feishu_bound_receive_id: str = ""     # sender open_id after first p2p message
    feishu_last_connected_at: str = ""    # iso time (best-effort)

    # Step 4: Naming
    assistant_name: str = ""       # bot name shown to user
    user_display_name: str = ""    # how assistant calls the user

    # Step 5: Quiz (temp)
    quiz_selected_sets: dict[str, str] = field(default_factory=dict)  # group_id -> set_id
    quiz_answers: list[dict[str, Any]] = field(default_factory=list)  # [{group_id,set_id,qid,selected:["A"]}]
    quiz_current_index: int = 0

    # Kimi output cached in draft (temp)
    profile_result: dict[str, Any] = field(default_factory=dict)
    profile_generated_at: str = ""  # iso

    updated_at: str = ""  # ISO time


class OnboardingDraft(QObject):
    """Write/read .tmp/onboarding_state.json."""

    def __init__(self, project_root: Path):
        super().__init__()
        self._root = Path(project_root).resolve()
        self._tmp_dir = self._root / ".tmp"
        self._state_file = self._tmp_dir / "onboarding_state.json"
        self._state = DraftState()

    def _now_iso(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _atomic_write_json(self, path: Path, obj: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    # -------- API exposed to QML --------
    @Slot()
    def loadDraft(self) -> None:
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text(encoding="utf-8"))

                self._state.step = int(data.get("step", 1))
                self._state.data_dir = str(data.get("data_dir", "") or "")

                self._state.kimi_api_key = str(data.get("kimi_api_key", "") or "")
                self._state.kimi_base_url = str(data.get("kimi_base_url", "") or "")
                self._state.kimi_model = str(data.get("kimi_model", "") or "")

                self._state.feishu_enabled = bool(data.get("feishu_enabled", True))
                self._state.feishu_app_id = str(data.get("feishu_app_id", "") or "")
                self._state.feishu_app_secret = str(data.get("feishu_app_secret", "") or "")
                self._state.feishu_bound_receive_type = str(
                    data.get("feishu_bound_receive_type", "open_id") or "open_id"
                )
                self._state.feishu_bound_receive_id = str(data.get("feishu_bound_receive_id", "") or "")
                self._state.feishu_last_connected_at = str(data.get("feishu_last_connected_at", "") or "")

                self._state.assistant_name = str(data.get("assistant_name", "") or "")
                self._state.user_display_name = str(data.get("user_display_name", "") or "")

                # quiz + profile cache
                qss = data.get("quiz_selected_sets", {})
                self._state.quiz_selected_sets = dict(qss) if isinstance(qss, dict) else {}

                qa = data.get("quiz_answers", [])
                self._state.quiz_answers = list(qa) if isinstance(qa, list) else []

                try:
                    self._state.quiz_current_index = int(data.get("quiz_current_index", 0) or 0)
                except Exception:
                    self._state.quiz_current_index = 0

                pr = data.get("profile_result", {})
                self._state.profile_result = dict(pr) if isinstance(pr, dict) else {}
                self._state.profile_generated_at = str(data.get("profile_generated_at", "") or "")

                self._state.updated_at = str(data.get("updated_at", "") or "")
        except Exception:
            self._state = DraftState()

    @Slot()
    def saveDraft(self) -> None:
        self._state.updated_at = self._now_iso()
        self._atomic_write_json(self._state_file, asdict(self._state))

    @Slot()
    def clearDraft(self) -> None:
        try:
            if self._state_file.exists():
                self._state_file.unlink()
            if self._tmp_dir.exists():
                try:
                    next(self._tmp_dir.iterdir())
                except StopIteration:
                    self._tmp_dir.rmdir()
        finally:
            self._state = DraftState()

    # -------- Step 1 --------
    @Slot(str)
    def setDraftDataDir(self, path: str) -> None:
        self._state.data_dir = (path or "").strip()

    @Slot(result=str)
    def getDraftDataDir(self) -> str:
        return self._state.data_dir

    @Slot(result=str)
    def getSuggestedDefaultDataDir(self) -> str:
        return str(default_user_data_dir(self._root))

    # -------- Step 2: Kimi --------
    @Slot(str)
    def setDraftKimiApiKey(self, key: str) -> None:
        self._state.kimi_api_key = (key or "").strip()

    @Slot(result=str)
    def getDraftKimiApiKey(self) -> str:
        return self._state.kimi_api_key

    @Slot(str)
    def setDraftKimiBaseUrl(self, url: str) -> None:
        self._state.kimi_base_url = (url or "").strip()

    @Slot(result=str)
    def getDraftKimiBaseUrl(self) -> str:
        return self._state.kimi_base_url

    @Slot(str)
    def setDraftKimiModel(self, model: str) -> None:
        self._state.kimi_model = (model or "").strip()

    @Slot(result=str)
    def getDraftKimiModel(self) -> str:
        return self._state.kimi_model

    @Slot(result=str)
    def getSuggestedDefaultKimiBaseUrl(self) -> str:
        return "https://api.moonshot.cn/v1"

    @Slot(result=str)
    def getSuggestedDefaultKimiModel(self) -> str:
        return "kimi-k2-thinking-turbo"

    # -------- Step 3: Feishu --------
    @Slot(bool)
    def setDraftFeishuEnabled(self, enabled: bool) -> None:
        self._state.feishu_enabled = bool(enabled)

    @Slot(result=bool)
    def getDraftFeishuEnabled(self) -> bool:
        return bool(self._state.feishu_enabled)

    @Slot(str)
    def setDraftFeishuAppId(self, app_id: str) -> None:
        self._state.feishu_app_id = (app_id or "").strip()

    @Slot(result=str)
    def getDraftFeishuAppId(self) -> str:
        return self._state.feishu_app_id

    @Slot(str)
    def setDraftFeishuAppSecret(self, app_secret: str) -> None:
        self._state.feishu_app_secret = (app_secret or "").strip()

    @Slot(result=str)
    def getDraftFeishuAppSecret(self) -> str:
        return self._state.feishu_app_secret

    @Slot(str)
    def setDraftFeishuBoundReceiveId(self, receive_id: str) -> None:
        self._state.feishu_bound_receive_id = (receive_id or "").strip()

    @Slot(result=str)
    def getDraftFeishuBoundReceiveId(self) -> str:
        return self._state.feishu_bound_receive_id

    @Slot(str)
    def setDraftFeishuBoundReceiveType(self, receive_type: str) -> None:
        t = (receive_type or "").strip()
        self._state.feishu_bound_receive_type = t or "open_id"

    @Slot(result=str)
    def getDraftFeishuBoundReceiveType(self) -> str:
        return self._state.feishu_bound_receive_type or "open_id"

    @Slot(str)
    def setDraftFeishuLastConnectedAt(self, iso_time: str) -> None:
        self._state.feishu_last_connected_at = (iso_time or "").strip()

    @Slot(result=str)
    def getDraftFeishuLastConnectedAt(self) -> str:
        return self._state.feishu_last_connected_at

    # -------- Step 4: Naming --------
    @Slot(str)
    def setDraftAssistantName(self, name: str) -> None:
        self._state.assistant_name = (name or "").strip()

    @Slot(result=str)
    def getDraftAssistantName(self) -> str:
        return self._state.assistant_name

    @Slot(str)
    def setDraftUserDisplayName(self, name: str) -> None:
        self._state.user_display_name = (name or "").strip()

    @Slot(result=str)
    def getDraftUserDisplayName(self) -> str:
        return self._state.user_display_name

    # -------- Step 5: Quiz draft (used by onboardingQuiz) --------
    @Slot(result="QVariantMap")
    def getDraftQuizSelectedSets(self) -> dict:
        return dict(self._state.quiz_selected_sets or {})

    @Slot(str, str)
    def setDraftQuizSelectedSet(self, group_id: str, set_id: str) -> None:
        gid = (group_id or "").strip()
        sid = (set_id or "").strip()
        if not gid:
            return
        self._state.quiz_selected_sets[gid] = sid

    @Slot(result="QVariantList")
    def getDraftQuizAnswers(self) -> list:
        return list(self._state.quiz_answers or [])

    @Slot("QVariantList")
    def setDraftQuizAnswers(self, answers: list) -> None:
        self._state.quiz_answers = list(answers or [])

    @Slot(int)
    def setDraftQuizCurrentIndex(self, idx: int) -> None:
        try:
            self._state.quiz_current_index = max(0, int(idx))
        except Exception:
            self._state.quiz_current_index = 0

    @Slot(result=int)
    def getDraftQuizCurrentIndex(self) -> int:
        return int(self._state.quiz_current_index or 0)

    @Slot(result="QVariantMap")
    def getDraftProfileResult(self) -> dict:
        return dict(self._state.profile_result or {})

    @Slot("QVariantMap")
    def setDraftProfileResult(self, result_obj: dict) -> None:
        self._state.profile_result = dict(result_obj or {})
        self._state.profile_generated_at = self._now_iso()

    @Slot()
    def clearQuizAndProfile(self) -> None:
        self._state.quiz_selected_sets = {}
        self._state.quiz_answers = []
        self._state.quiz_current_index = 0
        self._state.profile_result = {}
        self._state.profile_generated_at = ""

    @Slot(result=str)
    def getDraftProfileGeneratedAt(self) -> str:
        return self._state.profile_generated_at

    # -------- Step tracking --------
    @Slot(int)
    def setDraftStep(self, step: int) -> None:
        try:
            self._state.step = int(step)
        except Exception:
            self._state.step = 1

    @Slot(result=int)
    def getDraftStep(self) -> int:
        return int(self._state.step)
