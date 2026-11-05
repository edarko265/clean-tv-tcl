"""The phone bridge stays local, authenticated and independent of network ADB."""

import importlib.util
import asyncio
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import wave
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "phone_remote.py"
SPEC = importlib.util.spec_from_file_location("phone_remote", TOOL)
PHONE_REMOTE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = PHONE_REMOTE
SPEC.loader.exec_module(PHONE_REMOTE)


class _Sink:
    def __init__(self):
        self.commands = []

    def put(self, kind, value):
        self.commands.append((kind, value))
        return True


class PhoneRemoteTest(unittest.TestCase):
    def test_only_private_loopback_and_link_local_clients_are_accepted(self):
        for address in ("127.0.0.1", "192.168.1.9", "10.3.4.5", "172.16.2.1", "fe80::1"):
            with self.subTest(address=address):
                self.assertTrue(PHONE_REMOTE.private_client(address))
        for address in ("8.8.8.8", "1.1.1.1", "not-an-address"):
            with self.subTest(address=address):
                self.assertFalse(PHONE_REMOTE.private_client(address))

    def test_browser_token_is_long_stable_and_owner_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "token"
            first = PHONE_REMOTE.load_or_create_token(path)
            second = PHONE_REMOTE.load_or_create_token(path)
            self.assertEqual(first, second)
            self.assertGreaterEqual(len(first), 40)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_web_page_is_self_contained_and_has_full_remote_controls(self):
        page = (ROOT / "tools/phone-remote/index.html").read_text(encoding="utf-8")
        self.assertIn("__REMOTE_BASE__", page)
        self.assertIn('post("api/key"', page)
        self.assertIn('id="touchpad"', page)
        self.assertIn("Send + Enter", page)
        self.assertIn('maxlength="1000"', page)
        self.assertIn('data-key="TV_INPUT"', page)
        self.assertNotIn("<script src=", page)
        self.assertNotIn("https://", page)
        self.assertIn('rel="manifest"', page)
        self.assertIn('rel="apple-touch-icon"', page)
        self.assertNotIn("WLED", page)
        self.assertNotIn("lighting", page.lower())
        self.assertIn('id="voiceButton"', page)
        self.assertIn("Audio goes to your Raspberry Pi", page)
        self.assertIn('id="servicesCard"', page)
        self.assertIn('src="onboarding.svg"', page)

    def test_full_key_allowlist_and_text_limit(self):
        for key in ("0", "9", "APP_SWITCH", "CAPTIONS", "CLEAR", "DEL", "ENTER", "GUIDE", "INFO", "MENU", "SETTINGS", "TV_INPUT"):
            with self.subTest(key=key):
                self.assertIn(key, PHONE_REMOTE.ALLOWED_KEYS)
        self.assertEqual(1000, PHONE_REMOTE.TEXT_LIMIT)

    def test_http_server_requires_random_path_and_accepts_allowlisted_key(self):
        sink = _Sink()
        server = PHONE_REMOTE.RemoteServer(
            ("127.0.0.1", 0), b"base=__REMOTE_BASE__", "secret-token", PHONE_REMOTE.BridgeState(), sink,
            {"icon.png": ("image/png", b"private-icon")},
            {"jellyfin": PHONE_REMOTE.ServiceLink("jellyfin", "Jellyfin", "https://tv.example.test")},
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        root = f"http://127.0.0.1:{server.server_port}"
        try:
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(root + "/", timeout=2)
            self.assertEqual(404, denied.exception.code)
            request = urllib.request.Request(
                root + "/r/secret-token/api/key",
                data=b'{"key":"HOME"}',
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(202, response.status)
                self.assertIn("img-src 'self'", response.headers["Content-Security-Policy"])
            with urllib.request.urlopen(root + "/r/secret-token/icon.png", timeout=2) as response:
                self.assertEqual("image/png", response.headers["Content-Type"])
                self.assertEqual(b"private-icon", response.read())
            text_request = urllib.request.Request(
                root + "/r/secret-token/api/text",
                data=json.dumps({"text": "Akwaaba — hello 👋", "submit": True}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(text_request, timeout=2) as response:
                self.assertEqual(202, response.status)
            service_request = urllib.request.Request(
                root + "/r/secret-token/api/service",
                data=b'{"service":"jellyfin"}',
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(service_request, timeout=2) as response:
                self.assertEqual(202, response.status)
            self.assertEqual(
                [
                    ("keys", ("HOME", 1)),
                    ("text_submit", "Akwaaba — hello 👋"),
                    ("link", "https://tv.example.test"),
                ],
                sink.commands,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_docs_and_pinned_dependency_are_present(self):
        requirements = (ROOT / "tools/requirements-phone-remote.txt").read_text(encoding="utf-8")
        self.assertIn("androidtvremote2==0.3.2", requirements)
        self.assertIn("cryptography==50.0.2", requirements)
        self.assertIn("qrcode==8.2", requirements)
        docs = (ROOT / "docs/phone-remote.md").read_text(encoding="utf-8")
        self.assertIn("Network ADB remains off", docs)
        self.assertIn("focused", docs)
        self.assertIn("1,000 characters", docs)
        self.assertNotIn("WLED", docs)

    def test_private_service_links_are_validated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "services.json"
            path.write_text(
                json.dumps([{"id": "jellyfin", "label": "Jellyfin", "url": "https://tv.example.test"}]),
                encoding="utf-8",
            )
            links = PHONE_REMOTE.load_service_links(path)
            self.assertEqual("Jellyfin", links["jellyfin"].label)
            self.assertEqual("https://tv.example.test", links["jellyfin"].url)
            path.write_text(
                json.dumps([{"id": "jellyfin", "label": "Jellyfin", "url": "org.jellyfin.androidtv"}]),
                encoding="utf-8",
            )
            self.assertEqual("org.jellyfin.androidtv", PHONE_REMOTE.load_service_links(path)["jellyfin"].url)

    def test_voice_wav_validation_rejects_stereo(self):
        audio = BytesIO()
        with wave.open(audio, "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(16_000)
            output.writeframes(b"\0\0" * 320)
        transcriber = PHONE_REMOTE.VoiceTranscriber(("127.0.0.1", 1))
        with self.assertRaisesRegex(ValueError, "mono 16-bit"):
            transcriber.transcribe_wav(audio.getvalue())

    def test_onboarding_qr_is_generated_as_svg(self):
        image = PHONE_REMOTE.onboarding_svg("https://remote.example.test/r/secret-token/")
        self.assertIn(b"<svg", image)
        self.assertIn(b"<path", image)


class CommandWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_text_sender_enables_ime_only_during_a_send_and_chunks_long_text(self):
        instances = []

        class Remote:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs
                self.calls = []
                instances.append(self)

            async def async_connect(self):
                self.calls.append(("connect",))

            def send_text(self, value):
                self.calls.append(("text", value))

            def send_key_command(self, value):
                self.calls.append(("key", value))

            def disconnect(self):
                self.calls.append(("disconnect",))

        sender = PHONE_REMOTE.OnDemandTextSender(
            Remote, "tv.test", "client-cert.pem", "client-key.pem",
            settle_seconds=0, chunk_seconds=0, flush_seconds=0,
        )
        value = "a" * 80 + "b"
        await sender.send(value, submit=True)
        self.assertEqual(1, len(instances))
        self.assertTrue(instances[0].kwargs["enable_ime"])
        self.assertFalse(instances[0].kwargs["enable_voice"])
        self.assertEqual(
            [("connect",), ("text", "a" * 80), ("text", "b"), ("key", "ENTER"), ("disconnect",)],
            instances[0].calls,
        )

    async def test_text_submit_sends_text_then_enter_and_repeated_keys(self):
        class Remote:
            def __init__(self):
                self.calls = []

            def send_text(self, value):
                self.calls.append(("text", value))

            def send_key_command(self, value):
                self.calls.append(("key", value))

        remote = Remote()
        queue = asyncio.Queue()
        worker = asyncio.create_task(PHONE_REMOTE.command_worker(queue, remote, PHONE_REMOTE.BridgeState()))
        await queue.put(("text_submit", "The Darkos'"))
        await queue.put(("keys", ("DPAD_RIGHT", 3)))
        await asyncio.wait_for(queue.join(), timeout=1)
        worker.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await worker
        self.assertEqual(
            [("text", "The Darkos'"), ("key", "ENTER"), ("key", "DPAD_RIGHT"), ("key", "DPAD_RIGHT"), ("key", "DPAD_RIGHT")],
            remote.calls,
        )


if __name__ == "__main__":
    unittest.main()
