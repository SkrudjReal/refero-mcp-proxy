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
            RAW_SITES_CACHE=None, ALL_PRODUCTS_CACHE=None, ALL_LINKS_LOADED=False,
            ALL_LINKS_LOADED_PATH=None, LOCAL_FLOWS_INDEX=None, LOCAL_FLOWS_INDEX_DIR=None,
        )
        state.start()
        self.addCleanup(state.stop)
        env_patch = patch.dict(os.environ, {"REFERO_DATA_DIR": ""}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
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

    def test_zero_config_all_links_json_fallback(self):
        bundle = {
            "products": [
                {
                    "id": 101, "type": "web_site", "name": "Linear",
                    "domain_or_store": "linear.app", "categories": ["Productivity"],
                    "icon_url": "https://images.refero.design/icon.png", "total_images": 2,
                    "image_urls": [
                        "https://images.refero.design/screenshots/linear.app/desktop/aaaaaaaa-0000-0000-0000-000000000001/0.jpg",
                        "https://images.refero.design/screenshots/linear.app/desktop/aaaaaaaa-0000-0000-0000-000000000002/0.jpg",
                    ],
                },
                {
                    "id": 202, "type": "ios_app", "name": "Notion",
                    "domain_or_store": "apps.apple.com/notion", "categories": ["Notes"],
                    "icon_url": "https://images.refero.design/icon2.png", "total_images": 1,
                    "image_urls": [
                        "https://images.refero.design/app_screenshots/202/bbbbbbbb-0000-0000-0000-000000000001/0.jpg",
                    ],
                },
            ]
        }
        (self.root / "refero_all_links_images.json").write_text(json.dumps(bundle), encoding="utf-8")

        site_res = s.refero_search_site("linear")
        self.assertNotIn("error", site_res)
        self.assertEqual(site_res["total_count"], 1)
        self.assertEqual(site_res["records"][0]["name"], "Linear")

        cat_res = s.refero_get_catalog("apps", search="notion")
        self.assertNotIn("error", cat_res)
        self.assertEqual(cat_res["total_in_catalog"], 1)

        scr_res = s.refero_search_screens("linear", platform="web", per_page=5)
        self.assertNotIn("error", scr_res)
        self.assertEqual(len(scr_res["records"]), 2)

        # Flows must NOT crash with NameError when fleet/flows is absent
        flow_res = s.refero_search_flows("onboarding", platform="web")
        self.assertIn("error", flow_res)
        self.network.assert_not_called()

    def test_refero_data_dir_cas_flows_and_styles(self):
        import hashlib
        rdir = self.root / "mirror"
        # Styles without index.json
        st_dir = rdir / "styles" / "style-uuid-1"
        st_dir.mkdir(parents=True)
        (st_dir / "DESIGN.md").write_text("# DESIGN SPEC: Stripe\n## Overview\nClean", encoding="utf-8")
        (st_dir / "spec.json").write_text(json.dumps({"meta": {"siteName": "Stripe", "url": "https://stripe.com"}, "designSystem": {}}), encoding="utf-8")

        # Fleet flows (one web, one ios)
        fl_dir = rdir / "fleet" / "flows"
        fl_dir.mkdir(parents=True)
        (fl_dir / "10.json").write_text(json.dumps({"id": 10, "name": "Checkout Flow", "site": {"name": "Stripe", "domain": "stripe.com"}, "screenshots": []}), encoding="utf-8")
        (fl_dir / "11.json").write_text(json.dumps({"id": 11, "name": "Checkout Mobile", "app": {"name": "Revolut"}, "screenshots": []}), encoding="utf-8")

        # Fleet CAS image + _catalogs/sites_available.json
        img_url = "https://images.refero.design/screenshots/stripe.com/desktop/cccccccc-0000-0000-0000-000000000001/0.jpg"
        sha = hashlib.sha256(img_url.encode("utf-8")).hexdigest()
        cas_img = rdir / "fleet" / "images" / sha[:2] / f"{sha}.jpg"
        cas_img.parent.mkdir(parents=True)
        cas_img.write_bytes(b"cas-image-bytes" * 100)

        cat_dir = rdir / "_catalogs"
        cat_dir.mkdir(parents=True)
        (cat_dir / "sites_available.json").write_text(json.dumps([
            {"name": "Stripe", "domain": "stripe.com", "screenshots": [
                {"id": 999, "uuid": "cccccccc-0000-0000-0000-000000000001", "url": [img_url], "page_title": "Checkout"}
            ]}
        ]), encoding="utf-8")

        with patch.dict(os.environ, {"REFERO_DATA_DIR": str(rdir)}):
            # Styles search + get without index.json
            st_search = s.refero_search_styles("stripe")
            self.assertEqual(st_search["count"], 1)
            st_md = s.refero_get_style("style-uuid-1", response_format="md")
            self.assertIn("DESIGN SPEC: Stripe", st_md)

            # Flows search respects platform filter
            web_flows = s.refero_search_flows("checkout", platform="web")
            self.assertEqual(web_flows["total_records"], 1)
            self.assertEqual(web_flows["records"][0]["id"], 10)
            ios_flows = s.refero_search_flows("checkout", platform="ios")
            self.assertEqual(ios_flows["total_records"], 1)
            self.assertEqual(ios_flows["records"][0]["id"], 11)

            # Screen cold offline lookup + CAS image detection + CAS download
            scr = s.refero_get_screen(999)
            self.assertEqual(scr["id"], 999)
            img_info = s.refero_get_screen_image(999)
            self.assertTrue(img_info["is_locally_cached"])
            self.assertEqual(img_info["local_files"][0]["storage"], "cas")
            dl = s.refero_download_screen(999, output_dir=str(self.root / "cas_out"))
            self.assertEqual(dl["total_downloaded"], 1)
            self.assertEqual((self.root / "cas_out" / "screen_999.jpg").read_bytes(), b"cas-image-bytes" * 100)

        self.network.assert_not_called()

    def test_configure_clients_idempotent_toml_and_opencode_schema(self):
        import configure_clients as cc
        fake_home = self.root / "home"
        fake_home.mkdir()
        srv = Path(r"C:\Projects\refero-mcp-proxy\refero_mcp_server.py")
        py = r"C:\Python312\python.exe"
        ddir = r"D:\Datasets\refero-full-data"

        with patch.object(cc, "get_home_dir", return_value=fake_home):
            # Run Codex configuration TWICE to verify re.sub does not corrupt backslashes
            cc.configure_codex(srv, py, data_dir=ddir, offline=True)
            cc.configure_codex(srv, py, data_dir=ddir, offline=True)
            toml_text = (fake_home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn(r'command = "C:\\Python312\\python.exe"', toml_text)
            self.assertIn(r'REFERO_DATA_DIR = "D:\\Datasets\\refero-full-data"', toml_text)
            self.assertEqual(toml_text.count("[mcp_servers.refero]"), 1)

            # Verify OpenCode uses "environment" (not "env")
            cc.configure_opencode(srv, py, data_dir=ddir, offline=True)
            oc_cfg = json.loads((fake_home / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
            self.assertIn("environment", oc_cfg["mcp"]["refero"])
            self.assertNotIn("env", oc_cfg["mcp"]["refero"])
            self.assertEqual(oc_cfg["mcp"]["refero"]["environment"]["REFERO_OFFLINE"], "1")

    def test_unpack_dataset_blocks_zip_slip(self):
        import zipfile
        import unpack_dataset as ud
        bad_zip = self.root / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("../escape.txt", "boom")
        with self.assertRaises(ValueError):
            ud.extract_archive(bad_zip, self.root / "dest")


if __name__ == "__main__":
    unittest.main()
