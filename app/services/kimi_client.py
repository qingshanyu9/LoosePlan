# app/services/kimi_client.py
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request, error

from PySide6.QtCore import QObject, Signal, Slot, Property, QThreadPool, QRunnable


@dataclass(frozen=True)
class KimiConfig:
    api_key: str
    base_url: str
    model: str


def _normalize_base_url(u: str) -> str:
    s = (u or "").strip()
    while s.endswith("/"):
        s = s[:-1]
    return s


def _has_chinese(s: str) -> bool:
    for ch in s:
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def _extract_error_fields(raw: str) -> tuple[str, str, str]:
    """
    Returns (message, code, type). Any may be "".
    Supports OpenAI-compatible error formats:
      {"error":{"message": "...", "type": "...", "code": "..."}}
    """
    if not raw:
        return "", "", ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            err = obj.get("error")
            if isinstance(err, dict):
                msg = err.get("message") if isinstance(err.get("message"), str) else ""
                code = err.get("code") if isinstance(err.get("code"), str) else ""
                typ = err.get("type") if isinstance(err.get("type"), str) else ""
                return msg.strip(), code.strip(), typ.strip()
            msg2 = obj.get("message") if isinstance(obj.get("message"), str) else ""
            return msg2.strip(), "", ""
    except Exception:
        pass
    return (raw.strip()[:400], "", "")


def _localize_error(message: str, code: str = "", typ: str = "", http_status: int | None = None) -> str:
    msg = (message or "").strip()
    low = msg.lower()
    code_low = (code or "").lower()
    typ_low = (typ or "").lower()

    # Auth
    if (
        "invalid authentication" in low
        or "invalid api key" in low
        or "incorrect api key" in low
        or "authentication" in low and "invalid" in low
        or code_low in {"invalid_api_key", "unauthorized"}
        or typ_low in {"invalid_request_error"} and http_status == 401
        or http_status == 401
    ):
        return "认证失败：API Key 无效、已过期或无权限"

    # Model / not found
    if (
        "model" in low and ("not found" in low or "does not exist" in low)
        or code_low in {"model_not_found"}
    ):
        return "模型不可用：请检查 Model 名称或账号权限"

    # Rate limit
    if "rate limit" in low or code_low in {"rate_limit_exceeded"}:
        return "请求过于频繁：触发限流，请稍后再试"

    # Network-ish text
    if "timed out" in low or "timeout" in low:
        return "连接超时：请检查网络、代理或 Base URL"

    # If server already returns Chinese, keep it
    if _has_chinese(msg):
        return msg

    # Fallback
    return msg if msg else "连接失败：请检查网络或 Key"


def _make_req(url: str, api_key: str, method: str = "GET") -> request.Request:
    req = request.Request(url, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("Authorization", f"Bearer {api_key.strip()}")
    return req


def _http_read_json(req: request.Request, timeout_s: float) -> tuple[int, str]:
    with request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        status = getattr(resp, "status", 0) or 0
        return status, raw


def _test_models_fast(cfg: KimiConfig, timeout_s: float = 4.0) -> tuple[bool, str]:
    """
    Fast test (no model inference):
      1) GET /models/{model}  (fastest and validates model)
      2) fallback GET /models (validate auth + optionally validate model)
    """
    if not cfg.api_key.strip():
        return False, "请先输入 API Key"
    base = _normalize_base_url(cfg.base_url)
    if not base:
        return False, "Base URL 不能为空"
    model = (cfg.model or "").strip()
    if not model:
        return False, "Model 不能为空"

    # 1) GET /models/{model}
    url1 = f"{base}/models/{model}"
    try:
        st, raw = _http_read_json(_make_req(url1, cfg.api_key, "GET"), timeout_s=timeout_s)
        if 200 <= st < 300:
            return True, ""
        # If server returns JSON error
        msg, code, typ = _extract_error_fields(raw)
        return False, _localize_error(msg, code, typ, http_status=st)
    except error.HTTPError as e:
        # 404 could mean endpoint not supported or model not found → fallback to /models
        st = getattr(e, "code", None)
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        if st == 404:
            pass
        else:
            msg, code, typ = _extract_error_fields(raw)
            return False, _localize_error(msg, code, typ, http_status=st)
    except error.URLError:
        return False, "网络错误：请检查 Base URL、网络或代理设置"
    except Exception as ex:
        return False, f"连接失败：{ex}"

    # 2) GET /models
    url2 = f"{base}/models"
    try:
        st, raw = _http_read_json(_make_req(url2, cfg.api_key, "GET"), timeout_s=timeout_s)
        if 200 <= st < 300:
            # Try to validate model existence if list is present
            try:
                obj = json.loads(raw)
                data = obj.get("data") if isinstance(obj, dict) else None
                if isinstance(data, list):
                    ids = {m.get("id") for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)}
                    if ids and model not in ids:
                        return False, "模型不可用：请检查 Model 名称或账号权限"
            except Exception:
                pass
            return True, ""
        msg, code, typ = _extract_error_fields(raw)
        return False, _localize_error(msg, code, typ, http_status=st)
    except error.HTTPError as e:
        st = getattr(e, "code", None)
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        msg, code, typ = _extract_error_fields(raw)
        return False, _localize_error(msg, code, typ, http_status=st)
    except error.URLError:
        return False, "网络错误：请检查 Base URL、网络或代理设置"
    except Exception as ex:
        return False, f"连接失败：{ex}"


class _WorkerSignals(QObject):
    finished = Signal(bool, str)


class _TestWorker(QRunnable):
    def __init__(self, cfg: KimiConfig, timeout_s: float):
        super().__init__()
        self.signals = _WorkerSignals()
        self._cfg = cfg
        self._timeout_s = timeout_s

    def run(self) -> None:
        ok, msg = _test_models_fast(self._cfg, timeout_s=self._timeout_s)
        self.signals.finished.emit(ok, msg)


class KimiClient(QObject):
    testStarted = Signal()
    testFinished = Signal(bool, str)

    connectedChanged = Signal()
    testingChanged = Signal()
    lastErrorChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()

        self._cfg = KimiConfig(
            api_key="",
            base_url="https://api.moonshot.cn/v1",
            model="kimi-k2-thinking-turbo",
        )

        self._testing = False
        self._connected = False
        self._last_error = ""

    def _get_connected(self) -> bool:
        return self._connected

    def _get_testing(self) -> bool:
        return self._testing

    def _get_last_error(self) -> str:
        return self._last_error

    connected = Property(bool, _get_connected, notify=connectedChanged)
    testing = Property(bool, _get_testing, notify=testingChanged)
    lastError = Property(str, _get_last_error, notify=lastErrorChanged)

    def _set_connected(self, v: bool) -> None:
        v = bool(v)
        if self._connected != v:
            self._connected = v
            self.connectedChanged.emit()

    def _set_testing(self, v: bool) -> None:
        v = bool(v)
        if self._testing != v:
            self._testing = v
            self.testingChanged.emit()

    def _set_last_error(self, s: str) -> None:
        s = (s or "").strip()
        if self._last_error != s:
            self._last_error = s
            self.lastErrorChanged.emit()

    @Slot()
    def resetStatus(self) -> None:
        self._set_testing(False)
        self._set_connected(False)
        self._set_last_error("")

    @Slot(str, str, str)
    def setConfig(self, api_key: str, base_url: str, model: str) -> None:
        self._cfg = KimiConfig(
            api_key=(api_key or "").strip(),
            base_url=_normalize_base_url(base_url or ""),
            model=(model or "").strip(),
        )

    @Slot(str, str, str)
    def testConnection(self, api_key: str, base_url: str, model: str) -> None:
        self.setConfig(api_key, base_url, model)
        self._start_test()

    @Slot()
    def testCurrent(self) -> None:
        self._start_test()

    def _start_test(self) -> None:
        if self._testing:
            return

        if not self._cfg.api_key.strip():
            self._set_connected(False)
            self._set_last_error("请先输入 API Key")
            self.testFinished.emit(False, self._last_error)
            return

        self._set_last_error("")
        self._set_connected(False)
        self._set_testing(True)
        self.testStarted.emit()

        # 这里就是“快”的关键：不做 chat 推理，只做 /models 鉴权检测
        worker = _TestWorker(self._cfg, timeout_s=4.0)
        worker.signals.finished.connect(self._on_test_finished)
        self._pool.start(worker)

    @Slot(bool, str)
    def _on_test_finished(self, ok: bool, msg: str) -> None:
        self._set_testing(False)
        if ok:
            self._set_connected(True)
            self._set_last_error("")
            self.testFinished.emit(True, "")
        else:
            self._set_connected(False)
            self._set_last_error(msg or "连接失败：请检查网络或 Key")
            self.testFinished.emit(False, self._last_error)