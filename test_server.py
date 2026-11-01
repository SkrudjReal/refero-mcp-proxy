#!/usr/bin/env python3
"""
Test suite for refero_mcp_server.py
Validates all 14 tools and enforces strict pass/fail status with exit codes.
"""

import sys
import json
from pathlib import Path

# Import local module
import refero_mcp_server as s

def run_tests():
    print(f"Testing {s.SERVER_NAME} v{s.SERVER_VERSION}...")
    print(f"Total tools registered: {len(s.TOOLS)}")
    
    passed = []
    failed = []

    def check(name: str, condition: bool, detail: str = ""):
        if condition:
            passed.append(name)
            print(f"  [PASS] {name}{f': {detail}' if detail else ''}")
        else:
            failed.append(name)
            print(f"  [FAIL] {name}{f': {detail}' if detail else ''}")

    # 1. Styles search
    try:
        res = s.refero_search_styles("apple", limit=2)
        check("refero_search_styles", "styles" in res and len(res["styles"]) > 0, f"{res.get('count', 0)} styles found")
    except Exception as e:
        check("refero_search_styles", False, str(e))

    # 2. Get style
    try:
        if res.get("styles"):
            sid = res["styles"][0]["id"]
            res_style = s.refero_get_style(style_id=sid, response_format="md")
            has_spec = ("## North Star" in str(res_style) or "## Overview" in str(res_style)) and not str(res_style).startswith("# ERROR:")
            check("refero_get_style", has_spec, f"Style {sid} verified with valid parsed sections")
        else:
            check("refero_get_style", False, "No styles to test")
    except Exception as e:
        check("refero_get_style", False, str(e))

    # 3. Search screens
    screen_id = None
    try:
        res_screens = s.refero_search_screens("pricing", per_page=2)
        has_records = "records" in res_screens and len(res_screens["records"]) > 0
        has_embed = has_records and "markdown_embed" in res_screens["records"][0] and "direct_image_url" in res_screens["records"][0]
        check("refero_search_screens", has_records and has_embed, f"{len(res_screens.get('records', []))} screens retrieved with direct image links")
        if has_records:
            screen_id = res_screens["records"][0]["id"]
    except Exception as e:
        check("refero_search_screens", False, str(e))

    # 4. Get screen
    try:
        res_scr = s.refero_get_screen(screen_id=screen_id)
        is_match = isinstance(res_scr, dict) and res_scr.get("id") == screen_id
        check("refero_get_screen", is_match, f"Verified screen ID {screen_id}")
    except Exception as e:
        check("refero_get_screen", False, str(e))

    # 5. Get similar
    try:
        res_sim = s.refero_get_similar_screens(screen_id=screen_id, limit=2)
        check("refero_get_similar_screens", "records" in res_sim, f"{len(res_sim.get('records', []))} similar screens found")
    except Exception as e:
        check("refero_get_similar_screens", False, str(e))

    # 6. Get screen image & instructions
    try:
        res_img = s.refero_get_screen_image(screen_id=screen_id)
        has_full = "full_resolution_url" in res_img and "instructions_how_to_get_in_browser" in res_img
        check("refero_get_screen_image", has_full, "Full resolution CDN URL and browser guide present")
    except Exception as e:
        check("refero_get_screen_image", False, str(e))

    # 7. Image instructions tool
    try:
        res_inst = s.refero_get_image_instructions()
        has_inst = "direct_cdn_architecture" in res_inst and "browser_paywall_bypass_method" in res_inst
        check("refero_get_image_instructions", has_inst, "Complete CDN and console bypass snippets ready")
    except Exception as e:
        check("refero_get_image_instructions", False, str(e))

    # 8. Download screen test
    try:
        test_out = Path("test_download")
        res_dl = s.refero_download_screen(screen_id=screen_id, output_dir=str(test_out))
        dl_ok = res_dl.get("total_downloaded") == 1
        check("refero_download_screen", dl_ok, f"Downloaded {res_dl.get('files', [{}])[0].get('file_size_kb', 0)} KB")
        if test_out.exists():
            for f in test_out.glob("*"):
                f.unlink()
            test_out.rmdir()
    except Exception as e:
        check("refero_download_screen", False, str(e))

    # 9. Get screen content
    try:
        res_cnt = s.refero_get_screen_content(screen_id=screen_id)
        has_cnt = "dimensions" in res_cnt and "colors_palette_rgb" in res_cnt
        check("refero_get_screen_content", has_cnt, f"Extracted palette with {len(res_cnt.get('colors_palette_rgb', []))} colors")
    except Exception as e:
        check("refero_get_screen_content", False, str(e))

    # 10. Search flows
    flow_id = None
    try:
        res_flows = s.refero_search_flows("onboarding")
        has_fl = "records" in res_flows and len(res_flows["records"]) > 0
        check("refero_search_flows", has_fl, f"{len(res_flows.get('records', []))} flows discovered")
        if has_fl:
            flow_id = res_flows["records"][0]["id"]
    except Exception as e:
        check("refero_search_flows", False, str(e))

    # 11. Get flow
    try:
        if flow_id:
            res_fl = s.refero_get_flow(flow_id=flow_id)
            has_steps = "screenshots" in res_fl and len(res_fl.get("screenshots", [])) > 0
            check("refero_get_flow", has_steps, f"Flow {flow_id} with {len(res_fl.get('screenshots', []))} steps")
        else:
            check("refero_get_flow", False, "No flow ID available")
    except Exception as e:
        check("refero_get_flow", False, str(e))

    # 12. Search site
    try:
        res_site = s.refero_search_site("linear", per_page=2)
        has_site = "records" in res_site and len(res_site["records"]) > 0
        check("refero_search_site", has_site, f"{res_site.get('total_count', 0)} sites matched")
    except Exception as e:
        check("refero_search_site", False, str(e))

    # 13. Search app
    try:
        res_app = s.refero_search_app("revolut", per_page=2)
        has_app = "records" in res_app and len(res_app["records"]) > 0
        check("refero_search_app", has_app, f"{len(res_app.get('records', []))} iOS apps matched")
    except Exception as e:
        check("refero_search_app", False, str(e))

    # 14. Static catalog
    try:
        res_cat = s.refero_get_catalog("sites", search="stripe", limit=2)
        has_cat = "results" in res_cat and len(res_cat["results"]) > 0
        check("refero_get_catalog", has_cat, f"{res_cat.get('total_in_catalog', 0)} total catalog entries")
    except Exception as e:
        check("refero_get_catalog", False, str(e))

    print("\n" + "=" * 50)
    print(f"Results: {len(passed)}/{len(passed) + len(failed)} passed")
    if failed:
        print(f"FAILED tests ({len(failed)}): {', '.join(failed)}")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED SUCCESSFULLY.")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
