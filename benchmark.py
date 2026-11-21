#!/usr/bin/env python3
"""
Performance benchmark suite for refero-mcp-proxy.
Measures genuine latency: Remote Live API/CDN vs Local Mirror (CAS / JSON / Styles / Flows).
Every measurement asserts a valid, non-error payload so failures are never timed as successes.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import refero_mcp_server as s


def _clear_all_caches():
    s.RAW_SITES_CACHE = None
    s.CATALOG_SITES_CACHE = None
    s.CATALOG_APPS_CACHE = None
    s.STYLE_CACHE.clear()
    s.STYLE_CATALOG_LOADED = False
    s.SCREEN_CACHE_BY_ID.clear()
    s.SCREEN_CACHE_BY_UUID.clear()
    s.ALL_PRODUCTS_CACHE = None
    s.ALL_LINKS_LOADED = False
    s.ALL_LINKS_LOADED_PATH = None
    s.LOCAL_FLOWS_INDEX = None
    s.LOCAL_FLOWS_INDEX_DIR = None


def run_benchmarks():
    orig_data_dir = s.DATA_DIR
    orig_db_path = s.DB_PATH
    orig_env_rdir = os.environ.get("REFERO_DATA_DIR")
    local_rdir = s.get_refero_data_dir()

    print("=" * 68)
    print(" Refero MCP Proxy: Remote Live API vs Local Mirror Benchmarks")
    print("=" * 68)
    if local_rdir:
        print(f"Detected local mirror: {local_rdir}")
    else:
        print("[WARN] Local full mirror not detected (set REFERO_DATA_DIR for full CAS/Styles/Flows tests).")

    results = []

    with tempfile.TemporaryDirectory(prefix="refero-bench-") as tmp:
        tmp_path = Path(tmp)
        empty_data = tmp_path / "empty_data"
        empty_data.mkdir()

        def set_remote_mode():
            _clear_all_caches()
            s.DATA_DIR = empty_data
            s.DB_PATH = empty_data / "missing.db"
            os.environ["REFERO_DATA_DIR"] = ""
            s.OFFLINE_MODE = False

        def set_local_mode():
            _clear_all_caches()
            s.DATA_DIR = orig_data_dir
            s.DB_PATH = orig_db_path
            if orig_env_rdir is not None:
                os.environ["REFERO_DATA_DIR"] = orig_env_rdir
            else:
                os.environ.pop("REFERO_DATA_DIR", None)
            s.OFFLINE_MODE = True

        # ------------------------------------------------------------------
        # 1. Product / Site Search (`refero_search_site`)
        # ------------------------------------------------------------------
        print("\n[1/5] Product / Site Search (`refero_search_site('linear')`)...", flush=True)
        set_remote_mode()
        t0 = time.perf_counter()
        res_rem = s.refero_search_site("linear")
        rem_site = (time.perf_counter() - t0) * 1000
        assert isinstance(res_rem, dict) and res_rem.get("total_count", 0) > 0, f"Remote site search failed: {res_rem}"

        set_local_mode()
        # Cold load (includes JSON parse) + warm query
        t0 = time.perf_counter()
        res_loc = s.refero_search_site("linear")
        loc_site_cold = (time.perf_counter() - t0) * 1000
        assert isinstance(res_loc, dict) and res_loc.get("total_count", 0) > 0, f"Local site search failed: {res_loc}"

        t0 = time.perf_counter()
        res_loc_warm = s.refero_search_site("linear")
        loc_site_warm = (time.perf_counter() - t0) * 1000
        assert res_loc_warm.get("total_count", 0) > 0
        sp_site = rem_site / max(loc_site_warm, 0.001)
        results.append(("Product / Site Search (`refero_search_site`)", rem_site, loc_site_warm, sp_site))
        print(f"      Remote: {rem_site:.1f} ms | Local: {loc_site_warm:.2f} ms warm ({loc_site_cold:.1f} ms cold) -> {sp_site:.0f}x faster")

        # ------------------------------------------------------------------
        # 2. UX Journey Flow Retrieval (`refero_get_flow`)
        # ------------------------------------------------------------------
        print("\n[2/5] UX Journey Flow Retrieval (`refero_get_flow(10006)`)...", flush=True)
        set_remote_mode()
        t0 = time.perf_counter()
        res_rem_flow = s.refero_get_flow(10006)
        rem_flow = (time.perf_counter() - t0) * 1000
        assert isinstance(res_rem_flow, dict) and res_rem_flow.get("step_count", 0) > 0, f"Remote flow failed: {res_rem_flow}"

        set_local_mode()
        t0 = time.perf_counter()
        res_loc_flow = s.refero_get_flow(10006)
        loc_flow = (time.perf_counter() - t0) * 1000
        assert isinstance(res_loc_flow, dict) and res_loc_flow.get("step_count", 0) > 0, f"Local flow failed: {res_loc_flow}"
        sp_flow = rem_flow / max(loc_flow, 0.001)
        results.append(("UX Journey Flow (`refero_get_flow`)", rem_flow, loc_flow, sp_flow))
        print(f"      Remote: {rem_flow:.1f} ms | Local: {loc_flow:.2f} ms ({res_loc_flow['step_count']} steps) -> {sp_flow:.0f}x faster")

        # ------------------------------------------------------------------
        # 3. Design System Spec (`refero_get_style`)
        # ------------------------------------------------------------------
        print("\n[3/5] Design System Spec (`refero_get_style` Apple)...", flush=True)
        style_id = "a73148b9-449b-42cd-9f38-86ef694f500e"
        set_remote_mode()
        t0 = time.perf_counter()
        res_rem_style = s.refero_get_style(style_id, response_format="md")
        rem_style = (time.perf_counter() - t0) * 1000
        assert isinstance(res_rem_style, str) and not res_rem_style.startswith("# ERROR:") and len(res_rem_style) > 200, \
            f"Remote style failed: {str(res_rem_style)[:120]}"

        set_local_mode()
        t0 = time.perf_counter()
        res_loc_style = s.refero_get_style(style_id, response_format="md")
        loc_style = (time.perf_counter() - t0) * 1000
        assert isinstance(res_loc_style, str) and not res_loc_style.startswith("# ERROR:") and len(res_loc_style) > 200, \
            f"Local style failed: {str(res_loc_style)[:120]}"
        sp_style = rem_style / max(loc_style, 0.001)
        results.append(("Design System Spec (`refero_get_style`)", rem_style, loc_style, sp_style))
        print(f"      Remote: {rem_style:.1f} ms | Local: {loc_style:.2f} ms ({len(res_loc_style)} chars) -> {sp_style:.0f}x faster")

        # ------------------------------------------------------------------
        # 4. Screenshot Asset Resolution (CloudFront CDN vs Local CAS)
        # ------------------------------------------------------------------
        print("\n[4/5] Screenshot Asset Resolution (`download_file` CDN vs CAS)...", flush=True)
        img_url = "https://images.refero.design/screenshots/monday.com/desktop/01a7f2e1-5180-4c0d-bcaa-55d274d905db/0.jpg"
        set_remote_mode()
        rem_dst = tmp_path / "rem.jpg"
        t0 = time.perf_counter()
        rem_bytes = s.download_file(img_url, rem_dst)
        rem_img = (time.perf_counter() - t0) * 1000
        assert rem_bytes > 10_000 and rem_dst.is_file(), "Remote CDN download failed"

        set_local_mode()
        loc_dst = tmp_path / "loc.jpg"
        t0 = time.perf_counter()
        loc_bytes = s.download_file(img_url, loc_dst)
        loc_img = (time.perf_counter() - t0) * 1000
        assert loc_bytes == rem_bytes and loc_dst.is_file(), f"Local CAS copy mismatch ({loc_bytes} vs {rem_bytes})"
        sp_img = rem_img / max(loc_img, 0.001)
        results.append(("Screenshot Asset (`download_file` CAS)", rem_img, loc_img, sp_img))
        print(f"      Remote: {rem_img:.1f} ms | Local: {loc_img:.2f} ms ({loc_bytes / 1024:.1f} KB) -> {sp_img:.0f}x faster")

        # ------------------------------------------------------------------
        # 5. Catalog Query (`refero_get_catalog`)
        # ------------------------------------------------------------------
        print("\n[5/5] Catalog Query (`refero_get_catalog('sites')`)...", flush=True)
        set_remote_mode()
        t0 = time.perf_counter()
        res_rem_cat = s.refero_get_catalog(catalog_type="sites", limit=10)
        rem_cat = (time.perf_counter() - t0) * 1000
        assert isinstance(res_rem_cat, dict) and res_rem_cat.get("total_in_catalog", 0) > 0, f"Remote catalog failed: {res_rem_cat}"

        set_local_mode()
        t0 = time.perf_counter()
        res_loc_cat = s.refero_get_catalog(catalog_type="sites", limit=10)
        loc_cat = (time.perf_counter() - t0) * 1000
        assert isinstance(res_loc_cat, dict) and res_loc_cat.get("total_in_catalog", 0) > 0, f"Local catalog failed: {res_loc_cat}"
        sp_cat = rem_cat / max(loc_cat, 0.001)
        results.append(("Catalog Load (`refero_get_catalog`)", rem_cat, loc_cat, sp_cat))
        print(f"      Remote: {rem_cat:.1f} ms | Local: {loc_cat:.2f} ms ({res_loc_cat['total_in_catalog']} sites) -> {sp_cat:.0f}x faster")

    # Restore state
    s.DATA_DIR = orig_data_dir
    s.DB_PATH = orig_db_path
    if orig_env_rdir is not None:
        os.environ["REFERO_DATA_DIR"] = orig_env_rdir
    else:
        os.environ.pop("REFERO_DATA_DIR", None)

    print("\n" + "=" * 80)
    print(" BENCHMARK RESULTS TABLE (Verified Payloads)")
    print("=" * 80)
    print("| Operation | Remote Live API | Local Mirror | Acceleration |")
    print("| :--- | :--- | :--- | :--- |")
    for name, r_ms, l_ms, sp in results:
        print(f"| **{name}** | {r_ms:.1f} ms | {l_ms:.2f} ms | **{sp:.0f}x faster** |")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmarks()
