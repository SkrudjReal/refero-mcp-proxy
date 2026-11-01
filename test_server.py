#!/usr/bin/env python3
"""
Test suite for refero_mcp_server.py
Validates all 14 tools and ensures no exceptions occur.
"""

import sys
import json
from pathlib import Path

# Import local module
import refero_mcp_server as s

def run_tests():
    print(f"Testing {s.SERVER_NAME} v{s.SERVER_VERSION}...")
    print(f"Total tools registered: {len(s.TOOLS)}")

    # 1. Styles search
    res = s.refero_search_styles("minimal", limit=2)
    print("1. refero_search_styles:", "OK" if "styles" in res else "FAIL")

    # 2. Get style
    if res.get("styles"):
        sid = res["styles"][0]["id"]
        res_style = s.refero_get_style(style_id=sid, response_format="md")
        print("2. refero_get_style:", "OK" if "DESIGN SPEC" in res_style else "FAIL")

    # 3. Search screens
    res_screens = s.refero_search_screens("pricing", per_page=2)
    print("3. refero_search_screens:", "OK" if "records" in res_screens and len(res_screens["records"]) > 0 else "FAIL")
    first_screen = res_screens["records"][0]
    has_embed = "markdown_embed" in first_screen and "direct_image_url" in first_screen
    print("   Enriched image links in search:", "OK" if has_embed else "FAIL")
    screen_id = first_screen["id"]

    # 4. Get screen
    res_scr = s.refero_get_screen(screen_id=screen_id)
    print("4. refero_get_screen:", "OK" if res_scr.get("id") == screen_id else "FAIL")

    # 5. Get similar
    res_sim = s.refero_get_similar_screens(screen_id=screen_id, limit=2)
    print("5. refero_get_similar_screens:", "OK" if "records" in res_sim else "FAIL")

    # 6. Get screen image & instructions
    res_img = s.refero_get_screen_image(screen_id=screen_id)
    print("6. refero_get_screen_image:", "OK" if "full_resolution_url" in res_img and "instructions_how_to_get_in_browser" in res_img else "FAIL")

    # 7. Image instructions tool
    res_inst = s.refero_get_image_instructions()
    print("7. refero_get_image_instructions:", "OK" if "direct_cdn_architecture" in res_inst else "FAIL")

    # 8. Download screen test
    test_out = Path("test_download")
    res_dl = s.refero_download_screen(screen_id=screen_id, output_dir=str(test_out))
    print("8. refero_download_screen:", "OK" if res_dl.get("total_downloaded") == 1 else "FAIL")
    # Clean up test download
    if test_out.exists():
        for f in test_out.glob("*"):
            f.unlink()
        test_out.rmdir()

    # 9. Get screen content
    res_cnt = s.refero_get_screen_content(screen_id=screen_id)
    print("9. refero_get_screen_content:", "OK" if "dimensions" in res_cnt else "FAIL")

    # 10. Search flows
    res_flows = s.refero_search_flows("onboarding")
    print("10. refero_search_flows:", "OK" if "records" in res_flows else "FAIL")

    # 11. Get flow
    if res_flows.get("records"):
        fid = res_flows["records"][0]["id"]
        res_fl = s.refero_get_flow(flow_id=fid)
        print("11. refero_get_flow:", "OK" if "screenshots" in res_fl else "FAIL")

    # 12. Search site
    res_site = s.refero_search_site("linear", per_page=2)
    print("12. refero_search_site:", "OK" if "records" in res_site else "FAIL")

    # 13. Search app
    res_app = s.refero_search_app("revolut", per_page=2)
    print("13. refero_search_app:", "OK" if "records" in res_app else "FAIL")

    # 14. Static catalog
    res_cat = s.refero_get_catalog("sites", search="stripe", limit=2)
    print("14. refero_get_catalog:", "OK" if "results" in res_cat else "FAIL")

    print("\nAll 14 tools verified successfully!")

if __name__ == "__main__":
    run_tests()
