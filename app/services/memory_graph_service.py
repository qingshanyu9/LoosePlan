from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

from PySide6.QtCore import QObject, Property, Signal, Slot


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


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


def _normalize_base_url(value: str) -> str:
    text = (value or "").strip()
    while text.endswith("/"):
        text = text[:-1]
    return text


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _single_line(value: Any) -> str:
    return " ".join(_clean_text(value).split())


def _human_time(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return raw


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
        obj = json.loads(raw[start : end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


SOURCE_LABELS = {
    "初始化设定": {"label": "初始化设定", "style": "init"},
    "用户主动告知": {"label": "用户主动告知", "style": "user"},
    "聊天行为分析": {"label": "聊天行为分析", "style": "chat"},
    "用户聊天提及": {"label": "用户聊天提及", "style": "mention"},
    "用户设置": {"label": "用户设置", "style": "setting"},
}

GRAPH_SPEC: list[dict[str, Any]] = [
    {
        "title": "用户面板",
        "icon": "user",
        "items": [
            {"title": "基本信息", "icon": "user", "placeholder": "姓名、年龄、职业、联系方式等基础身份信息..."},
            {"title": "性格特征", "icon": "heart", "placeholder": "外向/内向、决策风格、沟通偏好、情绪模式等..."},
            {"title": "兴趣爱好", "icon": "star", "placeholder": "喜欢的书籍、电影、音乐、运动、游戏等..."},
            {"title": "健康与身体状态", "icon": "health", "placeholder": "过敏史、慢性不适、作息问题、健身目标等..."},
            {"title": "羁绊网络", "icon": "network", "placeholder": "重要社会关系、沟通称呼与互动偏好..."},
        ],
    },
    {
        "title": "日程看板",
        "icon": "calendar",
        "items": [
            {"title": "工作时间", "icon": "clock", "placeholder": "规律性工作时段、固定会议与高频工作窗口..."},
            {"title": "休息习惯", "icon": "moon", "placeholder": "睡/起时间、周末状态、睡前活动等..."},
            {"title": "限定活动", "icon": "calendar", "placeholder": "周期性安排、纪念日、固定节点等..."},
            {"title": "餐饮与运动规律", "icon": "food", "placeholder": "早餐、下午茶、运动频率与时间点等..."},
            {"title": "免打扰时段", "icon": "silent", "placeholder": "明确不希望被打扰的时间段与规则..."},
        ],
    },
    {
        "title": "行为图鉴",
        "icon": "layers",
        "items": [
            {"title": "沟通习惯", "icon": "message", "placeholder": "偏好回复长度、确认要求、典型回复延迟等..."},
            {"title": "消费习惯", "icon": "shopping", "placeholder": "消费档次、平台偏好、性价比敏感度等..."},
            {"title": "使用习惯", "icon": "device", "placeholder": "使用助手/软件/设备切换与输入偏好..."},
            {"title": "学习习惯", "icon": "book", "placeholder": "学习媒介偏好、碎片/深度模式、常看内容源等..."},
            {"title": "出行习惯", "icon": "travel", "placeholder": "通勤方式、差旅偏好、订票住宿习惯等..."},
        ],
    },
    {
        "title": "特殊规则",
        "icon": "shield",
        "items": [
            {"title": "隐私规则", "icon": "lock", "placeholder": "不可记录/不可同步/敏感内容处理规则..."},
            {"title": "回复规则", "icon": "reply", "placeholder": "对语气、角色和回复结构的明确要求..."},
            {"title": "题型规划", "icon": "list", "placeholder": "提醒逻辑、优先级、紧急通道和周末规则等..."},
            {"title": "格式规则", "icon": "format", "placeholder": "日期格式、表格/分点、强调方式等输出规范..."},
        ],
    },
]

ITEM_META: dict[tuple[str, str], dict[str, str]] = {}
for _section in GRAPH_SPEC:
    for _item in _section["items"]:
        ITEM_META[(_section["title"], _item["title"])] = {"icon": _item["icon"], "placeholder": _item["placeholder"]}


RULES: dict[tuple[str, str], dict[str, Any]] = {
    ("用户面板", "基本信息"): {"keywords": ["我叫", "我是", "昵称", "姓名", "职业", "行业", "城市", "住在", "来自", "电话", "邮箱", "联系方式", "岁"], "source": "用户主动告知"},
    ("用户面板", "性格特征"): {"keywords": [], "source": "聊天行为分析"},
    ("用户面板", "兴趣爱好"): {"keywords": ["喜欢", "爱好", "书", "电影", "音乐", "运动", "游戏", "旅行", "摄影", "动漫", "咖啡", "美食"], "source": "用户聊天提及"},
    ("用户面板", "健康与身体状态"): {"keywords": ["过敏", "失眠", "疲惫", "感冒", "头疼", "身体", "健身", "减脂", "减肥", "睡眠", "作息", "不舒服"], "source": "用户主动告知"},
    ("用户面板", "羁绊网络"): {"keywords": ["妈妈", "爸爸", "家人", "朋友", "同事", "老板", "老师", "客户", "伴侣", "孩子", "男朋友", "女朋友"], "source": "用户聊天提及"},
    ("日程看板", "工作时间"): {"keywords": ["上班", "工作时间", "开会", "会议", "周一", "周二", "周三", "周四", "周五", "上午", "下午", "晚上"], "source": "用户聊天提及"},
    ("日程看板", "休息习惯"): {"keywords": ["睡觉", "起床", "午休", "周末", "休息", "熬夜", "睡眠"], "source": "用户聊天提及"},
    ("日程看板", "限定活动"): {"keywords": ["每周", "每月", "月底", "发薪", "纪念日", "固定", "周末", "例会"], "source": "用户聊天提及"},
    ("日程看板", "餐饮与运动规律"): {"keywords": ["早餐", "午餐", "晚餐", "咖啡", "奶茶", "跑步", "健身", "瑜伽", "游泳", "散步", "锻炼"], "source": "用户聊天提及"},
    ("日程看板", "免打扰时段"): {"keywords": ["别打扰", "免打扰", "不要提醒", "睡觉时", "开会时", "深夜", "晚上不要"], "source": "用户主动告知"},
    ("行为图鉴", "沟通习惯"): {"keywords": ["确认", "回复", "简短", "详细", "直接", "分点", "说重点", "别废话", "语气"], "source": "聊天行为分析"},
    ("行为图鉴", "消费习惯"): {"keywords": ["买", "购买", "下单", "预算", "价格", "性价比", "优惠", "淘宝", "京东", "订阅", "会员"], "source": "聊天行为分析"},
    ("行为图鉴", "使用习惯"): {"keywords": ["iPhone", "Windows", "Mac", "飞书", "微信", "Notion", "桌面", "手机", "电脑", "App", "软件"], "source": "聊天行为分析"},
    ("行为图鉴", "学习习惯"): {"keywords": ["学习", "看书", "阅读", "课程", "教程", "播客", "笔记", "研究", "复盘", "资料"], "source": "用户聊天提及"},
    ("行为图鉴", "出行习惯"): {"keywords": ["地铁", "打车", "高铁", "飞机", "自驾", "通勤", "出差", "酒店", "火车", "订票"], "source": "用户聊天提及"},
    ("特殊规则", "隐私规则"): {"keywords": ["不要记录", "别记", "不要同步", "隐私", "保密", "敏感", "不要保存"], "source": "用户设置"},
    ("特殊规则", "回复规则"): {"keywords": ["回复时", "请用", "不要", "直接给", "分点", "简短", "中文", "语气", "只要结论"], "source": "用户设置"},
    ("特殊规则", "题型规划"): {"keywords": ["提醒", "提前", "紧急", "优先级", "工作日", "周末", "通知", "截止", "通道"], "source": "用户设置"},
    ("特殊规则", "格式规则"): {"keywords": ["格式", "日期", "表格", "分点", "标题", "markdown", "不要 emoji", "1. 2. 3.", "列表"], "source": "用户设置"},
}


class MemoryGraphService(QObject):
    categoriesChanged = Signal()
    currentCategoryChanged = Signal()
    currentCardsChanged = Signal()
    loadingChanged = Signal()
    toastRequested = Signal(str)
    _workerFinished = Signal(object)

    def __init__(self, *, get_data_dir: Callable[[], Path], parent: QObject | None = None):
        super().__init__(parent)
        self._get_data_dir = get_data_dir
        self._lock = threading.Lock()
        self._graph: dict[str, Any] = {}
        self._categories = [{"key": section["title"], "title": section["title"], "icon": section["icon"]} for section in GRAPH_SPEC]
        self._current_category = GRAPH_SPEC[0]["title"]
        self._current_cards: list[dict[str, Any]] = []
        self._loading = False
        self._workerFinished.connect(self._on_worker_finished)
        self.reload()

    def _data_dir(self) -> Path:
        return self._get_data_dir().resolve()

    def _graph_path(self) -> Path:
        return self._data_dir() / "memory_graph.json"

    def _backup_dir(self) -> Path:
        path = self._data_dir() / "memory_graph_backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _config(self) -> dict[str, Any]:
        return _read_json(self._data_dir() / "config.json", {})

    def _set_loading(self, value: bool) -> None:
        v = bool(value)
        if self._loading != v:
            self._loading = v
            self.loadingChanged.emit()

    def _empty_item(self) -> dict[str, str]:
        return {"content": "", "memory_time": "", "source": ""}

    def _default_graph(self) -> dict[str, Any]:
        sections: dict[str, dict[str, dict[str, str]]] = {}
        for section in GRAPH_SPEC:
            sections[section["title"]] = {item["title"]: self._empty_item() for item in section["items"]}
        return {"updated_at": _now_iso(), "sections": sections}

    def _normalize_graph(self, raw: Any) -> dict[str, Any]:
        obj = raw if isinstance(raw, dict) else {}
        sections_raw = obj.get("sections") if isinstance(obj.get("sections"), dict) else {}
        out = {"updated_at": str(obj.get("updated_at", "") or "").strip() or _now_iso(), "sections": {}}
        for section in GRAPH_SPEC:
            sec_in = sections_raw.get(section["title"]) if isinstance(sections_raw.get(section["title"]), dict) else {}
            sec_out: dict[str, dict[str, str]] = {}
            for item in section["items"]:
                item_in = sec_in.get(item["title"]) if isinstance(sec_in.get(item["title"]), dict) else {}
                content = _clean_text(item_in.get("content", ""))
                source = str(item_in.get("source", "") or "").strip()
                if source not in SOURCE_LABELS:
                    source = ""
                memory_time = str(item_in.get("memory_time", "") or "").strip() if content else ""
                sec_out[item["title"]] = {"content": content, "memory_time": memory_time, "source": source if content else ""}
            out["sections"][section["title"]] = sec_out
        return out

    def _ensure_graph(self) -> dict[str, Any]:
        path = self._graph_path()
        obj = self._normalize_graph(_read_json(path, {}))
        if not path.exists():
            _atomic_write_json(path, obj)
        return obj

    def _build_cards_for_category(self, category: str) -> list[dict[str, Any]]:
        sections = self._graph.get("sections") if isinstance(self._graph.get("sections"), dict) else {}
        section_data = sections.get(category) if isinstance(sections.get(category), dict) else {}
        cards: list[dict[str, Any]] = []
        for item in next((x["items"] for x in GRAPH_SPEC if x["title"] == category), []):
            raw = section_data.get(item["title"]) if isinstance(section_data.get(item["title"]), dict) else {}
            source = str(raw.get("source", "") or "").strip()
            meta = SOURCE_LABELS.get(source, {"label": "", "style": ""})
            cards.append({
                "section": category,
                "title": item["title"],
                "icon": item["icon"],
                "placeholder": item["placeholder"],
                "content": str(raw.get("content", "") or ""),
                "memory_time": str(raw.get("memory_time", "") or ""),
                "memory_time_text": _human_time(str(raw.get("memory_time", "") or "")),
                "source": source,
                "source_label": meta["label"],
                "source_style": meta["style"],
            })
        return cards

    def _refresh_cards(self) -> None:
        self._current_cards = self._build_cards_for_category(self._current_category)
        self.currentCardsChanged.emit()

    def _save_graph(self, graph: dict[str, Any]) -> None:
        self._graph = self._normalize_graph(graph)
        _atomic_write_json(self._graph_path(), self._graph)

    def _backup_graph(self, graph: dict[str, Any]) -> Path:
        path = self._backup_dir() / f"memory_graph_{_now().strftime('%Y%m%d_%H%M%S')}.json"
        _atomic_write_json(path, graph)
        return path

    def _is_meaningful_user_dialogue(self, text: str) -> bool:
        raw = _single_line(text)
        if len(raw) < 2:
            return False
        command_like = {
            "确认", "确定", "取消", "日程", "待办", "打开", "关闭", "导出", "分享",
            "记忆图谱", "每周回顾", "设置", "ok", "okay", "好的", "收到", "hello",
        }
        if raw in command_like or raw.lower() in command_like:
            return False
        if raw.startswith("/") or raw.startswith("add_") or raw.startswith("delete_") or raw.startswith("update_"):
            return False
        return not raw.isdigit()

    def _recent_user_dialogues(self, limit: int = 200) -> list[dict[str, str]]:
        chat_dir = self._data_dir() / "chat"
        if not chat_dir.exists():
            return []
        out: list[dict[str, str]] = []
        for path in sorted(chat_dir.glob("*.jsonl"), reverse=True):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
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
                if not isinstance(obj, dict) or str(obj.get("role", "") or "").strip() != "user":
                    continue
                text = _clean_text(obj.get("text", ""))
                if not self._is_meaningful_user_dialogue(text):
                    continue
                out.append({"ts": str(obj.get("ts", "") or ""), "channel": str(obj.get("channel", "") or ""), "text": text})
                if len(out) >= limit:
                    out.reverse()
                    return out
        out.reverse()
        return out

    def _dialogue_matches(self, dialogues: list[dict[str, str]], keywords: list[str], limit: int = 3) -> list[dict[str, str]]:
        if not keywords:
            return []
        found: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in reversed(dialogues):
            text = _single_line(item.get("text", ""))
            if not text:
                continue
            low = text.lower()
            if not any(keyword.lower() in low for keyword in keywords):
                continue
            if text in seen:
                continue
            seen.add(text)
            found.append(item)
            if len(found) >= limit:
                break
        found.reverse()
        return found

    def _shorten(self, text: str, limit: int = 40) -> str:
        clean = _single_line(text)
        if len(clean) <= limit:
            return clean
        return clean[: limit - 1].rstrip("，。；,;:： ") + "…"

    def _summarize_matches(self, matches: list[dict[str, str]]) -> tuple[str, str]:
        snippets: list[str] = []
        latest_ts = ""
        for item in matches[:2]:
            text = self._shorten(item.get("text", ""))
            if text:
                snippets.append(text)
            latest_ts = str(item.get("ts", "") or latest_ts)
        return "；".join(snippets), latest_ts

    def _infer_personality(self, dialogues: list[dict[str, str]], current: dict[str, str]) -> dict[str, str]:
        if not dialogues:
            return current
        texts = [_single_line(x.get("text", "")) for x in dialogues]
        planning_hits = sum(1 for text in texts if any(k in text for k in ["计划", "安排", "提醒", "确认", "完成", "进度"]))
        tech_hits = sum(1 for text in texts if any(k.lower() in text.lower() for k in ["qml", "python", "接口", "功能", "页面", "逻辑"]))
        detail_hits = sum(1 for text in texts if len(text) >= 18)
        tags: list[str] = []
        if planning_hits >= 2:
            tags.append("偏向结构化规划，重视执行闭环")
        if tech_hits >= 2:
            tags.append("讨论任务时目标明确，偏好直接落地")
        if detail_hits >= 3:
            tags.append("描述需求时信息密度较高，倾向细节澄清")
        if not tags:
            return current
        return {"content": "；".join(tags[:2]), "memory_time": str(dialogues[-1].get("ts", "") or _now_iso()), "source": "聊天行为分析"}

    def _infer_communication(self, dialogues: list[dict[str, str]], current: dict[str, str]) -> dict[str, str]:
        if not dialogues:
            return current
        texts = [_single_line(x.get("text", "")) for x in dialogues]
        avg_len = sum(len(x) for x in texts) / max(1, len(texts))
        tags: list[str] = []
        if any("确认" in x or "确定" in x for x in texts):
            tags.append("倾向明确确认后再执行")
        tags.append("常用短句直接下达需求" if avg_len < 12 else "说明问题时会补充足够上下文")
        if any(any(k in x for k in ["分点", "格式", "一样", "按照"]) for x in texts):
            tags.append("对结构和呈现方式有明确要求")
        return {"content": "；".join(tags[:2]), "memory_time": str(dialogues[-1].get("ts", "") or _now_iso()), "source": "聊天行为分析"}

    def _infer_usage(self, dialogues: list[dict[str, str]], current: dict[str, str]) -> dict[str, str]:
        if not dialogues:
            return current
        channels = {str(item.get("channel", "") or "").strip() for item in dialogues if str(item.get("channel", "") or "").strip()}
        mentions: list[str] = []
        all_text = "\n".join([_single_line(x.get("text", "")) for x in dialogues])
        if "QML" in all_text.upper():
            mentions.append("经常围绕 QML 页面与交互细节推进")
        if "飞书" in all_text:
            mentions.append("会在飞书与桌面入口之间切换使用")
        if "Python" in all_text or "python" in all_text:
            mentions.append("常结合 Python 服务层处理逻辑")
        if not mentions and channels:
            mentions.append("主要通过 " + " / ".join(sorted(channels)) + " 渠道与助手协作")
        if not mentions:
            return current
        return {"content": "；".join(mentions[:2]), "memory_time": str(dialogues[-1].get("ts", "") or _now_iso()), "source": "聊天行为分析"}

    def _build_local_graph(self, current_graph: dict[str, Any], dialogues: list[dict[str, str]]) -> dict[str, Any]:
        graph = self._normalize_graph(current_graph)
        if not dialogues:
            return graph
        for section in GRAPH_SPEC:
            section_out = graph["sections"][section["title"]]
            for item in section["items"]:
                key = (section["title"], item["title"])
                current_item = dict(section_out.get(item["title"], self._empty_item()))
                rule = RULES.get(key, {"keywords": [], "source": "用户聊天提及"})
                matches = self._dialogue_matches(dialogues, list(rule.get("keywords", [])), limit=3)
                content, latest_ts = self._summarize_matches(matches)
                if content:
                    section_out[item["title"]] = {"content": content, "memory_time": latest_ts or _now_iso(), "source": str(rule.get("source", "用户聊天提及"))}
                elif key == ("用户面板", "性格特征"):
                    section_out[item["title"]] = self._infer_personality(dialogues, current_item)
                elif key == ("行为图鉴", "沟通习惯"):
                    section_out[item["title"]] = self._infer_communication(dialogues, current_item)
                elif key == ("行为图鉴", "使用习惯"):
                    section_out[item["title"]] = self._infer_usage(dialogues, current_item)
                else:
                    section_out[item["title"]] = current_item
        graph["updated_at"] = _now_iso()
        return self._normalize_graph(graph)

    def _post_json(self, url: str, api_key: str, payload: dict[str, Any], timeout_s: float = 80.0) -> tuple[int, str]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("Authorization", f"Bearer {api_key.strip()}")
        with request.urlopen(req, data=data, timeout=timeout_s) as resp:
            return (getattr(resp, "status", 0) or 0, resp.read().decode("utf-8", errors="replace"))

    def _build_kimi_prompt(self, current_graph: dict[str, Any], dialogues: list[dict[str, str]]) -> str:
        lines = [
            "你是记忆图谱更新助手，只能基于用户对话内容更新记忆图谱。",
            "忽略系统提示、操作指令、确认词、日程命令、待办命令和非对话噪声。",
            "输出必须是 JSON，不要 Markdown，不要解释。",
            "必须输出完整 schema，sections 下固定 19 项全部保留。",
            "如果某项缺乏新证据，优先保留 current_memory 中已有内容；若 current_memory 也为空，则保持空字符串。",
            "source 只能是以下五个值之一：初始化设定、用户主动告知、聊天行为分析、用户聊天提及、用户设置。",
            "memory_time 必须是 ISO 时间；沿用旧内容时可沿用原 memory_time。",
            "性格特征、沟通习惯、使用习惯可以做行为分析，但仍只能基于用户对话。",
            "隐私规则、回复规则、题型规划、格式规则只有在用户明确表达要求时才填写。",
            "固定 schema：",
            json.dumps(self._default_graph(), ensure_ascii=False, indent=2),
            "current_memory：",
            json.dumps(current_graph, ensure_ascii=False, indent=2),
            "recent_user_dialogues：",
        ]
        for item in dialogues:
            lines.append(json.dumps({"ts": item.get("ts", ""), "channel": item.get("channel", ""), "role": "user", "text": item.get("text", "")}, ensure_ascii=False))
        return "\n".join(lines)

    def _build_kimi_graph(self, current_graph: dict[str, Any], dialogues: list[dict[str, str]]) -> dict[str, Any] | None:
        cfg = self._config()
        kimi = cfg.get("kimi") if isinstance(cfg.get("kimi"), dict) else {}
        api_key = str(kimi.get("api_key", "") or "").strip()
        base_url = _normalize_base_url(str(kimi.get("base_url", "") or "https://api.moonshot.cn/v1"))
        model = str(kimi.get("model", "") or "").strip()
        if not api_key or not base_url or not model:
            return None
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你只输出 JSON。"},
                {"role": "user", "content": self._build_kimi_prompt(current_graph, dialogues)},
            ],
            "temperature": 0.2,
        }
        try:
            status, raw = self._post_json(f"{base_url}/chat/completions", api_key, payload)
            if not (200 <= status < 300):
                return None
            resp = json.loads(raw)
            content = ""
            if isinstance(resp, dict):
                choices = resp.get("choices")
                if isinstance(choices, list) and choices:
                    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                    if isinstance(msg, dict):
                        content = str(msg.get("content", "") or "")
            obj = _extract_first_json(content)
            return self._normalize_graph(obj) if isinstance(obj, dict) else None
        except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None
        except Exception:
            return None

    def _merge_target_card(self, current_graph: dict[str, Any], candidate_graph: dict[str, Any], section: str, title: str) -> tuple[dict[str, Any], bool]:
        merged = self._normalize_graph(current_graph)
        current_item = merged["sections"][section][title]
        next_item = candidate_graph["sections"][section][title]
        if current_item == next_item:
            return merged, False
        merged["sections"][section][title] = dict(next_item)
        merged["updated_at"] = _now_iso()
        return merged, True

    def _build_candidate_graph(self, current_graph: dict[str, Any]) -> tuple[dict[str, Any], str]:
        dialogues = self._recent_user_dialogues(limit=200)
        candidate = self._build_kimi_graph(current_graph, dialogues)
        source_label = "Kimi"
        if not isinstance(candidate, dict):
            candidate = self._build_local_graph(current_graph, dialogues)
            source_label = "本地"
        return self._normalize_graph(candidate), source_label

    def _merge_full_graph(self, current_graph: dict[str, Any], candidate_graph: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        current_norm = self._normalize_graph(current_graph)
        candidate_norm = self._normalize_graph(candidate_graph)
        candidate_norm["updated_at"] = _now_iso()
        if current_norm == candidate_norm:
            return current_norm, False
        return candidate_norm, True

    @Slot(object)
    def _on_worker_finished(self, payload: object) -> None:
        data = payload if isinstance(payload, dict) else {}
        self._set_loading(False)
        if not data.get("ok", False):
            self.toastRequested.emit(str(data.get("message", "记忆图谱更新失败") or "记忆图谱更新失败"))
            return
        self.reload(select_category=str(data.get("category", "") or self._current_category))
        self.toastRequested.emit(str(data.get("message", "记忆图谱已更新") or "记忆图谱已更新"))

    @Property("QVariantList", notify=categoriesChanged)
    def categories(self) -> list:
        return list(self._categories)

    @Property(str, notify=currentCategoryChanged)
    def currentCategory(self) -> str:
        return self._current_category

    @Property("QVariantList", notify=currentCardsChanged)
    def currentCards(self) -> list:
        return list(self._current_cards)

    @Property(bool, notify=loadingChanged)
    def loading(self) -> bool:
        return bool(self._loading)

    @Slot(str)
    def selectCategory(self, category: str) -> None:
        wanted = (category or "").strip()
        if not any(x["key"] == wanted for x in self._categories):
            return
        if self._current_category != wanted:
            self._current_category = wanted
            self.currentCategoryChanged.emit()
        self._refresh_cards()

    @Slot()
    def reload(self, select_category: str = "") -> None:
        self._graph = self._ensure_graph()
        wanted = (select_category or "").strip()
        if wanted and any(x["key"] == wanted for x in self._categories) and self._current_category != wanted:
            self._current_category = wanted
            self.currentCategoryChanged.emit()
        self._refresh_cards()

    @Slot(str, str, str)
    def saveCard(self, section: str, title: str, content: str) -> None:
        sec = (section or "").strip()
        item_title = (title or "").strip()
        if (sec, item_title) not in ITEM_META:
            self.toastRequested.emit("无效的记忆卡片")
            return
        with self._lock:
            graph = self._ensure_graph()
            item = graph["sections"][sec][item_title]
            clean = _clean_text(content)
            if clean:
                item["content"] = clean
                item["memory_time"] = _now_iso()
                item["source"] = "用户设置"
            else:
                item["content"] = ""
                item["memory_time"] = ""
                item["source"] = ""
            graph["updated_at"] = _now_iso()
            self._save_graph(graph)
        self._refresh_cards()
        self.toastRequested.emit("记忆已保存")

    @Slot(str, str)
    def updateCardWithAi(self, section: str, title: str) -> None:
        sec = (section or "").strip()
        item_title = (title or "").strip()
        if self._loading:
            return
        if (sec, item_title) not in ITEM_META:
            self.toastRequested.emit("无效的记忆卡片")
            return
        self._set_loading(True)

        def _worker() -> None:
            try:
                with self._lock:
                    current_graph = self._ensure_graph()
                    candidate, source_label = self._build_candidate_graph(current_graph)
                    merged, changed = self._merge_target_card(current_graph, candidate, sec, item_title)
                    if changed:
                        self._backup_graph(current_graph)
                        self._save_graph(merged)
                        message = f"{item_title}已通过{source_label}更新"
                    else:
                        message = f"未发现可更新的{item_title}记忆"
                payload = {"ok": True, "message": message, "category": sec}
            except Exception as exc:
                payload = {"ok": False, "message": f"记忆图谱更新失败：{exc}", "category": sec}
            self._workerFinished.emit(payload)

        threading.Thread(target=_worker, name=f"MemoryGraph-{sec}-{item_title}", daemon=True).start()

    @Slot()
    def refreshGraphOnOpen(self) -> None:
        if self._loading:
            return
        self._set_loading(True)

        def _worker() -> None:
            try:
                with self._lock:
                    current_graph = self._ensure_graph()
                    candidate, _source_label = self._build_candidate_graph(current_graph)
                    merged, changed = self._merge_full_graph(current_graph, candidate)
                    if changed:
                        self._backup_graph(current_graph)
                        self._save_graph(merged)
                        message = "记忆图谱已自动更新"
                    else:
                        message = "记忆图谱已是最新状态"
                payload = {"ok": True, "message": message, "category": self._current_category}
            except Exception as exc:
                payload = {"ok": False, "message": f"记忆图谱更新失败：{exc}", "category": self._current_category}
            self._workerFinished.emit(payload)

        threading.Thread(target=_worker, name="MemoryGraphAutoRefresh", daemon=True).start()
