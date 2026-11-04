#!/usr/bin/env python3
"""Private LAN web remote for Android TV Remote Protocol v2.

The browser talks only to this computer.  This bridge pairs with Android TV's
encrypted Remote Service, so USB/network debugging can remain off.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import ipaddress
import json
import os
import secrets
import socket
import stat
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ALLOWED_KEYS = frozenset(
    {
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "APP_SWITCH",
        "BACK",
        "CAPTIONS",
        "CHANNEL_DOWN",
        "CHANNEL_UP",
        "CLEAR",
        "DEL",
        "DPAD_CENTER",
        "DPAD_DOWN",
        "DPAD_LEFT",
        "DPAD_RIGHT",
        "DPAD_UP",
        "ENTER",
        "FORWARD_DEL",
        "GUIDE",
        "HOME",
        "INFO",
        "MEDIA_FAST_FORWARD",
        "MEDIA_NEXT",
        "MEDIA_PAUSE",
        "MEDIA_PLAY",
        "MEDIA_PLAY_PAUSE",
        "MEDIA_PREVIOUS",
        "MEDIA_REWIND",
        "MEDIA_STOP",
        "MENU",
        "MUTE",
        "POWER",
        "SEARCH",
        "SETTINGS",
        "SPACE",
        "TAB",
        "TV_INPUT",
        "VOLUME_DOWN",
        "VOLUME_MUTE",
        "VOLUME_UP",
    }
)

TEXT_LIMIT = 1000

APP_LINKS = {
    "netflix": "netflix://",
    "youtube": "https://www.youtube.com",
    "disney": "https://www.disneyplus.com",
    "max": "https://play.max.com",
    "prime": "https://app.primevideo.com",
    "spotify": "spotify://",
}

def private_client(address: str) -> bool:
    """Return whether an HTTP peer is local/private, including IPv4-mapped IPv6."""
    word = address.split("%", 1)[0]
    try:
        ip = ipaddress.ip_address(word)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local


def secure_data_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(stat.S_IRWXU)
    except OSError:
        pass


def load_or_create_token(path: Path) -> str:
    if path.exists():
        token = path.read_text(encoding="ascii").strip()
        if len(token) >= 40:
            return token
        raise ValueError(f"{path} contains an invalid short token; remove that file to regenerate it")
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n", encoding="ascii")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return token


def local_address_for(tv_host: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((tv_host, 9))
        return str(sock.getsockname()[0])
    finally:
        sock.close()


@dataclass
class BridgeState:
    available: bool = False
    is_on: bool = False
    current_app: str = ""
    volume: int | None = None
    muted: bool = False
    last_error: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(self, **values: Any) -> None:
        with self._lock:
            for key, value in values.items():
                setattr(self, key, value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "available": self.available,
                "is_on": self.is_on,
                "current_app": self.current_app,
                "volume": self.volume,
                "muted": self.muted,
                "last_error": self.last_error,
            }


class CommandSink:
    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[tuple[str, Any]]) -> None:
        self.loop = loop
        self.queue = queue

    def put(self, kind: str, value: Any) -> bool:
        if self.queue.qsize() >= self.queue.maxsize:
            return False
        self.loop.call_soon_threadsafe(self.queue.put_nowait, (kind, value))
        return True


class RequestLimiter:
    def __init__(self, limit: int = 160, seconds: float = 10.0) -> None:
        self.limit = limit
        self.seconds = seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, address: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[address]
            while hits and hits[0] < now - self.seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


class RemoteServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        page: bytes,
        token: str,
        state: BridgeState,
        sink: CommandSink,
        assets: dict[str, tuple[str, bytes]] | None = None,
    ) -> None:
        self.page = page
        self.prefix = f"/r/{token}/"
        self.state = state
        self.sink = sink
        self.assets = assets or {}
        self.limiter = RequestLimiter()
        super().__init__(address, RemoteHandler)


class RemoteHandler(BaseHTTPRequestHandler):
    server: RemoteServer

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _authorized(self) -> bool:
        address = self.client_address[0]
        if not private_client(address):
            self._json(HTTPStatus.FORBIDDEN, {"ok": False})
            return False
        if not self.server.limiter.allow(address):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"ok": False})
            return False
        if not self.path.startswith(self.server.prefix):
            self._json(HTTPStatus.NOT_FOUND, {"ok": False})
            return False
        return True

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"ok": False})

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            return
        route = self.path[len(self.server.prefix) :].split("?", 1)[0]
        if route in {"", "index.html"}:
            body = self.server.page.replace(b"__REMOTE_BASE__", self.server.prefix.encode("ascii"))
            self._headers(HTTPStatus.OK, "text/html; charset=utf-8", len(body))
            self.wfile.write(body)
        elif route in self.server.assets:
            content_type, body = self.server.assets[route]
            self._headers(HTTPStatus.OK, content_type, len(body))
            self.wfile.write(body)
        elif route == "api/status":
            self._json(HTTPStatus.OK, {"ok": True, **self.server.state.snapshot()})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            return
        if self.headers.get_content_type() != "application/json":
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"ok": False})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if size < 2 or size > 16384:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
            return
        try:
            value = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
            return
        if not isinstance(value, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
            return
        route = self.path[len(self.server.prefix) :].split("?", 1)[0]
        command: tuple[str, Any] | None = None
        if route == "api/key" and value.get("key") in ALLOWED_KEYS:
            count = value.get("count", 1)
            if isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= 20:
                command = ("keys", (value["key"], count))
        elif route == "api/app" and value.get("app") in APP_LINKS:
            command = ("app", value["app"])
        elif route == "api/text" and isinstance(value.get("text"), str):
            text = value["text"]
            submit = value.get("submit", False)
            if 0 < len(text) <= TEXT_LIMIT and "\x00" not in text and isinstance(submit, bool):
                command = ("text_submit" if submit else "text", text)
        if command is None:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
        elif not self.server.sink.put(*command):
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False})
        else:
            self._json(HTTPStatus.ACCEPTED, {"ok": True})


async def pair(remote: Any) -> None:
    name, _mac = await remote.async_get_name_and_mac()
    print(f"Pairing request sent to {name or remote.host}.")
    await remote.async_start_pairing()
    code = await asyncio.to_thread(input, "Enter the code shown on the TV: ")
    await remote.async_finish_pairing(code.strip())


async def command_worker(queue: asyncio.Queue[tuple[str, Any]], remote: Any, state: BridgeState) -> None:
    while True:
        kind, value = await queue.get()
        try:
            if kind == "keys":
                key, count = value
                for _ in range(count):
                    remote.send_key_command(key)
            elif kind == "app":
                remote.send_launch_app_command(APP_LINKS[value])
            elif kind == "text":
                remote.send_text(value)
            elif kind == "text_submit":
                remote.send_text(value)
                remote.send_key_command("ENTER")
            state.update(last_error="")
        except Exception as exc:  # keep the bridge alive and avoid leaking network details to the phone
            state.update(last_error=f"{kind} command failed: {type(exc).__name__}")
        finally:
            queue.task_done()


def volume_values(info: Any) -> tuple[int | None, bool]:
    if info is None:
        return None, False
    level = getattr(info, "volume_level", getattr(info, "level", None))
    muted = bool(getattr(info, "muted", getattr(info, "is_muted", False)))
    return level if isinstance(level, int) else None, muted


async def run(args: argparse.Namespace) -> None:
    try:
        from androidtvremote2 import AndroidTVRemote, CannotConnect, ConnectionClosed, InvalidAuth
    except ImportError:
        raise SystemExit("androidtvremote2 is missing; run tools/phone-remote.sh instead") from None

    data_dir = Path(args.data_dir).expanduser().resolve()
    secure_data_dir(data_dir)
    token = load_or_create_token(data_dir / "browser-token")
    state = BridgeState()
    remote = AndroidTVRemote(
        "Clean TV TCL Phone Remote",
        str(data_dir / "client-cert.pem"),
        str(data_dir / "client-key.pem"),
        args.tv,
        enable_ime=True,
        enable_voice=False,
    )
    generated = await remote.async_generate_cert_if_missing()
    if generated:
        await pair(remote)
    try:
        await remote.async_connect()
    except InvalidAuth:
        await pair(remote)
        await remote.async_connect()
    except (CannotConnect, ConnectionClosed) as exc:
        raise SystemExit(f"could not reach Android TV Remote Service at {args.tv}: {type(exc).__name__}") from None

    state.update(available=True, is_on=bool(remote.is_on), current_app=remote.current_app or "")
    level, muted = volume_values(remote.volume_info)
    state.update(volume=level, muted=muted)
    remote.add_is_available_updated_callback(lambda value: state.update(available=bool(value)))
    remote.add_is_on_updated_callback(lambda value: state.update(is_on=bool(value)))
    remote.add_current_app_updated_callback(lambda value: state.update(current_app=value or ""))
    remote.add_volume_info_updated_callback(
        lambda value: state.update(volume=volume_values(value)[0], muted=volume_values(value)[1])
    )
    remote.keep_reconnecting()

    asset_dir = Path(__file__).with_name("phone-remote")
    page_path = asset_dir / "index.html"
    page = page_path.read_bytes()
    assets = {
        "manifest.webmanifest": ("application/manifest+json; charset=utf-8", (asset_dir / "manifest.webmanifest").read_bytes()),
        "icon-192.png": ("image/png", (asset_dir / "icon-192.png").read_bytes()),
        "icon-512.png": ("image/png", (asset_dir / "icon-512.png").read_bytes()),
    }
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=128)
    loop = asyncio.get_running_loop()
    server = RemoteServer((args.bind, args.port), page, token, state, CommandSink(loop, queue), assets)
    thread = threading.Thread(target=server.serve_forever, name="phone-remote-http", daemon=True)
    thread.start()
    address = local_address_for(args.tv)
    print(f"Phone remote: http://{address}:{args.port}{server.prefix}")
    print("Private LAN only. Press Ctrl-C to stop; the browser server then closes immediately.")
    worker = asyncio.create_task(command_worker(queue, remote, state))
    try:
        await asyncio.Event().wait()
    finally:
        server.shutdown()
        server.server_close()
        worker.cancel()
        remote.disconnect()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--tv", required=True, help="TV IPv4 address, for example 192.168.1.50")
    result.add_argument("--bind", default="0.0.0.0", help="browser listener address (default: all LAN interfaces)")
    result.add_argument("--port", type=int, default=8765, help="browser listener port (default: 8765)")
    result.add_argument(
        "--data-dir", default=str(Path(__file__).resolve().parent.parent / "work" / "phone-remote"),
        help="private certificate/token directory (default: ignored work/phone-remote)",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    if not 1 <= args.port <= 65535:
        parser().error("--port must be from 1 through 65535")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nPhone remote stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
