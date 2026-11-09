#!/usr/bin/env python3
"""
Refero iOS Apps & Categories URL Harvester
------------------------------------------
1. Fetches all 312 iOS applications across 13 pages of /v1/apps/available.
2. Concurrently fetches categories & metadata from /v1/apps/{id}.
3. Integrates deep UX Flow screenshots for Bond (317) and other mapped apps.
4. Groups and exports to:
   - data/refero_catalog_by_category.json
   - data/refero_catalog_by_app.json
"""

import os
import json
import time
import urllib.request
import urllib.parse
import concurrent.futures
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

def fetch_json(url: str, retries: int = 3, timeout: int = 8) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt == retries - 1:
                return {}
            time.sleep(0.4 * (attempt + 1))
    return {}

def get_app_meta(app_id: int) -> dict:
    url = f"https://api.refero.design/v1/apps/{app_id}"
    data = fetch_json(url)
    if not data or not isinstance(data, dict):
        return {"id": app_id, "categories": [], "screenshots_count": 0}
    return data

def main():
    print("=" * 70)
    print("  REFERO CATALOG BUILDER — ALL APPS & CATEGORIES")
    print("=" * 70)

    # 1. Fetch available apps across all 13 pages
    print("[1/3] Fetching 312 iOS applications from /v1/apps/available...")
    all_apps_raw = []
    
    def fetch_page(page):
        url = f"https://api.refero.design/v1/apps/available?page={page}"
        d = fetch_json(url)
        return d.get("records", [])

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(fetch_page, p) for p in range(1, 14)]
        for f in concurrent.futures.as_completed(futures):
            all_apps_raw.extend(f.result())

    print(f"      Retrieved {len(all_apps_raw)} app records from available index.")

    # Deduplicate apps by ID
    unique_apps = {a["id"]: a for a in all_apps_raw if "id" in a}
    app_ids = sorted(list(unique_apps.keys()))
    print(f"      Unique app IDs: {len(app_ids)}")

    # 2. Fetch categories & metadata for all apps in parallel
    print("[2/3] Fetching categories and metadata across all apps...")
    app_meta_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        future_map = {ex.submit(get_app_meta, aid): aid for aid in app_ids}
        done_cnt = 0
        for f in concurrent.futures.as_completed(future_map):
            meta = f.result()
            aid = future_map[f]
            app_meta_map[aid] = meta
            done_cnt += 1
            if done_cnt % 50 == 0 or done_cnt == len(app_ids):
                print(f"      Progress: {done_cnt}/{len(app_ids)} apps metadata fetched...")

    # Load Bond deep inventory if exists
    bond_deep_screens = []
    bond_summary_file = DATA_DIR / "bond_ios_optimized" / "summary.json"
    if bond_summary_file.exists():
        try:
            with open(bond_summary_file, "r", encoding="utf-8") as f:
                bs = json.load(f)
                bond_deep_screens = bs.get("records", [])
        except Exception:
            pass

    # 3. Assemble unified app structures with all URLs
    print("[3/3] Assembling structured JSON and grouping by category...")
    processed_apps = []
    by_category = defaultdict(list)
    total_urls_collected = 0

    for aid in app_ids:
        raw_app = unique_apps[aid]
        meta = app_meta_map.get(aid, {})

        categories = [c.get("name") for c in meta.get("categories", []) if c.get("name")]
        if not categories:
            categories = ["Uncategorized"]

        # Collect & deduplicate all screenshot URLs
        screen_map = {}

        # Sourcing from raw_app['screenshots']
        for s in raw_app.get("screenshots", []):
            sid = s.get("id")
            if sid and sid not in screen_map:
                screen_map[sid] = {
                    "id": sid,
                    "uuid": s.get("uuid"),
                    "url": s.get("url"),
                    "thumbnail_url": s.get("thumbnail_url"),
                    "preview_url": s.get("preview_url") or (f"https://images.refero.design/screenshots/apps/{aid}/ios/{s.get('uuid')}_preview.jpg" if s.get("uuid") else None),
                    "colors": s.get("colors", [])
                }

        # Sourcing from raw_app['featured_screenshots']
        for s in raw_app.get("featured_screenshots", []):
            sid = s.get("id")
            if sid and sid not in screen_map:
                screen_map[sid] = {
                    "id": sid,
                    "uuid": s.get("uuid"),
                    "url": s.get("url"),
                    "thumbnail_url": s.get("thumbnail_url"),
                    "preview_url": s.get("preview_url") or (f"https://images.refero.design/screenshots/apps/{aid}/ios/{s.get('uuid')}_preview.jpg" if s.get("uuid") else None),
                    "colors": s.get("colors", [])
                }

        # If Bond (317), inject all deep harvested screens
        if aid == 317 and bond_deep_screens:
            for s in bond_deep_screens:
                sid = s.get("id")
                uuid = s.get("uuid")
                if sid:
                    if sid not in screen_map:
                        screen_map[sid] = {
                            "id": sid,
                            "uuid": uuid,
                            "flow_name": s.get("flow_name"),
                            "url": f"https://images.refero.design/screenshots/317/mobile/{uuid}.jpg",
                            "thumbnail_url": f"https://images.refero.design/screenshots/317/mobile/{uuid}_thumb.jpg",
                            "preview_url": f"https://images.refero.design/screenshots/apps/317/ios/{uuid}_preview.jpg",
                            "local_optimized_file": s.get("file_name")
                        }
                    else:
                        screen_map[sid]["flow_name"] = s.get("flow_name")
                        screen_map[sid]["local_optimized_file"] = s.get("file_name")

        screenshots_list = list(screen_map.values())
        total_urls_collected += len(screenshots_list)

        app_entry = {
            "id": aid,
            "name": raw_app.get("name"),
            "description": raw_app.get("description"),
            "store_url": raw_app.get("store_url"),
            "icon_url": raw_app.get("icon_url"),
            "background_url": raw_app.get("background_url"),
            "background_color": raw_app.get("background_color"),
            "categories": categories,
            "reported_screenshots_count": meta.get("screenshots_count", len(screenshots_list)),
            "collected_screenshots_count": len(screenshots_list),
            "screenshots": screenshots_list
        }

        processed_apps.append(app_entry)

        # Index under each category
        for cat in categories:
            by_category[cat].append({
                "id": app_entry["id"],
                "name": app_entry["name"],
                "description": app_entry["description"],
                "store_url": app_entry["store_url"],
                "icon_url": app_entry["icon_url"],
                "collected_screenshots_count": len(screenshots_list),
                "screenshots": screenshots_list
            })

    # Prepare outputs
    meta_info = {
        "title": "Refero iOS Apps & Screenshots Catalog",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_apps": len(processed_apps),
        "total_categories": len(by_category),
        "total_screenshot_urls": total_urls_collected,
        "categories_list": sorted(list(by_category.keys()))
    }

    category_output = {
        "metadata": meta_info,
        "categories": {cat: by_category[cat] for cat in sorted(by_category.keys())}
    }

    app_output = {
        "metadata": meta_info,
        "apps": processed_apps
    }

    cat_file = DATA_DIR / "refero_catalog_by_category.json"
    app_file = DATA_DIR / "refero_catalog_by_app.json"

    with open(cat_file, "w", encoding="utf-8") as f:
        json.dump(category_output, f, indent=2, ensure_ascii=False)

    with open(app_file, "w", encoding="utf-8") as f:
        json.dump(app_output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("  CATALOG GENERATION COMPLETE")
    print("=" * 70)
    print(f"  Total Applications:    {len(processed_apps)}")
    print(f"  Total Categories:      {len(by_category)}")
    print(f"  Total Screenshot URLs: {total_urls_collected}")
    print(f"  Output by Category:    {cat_file}")
    print(f"  Output by Application: {app_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()
