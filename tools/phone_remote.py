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
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ALLOWED_KEYS = frozenset(
    {
        "BACK",
        "DPAD_CENTER",
        "DPAD_DOWN",
        "DPAD_LEFT",
        "DPAD_RIGHT",
        "DPAD_UP",
        "HOME",
        "MEDIA_FAST_FORWARD",
        "MEDIA_NEXT",
        "MEDIA_PAUSE",
        "MEDIA_PLAY",
        "MEDIA_PLAY_PAUSE",
        "MEDIA_PREVIOUS",
        "MEDIA_REWIND",
        "MEDIA_STOP",
        "MUTE",
        "POWER",
        "VOLUME_DOWN",
        "VOLUME_MUTE",
        "VOLUME_UP",
    }
)

APP_LINKS = {
    "netflix": "netflix://",
    "youtube": "https://www.youtube.com",
    "disney": "https://www.disneyplus.com",
    "max": "https://play.max.com",
    "prime": "https://app.primevideo.com",
    "spotify": "spotify://",
}

APP_COLORS = (
    ("com.netflix", (229, 9, 20)),
    ("com.google.android.youtube", (255, 0, 0)),
    ("com.disney", (0, 174, 239)),
    ("com.wbd", (110, 80, 255)),
    ("com.amazon", (0, 168, 225)),
    ("com.spotify", (29, 185, 84)),
    ("com.gathin.tvhome", (109, 103, 174)),
)


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


def app_color(package: str) -> tuple[int, int, int]:
    for prefix, color in APP_COLORS:
        if package.startswith(prefix):
            return color
    return (95, 74, 139)


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


def parse_wled_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("WLED address must be an http(s) URL, for example http://192.168.1.60")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("WLED address must not contain credentials, a query or a fragment")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


@dataclass
class BridgeState:
    available: bool = False
    is_on: bool = False
    current_app: str = ""
    volume: int | None = None
    muted: bool = False
    led_configured: bool = False
    led_sync: bool = True
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
                "led_configured": self.led_configured,
                "led_sync": self.led_sync,
                "last_error": self.last_error,
            }


class WledClient:
    def __init__(self, base_url: str) -> None:
        self.endpoint = parse_wled_url(base_url) + "/json/state"

    def set_color(self, color: tuple[int, int, int], brightness: int = 128) -> None:
        brightness = max(1, min(255, int(brightness)))
        body = json.dumps(
            {"on": True, "bri": brightness, "transition": 6, "seg": [{"col": [[*color]]}]},
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "CleanTVTCL-PhoneRemote/1"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            if not 200 <= response.status < 300:
                raise OSError(f"WLED returned HTTP {response.status}")

    def set_on(self, enabled: bool) -> None:
        body = json.dumps({"on": bool(enabled)}, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "CleanTVTCL-PhoneRemote/1"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            if not 200 <= response.status < 300:
                raise OSError(f"WLED returned HTTP {response.status}")


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
    ) -> None:
        self.page = page
        self.prefix = f"/r/{token}/"
        self.state = state
        self.sink = sink
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
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
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
        if size < 2 or size > 4096:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
            return
        try:
            value = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
            return
        route = self.path[len(self.server.prefix) :].split("?", 1)[0]
        command: tuple[str, Any] | None = None
        if route == "api/key" and value.get("key") in ALLOWED_KEYS:
            command = ("key", value["key"])
        elif route == "api/app" and value.get("app") in APP_LINKS:
            command = ("app", value["app"])
        elif route == "api/text" and isinstance(value.get("text"), str) and 0 < len(value["text"]) <= 256:
            command = ("text", value["text"])
        elif route == "api/led" and self.server.state.snapshot()["led_configured"]:
            action = value.get("action")
            if action == "sync":
                command = ("led_sync", bool(value.get("enabled")))
            elif action == "power":
                command = ("led_power", bool(value.get("enabled")))
            elif action == "color" and isinstance(value.get("color"), str):
                word = value["color"]
                if len(word) == 7 and word.startswith("#"):
                    try:
                        rgb = tuple(int(word[pos : pos + 2], 16) for pos in (1, 3, 5))
                        command = ("led_color", (rgb, int(value.get("brightness", 128))))
                    except (TypeError, ValueError):
                        command = None
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


async def command_worker(
    queue: asyncio.Queue[tuple[str, Any]], remote: Any, state: BridgeState, wled: WledClient | None
) -> None:
    while True:
        kind, value = await queue.get()
        try:
            if kind == "key":
                remote.send_key_command(value)
            elif kind == "app":
                remote.send_launch_app_command(APP_LINKS[value])
            elif kind == "text":
                remote.send_text(value)
            elif kind == "led_sync":
                state.update(led_sync=value)
            elif kind == "led_power" and wled:
                await asyncio.to_thread(wled.set_on, value)
            elif kind == "led_color" and wled:
                color, brightness = value
                state.update(led_sync=False)
                await asyncio.to_thread(wled.set_color, color, brightness)
            state.update(last_error="")
        except Exception as exc:  # keep the bridge alive and avoid leaking network details to the phone
            state.update(last_error=f"{kind} command failed: {type(exc).__name__}")
        finally:
            queue.task_done()


async def app_light_worker(state: BridgeState, wled: WledClient | None) -> None:
    previous = ""
    while True:
        await asyncio.sleep(0.5)
        snapshot = state.snapshot()
        current = snapshot["current_app"]
        if not wled or not snapshot["led_sync"] or not current or current == previous:
            continue
        previous = current
        try:
            await asyncio.to_thread(wled.set_color, app_color(current), 128)
            state.update(last_error="")
        except (OSError, urllib.error.URLError) as exc:
            state.update(last_error=f"LED sync failed: {type(exc).__name__}")


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
    state = BridgeState(led_configured=bool(args.wled))
    wled = WledClient(args.wled) if args.wled else None
    remote = AndroidTVRemote(
        "Clean TV TCL Phone Remote",
        str(data_dir / "client-cert.pem"),
        str(data_dir / "client-key.pem"),
        args.tv,
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

    page_path = Path(__file__).with_name("phone-remote") / "index.html"
    page = page_path.read_bytes()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=128)
    loop = asyncio.get_running_loop()
    server = RemoteServer((args.bind, args.port), page, token, state, CommandSink(loop, queue))
    thread = threading.Thread(target=server.serve_forever, name="phone-remote-http", daemon=True)
    thread.start()
    address = local_address_for(args.tv)
    print(f"Phone remote: http://{address}:{args.port}{server.prefix}")
    print("Private LAN only. Press Ctrl-C to stop; the browser server then closes immediately.")
    if wled:
        print("WLED app-aware lighting is enabled; manual colour control is available on the phone.")
    worker = asyncio.create_task(command_worker(queue, remote, state, wled))
    lights = asyncio.create_task(app_light_worker(state, wled))
    try:
        await asyncio.Event().wait()
    finally:
        server.shutdown()
        server.server_close()
        worker.cancel()
        lights.cancel()
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
    result.add_argument("--wled", help="optional WLED base URL, for example http://192.168.1.60")
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
