#!/usr/bin/env python3
"""Private LAN web remote for Android TV Remote Protocol v2.

The browser talks only to this computer.  This bridge pairs with Android TV's
encrypted Remote Service, so USB/network debugging can remain off.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import io
import ipaddress
import json
import os
import secrets
import socket
import stat
import sys
import threading
import time
import wave
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
VOICE_LIMIT = 6 * 1024 * 1024
VOICE_SECONDS_LIMIT = 30

APP_LINKS = {
    "netflix": "netflix://",
    "youtube": "https://www.youtube.com",
    "disney": "https://www.disneyplus.com",
    "max": "https://play.max.com",
    "prime": "https://app.primevideo.com",
    "spotify": "spotify://",
}


@dataclass(frozen=True)
class ServiceLink:
    id: str
    label: str
    url: str


def load_service_links(path: Path | None) -> dict[str, ServiceLink]:
    """Load private, host-specific TV links without baking addresses into the repo."""
    if path is None or not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or len(value) > 16:
        raise ValueError("service-links.json must be a list of at most 16 links")
    result: dict[str, ServiceLink] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each service link must be an object")
        link_id, label, url = item.get("id"), item.get("label"), item.get("url")
        if not isinstance(link_id, str) or not link_id.replace("-", "").isalnum() or len(link_id) > 32:
            raise ValueError("service link ids must be short letters, numbers or hyphens")
        if not isinstance(label, str) or not 1 <= len(label) <= 32:
            raise ValueError("service link labels must be 1-32 characters")
        if not isinstance(url, str) or not url.startswith(("http://", "https://", "market://")) or len(url) > 500:
            raise ValueError("service link URLs must be http(s) or Play Store URLs")
        if link_id in result:
            raise ValueError(f"duplicate service link id: {link_id}")
        result[link_id] = ServiceLink(link_id, label, url)
    return result


def _event(kind: str, data: dict[str, Any] | None = None, payload: bytes = b"") -> bytes:
    header: dict[str, Any] = {"type": kind}
    if data:
        header["data"] = data
    if payload:
        header["payload_length"] = len(payload)
    return json.dumps(header, separators=(",", ":")).encode("utf-8") + b"\n" + payload


class VoiceTranscriber:
    """Small Wyoming client; audio stays on the configured private endpoint."""

    def __init__(self, address: tuple[str, int], timeout: float = 45.0) -> None:
        self.address = address
        self.timeout = timeout

    def transcribe_wav(self, body: bytes) -> str:
        try:
            with wave.open(io.BytesIO(body), "rb") as audio:
                channels = audio.getnchannels()
                width = audio.getsampwidth()
                rate = audio.getframerate()
                frames = audio.getnframes()
                compressed = audio.getcomptype() != "NONE"
                if compressed or channels != 1 or width != 2 or not 8_000 <= rate <= 96_000:
                    raise ValueError("voice audio must be mono 16-bit PCM WAV")
                if frames <= 0 or frames > rate * VOICE_SECONDS_LIMIT:
                    raise ValueError(f"voice audio must be 1-{VOICE_SECONDS_LIMIT} seconds")
                pcm = audio.readframes(frames)
        except (EOFError, wave.Error) as exc:
            raise ValueError("voice audio is not a valid WAV file") from exc

        audio_format = {"rate": rate, "width": width, "channels": channels}
        with socket.create_connection(self.address, timeout=5.0) as client:
            client.settimeout(self.timeout)
            client.sendall(_event("transcribe", {"language": "en"}))
            client.sendall(_event("audio-start", audio_format))
            for offset in range(0, len(pcm), 8192):
                client.sendall(_event("audio-chunk", audio_format, pcm[offset : offset + 8192]))
            client.sendall(_event("audio-stop"))
            reader = client.makefile("rb")
            for _ in range(128):
                line = reader.readline(65_537)
                if not line:
                    break
                if len(line) > 65_536:
                    raise RuntimeError("Wyoming response header is too large")
                response = json.loads(line.decode("utf-8"))
                data_length = int(response.get("data_length", 0))
                payload_length = int(response.get("payload_length", 0))
                if data_length:
                    extra = json.loads(reader.read(data_length).decode("utf-8"))
                    response.setdefault("data", {}).update(extra)
                if payload_length:
                    reader.read(payload_length)
                if response.get("type") == "transcript":
                    text = response.get("data", {}).get("text", "").strip()
                    if not text:
                        raise ValueError("no speech was detected")
                    return text[:TEXT_LIMIT]
                if response.get("type") == "error":
                    raise RuntimeError("local speech service returned an error")
        raise RuntimeError("local speech service returned no transcript")


def onboarding_svg(url: str) -> bytes:
    import qrcode
    import qrcode.image.svg

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage)
    return image.to_string()

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
        links: dict[str, ServiceLink] | None = None,
        transcriber: VoiceTranscriber | None = None,
    ) -> None:
        self.page = page
        self.prefix = f"/r/{token}/"
        self.state = state
        self.sink = sink
        self.assets = assets or {}
        self.links = links or {}
        self.transcriber = transcriber
        self.voice_lock = threading.BoundedSemaphore(1)
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
            services = [{"id": link.id, "label": link.label} for link in self.server.links.values()]
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self.server.state.snapshot(),
                    "voice_enabled": self.server.transcriber is not None,
                    "services": services,
                },
            )
        else:
            self._json(HTTPStatus.NOT_FOUND, {"ok": False})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            return
        route = self.path[len(self.server.prefix) :].split("?", 1)[0]
        if route == "api/voice":
            if self.server.transcriber is None:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False})
                return
            if self.headers.get_content_type() not in {"audio/wav", "audio/x-wav"}:
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"ok": False})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = 0
            if size < 46 or size > VOICE_LIMIT:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid audio size"})
                return
            if not self.server.voice_lock.acquire(blocking=False):
                self._json(HTTPStatus.TOO_MANY_REQUESTS, {"ok": False, "error": "dictation is already running"})
                return
            try:
                transcript = self.server.transcriber.transcribe_wav(self.rfile.read(size))
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": str(exc)})
                return
            finally:
                self.server.voice_lock.release()
            self._json(HTTPStatus.OK, {"ok": True, "text": transcript})
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
        command: tuple[str, Any] | None = None
        if route == "api/key" and value.get("key") in ALLOWED_KEYS:
            count = value.get("count", 1)
            if isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= 20:
                command = ("keys", (value["key"], count))
        elif route == "api/app" and value.get("app") in APP_LINKS:
            command = ("app", value["app"])
        elif route == "api/service" and value.get("service") in self.server.links:
            command = ("link", self.server.links[value["service"]].url)
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
            elif kind == "link":
                remote.send_launch_app_command(value)
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
    links = load_service_links(Path(args.service_links).expanduser().resolve() if args.service_links else None)
    transcriber = None
    if args.wyoming_whisper:
        host, separator, port_text = args.wyoming_whisper.rpartition(":")
        if not separator or not host or not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise SystemExit("--wyoming-whisper must be HOST:PORT")
        transcriber = VoiceTranscriber((host, int(port_text)))
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
    address = local_address_for(args.tv)
    public_base = args.public_base_url.rstrip("/") if args.public_base_url else f"http://{address}:{args.port}"
    if not public_base.startswith(("http://", "https://")):
        raise SystemExit("--public-base-url must start with http:// or https://")
    remote_url = public_base + f"/r/{token}/"
    assets["onboarding.svg"] = ("image/svg+xml; charset=utf-8", onboarding_svg(remote_url))
    server = RemoteServer(
        (args.bind, args.port), page, token, state, CommandSink(loop, queue), assets, links, transcriber
    )
    thread = threading.Thread(target=server.serve_forever, name="phone-remote-http", daemon=True)
    thread.start()
    print(f"Phone remote: {remote_url}")
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
    result.add_argument("--service-links", help="private JSON file of named homelab links")
    result.add_argument("--wyoming-whisper", help="private Wyoming speech-to-text endpoint as HOST:PORT")
    result.add_argument("--public-base-url", help="HTTPS origin shown in onboarding links and QR code")
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
