#!/usr/bin/env python3
"""
Refero Complete Multi-Product Image URLs Harvester
--------------------------------------------------
Builds a unified, exhaustive JSON manifest mapping 60,000+ direct image URLs
to their exact owning applications and websites:

Structure per product:
{
  "name": "Banana Test",
  "type": "ios_app" | "web_site",
  "id": 123,
  "categories": ["Utility", "Productivity"],
  "domain_or_store": "...",
  "icon_url": "...",
  "total_images": 219,
  "image_urls": [
    "https://images.refero.design/...",
    ...
  ]
}
"""

import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.parse
import concurrent.futures
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

def fetch_json(url: str, retries: int = 2, timeout: int = 5) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt == retries - 1:
                return {}
            time.sleep(0.3 * (attempt + 1))
    return {}

def main():
    print("=" * 75)
    print("  REFERO 60K+ IMAGES MEGA-HARVESTER — MAPPING URLS TO PRODUCTS")
    print("=" * 75)

    products = defaultdict(lambda: {
        "name": "",
        "type": "product",
        "id": None,
        "categories": set(),
        "domain_or_store": "",
        "icon_url": "",
        "background_url": "",
        "image_urls": set()
    })

    # -------------------------------------------------------------
    # 1. Ingest existing 312 iOS apps from refero_catalog_by_app.json
    # -------------------------------------------------------------
    app_cat_file = DATA_DIR / "refero_catalog_by_app.json"
    if app_cat_file.exists():
        print("[1/5] Ingesting 312 iOS Apps from local catalog...")
        with open(app_cat_file, "r", encoding="utf-8") as f:
            d = json.load(f)
            for a in d.get("apps", []):
                aid = a.get("id")
                name = a.get("name") or f"iOS App {aid}"
                key = ("ios_app", aid)
                p = products[key]
                p["name"] = name
                p["type"] = "ios_app"
                p["id"] = aid
                p["domain_or_store"] = a.get("store_url", "")
                p["icon_url"] = a.get("icon_url", "")
                p["background_url"] = a.get("background_url", "")
                for c in a.get("categories", []):
                    p["categories"].add(c)
                for s in a.get("screenshots", []):
                    if s.get("url"):
                        u = s["url"]
                        if isinstance(u, list):
                            for x in u: p["image_urls"].add(x)
                        else:
                            p["image_urls"].add(u)
                    if s.get("preview_url"): p["image_urls"].add(s["preview_url"])
                    if s.get("thumbnail_url"): p["image_urls"].add(s["thumbnail_url"])

    # -------------------------------------------------------------
    # 2. Ingest 438 Web Sites from /v1/sites/available
    # -------------------------------------------------------------
    print("[2/5] Fetching all 438 Web Sites from /v1/sites/available (19 pages)...")
    def fetch_site_page(p):
        d = fetch_json(f"https://api.refero.design/v1/sites/available?page={p}")
        return d.get("records", [])

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(fetch_site_page, p) for p in range(1, 20)]
        for f in concurrent.futures.as_completed(futures):
            for site in f.result():
                sid = site.get("id")
                name = site.get("name") or site.get("domain") or f"Site {sid}"
                key = ("web_site", sid)
                p = products[key]
                p["name"] = name
                p["type"] = "web_site"
                p["id"] = sid
                p["domain_or_store"] = site.get("domain", "")
                p["icon_url"] = site.get("favicon_url", "")
                for s in site.get("screenshots", []):
                    u = s.get("url")
                    if isinstance(u, list):
                        for slice_url in u: p["image_urls"].add(slice_url)
                    elif isinstance(u, str) and u:
                        p["image_urls"].add(u)
                    if s.get("thumbnail_url"): p["image_urls"].add(s["thumbnail_url"])
                    if s.get("preview_url"): p["image_urls"].add(s["preview_url"])

    # -------------------------------------------------------------
    # 3. Ingest catalogs/sites_full.json (21,809 full page slices)
    # -------------------------------------------------------------
    sites_full_file = DATA_DIR / "catalogs" / "sites_full.json"
    if sites_full_file.exists():
        print("[3/5] Merging full vertical slice URLs from catalogs/sites_full.json...")
        with open(sites_full_file, "r", encoding="utf-8") as f:
            for site in json.load(f):
                sid = site.get("id")
                name = site.get("name") or site.get("domain")
                key = ("web_site", sid)
                p = products[key]
                p["name"] = p["name"] or name
                p["type"] = "web_site"
                p["id"] = sid
                p["domain_or_store"] = p["domain_or_store"] or site.get("domain", "")
                p["icon_url"] = p["icon_url"] or site.get("favicon_url", "")
                for scr in site.get("screenshots", []):
                    u = scr.get("url")
                    if isinstance(u, list):
                        for slice_url in u: p["image_urls"].add(slice_url)
                    elif isinstance(u, str) and u:
                        p["image_urls"].add(u)
                    if scr.get("thumbnail_url"): p["image_urls"].add(scr["thumbnail_url"])

    # -------------------------------------------------------------
    # 4. Ingest SQLite DB (screens, media_queue, flows)
    # -------------------------------------------------------------
    db_file = DATA_DIR / "refero_local.db"
    if db_file.exists():
        print("[4/5] Merging database media queues, screens, and existing UX Flows...")
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()

        # Flows
        cur.execute("SELECT raw_json FROM flows;")
        for row in cur.fetchall():
            try:
                flow = json.loads(row[0])
                app_meta = flow.get("app")
                site_meta = flow.get("site")
                if app_meta and app_meta.get("id"):
                    key = ("ios_app", app_meta["id"])
                    p = products[key]
                    p["name"] = p["name"] or app_meta.get("name")
                    p["type"] = "ios_app"
                    p["id"] = app_meta["id"]
                elif site_meta and (site_meta.get("id") or site_meta.get("name")):
                    key = ("web_site", site_meta.get("id") or site_meta.get("name"))
                    p = products[key]
                    p["name"] = p["name"] or site_meta.get("name")
                    p["type"] = "web_site"
                    p["id"] = site_meta.get("id")
                else:
                    continue

                for s in flow.get("screenshots", []):
                    u = s.get("url")
                    if isinstance(u, list):
                        for x in u: p["image_urls"].add(x)
                    elif isinstance(u, str) and u:
                        p["image_urls"].add(u)
                    if s.get("preview_url"): p["image_urls"].add(s["preview_url"])
                    if s.get("thumbnail_url"): p["image_urls"].add(s["thumbnail_url"])
            except Exception:
                pass

        # Media queue mapped to site
        cur.execute("SELECT s.site_name, s.platform, m.url FROM media_queue m JOIN screens s ON m.screen_id = s.id;")
        for s_name, plat, u in cur.fetchall():
            ptype = "ios_app" if plat == "ios" else "web_site"
            for (tp, i), p in products.items():
                if p["name"] == s_name:
                    p["image_urls"].add(u)
                    break

    # -------------------------------------------------------------
    # 5. Fast sweep of active UX Flows (12,500 .. 14,429)
    # -------------------------------------------------------------
    print("[5/5] Rapidly harvesting active UX Flows (12,500 .. 14,429) across products...")
    def sweep_flow(fid):
        d = fetch_json(f"https://api.refero.design/v1/flows/{fid}")
        if not d or not isinstance(d, dict):
            return None
        app_meta = d.get("app")
        site_meta = d.get("site")
        scrs = d.get("screenshots", [])
        if not scrs or (not app_meta and not site_meta):
            return None
        return app_meta, site_meta, scrs

    flow_count = 0
    flow_screens_added = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
        futures = [ex.submit(sweep_flow, fid) for fid in range(12500, 14430)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if not res:
                continue
            app_meta, site_meta, scrs = res
            flow_count += 1
            if app_meta and app_meta.get("id"):
                key = ("ios_app", app_meta["id"])
                p = products[key]
                p["name"] = p["name"] or app_meta.get("name")
                p["type"] = "ios_app"
                p["id"] = app_meta["id"]
            elif site_meta and (site_meta.get("id") or site_meta.get("name")):
                key = ("web_site", site_meta.get("id") or site_meta.get("name"))
                p = products[key]
                p["name"] = p["name"] or site_meta.get("name")
                p["type"] = "web_site"
                p["id"] = site_meta.get("id")
            else:
                continue

            for s in scrs:
                u = s.get("url")
                if isinstance(u, list):
                    for x in u:
                        p["image_urls"].add(x)
                        flow_screens_added += 1
                elif isinstance(u, str) and u:
                    p["image_urls"].add(u)
                    flow_screens_added += 1
                if s.get("preview_url"):
                    p["image_urls"].add(s["preview_url"])
                    flow_screens_added += 1
                if s.get("thumbnail_url"):
                    p["image_urls"].add(s["thumbnail_url"])
                    flow_screens_added += 1

    print(f"      Swept {flow_count} active flows, harvesting {flow_screens_added} image links.")

    # -------------------------------------------------------------
    # Assemble Final Output
    # -------------------------------------------------------------
    product_list = []
    total_images_all = 0

    for (ptype, pid), p in products.items():
        if not p["name"] or not p["image_urls"]:
            continue
        urls_sorted = sorted(list(p["image_urls"]))
        total_images_all += len(urls_sorted)
        product_list.append({
            "name": p["name"],
            "type": p["type"],
            "id": p["id"],
            "categories": sorted(list(p["categories"])),
            "domain_or_store": p["domain_or_store"],
            "icon_url": p["icon_url"],
            "total_images": len(urls_sorted),
            "image_urls": urls_sorted
        })

    # Sort products by total image count descending
    product_list.sort(key=lambda x: x["total_images"], reverse=True)

    mega_catalog = {
        "metadata": {
            "title": "Refero Complete Multi-Product Screenshot Catalog",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_products": len(product_list),
            "total_image_urls": total_images_all,
            "ios_apps_count": sum(1 for p in product_list if p["type"] == "ios_app"),
            "web_sites_count": sum(1 for p in product_list if p["type"] == "web_site")
        },
        "products": product_list
    }

    out_file = DATA_DIR / "refero_mega_products_catalog.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(mega_catalog, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 75)
    print("  MEGA-CATALOG GENERATION COMPLETE")
    print("=" * 75)
    print(f"  Total Products:         {len(product_list)}")
    print(f"  Total Direct Image URLs:{total_images_all:,}")
    print(f"  iOS Apps:               {mega_catalog['metadata']['ios_apps_count']}")
    print(f"  Web Sites:              {mega_catalog['metadata']['web_sites_count']}")
    print(f"  Output Manifest:        {out_file}")
    print("=" * 75)

    print("\nTop 10 Products by Image Volume:")
    for p in product_list[:10]:
        print(f"  - {p['name']} ({p['type']}): {p['total_images']} image URLs")

if __name__ == "__main__":
    main()
