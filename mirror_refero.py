#!/usr/bin/env python3
"""
Refero Full Local Mirror & Autonomous Data Exporter
Extracts and mirrors the entire Refero platform locally:
1. Static Catalogs (439 web sites, 313 iOS apps, full site screen maps)
2. All 1,342 Design Systems & AI Prompts from styles.refero.design (DESIGN.md + JSON specs)
3. All 52 AI Agent Collections (landing pages, dashboards, cursor prompts, design context)
4. All UX Journey Flows (7,421 flows across web and mobile)
5. All Web & iOS Screens Metadata (145,000+ screens indexed into SQLite refero_local.db)
6. Website Frontend bundles (HTML, JS engines, CSS)
7. Resumable high-concurrency image scraper (CloudFront 2732px lossless assets)
"""

import sys
import os
import re
import json
import sqlite3
import argparse
import time
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
REFERO_API_BASE = "https://api.refero.design"
REFERO_WEB_BASE = "https://refero.design"
REFERO_STYLES_BASE = "https://styles.refero.design"
REFERO_IMAGES_BASE = "https://images.refero.design"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CATALOGS_DIR = DATA_DIR / "catalogs"
STYLES_DIR = DATA_DIR / "styles"
COLLECTIONS_DIR = DATA_DIR / "collections"
SITE_MIRROR_DIR = DATA_DIR / "site_mirror"
SCREENSHOTS_DIR = DATA_DIR / "media"
DB_PATH = DATA_DIR / "refero_local.db"


def fetch_url(url: str, is_json: bool = False, timeout: int = 15, retries: int = 3) -> Any:
    """Fetch URL with retries, timeout, and custom user-agent."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json" if is_json else "*/*"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                if is_json:
                    return json.loads(content.decode("utf-8"))
                return content.decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == retries - 1:
                return {"error": str(e), "url": url}
            time.sleep(1.0 * (attempt + 1))
    return {"error": "Max retries exceeded", "url": url}


def fetch_binary(url: str, dest_path: Path, timeout: int = 25, retries: int = 3) -> bool:
    """Download binary asset to disk atomically."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                with open(tmp_path, "wb") as f:
                    f.write(content)
                tmp_path.replace(dest_path)
                return True
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            if attempt == retries - 1:
                return False
            time.sleep(1.0 * (attempt + 1))
    return False


# =====================================================================
# Database Setup
# =====================================================================

def init_database() -> sqlite3.Connection:
    """Initializes local SQLite database for offline querying and image queueing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    
    with conn:
        # Screens catalog table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screens (
                id TEXT PRIMARY KEY,
                uuid TEXT,
                platform TEXT,
                site_name TEXT,
                domain TEXT,
                page_title TEXT,
                page_url TEXT,
                width INTEGER,
                height INTEGER,
                colors_json TEXT,
                fonts_json TEXT,
                patterns_json TEXT,
                elements_json TEXT,
                slices_count INTEGER,
                primary_image_url TEXT,
                all_slices_json TEXT,
                raw_json TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_screens_uuid ON screens (uuid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_screens_domain ON screens (domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_screens_platform ON screens (platform)")

        # Flows table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flows (
                id TEXT PRIMARY KEY,
                platform TEXT,
                title TEXT,
                description TEXT,
                step_count INTEGER,
                site_name TEXT,
                domain TEXT,
                screens_json TEXT,
                raw_json TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_domain ON flows (domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_platform ON flows (platform)")

        # Styles / Design Systems table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS styles (
                id TEXT PRIMARY KEY,
                site_name TEXT,
                url TEXT,
                theme TEXT,
                north_star TEXT,
                description TEXT,
                elevation_philosophy TEXT,
                dos_json TEXT,
                donts_json TEXT,
                colors_json TEXT,
                typography_json TEXT,
                raw_json TEXT,
                design_md TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_styles_name ON styles (site_name)")

        # Media download queue table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS media_queue (
                url TEXT PRIMARY KEY,
                screen_id TEXT,
                platform TEXT,
                slice_index INTEGER,
                local_path TEXT,
                downloaded INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                error TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_downloaded ON media_queue (downloaded)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_screen ON media_queue (screen_id)")

    return conn


# =====================================================================
# Phase 1: Static Catalogs & Frontend Bundles
# =====================================================================

def dump_catalogs() -> Dict[str, Any]:
    """Dumps static catalogs from Refero and indexes sites_full screens into SQLite."""
    CATALOGS_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    
    endpoints = {
        "sites.json": f"{REFERO_WEB_BASE}/json/sites.json",
        "apps.json": f"{REFERO_WEB_BASE}/json/apps.json",
        "sites_full.json": f"{REFERO_API_BASE}/v1/sites"
    }
    
    for filename, url in endpoints.items():
        print(f"[*] Fetching catalog {filename} from {url}...")
        data = fetch_url(url, is_json=True)
        if isinstance(data, (list, dict)) and "error" not in data:
            dest = CATALOGS_DIR / filename
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            count = len(data) if isinstance(data, list) else len(data.keys())
            results[filename] = {"status": "ok", "items": count, "path": str(dest)}
            print(f"[+] Saved {filename}: {count} records ({dest.stat().st_size / 1024:.1f} KB)")
        else:
            print(f"[-] Failed to fetch {filename}: {data.get('error') if isinstance(data, dict) else 'error'}")
            results[filename] = {"status": "error", "error": str(data)}
            
    # Index sites_full.json into database immediately
    import_sites_full_to_db()
    return results


def import_sites_full_to_db() -> int:
    """Imports all embedded screens from data/catalogs/sites_full.json directly into SQLite."""
    full_path = CATALOGS_DIR / "sites_full.json"
    if not full_path.exists():
        return 0
        
    conn = init_database()
    with open(full_path, "r", encoding="utf-8") as f:
        sites_data = json.load(f)
        
    print(f"[*] Indexing {len(sites_data)} sites from sites_full.json into SQLite...")
    total_screens = 0
    with conn:
        for site in sites_data:
            s_name = site.get("name", "")
            domain = site.get("domain", "")
            for scr in site.get("screenshots", []):
                sid = str(scr.get("id"))
                raw_url = scr.get("url")
                urls = raw_url if isinstance(raw_url, list) else ([raw_url] if raw_url else [])
                primary = urls[0] if urls else (scr.get("thumbnail_url") or "")
                
                # Extract UUID from image URL if possible
                uuid = ""
                for u in urls:
                    m = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', u)
                    if m:
                        uuid = m.group(1)
                        break
                        
                scr["site"] = {"name": s_name, "domain": domain}
                conn.execute("""
                    INSERT OR REPLACE INTO screens (
                        id, uuid, platform, site_name, domain, page_title, page_url,
                        width, height, colors_json, fonts_json, patterns_json, elements_json,
                        slices_count, primary_image_url, all_slices_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sid,
                    uuid,
                    "web",
                    s_name,
                    domain,
                    scr.get("page_title") or scr.get("title", ""),
                    scr.get("page_url", ""),
                    scr.get("width") or 0,
                    scr.get("height") or 0,
                    json.dumps(scr.get("colors", [])),
                    json.dumps(scr.get("fonts", [])),
                    json.dumps(scr.get("design_patterns", [])),
                    json.dumps(scr.get("page_elements", [])),
                    len(urls),
                    primary,
                    json.dumps(urls),
                    json.dumps(scr)
                ))
                queue_screen_images(conn, scr, platform="web")
                total_screens += 1
                
    print(f"[+] Successfully indexed {total_screens} web screens from sites_full.json into SQLite!")
    return total_screens


def dump_site_frontend() -> Dict[str, Any]:
    """Archives static frontend files from refero.design and styles.refero.design."""
    SITE_MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    
    pages = [
        ("refero_home.html", f"{REFERO_WEB_BASE}/"),
        ("styles_home.html", f"{REFERO_STYLES_BASE}/"),
        ("refero_sitemap.xml", f"{REFERO_WEB_BASE}/sitemap.xml"),
        ("styles_sitemap.xml", f"{REFERO_STYLES_BASE}/sitemap.xml"),
        ("styles_collections.xml", f"{REFERO_STYLES_BASE}/sitemaps/collections.xml"),
        ("styles_list.xml", f"{REFERO_STYLES_BASE}/sitemaps/styles.xml"),
    ]
    
    for filename, url in pages:
        print(f"[*] Mirroring page {filename}...")
        html = fetch_url(url, is_json=False)
        if isinstance(html, str) and not html.startswith('{"error":'):
            dest = SITE_MIRROR_DIR / filename
            with open(dest, "w", encoding="utf-8") as f:
                f.write(html)
            saved.append(filename)
            
            # Extract JS/CSS bundle links from home pages
            if filename in ("refero_home.html", "styles_home.html"):
                assets = re.findall(r'(?:src|href)=[\"\'](/_next/static/[^\"\']+|/static/[^\"\']+)[\"\']', html)
                base = REFERO_STYLES_BASE if "styles" in filename else REFERO_WEB_BASE
                for asset in assets[:15]:
                    asset_url = base + asset
                    asset_name = Path(asset.split("?")[0]).name
                    dest_asset = SITE_MIRROR_DIR / asset_name
                    if not dest_asset.exists():
                        fetch_binary(asset_url, dest_asset)
                        
    print(f"[+] Frontend bundles mirrored: {len(saved)} base pages saved to {SITE_MIRROR_DIR}")
    return {"saved_pages": saved}


# =====================================================================
# Phase 2: Design Systems & Prompts (styles.refero.design)
# =====================================================================

def parse_design_system_html(html: str, target_uuid: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], str]]:
    """Extracts parsed meta, designSystem dict, and formatted DESIGN.md prompt from RSC stream."""
    parsed_result = None
    for p in re.finditer(r'self\.__next_f\.push\(\[1,\"(.*?)\"\]\)', html):
        raw = p.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
        m = re.search(r'\"result\":(\{)', raw)
        if m:
            start_idx = m.start(1)
            try:
                parsed_result, _ = json.JSONDecoder().raw_decode(raw[start_idx:])
                break
            except Exception:
                pass
                
    if not parsed_result:
        return None
        
    ds = parsed_result.get("designSystem", {})
    r_meta = parsed_result.get("meta", {})
    name = r_meta.get("siteName", target_uuid)
    source_url = r_meta.get("url", f"{REFERO_STYLES_BASE}/style/{target_uuid}")
    
    # Render structured Markdown prompt
    md = f"# DESIGN SPEC: {name}\n"
    md += f"> Source: {source_url}\n"
    md += f"> Style ID: {target_uuid}\n\n"
    
    if ds.get("northStar"):
        md += f"## North Star (Design Prompt)\n{ds['northStar']}\n\n"
    if ds.get("description"):
        md += f"## Aesthetic Overview\n{ds['description']}\n\n"
    if ds.get("theme"):
        md += f"## Theme Default\n- `{ds['theme']}`\n\n"
    if ds.get("elevationPhilosophy"):
        md += f"## Elevation & Surfaces\n{ds['elevationPhilosophy']}\n\n"
    if ds.get("dos"):
        md += "## Do's\n" + "\n".join(f"- {d}" for d in ds["dos"]) + "\n\n"
    if ds.get("donts"):
        md += "## Don'ts\n" + "\n".join(f"- {d}" for d in ds["donts"]) + "\n\n"
    if ds.get("colors"):
        md += f"## Color System Tokens\n```json\n{json.dumps(ds['colors'], indent=2)}\n```\n\n"
    if ds.get("typography"):
        md += f"## Typography System\n```json\n{json.dumps(ds['typography'], indent=2)}\n```\n\n"
    if ds.get("layout"):
        md += f"## Layout & Grid Tokens\n```json\n{json.dumps(ds['layout'], indent=2)}\n```\n\n"
    if ds.get("spacing"):
        md += f"## Spacing Tokens\n```json\n{json.dumps(ds['spacing'], indent=2)}\n```\n\n"
    if ds.get("components"):
        md += f"## Component Tokens & Patterns\n```json\n{json.dumps(ds['components'], indent=2)}\n```\n\n"
    if ds.get("surfaces"):
        md += f"## Surface Hierarchy\n```json\n{json.dumps(ds['surfaces'], indent=2)}\n```\n\n"
        
    return r_meta, ds, md


def dump_all_styles(max_workers: int = 8, limit: Optional[int] = None) -> int:
    """Scrapes all 1,342 design systems from styles sitemap into Markdown prompts and SQLite."""
    STYLES_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_database()
    
    print("[*] Fetching styles sitemap from https://styles.refero.design/sitemaps/styles.xml...")
    sitemap_xml = fetch_url(f"{REFERO_STYLES_BASE}/sitemaps/styles.xml", is_json=False)
    if not isinstance(sitemap_xml, str) or "<loc>" not in sitemap_xml:
        print("[-] Could not retrieve styles sitemap!")
        return 0
        
    urls = re.findall(r'<loc>(https://styles\.refero\.design/style/([0-9a-f\-]{36}))</loc>', sitemap_xml)
    print(f"[+] Found {len(urls)} design systems in sitemap!")
    
    if limit:
        urls = urls[:limit]
        print(f"[*] Limiting styles dump to {limit} entries as requested.")
        
    master_index = []
    success_count = 0
    
    def process_style(item: Tuple[str, str]) -> Optional[Dict[str, Any]]:
        full_url, style_uuid = item
        spec_dir = STYLES_DIR / style_uuid
        md_file = spec_dir / "DESIGN.md"
        json_file = spec_dir / "spec.json"
        
        # Check if already downloaded on disk
        if md_file.exists() and json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                with open(md_file, "r", encoding="utf-8") as f:
                    cached_md = f.read()
                return {
                    "uuid": style_uuid,
                    "meta": cached_data.get("meta", {}),
                    "ds": cached_data.get("designSystem", {}),
                    "md": cached_md
                }
            except Exception:
                pass
                
        html = fetch_url(full_url, is_json=False)
        if not isinstance(html, str) or html.startswith('{"error":'):
            return None
            
        parsed = parse_design_system_html(html, style_uuid)
        if not parsed:
            return None
            
        meta, ds, md = parsed
        spec_dir.mkdir(parents=True, exist_ok=True)
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({"meta": meta, "designSystem": ds}, f, indent=2, ensure_ascii=False)
            
        return {"uuid": style_uuid, "meta": meta, "ds": ds, "md": md}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_style, item): item for item in urls}
        done_count = 0
        for fut in as_completed(futures):
            done_count += 1
            res = fut.result()
            if res:
                success_count += 1
                uuid = res["uuid"]
                meta = res["meta"]
                ds = res["ds"]
                md = res["md"]
                name = meta.get("siteName", uuid)
                master_index.append({"id": uuid, "siteName": name, "url": meta.get("url", "")})
                
                # Insert into SQLite
                with conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO styles (
                            id, site_name, url, theme, north_star, description,
                            elevation_philosophy, dos_json, donts_json, colors_json,
                            typography_json, raw_json, design_md
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        uuid,
                        name,
                        meta.get("url", ""),
                        ds.get("theme", ""),
                        ds.get("northStar", ""),
                        ds.get("description", ""),
                        ds.get("elevationPhilosophy", ""),
                        json.dumps(ds.get("dos", [])),
                        json.dumps(ds.get("donts", [])),
                        json.dumps(ds.get("colors", {})),
                        json.dumps(ds.get("typography", {})),
                        json.dumps({"meta": meta, "designSystem": ds}),
                        md
                    ))
                    
            if done_count % 50 == 0 or done_count == len(urls):
                print(f"[*] Processed styles: {done_count}/{len(urls)} ({success_count} valid design systems dumped)")

    # Save master styles index
    with open(STYLES_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(master_index, f, indent=2, ensure_ascii=False)
        
    print(f"[+] Complete styles dump finished: {success_count} design systems saved in {STYLES_DIR} & SQLite!")
    return success_count


def dump_all_collections() -> int:
    """Scrapes all 52 AI Agent prompt collections."""
    COLLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    xml = fetch_url(f"{REFERO_STYLES_BASE}/sitemaps/collections.xml", is_json=False)
    if not isinstance(xml, str):
        return 0
    urls = re.findall(r'<loc>(https://styles\.refero\.design/ai-agents/[^<]+)</loc>', xml)
    print(f"[*] Found {len(urls)} AI prompt collections in sitemap...")
    
    count = 0
    for url in urls:
        slug = url.split("/")[-1]
        dest = COLLECTIONS_DIR / f"{slug}.html"
        if not dest.exists():
            html = fetch_url(url, is_json=False)
            if isinstance(html, str):
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(html)
                count += 1
                
    print(f"[+] Mirrored {count} new AI collections in {COLLECTIONS_DIR}")
    return count


# =====================================================================
# Phase 3: UX Flows & Screens Metadata (SQLite Indexer)
# =====================================================================

def dump_flows(platform: str = "web", max_pages: int = 350, workers: int = 8) -> int:
    """Scrapes multi-step UX journey flows (web or ios) into SQLite using concurrent workers."""
    conn = init_database()
    ep = "search_flow/apps" if platform == "ios" else "search_flow"
    print(f"[*] Discovering {platform.upper()} flows pagination...")
    first_page = fetch_url(f"{REFERO_API_BASE}/v1/{ep}?page=1", is_json=True)
    if not isinstance(first_page, dict):
        print(f"[-] Failed to query {ep} API")
        return 0
    pag = first_page.get("pagination", {})
    total_pages = min(max_pages, pag.get("pages", 310))
    print(f"[*] Scraping {total_pages} {platform.upper()} flow pages using {workers} worker threads...")
    
    pages_to_fetch = list(range(1, total_pages + 1))
    
    def fetch_flow_page(p: int) -> List[Dict[str, Any]]:
        url = f"{REFERO_API_BASE}/v1/{ep}?page={p}"
        data = fetch_url(url, is_json=True)
        if isinstance(data, dict):
            return data.get("records", [])
        return []

    total_saved = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_flow_page, p): p for p in pages_to_fetch}
        for fut in as_completed(futures):
            records = fut.result()
            if records:
                with conn:
                    for r in records:
                        fid = str(r.get("id"))
                        title = r.get("title") or r.get("name") or f"Flow {fid}"
                        desc = r.get("description", "")
                        scrs = r.get("screenshots", [])
                        site_name = ""
                        domain = ""
                        if scrs and isinstance(scrs[0], dict):
                            site_info = scrs[0].get("site", {})
                            if isinstance(site_info, dict):
                                site_name = site_info.get("name", "")
                                domain = site_info.get("domain", "")
                                
                        conn.execute("""
                            INSERT OR REPLACE INTO flows (
                                id, platform, title, description, step_count, site_name, domain, screens_json, raw_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fid,
                            platform,
                            title,
                            desc,
                            len(scrs),
                            site_name,
                            domain,
                            json.dumps(scrs),
                            json.dumps(r)
                        ))
                        
                        for scr in scrs:
                            queue_screen_images(conn, scr, platform=platform)
                            
                        total_saved += 1
                        
            if total_saved > 0 and total_saved % 200 == 0:
                print(f"[*] {platform.upper()} flows indexed: {total_saved}...")
                
    print(f"[+] Total {platform.upper()} flows saved to SQLite: {total_saved}")
    return total_saved


POPULAR_FLOW_TOPICS = [
    "onboarding", "checkout", "login", "signup", "payment", "cart", "settings",
    "dashboard", "pricing", "profile", "billing", "invite", "filter", "search",
    "modal", "delete", "create", "edit", "upload", "export", "security", "auth",
    "password", "welcome", "verify", "subscribe", "notification", "integration",
    "feedback", "empty state", "dark mode", "team", "api", "analytics"
]

def dump_topic_flows(workers: int = 8) -> int:
    """Scrapes flows across all major UX pattern topics into SQLite."""
    conn = init_database()
    print(f"[*] Scraping flows across {len(POPULAR_FLOW_TOPICS)} popular UX topics...")
    total_saved = 0
    
    def fetch_topic(topic: str) -> List[Dict[str, Any]]:
        results = []
        for ep in ("search_flow", "search_flow/apps"):
            url = f"{REFERO_API_BASE}/v1/{ep}?query={urllib.parse.quote(topic)}&page=1"
            data = fetch_url(url, is_json=True)
            if isinstance(data, dict):
                recs = data.get("records", [])
                plat = "ios" if "apps" in ep else "web"
                for r in recs:
                    r["_platform"] = plat
                    results.append(r)
        return results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_topic, t): t for t in POPULAR_FLOW_TOPICS}
        for fut in as_completed(futures):
            recs = fut.result()
            if recs:
                with conn:
                    for r in recs:
                        fid = str(r.get("id"))
                        title = r.get("title") or r.get("name") or f"Flow {fid}"
                        desc = r.get("description", "")
                        scrs = r.get("screenshots", [])
                        plat = r.get("_platform", "web")
                        site_name = ""
                        domain = ""
                        if scrs and isinstance(scrs[0], dict):
                            site_info = scrs[0].get("site", {})
                            if isinstance(site_info, dict):
                                site_name = site_info.get("name", "")
                                domain = site_info.get("domain", "")
                                
                        conn.execute("""
                            INSERT OR REPLACE INTO flows (
                                id, platform, title, description, step_count, site_name, domain, screens_json, raw_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fid,
                            plat,
                            title,
                            desc,
                            len(scrs),
                            site_name,
                            domain,
                            json.dumps(scrs),
                            json.dumps(r)
                        ))
                        
                        for scr in scrs:
                            queue_screen_images(conn, scr, platform=plat)
                            
                        total_saved += 1
                        
    print(f"[+] Total topic-based flows indexed: {total_saved}")
    return total_saved


def queue_screen_images(conn: sqlite3.Connection, scr: Dict[str, Any], platform: str = "web"):
    """Inserts image URLs into media_queue for subsequent batch downloading."""
    sid = str(scr.get("id", ""))
    urls = []
    raw_url = scr.get("url")
    if isinstance(raw_url, list):
        urls.extend(raw_url)
    elif isinstance(raw_url, str):
        urls.append(raw_url)
    if not urls and scr.get("preview_url"):
        urls.append(scr["preview_url"])
        
    for idx, u in enumerate(urls):
        if not u or not isinstance(u, str):
            continue
        # Deduce local filename
        ext = ".jpg"
        clean_url = u.split("?")[0]
        subpath = clean_url.replace("https://images.refero.design/", "")
        local_path = str(SCREENSHOTS_DIR / subpath)
        
        conn.execute("""
            INSERT OR IGNORE INTO media_queue (url, screen_id, platform, slice_index, local_path, downloaded)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (u, sid, platform, idx, local_path))


def dump_screens_metadata(platform: str = "web", max_pages: int = 50, workers: int = 8) -> int:
    """Scrapes screen records from /v1/search or /v1/search/apps and indexes into SQLite using concurrent workers."""
    conn = init_database()
    ep = "search/apps" if platform == "ios" else "search"
    print(f"[*] Discovering {platform.upper()} screens pagination...")
    first_page = fetch_url(f"{REFERO_API_BASE}/v1/{ep}?page=1&per_page=24", is_json=True)
    if not isinstance(first_page, dict):
        return 0
    pag = first_page.get("pagination", {})
    total_pages = min(max_pages, pag.get("pages", 100))
    print(f"[*] Scraping {total_pages} {platform.upper()} screens pages using {workers} worker threads...")
    
    pages_to_fetch = list(range(1, total_pages + 1))
    
    def fetch_screen_page(p: int) -> List[Dict[str, Any]]:
        url = f"{REFERO_API_BASE}/v1/{ep}?page={p}&per_page=24"
        data = fetch_url(url, is_json=True)
        if isinstance(data, dict):
            return data.get("records", [])
        return []

    total_screens = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_screen_page, p): p for p in pages_to_fetch}
        for fut in as_completed(futures):
            records = fut.result()
            if records:
                with conn:
                    for r in records:
                        sid = str(r.get("id"))
                        uuid = r.get("uuid", "")
                        site_info = r.get("site", {})
                        site_name = site_info.get("name", "") if isinstance(site_info, dict) else ""
                        domain = site_info.get("domain", "") if isinstance(site_info, dict) else r.get("domain", "")
                        
                        raw_url = r.get("url")
                        urls = raw_url if isinstance(raw_url, list) else ([raw_url] if raw_url else [])
                        primary = urls[0] if urls else (r.get("preview_url") or "")
                        
                        conn.execute("""
                            INSERT OR REPLACE INTO screens (
                                id, uuid, platform, site_name, domain, page_title, page_url,
                                width, height, colors_json, fonts_json, patterns_json, elements_json,
                                slices_count, primary_image_url, all_slices_json, raw_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            sid,
                            uuid,
                            platform,
                            site_name,
                            domain,
                            r.get("page_title") or r.get("title", ""),
                            r.get("page_url", ""),
                            r.get("width") or 0,
                            r.get("height") or 0,
                            json.dumps(r.get("colors", [])),
                            json.dumps(r.get("fonts", [])),
                            json.dumps(r.get("design_patterns", [])),
                            json.dumps(r.get("page_elements", [])),
                            len(urls),
                            primary,
                            json.dumps(urls),
                            json.dumps(r)
                        ))
                        
                        queue_screen_images(conn, r, platform=platform)
                        total_screens += 1
                        
            if total_screens > 0 and total_screens % 300 == 0:
                print(f"[*] {platform.upper()} screens indexed: {total_screens}...")
                
    print(f"[+] Total {platform.upper()} screens indexed: {total_screens}")
    return total_screens


# =====================================================================
# Phase 4: High-Performance Resumable Media Downloader
# =====================================================================

def download_media_queue(max_workers: int = 10, hero_only: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
    """Downloads queued screenshot assets with concurrency, resuming from disk."""
    conn = init_database()
    
    query = "SELECT url, screen_id, local_path FROM media_queue WHERE downloaded = 0"
    if hero_only:
        query += " AND slice_index = 0"
    if limit:
        query += f" LIMIT {limit}"
        
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    
    print(f"[*] Media downloader starting: {len(rows)} pending assets queued (Workers: {max_workers}, Hero-Only: {hero_only})...")
    if not rows:
        print("[+] All queued assets already downloaded!")
        return {"downloaded": 0, "failed": 0, "remaining": 0}
        
    success_count = 0
    fail_count = 0
    
    def worker(item: Tuple[str, str, str]) -> Tuple[str, bool, int, str]:
        url, sid, local_path_str = item
        dest_path = Path(local_path_str)
        
        # If file already exists and is non-empty, mark as done
        if dest_path.exists() and dest_path.stat().st_size > 1024:
            return url, True, dest_path.stat().st_size, ""
            
        ok = fetch_binary(url, dest_path)
        if ok and dest_path.exists():
            return url, True, dest_path.stat().st_size, ""
        return url, False, 0, "Download failed"

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, r): r for r in rows}
        batch_updates = []
        
        for idx, fut in enumerate(as_completed(futures), start=1):
            url, ok, size, err = fut.result()
            if ok:
                success_count += 1
                batch_updates.append((1, size, "", url))
            else:
                fail_count += 1
                batch_updates.append((0, 0, err, url))
                
            if len(batch_updates) >= 50:
                with conn:
                    conn.executemany("""
                        UPDATE media_queue SET downloaded = ?, file_size = ?, error = ? WHERE url = ?
                    """, batch_updates)
                batch_updates.clear()
                print(f"[*] Assets downloaded: {idx}/{len(rows)} (Success: {success_count}, Failed: {fail_count})")
                
        if batch_updates:
            with conn:
                conn.executemany("""
                    UPDATE media_queue SET downloaded = ?, file_size = ?, error = ? WHERE url = ?
                """, batch_updates)
                
    print(f"[+] Download batch complete: {success_count} downloaded, {fail_count} failed.")
    return {"downloaded": success_count, "failed": fail_count, "total_queued": len(rows)}


# =====================================================================
# Main Orchestrator
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Refero Full Local Mirror & Autonomous Data Exporter")
    parser.add_argument("--all", action="store_true", help="Run full metadata & catalog mirror and queue all assets")
    parser.add_argument("--catalogs", action="store_true", help="Dump static JSON catalogs & frontend bundles")
    parser.add_argument("--styles", action="store_true", help="Dump all 1,342 design systems & AI prompts")
    parser.add_argument("--styles-limit", type=int, default=None, help="Limit number of styles to scrape for testing")
    parser.add_argument("--collections", action="store_true", help="Dump all 52 AI Agent prompt collections")
    parser.add_argument("--flows", action="store_true", help="Scrape UX journey flows")
    parser.add_argument("--screens", action="store_true", help="Scrape Web & iOS screens metadata")
    parser.add_argument("--pages", type=int, default=20, help="Max pages per endpoint when scraping screens/flows")
    parser.add_argument("--download-images", action="store_true", help="Download queued screenshot images")
    parser.add_argument("--hero-only", action="store_true", help="Download only hero / primary screenshot for each screen")
    parser.add_argument("--workers", type=int, default=8, help="Concurrency worker threads")
    parser.add_argument("--limit-images", type=int, default=None, help="Limit number of images to download")
    parser.add_argument("--status", action="store_true", help="Show summary of local mirror database and assets")
    
    args = parser.parse_args()
    
    if args.status or len(sys.argv) == 1:
        conn = init_database()
        cur = conn.cursor()
        print("\n=== REFERO LOCAL MIRROR STATUS ===")
        print(f"Local Storage Path: {DATA_DIR}")
        
        # Count styles
        cur.execute("SELECT COUNT(*) FROM styles")
        style_count = cur.fetchone()[0]
        print(f"Design Systems (Prompts): {style_count}")
        
        # Count screens
        cur.execute("SELECT COUNT(*) FROM screens")
        scr_count = cur.fetchone()[0]
        print(f"Indexed Screens: {scr_count}")
        
        # Count flows
        cur.execute("SELECT COUNT(*) FROM flows")
        flow_count = cur.fetchone()[0]
        print(f"UX Flows: {flow_count}")
        
        # Count media
        cur.execute("SELECT COUNT(*), SUM(downloaded), SUM(file_size) FROM media_queue")
        total_m, down_m, total_bytes = cur.fetchone()
        down_m = down_m or 0
        total_bytes = total_bytes or 0
        print(f"Media Queue: {total_m or 0} total images ({down_m} downloaded, {total_bytes / (1024*1024):.2f} MB)")
        print("===================================\n")
        if len(sys.argv) == 1:
            parser.print_help()
            return
            
    if args.all or args.catalogs:
        dump_catalogs()
        dump_site_frontend()
        
    if args.all or args.collections:
        dump_all_collections()
        
    if args.all or args.styles:
        dump_all_styles(max_workers=args.workers, limit=args.styles_limit)
        
    if args.all or args.flows:
        dump_flows(platform="web", max_pages=args.pages, workers=args.workers)
        dump_flows(platform="ios", max_pages=args.pages, workers=args.workers)
        dump_topic_flows(workers=args.workers)
        
    if args.all or args.screens:
        dump_screens_metadata(platform="web", max_pages=args.pages, workers=args.workers)
        dump_screens_metadata(platform="ios", max_pages=args.pages, workers=args.workers)
        
    if args.download_images:
        download_media_queue(max_workers=args.workers, hero_only=args.hero_only, limit=args.limit_images)


if __name__ == "__main__":
    main()
