#!/usr/bin/env python3
"""
Bond iOS App (ID: 317) Screen Downloader & ImageMagick Optimize
---------------------------------------------------------------
1. Harvests all screens across 35 UX Flows and Search facets.
2. Downloads lossless raw images to local cache.
3. Compresses with ImageMagick 7:
   magick input -resize "1280x1280>" (or 2560) -quality 87 -interlace Plane -strip output
4. Saves optimized deliverables into local output folder.
"""

import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.parse
import subprocess
import concurrent.futures
from pathlib import Path

# Paths (WSL / Linux)
SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / "data" / "bond_raw_cache"
OPT_DIR = SCRIPT_DIR / "data" / "bond_ios_optimized"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OPT_DIR.mkdir(parents=True, exist_ok=True)

MAGICK_BIN = "/home/velunae/.local/bin/magick"
if not os.path.exists(MAGICK_BIN):
    # Fallback to system convert
    MAGICK_BIN = shutil.which("magick") or shutil.which("convert")

AUTH_TOKEN = os.environ.get(
    "REFERO_TOKEN",
    "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjE4MjUwOTIxNDcsInN1YiI6Im5WWTVkbU0zZjI3QUQ1NDJNaDBITHg3N3hmVkxFMDlSIiwibmFtZSI6IlNvbW5hdmVyZSIsInJvbGVzIjpbInVzZXIiXSwiaXNzIjoicmVmZXIubWVkaWEifQ.Du6Dm5r33pb-eVg1wBzIxFNL0peH38rDNs6IgD_WB84"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Authorization": f"Bearer {AUTH_TOKEN}"
}

PHOTO_FLOW_KEYWORDS = ["photo", "camera", "story", "stories", "capture", "image", "media"]

# =====================================================================
# Phase 1: Screen Inventory Harvesting
# =====================================================================

def fetch_json(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == retries - 1:
                return {}
            time.sleep(0.5 * (attempt + 1))
    return {}

def collect_bond_screens():
    screens = {}
    print("[1/4] Harvesting screens from 35 UX Flows (14370..14404)...")
    
    def get_flow(fid):
        d = fetch_json(f"https://api.refero.design/v1/flows/{fid}")
        app = d.get("app") or {}
        if app.get("id") == 317 or app.get("name") == "Bond":
            flow_name = d.get("name", f"Flow {fid}")
            scrs = d.get("screenshots", [])
            return fid, flow_name, scrs
        return fid, None, []

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(get_flow, fid) for fid in range(14370, 14405)]
        for f in concurrent.futures.as_completed(futures):
            fid, flow_name, scrs = f.result()
            if flow_name:
                for s in scrs:
                    sid = s.get("id")
                    if sid:
                        s["flow_id"] = fid
                        s["flow_name"] = flow_name
                        screens[sid] = s

    print(f"      Collected {len(screens)} screens from UX Flows.")

    print("[2/4] Harvesting remaining screens via search facet sweep...")
    terms = [
        "", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
        "profile", "story", "chat", "ai", "settings", "home", "photo", "voice", "list", "feed", "search", "edit", "delete",
        "recommendation", "comment", "share", "memory", "memories", "user", "friend", "onboarding", "signup", "login", "camera"
    ]
    orders = ["trending", "latest", "oldest", "popular", "random"]

    def search_query(t, o):
        q_part = f"&query={urllib.parse.quote(t)}" if t else ""
        url = f"https://api.refero.design/v1/search/apps?app_id[id][]=317&order={o}{q_part}"
        d = fetch_json(url)
        return d.get("records", [])

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(search_query, t, o) for t in terms for o in orders]
        for f in concurrent.futures.as_completed(futures):
            for s in f.result():
                sid = s.get("id")
                if sid and sid not in screens:
                    screens[sid] = s

    print(f"      Total deduplicated screens for Bond: {len(screens)}")
    return list(screens.values())

# =====================================================================
# Phase 2: Raw Image Download into Cache
# =====================================================================

def get_image_url(s: dict) -> str:
    raw = s.get("url")
    if isinstance(raw, list) and raw:
        return raw[0]
    elif isinstance(raw, str) and raw:
        return raw
    return s.get("preview_url") or s.get("thumbnail_url") or ""

def download_raw_image(screen: dict) -> tuple:
    sid = screen.get("id")
    uuid = screen.get("uuid", "unknown")
    url = get_image_url(screen)
    if not url:
        return sid, None, 0, "No URL"

    ext = ".jpg"
    if ".png" in url.lower():
        ext = ".png"

    dest_file = CACHE_DIR / f"bond_{sid}_{uuid}{ext}"
    if dest_file.exists() and dest_file.stat().st_size > 500:
        return sid, dest_file, dest_file.stat().st_size, "Cached"

    tmp_file = dest_file.with_suffix(dest_file.suffix + ".tmp")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
            with urllib.request.urlopen(req, timeout=20) as resp:
                content = resp.read()
                with open(tmp_file, "wb") as f:
                    f.write(content)
                tmp_file.replace(dest_file)
                return sid, dest_file, len(content), "Downloaded"
        except Exception as e:
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass
            time.sleep(0.5 * (attempt + 1))

    return sid, None, 0, "Download Failed"

# =====================================================================
# Phase 3: ImageMagick Optimization
# =====================================================================

def optimize_image(screen: dict, raw_path: Path) -> dict:
    sid = screen.get("id")
    uuid = screen.get("uuid", "unknown")
    flow_name = screen.get("flow_name", "")

    # Decide geometry: 2560 for photos/large hero assets, 1280 for standard mobile UI
    is_photo = any(k in flow_name.lower() for k in PHOTO_FLOW_KEYWORDS)
    geometry = "2560x2560>" if is_photo else "1280x1280>"

    out_file = OPT_DIR / f"bond_{sid}_{uuid}.jpg"

    # Execute ImageMagick command:
    # magick input -resize "geometry" -quality 87 -interlace Plane -strip output
    cmd = [
        MAGICK_BIN,
        str(raw_path),
        "-resize", geometry,
        "-quality", "87",
        "-interlace", "Plane",
        "-strip",
        str(out_file)
    ]

    raw_size = raw_path.stat().st_size
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - t0

    if res.returncode != 0:
        return {
            "id": sid,
            "uuid": uuid,
            "flow_name": flow_name,
            "status": "error",
            "error": res.stderr.strip(),
            "raw_size": raw_size,
            "opt_size": 0,
            "saved_pct": 0.0
        }

    opt_size = out_file.stat().st_size
    saved_pct = ((raw_size - opt_size) / raw_size * 100) if raw_size > 0 else 0.0

    return {
        "id": sid,
        "uuid": uuid,
        "flow_name": flow_name,
        "geometry": geometry,
        "raw_size": raw_size,
        "opt_size": opt_size,
        "saved_pct": round(saved_pct, 2),
        "duration_sec": round(duration, 3),
        "file_name": out_file.name,
        "status": "ok"
    }

# =====================================================================
# Main Orchestration
# =====================================================================

def main():
    print("=" * 70)
    print("  BOND iOS (APP 317) - FULL DOWNLOAD & IMAGEMAGICK OPTIMIZATION")
    print(f"  ImageMagick Engine: {MAGICK_BIN}")
    print(f"  Raw Cache:          {CACHE_DIR}")
    print(f"  Optimized Output:   {OPT_DIR}")
    print("=" * 70)

    # 1. Collect
    screens = collect_bond_screens()
    total_screens = len(screens)
    print(f"\n[3/4] Downloading {total_screens} raw original images into cache...")

    download_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        future_map = {ex.submit(download_raw_image, s): s for s in screens}
        for f in concurrent.futures.as_completed(future_map):
            sid, path, size, status = f.result()
            download_results[sid] = (path, size, status)

    downloaded_cnt = sum(1 for p, sz, st in download_results.values() if p and p.exists())
    print(f"      Successfully cached: {downloaded_cnt} / {total_screens} images.")

    # 2. Optimize
    print(f"\n[4/4] Compressing via ImageMagick (-resize, -quality 87, -interlace Plane, -strip)...")
    opt_reports = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        opt_futures = {}
        for s in screens:
            sid = s.get("id")
            path, size, status = download_results.get(sid, (None, 0, ""))
            if path and path.exists():
                opt_futures[ex.submit(optimize_image, s, path)] = sid

        count = 0
        for f in concurrent.futures.as_completed(opt_futures):
            rep = f.result()
            opt_reports.append(rep)
            count += 1
            if count % 25 == 0 or count == len(opt_futures):
                print(f"      Processed {count}/{len(opt_futures)} images...")

    # Statistics
    total_raw_bytes = sum(r["raw_size"] for r in opt_reports if r["status"] == "ok")
    total_opt_bytes = sum(r["opt_size"] for r in opt_reports if r["status"] == "ok")
    total_saved_bytes = total_raw_bytes - total_opt_bytes
    avg_saved_pct = (total_saved_bytes / total_raw_bytes * 100) if total_raw_bytes > 0 else 0.0

    summary = {
        "app_id": 317,
        "app_name": "Bond",
        "platform": "ios",
        "imagemagick_binary": MAGICK_BIN,
        "total_screens": total_screens,
        "processed_screens": len(opt_reports),
        "total_raw_mb": round(total_raw_bytes / (1024 * 1024), 2),
        "total_optimized_mb": round(total_opt_bytes / (1024 * 1024), 2),
        "total_saved_mb": round(total_saved_bytes / (1024 * 1024), 2),
        "total_savings_pct": round(avg_saved_pct, 2),
        "records": opt_reports
    }

    summary_path = OPT_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("  EXPERIMENT RESULTS SUMMARY")
    print("=" * 70)
    print(f"  Total screens:      {total_screens}")
    print(f"  Processed screens:  {len(opt_reports)}")
    print(f"  Raw Cache Total:    {summary['total_raw_mb']} MB")
    print(f"  Optimized Total:    {summary['total_optimized_mb']} MB")
    print(f"  Disk Space Saved:   {summary['total_saved_mb']} MB ({summary['total_savings_pct']}%)")
    print(f"  Summary Report:     {summary_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
