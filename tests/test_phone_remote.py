"""The phone bridge stays local, authenticated and independent of network ADB."""

import importlib.util
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
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "phone_remote.py"
SPEC = importlib.util.spec_from_file_location("phone_remote", TOOL)
PHONE_REMOTE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = PHONE_REMOTE
SPEC.loader.exec_module(PHONE_REMOTE)


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


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

    def test_wled_url_rejects_non_http_and_credentials(self):
        self.assertEqual("http://192.168.1.60", PHONE_REMOTE.parse_wled_url("http://192.168.1.60/"))
        for value in ("file:///tmp/light", "ftp://192.168.1.60", "http://user:pass@192.168.1.60"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PHONE_REMOTE.parse_wled_url(value)

    def test_wled_payload_clamps_brightness_and_contains_rgb(self):
        client = PHONE_REMOTE.WledClient("http://192.168.1.60")
        with mock.patch.object(PHONE_REMOTE.urllib.request, "urlopen", return_value=_Response()) as opened:
            client.set_color((109, 103, 174), 999)
        request = opened.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(255, payload["bri"])
        self.assertEqual([109, 103, 174], payload["seg"][0]["col"][0])
        self.assertEqual("http://192.168.1.60/json/state", request.full_url)

    def test_app_colours_include_home_and_dock_apps(self):
        self.assertEqual((109, 103, 174), PHONE_REMOTE.app_color("com.gathin.tvhome"))
        self.assertEqual((229, 9, 20), PHONE_REMOTE.app_color("com.netflix.ninja"))
        self.assertEqual((29, 185, 84), PHONE_REMOTE.app_color("com.spotify.tv.android"))

    def test_web_page_has_no_external_assets_and_uses_token_base(self):
        page = (ROOT / "tools/phone-remote/index.html").read_text(encoding="utf-8")
        self.assertIn("__REMOTE_BASE__", page)
        self.assertIn('post("api/key"', page)
        self.assertNotIn("<script src=", page)
        self.assertNotIn("<link ", page)

    def test_http_server_requires_random_path_and_accepts_allowlisted_key(self):
        sink = _Sink()
        server = PHONE_REMOTE.RemoteServer(
            ("127.0.0.1", 0), b"base=__REMOTE_BASE__", "secret-token", PHONE_REMOTE.BridgeState(), sink
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
            self.assertEqual([("key", "HOME")], sink.commands)
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
        self.assertIn("USB only for power", docs)


if __name__ == "__main__":
    unittest.main()
