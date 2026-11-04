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
            self.assertEqual(
                [("keys", ("HOME", 1)), ("text_submit", "Akwaaba — hello 👋")],
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
        docs = (ROOT / "docs/phone-remote.md").read_text(encoding="utf-8")
        self.assertIn("Network ADB remains off", docs)
        self.assertIn("focused", docs)
        self.assertIn("1,000 characters", docs)
        self.assertNotIn("WLED", docs)


class CommandWorkerTest(unittest.IsolatedAsyncioTestCase):
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
