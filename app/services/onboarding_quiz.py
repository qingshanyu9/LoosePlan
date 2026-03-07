# app/services/onboarding_quiz.py
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot, QTimer


@dataclass(frozen=True)
class _FlatQuestion:
    group_index: int
    group_id: str
    group_name: str
    set_id: str
    q_index_in_group: int
    qid: str
    qtype: str
    title: str
    options: list[dict[str, str]]


class OnboardingQuiz(QObject):
    """
    Quiz manager for onboarding step 5.

    改动重点：
    - 不再“每次点选都 saveDraft()”，改为 250ms 防抖落盘（大幅降低 UI 被 IO 卡住概率）
    - 提供 flushPending()，提交/跳转前强制落盘
    """

    stateChanged = Signal()

    def __init__(self, project_root: Path, draft: QObject, parent: QObject | None = None):
        super().__init__(parent)
        self._root = Path(project_root).resolve()
        self._draft = draft

        self._bank: dict[str, Any] = {}
        self._flat: list[_FlatQuestion] = []
        self._answers_by_qid: dict[str, list[str]] = {}

        # debounce save
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self._flush_save)

        self._dirty_answers = False
        self._dirty_index = False

    # ---------------- internal helpers ----------------
    def _load_bank(self) -> None:
        bank_path = self._root / "data" / "question_bank.json"
        if not bank_path.exists():
            bank_path = self._root / "question_bank.json"
        if not bank_path.exists():
            raise FileNotFoundError(f"question_bank.json not found: {bank_path}")
        self._bank = json.loads(bank_path.read_text(encoding="utf-8"))

    def _get_selected_sets(self) -> dict[str, str]:
        try:
            return dict(self._draft.getDraftQuizSelectedSets())
        except Exception:
            return {}

    def _persist_selected_sets(self, selected: dict[str, str]) -> None:
        for gid, sid in selected.items():
            self._draft.setDraftQuizSelectedSet(gid, sid)
        # 初始化阶段落一次即可
        self._draft.saveDraft()

    def _load_answers_from_draft(self) -> None:
        self._answers_by_qid = {}
        try:
            answers = self._draft.getDraftQuizAnswers()
        except Exception:
            answers = []
        if isinstance(answers, list):
            for a in answers:
                if not isinstance(a, dict):
                    continue
                qid = str(a.get("qid", "") or "")
                selected = a.get("selected", [])
                if qid:
                    if isinstance(selected, list):
                        self._answers_by_qid[qid] = [str(x) for x in selected if str(x)]
                    elif isinstance(selected, str):
                        self._answers_by_qid[qid] = [selected]

    def _build_answers_payload(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for fq in self._flat:
            sel = self._answers_by_qid.get(fq.qid)
            if not sel:
                continue
            out.append({
                "group_id": fq.group_id,
                "set_id": fq.set_id,
                "qid": fq.qid,
                "selected": list(sel),
            })
        return out

    def _schedule_save(self, *, answers: bool = False, index: bool = False) -> None:
        if answers:
            self._dirty_answers = True
        if index:
            self._dirty_index = True
        # 重新计时（防抖）
        self._save_timer.start()

    def _flush_save(self) -> None:
        """
        真正落盘：把内存态写回 draft，然后 saveDraft。
        """
        try:
            if self._dirty_answers:
                self._draft.setDraftQuizAnswers(self._build_answers_payload())
                self._dirty_answers = False
            if self._dirty_index:
                # currentIndex 已经 set 到 draft 里，这里只是统一 save
                self._dirty_index = False
            self._draft.saveDraft()
        except Exception:
            # 不要让异常把 UI 打断
            pass

    # ---------------- build flat questions ----------------
    def _build_flat_questions(self) -> None:
        groups = self._bank.get("groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError("question_bank.json: missing groups")

        selected_sets = self._get_selected_sets()

        # choose a set per group if missing
        for g in groups:
            if not isinstance(g, dict):
                continue
            gid = str(g.get("group_id", "") or "")
            if not gid:
                continue
            if gid in selected_sets and selected_sets[gid]:
                continue
            sets = g.get("sets")
            if not isinstance(sets, list) or not sets:
                continue
            pick = random.choice(sets)
            sid = str(pick.get("set_id", "") or "")
            if sid:
                selected_sets[gid] = sid

        self._persist_selected_sets(selected_sets)

        flat: list[_FlatQuestion] = []
        for gi, g in enumerate(groups):
            if not isinstance(g, dict):
                continue
            gid = str(g.get("group_id", "") or "")
            gname = str(g.get("group_name", "") or "")
            sets = g.get("sets")
            if not gid or not isinstance(sets, list):
                continue
            sid = str(selected_sets.get(gid, "") or "")
            target_set = None
            for s in sets:
                if isinstance(s, dict) and str(s.get("set_id", "") or "") == sid:
                    target_set = s
                    break
            if target_set is None and sets:
                target_set = sets[0]
                sid = str(target_set.get("set_id", "") or "")

            questions = (target_set or {}).get("questions")
            if not isinstance(questions, list):
                questions = []

            for qi, q in enumerate(questions):
                if not isinstance(q, dict):
                    continue
                qid = str(q.get("qid", "") or "")
                qtype = str(q.get("type", "single") or "single")
                title = str(q.get("title", "") or "")
                options = q.get("options")
                opt_list: list[dict[str, str]] = []
                if isinstance(options, list):
                    for o in options:
                        if not isinstance(o, dict):
                            continue
                        k = str(o.get("key", "") or "")
                        t = str(o.get("text", "") or "")
                        if k and t:
                            opt_list.append({"key": k, "text": t})
                flat.append(_FlatQuestion(
                    group_index=gi,
                    group_id=gid,
                    group_name=gname,
                    set_id=sid,
                    q_index_in_group=qi + 1,
                    qid=qid,
                    qtype=qtype,
                    title=title,
                    options=opt_list,
                ))

        self._flat = flat

    # ---------------- QML slots ----------------
    @Slot()
    def loadOrInit(self) -> None:
        self._draft.loadDraft()
        self._load_bank()
        self._load_answers_from_draft()
        self._build_flat_questions()
        self.stateChanged.emit()

    @Slot()
    def flushPending(self) -> None:
        """
        提交/跳转前调用，强制把防抖队列中的写入立刻落盘。
        """
        try:
            if self._save_timer.isActive():
                self._save_timer.stop()
            self._flush_save()
        except Exception:
            pass

    @Slot(result=int)
    def totalQuestions(self) -> int:
        return len(self._flat)

    @Slot(int, result="QVariantMap")
    def getQuestion(self, index: int) -> dict:
        if not self._flat:
            return {}
        idx = max(0, min(int(index), len(self._flat) - 1))
        fq = self._flat[idx]
        return {
            "group_index": fq.group_index,
            "group_id": fq.group_id,
            "group_name": fq.group_name,
            "set_id": fq.set_id,
            "q_index_in_group": fq.q_index_in_group,
            "qid": fq.qid,
            "type": fq.qtype,
            "title": fq.title,
            "options": list(fq.options),
            "selected": list(self._answers_by_qid.get(fq.qid, [])),
        }

    @Slot(int, result=bool)
    def isAnswered(self, index: int) -> bool:
        if not self._flat:
            return False
        idx = max(0, min(int(index), len(self._flat) - 1))
        qid = self._flat[idx].qid
        sel = self._answers_by_qid.get(qid, [])
        return bool(sel)

    @Slot(int, str)
    def toggleOption(self, index: int, key: str) -> None:
        if not self._flat:
            return
        idx = max(0, min(int(index), len(self._flat) - 1))
        fq = self._flat[idx]
        k = (key or "").strip()
        if not k:
            return

        cur = list(self._answers_by_qid.get(fq.qid, []))
        if fq.qtype == "multi":
            if k in cur:
                cur = [x for x in cur if x != k]
            else:
                cur.append(k)
        else:
            cur = [k]

        seen = set()
        cur2: list[str] = []
        for x in cur:
            if x and x not in seen:
                seen.add(x)
                cur2.append(x)

        self._answers_by_qid[fq.qid] = cur2

        # 防抖保存（不再立刻 saveDraft）
        self._schedule_save(answers=True)

        self.stateChanged.emit()

    @Slot(int, result=int)
    def groupIndexForQuestion(self, index: int) -> int:
        if not self._flat:
            return 0
        idx = max(0, min(int(index), len(self._flat) - 1))
        return int(self._flat[idx].group_index)

    @Slot(result=int)
    def getCurrentIndexOrZero(self) -> int:
        try:
            idx = int(self._draft.getDraftQuizCurrentIndex() or 0)
        except Exception:
            idx = 0
        if not self._flat:
            return 0
        return max(0, min(idx, len(self._flat) - 1))

    @Slot(int)
    def setCurrentIndex(self, idx: int) -> None:
        try:
            self._draft.setDraftQuizCurrentIndex(int(idx))
            self._schedule_save(index=True)
        except Exception:
            pass

    @Slot()
    def resetQuiz(self) -> None:
        try:
            self._draft.clearQuizAndProfile()
            self._draft.saveDraft()
        except Exception:
            pass
        self.loadOrInit()
        self.setCurrentIndex(0)

    @Slot(result="QVariantList")
    def exportAnswersForKimi(self) -> list:
        out: list[dict[str, Any]] = []
        for fq in self._flat:
            sel_keys = self._answers_by_qid.get(fq.qid, [])
            if not sel_keys:
                continue
            key2text = {o["key"]: o["text"] for o in fq.options}
            out.append({
                "group_id": fq.group_id,
                "group_name": fq.group_name,
                "set_id": fq.set_id,
                "qid": fq.qid,
                "title": fq.title,
                "selected": list(sel_keys),
                "selected_text": [key2text.get(k, "") for k in sel_keys],
            })
        return out