"""Deterministic stdlib tests; no account, network or existing mirror required."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import mirror_refero as mirror
import refero_mcp_server as s


class ServerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="refero-regression-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        state = patch.multiple(
            s, DATA_DIR=self.data, DB_PATH=self.data / "refero_local.db", OFFLINE_MODE=True,
            STYLE_CACHE={}, STYLE_CATALOG_LOADED=False, CATALOG_APPS_CACHE=None,
            CATALOG_SITES_CACHE=None, SCREEN_CACHE_BY_ID={}, SCREEN_CACHE_BY_UUID={},
            RAW_SITES_CACHE=None,
        )
        state.start()
        self.addCleanup(state.stop)
        network = patch.object(s.urllib.request, "urlopen", side_effect=AssertionError("Unexpected network call"))
        self.network = network.start()
        self.addCleanup(network.stop)

    def fixture(self):
        with patch.multiple(mirror, DATA_DIR=self.data, DB_PATH=s.DB_PATH):
            conn = mirror.init_database()
        catalogs = self.data / "catalogs"
        catalogs.mkdir()
        (catalogs / "apps.json").write_text(json.dumps([{"id": 7, "name": "Revolut", "description": "Bank"}]), encoding="utf-8")
        (catalogs / "sites.json").write_text(json.dumps([{"name": "Stripe", "domain": "stripe.com"}]), encoding="utf-8")
        records = []
        with conn:
            for sid in (1, 2):
                uuid = f"00000000-0000-0000-0000-{sid:012d}"
                url = f"https://images.refero.design/screenshots/linear.app/desktop/{uuid}/0.jpg"
                record = {"id": sid, "uuid": uuid, "site": {"name": "Linear", "domain": "linear.app"},
                          "domain": "linear.app", "url": [url], "height": 100, "width": 100,
                          "colors": [], "fonts": [], "page_title": "Pricing"}
                records.append(record)
                conn.execute("INSERT INTO screens (id, uuid, platform, site_name, domain, page_title, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (str(sid), uuid, "web", "Linear", "linear.app", "Pricing", json.dumps(record)))
                image = self.data / "media" / "screenshots" / "linear.app" / "desktop" / uuid / "0.jpg"
                image.parent.mkdir(parents=True)
                image.write_bytes(b"cached image" * 100)
                conn.execute("INSERT INTO media_queue (url, screen_id, local_path, downloaded) VALUES (?, ?, ?, 1)",
                             (url, str(sid), str(image)))
            flow = {"id": 3, "title": "Onboarding", "screenshots": records}
            conn.execute("INSERT INTO flows (id, platform, title, description, raw_json) VALUES (?, ?, ?, ?, ?)",
                         ("3", "web", "Onboarding", "Signup", json.dumps(flow)))
        conn.close()
        (catalogs / "sites_full.json").write_text(json.dumps([{"name": "Linear", "domain": "linear.app", "screenshots": records}]), encoding="utf-8")
        styles = self.data / "styles"
        spec = styles / "style-1"
        spec.mkdir(parents=True)
        (styles / "index.json").write_text(json.dumps([{"id": "style-1", "siteName": "Apple", "url": "https://apple.com"}]), encoding="utf-8")
        (spec / "DESIGN.md").write_text("# Apple\n## Overview\nMinimal", encoding="utf-8")
        (spec / "spec.json").write_text(json.dumps({"meta": {"siteName": "Apple"}, "designSystem": {}}), encoding="utf-8")

    def call(self, name, args):
        return s.process_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": name, "arguments": args}})

    def test_all_tools_work_offline_without_network(self):
        self.fixture()
        cases = {
            "refero_search_styles": {"query": "apple"},
            "refero_get_style": {"style_id": "style-1"},
            "refero_search_screens": {"query": "pricing"},
            "refero_get_screen": {"screen_id": 1},
            "refero_get_similar_screens": {"screen_id": 1},
            "refero_get_screen_image": {"screen_id": 1},
            "refero_download_screen": {"screen_id": 1, "output_dir": str(self.root / "output")},
            "refero_get_image_instructions": {},
            "refero_get_screen_content": {"screen_id": 1},
            "refero_search_flows": {"query": "onboarding"},
            "refero_get_flow": {"flow_id": 3},
            "refero_search_site": {"query": "linear"},
            "refero_search_app": {"query": "revolut"},
            "refero_get_catalog": {"catalog_type": "sites"},
        }
        self.assertEqual(set(cases), {t["name"] for t in s.TOOLS})
        for name, args in cases.items():
            with self.subTest(tool=name):
                response = self.call(name, args)
                self.assertNotIn("error", response)
                self.assertFalse(response["result"]["isError"], response)
        self.network.assert_not_called()
        self.assertEqual((self.root / "output" / "screen_1.jpg").read_bytes(), b"cached image" * 100)

    def test_missing_offline_media_and_catalog_are_errors(self):
        self.fixture()
        for path in (self.data / "media").rglob("*.jpg"):
            path.unlink()
        self.assertTrue(self.call("refero_download_screen", {"screen_id": 1, "output_dir": str(self.root / "out")})["result"]["isError"])
        (self.data / "catalogs" / "apps.json").unlink()
        self.assertTrue(self.call("refero_search_app", {"query": "x"})["result"]["isError"])
        self.assertIn("error", s.http_get("https://example.test"))
        self.network.assert_not_called()

    def test_offline_app_pagination(self):
        self.fixture()
        apps = [{"name": f"App {i}"} for i in range(3)]
        (self.data / "catalogs" / "apps.json").write_text(json.dumps(apps), encoding="utf-8")
        result = s.refero_search_app("App", page=2, per_page=2)
        self.assertEqual(result["records"], apps[2:])
        self.assertEqual(result["total_count"], 3)

    def test_missing_offline_catalogs_and_json_spec_are_errors(self):
        for name, args in (("refero_search_styles", {}),
                           ("refero_search_site", {"query": "x"}),
                           ("refero_get_catalog", {}),
                           ("refero_get_style", {"style_id": "missing", "response_format": "json"})):
            with self.subTest(tool=name):
                result = self.call(name, args)["result"]
                self.assertTrue(result["isError"])
                if name == "refero_get_style":
                    self.assertIn("error", json.loads(result["content"][0]["text"]))
        self.network.assert_not_called()

    def test_offline_media_can_be_read_after_moving_mirror(self):
        self.fixture()
        conn = s.get_db_conn()
        with conn:
            conn.execute("UPDATE media_queue SET local_path = ?", ("/missing/old/machine/image.jpg",))
        conn.close()
        result = s.refero_download_screen(1, output_dir=str(self.root / "moved-output"))
        self.assertEqual(result["total_failed"], 0)
        self.assertEqual((self.root / "moved-output" / "screen_1.jpg").read_bytes(), b"cached image" * 100)
        self.network.assert_not_called()

    def test_download_preserves_existing_file_on_network_failure(self):
        target = self.root / "screen_1.jpg"
        target.write_bytes(b"original")
        with patch.object(s, "OFFLINE_MODE", False), patch.object(s, "refero_get_screen_image", return_value={"all_slices_urls": ["https://example.test/image"]}):
            self.network.side_effect = OSError("Network unavailable")
            result = s.refero_download_screen(1, output_dir=str(self.root))
        self.assertEqual(result["total_failed"], 1)
        self.assertEqual(target.read_bytes(), b"original")

    def test_download_is_atomic_on_partial_response_and_success(self):
        target = self.root / "image.jpg"
        target.write_bytes(b"original")
        with patch.object(s, "OFFLINE_MODE", False):
            with io.BytesIO(b"partial") as source:
                self.network.side_effect = None
                self.network.return_value = source
                with patch.object(source, "read", side_effect=[b"partial", OSError("Connection closed")]):
                    with self.assertRaises(OSError):
                        s.download_file("https://example.test/image", target)
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(list(self.root.glob("*.tmp")), [])
            self.network.return_value = io.BytesIO(b"")
            with self.assertRaises(ValueError):
                s.download_file("https://example.test/image", target)
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(list(self.root.glob("*.tmp")), [])
            self.network.return_value = io.BytesIO(b"replacement")
            self.assertEqual(s.download_file("https://example.test/image", target), 11)
            self.assertEqual(target.read_bytes(), b"replacement")

    def test_invalid_arguments_and_unknown_tools(self):
        cases = [("missing", {}), ("refero_search_screens", {}),
                 ("refero_search_screens", {"query": "x", "page": True}),
                 ("refero_search_screens", {"query": "x", "page": 0}),
                 ("refero_search_screens", {"query": "x", "per_page": 51}),
                 ("refero_search_screens", {"query": "x", "platform": "invalid"}),
                 ("refero_get_screen", {"screen_ids": []}),
                 ("refero_get_screen", {"screen_id": "../file"}),
                 ("refero_get_screen", {"screen_id": 1, "screen_ids": [2]}),
                 ("refero_get_screen", {"screen_id": 1, "extra": 2}),
                 ("refero_get_screen", None)]
        for name, args in cases:
            with self.subTest(name=name, args=args):
                self.assertEqual(self.call(name, args)["error"]["code"], -32602)
        self.network.assert_not_called()

    def test_execution_errors_marked_and_process_survives(self):
        for data in ({"error": "API failure"}, [{"error": "not found"}], "# ERROR: Missing spec",
                     {"total_failed": 1, "files": []}):
            with self.subTest(data=data), patch.object(s, "handle_call", return_value=data):
                self.assertTrue(self.call("refero_get_screen", {"screen_id": 1})["result"]["isError"])
        with patch.object(s, "handle_call", side_effect=OSError("Disk full")):
            self.assertTrue(self.call("refero_get_screen", {"screen_id": 1})["result"]["isError"])
        self.assertEqual(s.process_request({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"], {})

    def test_notifications_do_not_receive_responses(self):
        for method in ("notifications/initialized", "notifications/cancelled", "notifications/unknown", "ping"):
            self.assertIsNone(s.process_request({"jsonrpc": "2.0", "method": method}))

    def test_stdio_recovers_from_malformed_messages(self):
        ping = {"jsonrpc": "2.0", "id": 10, "method": "ping"}
        messages = ["{broken", "[]", "null", json.dumps({**ping, "params": None}),
                    json.dumps({"jsonrpc": "2.0", "method": "notifications/cancelled"}),
                    json.dumps([ping, {"jsonrpc": "2.0", "method": "notifications/initialized"}]),
                    json.dumps({**ping, "id": "проверка"}, ensure_ascii=False)]
        env = dict(os.environ, REFERO_OFFLINE="1")
        result = subprocess.run([sys.executable, str(Path(s.__file__).resolve())],
                                input="\n".join(messages) + "\n", capture_output=True,
                                text=True, encoding="utf-8", timeout=10, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r["error"]["code"] for r in responses[:4]], [-32700, -32600, -32600, -32602])
        self.assertEqual(responses[4], [{"jsonrpc": "2.0", "id": 10, "result": {}}])
        self.assertEqual(responses[5]["result"], {})
        self.assertEqual(responses[5]["id"], "проверка")
        self.assertEqual(len(responses), 6)

    def test_live_smoke_uses_only_its_temporary_directory(self):
        import test_server
        self.fixture()
        sentinel = self.root / "test_download" / "keep.txt"
        sentinel.parent.mkdir()
        sentinel.write_text("keep", encoding="utf-8")
        old_cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, old_cwd)
        with tempfile.TemporaryDirectory(prefix="refero-smoke-") as tmp:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                test_server.run_tests(Path(tmp))
            self.assertEqual(result.exception.code, 0)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
