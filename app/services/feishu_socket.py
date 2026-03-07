from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from PySide6.QtCore import QObject, Property, Signal, Slot, QStandardPaths

from app.core.app_paths import default_user_data_dir


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _normalize_base_url(u: str) -> str:
    s = (u or "").strip()
    while s.endswith("/"):
        s = s[:-1]
    return s


def _read_runtime_last_data_dir() -> str:
    try:
        loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        if not loc:
            return ""
        p = Path(loc).resolve() / "runtime.json"
        if not p.exists():
            return ""
        obj = json.loads(p.read_text(encoding="utf-8"))
        v = obj.get("last_data_dir", "")
        return str(v).strip() if isinstance(v, str) else ""
    except Exception:
        return ""


@dataclass
class _TokenCache:
    token: str = ""
    expires_at: float = 0.0


class FeishuSocket(QObject):
    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2

    stateChanged = Signal(int)
    lastErrorChanged = Signal(str)
    boundReceiveIdChanged = Signal(str)
    toastRequested = Signal(str)

    _reqSetState = Signal(int)
    _reqSetError = Signal(str)
    _reqSetBound = Signal(str)
    _reqToast = Signal(str)

    def __init__(self, project_root: Path, onboardingDraft: Optional[QObject] = None):
        super().__init__()
        self._project_root = Path(project_root).resolve()
        self._onboarding = onboardingDraft
        self._http = requests.Session()
        self._http_lock = threading.Lock()
        self._token = _TokenCache()
        self._token_lock = threading.Lock()
        self._config_lock = threading.Lock()

        self._state = self.STATE_DISCONNECTED
        self._last_error = ""
        self._bound_receive_id = ""
        self._bound_receive_type = "chat_id"
        self._app_id = ""
        self._app_secret = ""
        self._data_dir = default_user_data_dir(self._project_root)
        self._stop_flag = threading.Event()
        self._ws_client: Any = None
        self._message_handler: Optional[Callable[[str, str, str], str]] = None

        self._reqSetState.connect(self._set_state)
        self._reqSetError.connect(self._set_error)
        self._reqSetBound.connect(self._set_bound_receive_id)
        self._reqToast.connect(self._emit_toast)

    @Property(int, constant=True)
    def StateDisconnected(self) -> int:
        return self.STATE_DISCONNECTED

    @Property(int, constant=True)
    def StateConnecting(self) -> int:
        return self.STATE_CONNECTING

    @Property(int, constant=True)
    def StateConnected(self) -> int:
        return self.STATE_CONNECTED

    def _set_state(self, s: int) -> None:
        if self._state != s:
            self._state = s
            self.stateChanged.emit(self._state)

    @Property(int, notify=stateChanged)
    def state(self) -> int:
        return int(self._state)

    def _set_error(self, msg: str) -> None:
        m = (msg or "").strip()
        if self._last_error != m:
            self._last_error = m
            self.lastErrorChanged.emit(self._last_error)

    @Property(str, notify=lastErrorChanged)
    def lastError(self) -> str:
        return self._last_error

    def _set_bound_receive_id(self, rid: str) -> None:
        r = (rid or "").strip()
        if self._bound_receive_id != r:
            self._bound_receive_id = r
            self.boundReceiveIdChanged.emit(self._bound_receive_id)

    @Property(str, notify=boundReceiveIdChanged)
    def boundReceiveId(self) -> str:
        return self._bound_receive_id

    @Property(str, constant=True)
    def boundReceiveType(self) -> str:
        return self._bound_receive_type

    def _should_persist_to_draft(self) -> bool:
        return (self._project_root / ".tmp" / "onboarding_state.json").exists()

    @Slot(str)
    def _emit_toast(self, text: str) -> None:
        t = (text or "").strip()
        if t:
            self.toastRequested.emit(t)

    def setMessageHandler(self, handler: Callable[[str, str, str], str]) -> None:
        self._message_handler = handler

    def _persist_to_draft(
        self,
        *,
        enabled: Optional[bool] = None,
        bound_receive_id: Optional[str] = None,
        bound_receive_type: Optional[str] = None,
    ) -> None:
        if not self._onboarding or not self._should_persist_to_draft():
            return
        try:
            if enabled is not None:
                self._onboarding.setDraftFeishuEnabled(bool(enabled))
            self._onboarding.setDraftFeishuAppId(self._app_id)
            self._onboarding.setDraftFeishuAppSecret(self._app_secret)
            if bound_receive_id is not None:
                self._onboarding.setDraftFeishuBoundReceiveId(str(bound_receive_id or "").strip())
            if bound_receive_type is not None:
                self._onboarding.setDraftFeishuBoundReceiveType(str(bound_receive_type or "").strip())
            if self._state == self.STATE_CONNECTED:
                self._onboarding.setDraftFeishuLastConnectedAt(_now_iso())
            self._onboarding.saveDraft()
        except Exception:
            pass

    def _persist_config_bound(self, chat_id: str) -> None:
        cid = (chat_id or "").strip()
        if not cid:
            return
        cfg_path = self._data_dir / "config.json"
        if not cfg_path.exists():
            return
        with self._config_lock:
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                return
            if not isinstance(cfg, dict):
                return
            feishu_cfg = cfg.get("feishu")
            if not isinstance(feishu_cfg, dict):
                feishu_cfg = {}
                cfg["feishu"] = feishu_cfg
            feishu_cfg["bound_receive_id"] = cid
            feishu_cfg["bound_receive_type"] = self._bound_receive_type or "chat_id"
            tmp = cfg_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(cfg_path)

    def _candidate_config_paths(self) -> list[Path]:
        out: list[Path] = []
        try:
            dd = str(self._onboarding.getDraftDataDir() or "").strip() if self._onboarding else ""
        except Exception:
            dd = ""
        if dd:
            out.append(Path(dd).expanduser().resolve() / "config.json")
        rd = _read_runtime_last_data_dir()
        if rd:
            out.append(Path(rd).expanduser().resolve() / "config.json")
        out.append((default_user_data_dir(self._project_root) / "config.json").resolve())
        dedup: list[Path] = []
        seen = set()
        for p in out:
            s = str(p)
            if s in seen:
                continue
            seen.add(s)
            dedup.append(p)
        return dedup

    @Slot()
    def autoStart(self) -> None:
        cfg_path: Optional[Path] = None
        for p in self._candidate_config_paths():
            if p.exists():
                cfg_path = p
                break
        if cfg_path is None:
            return
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return
        feishu_cfg = cfg.get("feishu") if isinstance(cfg.get("feishu"), dict) else {}
        if not bool(feishu_cfg.get("enabled", False)):
            return
        app_id = str(feishu_cfg.get("app_id", "") or "").strip()
        app_secret = str(feishu_cfg.get("app_secret", "") or "").strip()
        bound_id = str(feishu_cfg.get("bound_receive_id", "") or "").strip()
        self._bound_receive_type = str(feishu_cfg.get("bound_receive_type", "") or "chat_id").strip() or "chat_id"
        if not app_id or not app_secret:
            return
        self._data_dir = cfg_path.parent.resolve()
        self.startLongConnection(app_id, app_secret, bound_id)

    @Slot(str, str, str)
    def startLongConnection(self, app_id: str, app_secret: str, bound_receive_id: str) -> None:
        app_id = (app_id or "").strip()
        app_secret = (app_secret or "").strip()
        bound_receive_id = (bound_receive_id or "").strip()
        if not app_id or not app_secret:
            self._set_error("请填写 App ID 和 App Secret")
            self._set_state(self.STATE_DISCONNECTED)
            return
        self._app_id = app_id
        self._app_secret = app_secret
        if bound_receive_id:
            self._set_bound_receive_id(bound_receive_id)
        self._persist_to_draft(
            enabled=True,
            bound_receive_id=bound_receive_id or None,
            bound_receive_type=self._bound_receive_type,
        )

        self.stopLongConnection()
        self._stop_flag.clear()
        self._set_error("")
        self._set_state(self.STATE_CONNECTING)
        threading.Thread(target=self._run_ws_forever, name="FeishuSocket", daemon=True).start()

    @Slot()
    def stopLongConnection(self) -> None:
        self._stop_flag.set()
        cli = self._ws_client
        self._ws_client = None
        for meth in ("stop", "close", "shutdown"):
            try:
                if cli is not None and hasattr(cli, meth):
                    getattr(cli, meth)()
                    break
            except Exception:
                pass
        self._set_state(self.STATE_DISCONNECTED)

    @Slot(str)
    def setBoundChatId(self, chat_id: str) -> None:
        cid = (chat_id or "").strip()
        if not cid:
            self._emit_toast("Chat ID 不能为空")
            return
        self._set_bound_receive_id(cid)
        self._bound_receive_type = "chat_id"
        self._persist_to_draft(bound_receive_id=cid, bound_receive_type="chat_id")
        self._persist_config_bound(cid)
        self._emit_toast("Chat ID 已更新")

    @Slot(str)
    def sendToBound(self, text: str) -> None:
        msg = (text or "").strip()
        if not msg:
            return
        if not self._bound_receive_id:
            self._emit_toast("未绑定：请先在飞书发一句话完成绑定")
            return

        def _worker() -> None:
            try:
                self._send_text(
                    receive_id=self._bound_receive_id,
                    text=msg,
                    receive_id_type=self._bound_receive_type or "chat_id",
                )
            except Exception as ex:
                self._reqSetError.emit(str(ex))

        threading.Thread(target=_worker, name="FeishuPush", daemon=True).start()

    @Slot(str, str)
    def testConnection(self, app_id: str, app_secret: str) -> None:
        aid = (app_id or "").strip()
        secret = (app_secret or "").strip()
        if not aid or not secret:
            self._reqSetError.emit("请先填写 App ID 和 App Secret")
            return

        def _worker() -> None:
            old_app_id = self._app_id
            old_app_secret = self._app_secret
            try:
                self._app_id = aid
                self._app_secret = secret
                _ = self._get_tenant_access_token(timeout_s=8.0)
                self._reqSetError.emit("")
                self._reqToast.emit("飞书连接测试成功")
            except Exception as ex:
                self._reqSetError.emit(str(ex))
            finally:
                self._app_id = old_app_id
                self._app_secret = old_app_secret

        threading.Thread(target=_worker, name="FeishuTest", daemon=True).start()

    def _monitor_ws_state(self, cli: Any) -> None:
        while not self._stop_flag.is_set() and self._ws_client is cli:
            conn = getattr(cli, "_conn", None)
            is_live = bool(conn is not None and not bool(getattr(conn, "closed", False)))
            self._reqSetState.emit(self.STATE_CONNECTED if is_live else self.STATE_CONNECTING)
            if is_live:
                self._reqSetError.emit("")
            time.sleep(1.0)

    def _get_tenant_access_token(self, timeout_s: float = 6.0) -> str:
        now = time.time()
        with self._token_lock:
            if self._token.token and now < self._token.expires_at - 60:
                return self._token.token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        with self._http_lock:
            resp = self._http.post(
                url,
                json={"app_id": self._app_id, "app_secret": self._app_secret},
                timeout=timeout_s,
            )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code != 200 or int((data or {}).get("code", -1)) != 0:
            msg = (data or {}).get("msg") or f"HTTP {resp.status_code}"
            raise RuntimeError(f"获取 tenant_access_token 失败：{msg}")
        token = str((data or {}).get("tenant_access_token") or "")
        expire = int((data or {}).get("expire", 3600))
        with self._token_lock:
            self._token.token = token
            self._token.expires_at = time.time() + expire
        return token

    def _send_text(self, *, receive_id: str, text: str, receive_id_type: str = "chat_id") -> None:
        token = self._get_tenant_access_token(timeout_s=6.0)
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        with self._http_lock:
            resp = self._http.post(url, headers=headers, json=payload, timeout=8.0)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code != 200 or int((data or {}).get("code", -1)) != 0:
            msg = (data or {}).get("msg") or f"HTTP {resp.status_code}"
            raise RuntimeError(f"发送消息失败：{msg}")

    def _run_ws_forever(self) -> None:
        if self._stop_flag.is_set():
            return
        try:
            _ = self._get_tenant_access_token(timeout_s=6.0)
        except Exception as ex:
            self._reqSetError.emit(str(ex))
            self._reqSetState.emit(self.STATE_DISCONNECTED)
            return
        if self._stop_flag.is_set():
            return
        try:
            import lark_oapi as lark
        except Exception:
            self._reqSetError.emit("缺少依赖：lark-oapi")
            self._reqSetState.emit(self.STATE_DISCONNECTED)
            return
        try:
            builder = lark.EventDispatcherHandler.builder("", "")
        except TypeError:
            builder = lark.EventDispatcherHandler.builder("", "", lark.LogLevel.INFO)
        self._register_noop_message_read(builder)
        handler = builder.register_p2_im_message_receive_v1(self._on_p2_im_message_receive_v1).build()
        try:
            self._ws_client = lark.ws.Client(
                self._app_id,
                self._app_secret,
                event_handler=handler,
                log_level=getattr(lark, "LogLevel", None).INFO if hasattr(lark, "LogLevel") else None,
            )
            threading.Thread(target=self._monitor_ws_state, args=(self._ws_client,), name="FeishuWsState", daemon=True).start()
            self._persist_to_draft(
                enabled=True,
                bound_receive_id=self._bound_receive_id or None,
                bound_receive_type=self._bound_receive_type,
            )
            if self._bound_receive_id:
                try:
                    self._send_text(receive_id=self._bound_receive_id, text="已连接", receive_id_type="chat_id")
                except Exception:
                    pass
            else:
                self._reqToast.emit("已连接，请去飞书给机器人发一句话完成绑定")
            self._ws_client.start()
        except Exception as ex:
            self._reqSetError.emit(str(ex))
            self._reqSetState.emit(self.STATE_DISCONNECTED)

    def _register_noop_message_read(self, builder: Any) -> None:
        noop = lambda *_a, **_kw: None  # noqa: E731
        preferred = [
            "register_im_message_read_v1",
            "register_im_message_message_read_v1",
            "register_p2_im_message_read_v1",
            "register_p2_im_message_message_read_v1",
        ]
        for name in preferred:
            fn = getattr(builder, name, None)
            if callable(fn):
                try:
                    fn(noop)
                    return
                except Exception:
                    pass
        for name in dir(builder):
            if not name.startswith("register"):
                continue
            if "message_read_v1" not in name:
                continue
            fn = getattr(builder, name, None)
            if not callable(fn):
                continue
            try:
                fn(noop)
                return
            except Exception:
                continue
        reg = getattr(builder, "register", None)
        if callable(reg):
            try:
                reg("im.message.message_read_v1", noop)
            except Exception:
                pass

    def _extract_text(self, event: dict[str, Any]) -> str:
        msg = event.get("message") if isinstance(event.get("message"), dict) else {}
        if str(msg.get("message_type", "") or "").strip() != "text":
            return ""
        content_raw = msg.get("content")
        if not isinstance(content_raw, str) or not content_raw.strip():
            return ""
        try:
            obj = json.loads(content_raw)
            if isinstance(obj, dict):
                return str(obj.get("text", "") or "").strip()
        except Exception:
            pass
        return ""

    def _extract_chat_id(self, event: dict[str, Any]) -> str:
        msg = event.get("message") if isinstance(event.get("message"), dict) else {}
        cid = str(msg.get("chat_id", "") or "").strip()
        if not cid:
            cid = str(msg.get("open_chat_id", "") or "").strip()
        return cid

    def _handle_incoming(self, chat_id: str, open_id: str, text: str) -> None:
        if self._stop_flag.is_set():
            return
        reply = ""
        if self._message_handler is not None:
            try:
                reply = str(self._message_handler(chat_id, open_id, text) or "").strip()
            except Exception as ex:
                reply = f"处理消息失败：{ex}"
        if not reply:
            reply = "收到。"
        try:
            self._send_text(receive_id=chat_id, text=reply, receive_id_type="chat_id")
        except Exception as ex:
            self._reqSetError.emit(str(ex))

    def _on_p2_im_message_receive_v1(self, data: Any) -> None:
        if self._stop_flag.is_set():
            return
        try:
            import lark_oapi as lark

            raw = lark.JSON.marshal(data)
            payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
            event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
            msg = event.get("message") if isinstance(event.get("message"), dict) else {}
            if str(msg.get("chat_type", "") or "").strip() != "p2p":
                return
            sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
            sender_id = sender.get("sender_id") if isinstance(sender.get("sender_id"), dict) else {}
            open_id = str(sender_id.get("open_id", "") or "").strip()
            chat_id = self._extract_chat_id(event)
            if not chat_id:
                return
            if not self._bound_receive_id:
                self._bound_receive_type = "chat_id"
                self._reqSetBound.emit(chat_id)
                self._persist_to_draft(enabled=True, bound_receive_id=chat_id, bound_receive_type="chat_id")
                self._persist_config_bound(chat_id)
                try:
                    self._send_text(receive_id=chat_id, text="已连接", receive_id_type="chat_id")
                except Exception as ex:
                    self._reqSetError.emit(str(ex))
                self._reqToast.emit("飞书机器人绑定成功")
                return
            text = self._extract_text(event)
            if not text:
                return
            threading.Thread(
                target=self._handle_incoming,
                args=(chat_id, open_id, text),
                daemon=True,
            ).start()
        except Exception:
            return
