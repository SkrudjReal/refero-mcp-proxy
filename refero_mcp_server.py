#!/usr/bin/env python3
"""
Refero MCP Proxy Server (Pure Python, Zero External Dependencies)
Provides complete integration with Refero (refero.design) UI/UX design intelligence:
- Real product screens (Web & iOS) with direct CDN links and Markdown/HTML embeds
- Multi-step User Flows (Onboarding, Checkout, Auth, Settings)
- Curated Design Systems (Typography, Color Palettes, Spacing, Tokens) from styles.refero.design
- Lossless full-resolution (2732px) image retrieval, asset variants, and local batch downloads
- Built-in instructions and snippets for extracting images and bypassing client-side paywalls
- Static database catalogs for 317+ apps and 500+ sites (zero tokens, zero auth)
"""

import sys
import json
import urllib.request
import urllib.parse
import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

SERVER_NAME = "refero-mcp-proxy"
SERVER_VERSION = "2.2.0"

REFERO_API_BASE = "https://api.refero.design"
REFERO_CHAT_BASE = "https://chat.refero.design"
REFERO_STYLES_BASE = "https://styles.refero.design"
REFERO_WEB_BASE = "https://refero.design"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Optional token from environment if user wants authenticated access
AUTH_TOKEN = os.environ.get("REFERO_TOKEN", "").strip()

# In-memory caches for fast lookup
STYLE_CACHE: Dict[str, Dict[str, Any]] = {}
STYLE_CATALOG_LOADED = False
CATALOG_APPS_CACHE: Optional[List[Dict[str, Any]]] = None
CATALOG_SITES_CACHE: Optional[List[Dict[str, Any]]] = None
SCREEN_CACHE_BY_ID: Dict[str, Dict[str, Any]] = {}
SCREEN_CACHE_BY_UUID: Dict[str, Dict[str, Any]] = {}
RAW_SITES_CACHE: Optional[List[Dict[str, Any]]] = None


def http_get(url: str, is_json: bool = False, custom_headers: Optional[Dict[str, str]] = None) -> Any:
    """Performs HTTP GET with error handling and optional authentication."""
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json" if is_json else "*/*",
        "ngrok-skip-browser-warning": "1"
    }
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}" if not AUTH_TOKEN.startswith("Bearer ") else AUTH_TOKEN
    if custom_headers:
        headers.update(custom_headers)

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            if is_json:
                return json.loads(content.decode("utf-8"))
            return content.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(body)
            return {"error": err_json.get("error", f"HTTP {e.code}"), "status_code": e.code, "body": err_json}
        except Exception:
            return {"error": f"HTTP {e.code}", "status_code": e.code, "body": body}
    except Exception as e:
        return {"error": str(e)}


def download_file(url: str, dest_path: Path) -> int:
    """Downloads a binary file (e.g. screenshot image) to destination path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        content = resp.read()
        with open(dest_path, "wb") as f:
            f.write(content)
        return len(content)


def extract_primary_image_url(record: Dict[str, Any]) -> Optional[str]:
    """Extracts first lossless full-res image URL from record url list or preview_url."""
    raw_url = record.get("url")
    if isinstance(raw_url, list) and len(raw_url) > 0:
        return raw_url[0]
    elif isinstance(raw_url, str) and raw_url:
        return raw_url
    return record.get("preview_url") or record.get("thumbnail_url")


def enrich_screen_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Enriches a screen record with direct image links, markdown/html embeds, and download commands."""
    if not isinstance(record, dict):
        return record
    img_url = extract_primary_image_url(record)
    sid = record.get("id")
    uuid = record.get("uuid")

    # If uuid is missing in record but in image url, extract it
    if not uuid and img_url:
        m = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', img_url)
        if m:
            uuid = m.group(1)
            record["uuid"] = uuid

    site_info = record.get("site")
    site_name = ""
    if isinstance(site_info, dict):
        site_name = site_info.get("name", "")
    title = site_name or record.get("domain") or f"Screen {sid}"

    if img_url:
        record["direct_image_url"] = img_url
        record["markdown_embed"] = f"![{title}]({img_url})"
        record["html_embed"] = f'<img src="{img_url}" alt="{title}" />'
    if sid or uuid:
        ref_id = sid or uuid
        record["download_command"] = f"refero_download_screen(screen_id='{ref_id}')"

    # Index in global cache
    if sid is not None:
        SCREEN_CACHE_BY_ID[str(sid)] = record
    if uuid:
        SCREEN_CACHE_BY_UUID[str(uuid)] = record

    return record


def index_sites_screens():
    """Fetches /v1/sites once and indexes all contained screens by numeric ID and UUID."""
    global RAW_SITES_CACHE
    if RAW_SITES_CACHE is not None:
        return
    raw = http_get(f"{REFERO_API_BASE}/v1/sites", is_json=True)
    if isinstance(raw, list):
        RAW_SITES_CACHE = raw
        for site in raw:
            s_name = site.get("name", "")
            s_domain = site.get("domain", "")
            for scr in site.get("screenshots", []):
                if isinstance(scr, dict):
                    scr["site"] = {"name": s_name, "domain": s_domain}
                    enrich_screen_record(scr)


# =====================================================================
# 1. Styles & Design Systems (styles.refero.design)
# =====================================================================

def load_styles_catalog(max_pages: int = 5):
    """Scrapes and caches design systems from styles.refero.design."""
    global STYLE_CATALOG_LOADED
    if STYLE_CATALOG_LOADED and len(STYLE_CACHE) > 0:
        return

    for page in range(1, max_pages + 1):
        url = f"{REFERO_STYLES_BASE}/?page={page}" if page > 1 else f"{REFERO_STYLES_BASE}/"
        try:
            html = http_get(url)
            for p in re.finditer(r'self\.__next_f\.push\(\[1,\"(.*?)\"\]\)', html):
                chunk = p.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                for m in re.finditer(r'\"id\":\"([0-9a-f\-]{36})\"', chunk):
                    sid = m.group(1)
                    sub = chunk[m.start():m.start() + 600]
                    name_m = re.search(r'\"siteName\":\"([^\"]+)\"', sub)
                    url_m = re.search(r'\"url\":\"([^\"]+)\"', sub)
                    sname = name_m.group(1) if name_m else "Unknown"
                    surl = url_m.group(1) if url_m else ""
                    if sid not in STYLE_CACHE and sname != "Unknown":
                        STYLE_CACHE[sid] = {
                            "id": sid,
                            "url": surl,
                            "siteName": sname,
                            "page": page
                        }
        except Exception:
            break
    STYLE_CATALOG_LOADED = True


def refero_search_styles(query: str = "", limit: int = 10) -> Dict[str, Any]:
    """Search design styles by query keyword (e.g. 'Apple', 'Cursor', 'Minimal')."""
    load_styles_catalog()
    q_lower = query.lower().strip()
    matches = []
    for sid, info in STYLE_CACHE.items():
        if not q_lower or q_lower in info["siteName"].lower() or q_lower in info["url"].lower():
            matches.append(info)
            if len(matches) >= limit:
                break
    return {
        "query": query,
        "count": len(matches),
        "total_cached": len(STYLE_CACHE),
        "styles": matches
    }


def refero_get_style(style_id: Optional[str] = None, style_ids: Optional[List[str]] = None, response_format: str = "md") -> Any:
    """Fetch structured design spec (DESIGN.md) for given style ID(s)."""
    targets = []
    if style_ids:
        targets = style_ids
    elif style_id:
        targets = [style_id]

    results = []
    for sid in targets:
        target_uuid = sid
        if sid not in STYLE_CACHE:
            load_styles_catalog()
            for cuid, info in STYLE_CACHE.items():
                if info["siteName"].lower() == sid.lower():
                    target_uuid = cuid
                    break

        url = f"{REFERO_STYLES_BASE}/style/{target_uuid}"
        html = http_get(url)
        design_md = ""
        parsed_result = None

        if isinstance(html, str):
            for p in re.finditer(r'self\.__next_f\.push\(\[1,\"(.*?)\"\]\)', html):
                raw = p.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                m = re.search(r'\"result\":(\{.*)', raw)
                if m:
                    sub = m.group(1)
                    depth = 0
                    end_idx = 0
                    for i, char in enumerate(sub):
                        if char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                end_idx = i + 1
                                break
                    if end_idx > 0:
                        try:
                            parsed_result = json.loads(sub[:end_idx])
                            break
                        except Exception:
                            pass

        meta = STYLE_CACHE.get(target_uuid, {"id": target_uuid})
        if parsed_result:
            ds = parsed_result.get("designSystem", {})
            r_meta = parsed_result.get("meta", {})
            name = r_meta.get("siteName") or meta.get("siteName", target_uuid)
            source_url = r_meta.get("url") or meta.get("url", f"{REFERO_STYLES_BASE}/style/{target_uuid}")

            md = f"# DESIGN SPEC: {name}\n"
            md += f"> Source: {source_url}\n\n"
            if ds.get("northStar"):
                md += f"## North Star\n{ds['northStar']}\n\n"
            if ds.get("description"):
                md += f"## Overview\n{ds['description']}\n\n"
            if ds.get("elevationPhilosophy"):
                md += f"## Elevation & Surfaces\n{ds['elevationPhilosophy']}\n\n"
            if ds.get("dos"):
                md += "## Do's\n" + "\n".join(f"- {d}" for d in ds['dos']) + "\n\n"
            if ds.get("donts"):
                md += "## Don'ts\n" + "\n".join(f"- {d}" for d in ds['donts']) + "\n\n"
            if ds.get("colors"):
                md += f"## Color System\n```json\n{json.dumps(ds['colors'], indent=2)}\n```\n\n"
            if ds.get("typography"):
                md += f"## Typography\n```json\n{json.dumps(ds['typography'], indent=2)}\n```\n\n"
            design_md = md

        if response_format == "json":
            results.append({
                "style_id": target_uuid,
                "meta": meta,
                "parsed_result": parsed_result,
                "design_spec_length": len(design_md),
                "design_spec": design_md
            })
        else:
            header = f"# DESIGN SPEC: {meta.get('siteName', target_uuid)}\n"
            header += f"> Source: {meta.get('url', f'{REFERO_STYLES_BASE}/style/{target_uuid}')}\n\n"
            results.append(design_md if design_md else header + "Specification not parsed or style not found.")

    if len(results) == 1:
        return results[0]
    return results


# =====================================================================
# 2. Screens & UI Elements (api.refero.design)
# =====================================================================

def refero_search_screens(query: str, platform: str = "web", order: str = "trending", page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Search real UI screens using semantic search across web and iOS products.
    Order can be 'trending', 'latest', or 'oldest' to bypass single-page limits.
    Enriches all records with direct lossless image links and Markdown/HTML embeds.
    """
    encoded_q = urllib.parse.quote(query)
    ep = "search/apps" if platform == "ios" else "search"
    url = f"{REFERO_API_BASE}/v1/{ep}?query={encoded_q}&order={order}&page={page}&per_page={per_page}"
    data = http_get(url, is_json=True)
    if isinstance(data, dict):
        data["browser_paywall_note"] = "On refero.design web, a client-side paywall activates on card #12. This direct API returns all records unblocked."
        records = data.get("records", [])
        if isinstance(records, list):
            data["records"] = [enrich_screen_record(r) for r in records]
    return data


def refero_get_screen(screen_id: Optional[Union[str, int]] = None, screen_ids: Optional[List[Union[str, int]]] = None) -> Any:
    """
    Get full details for one or more screens by numeric ID or UUID.
    Uses official /v1/screenshots/{uuid} and /v1/app_screenshots/{uuid} endpoints.
    """
    targets = []
    if screen_ids:
        targets = [str(x) for x in screen_ids]
    elif screen_id is not None:
        targets = [str(screen_id)]

    results = []
    for sid in targets:
        # 1. Check in-memory cache first
        if sid in SCREEN_CACHE_BY_UUID:
            results.append(SCREEN_CACHE_BY_UUID[sid])
            continue
        if sid in SCREEN_CACHE_BY_ID:
            results.append(SCREEN_CACHE_BY_ID[sid])
            continue

        # 2. If it is a UUID (contains hyphens or 32+ hex chars)
        is_uuid = bool(re.search(r'[0-9a-f]{8}-[0-9a-f]{4}', sid))
        if is_uuid:
            # Query web screenshots show
            data = http_get(f"{REFERO_API_BASE}/v1/screenshots/{sid}", is_json=True)
            if isinstance(data, dict) and "id" in data:
                results.append(enrich_screen_record(data))
                continue
            # Fallback to iOS app_screenshots show
            data_app = http_get(f"{REFERO_API_BASE}/v1/app_screenshots/{sid}", is_json=True)
            if isinstance(data_app, dict) and "id" in data_app:
                results.append(enrich_screen_record(data_app))
                continue

        # 3. If numeric ID, index sites screens or query
        index_sites_screens()
        if sid in SCREEN_CACHE_BY_ID:
            results.append(SCREEN_CACHE_BY_ID[sid])
            continue

        # Fallback search query - strictly verify ID or UUID matches
        encoded_id = urllib.parse.quote(str(sid))
        data_s = http_get(f"{REFERO_API_BASE}/v1/search?query={encoded_id}&page=1&per_page=10", is_json=True)
        recs = data_s.get("records", []) if isinstance(data_s, dict) else []
        matched = None
        for r in recs:
            if str(r.get("id")) == str(sid) or str(r.get("uuid")) == str(sid):
                matched = r
                break
        if matched:
            results.append(enrich_screen_record(matched))
        else:
            results.append({"error": "Screen not found", "screen_id": sid})

    if len(results) == 1:
        return results[0]
    return results


def refero_get_similar_screens(screen_id: Union[str, int], limit: int = 10, platform: str = "web") -> Dict[str, Any]:
    """Get visually and functionally similar screens for a given screen ID, enriched with image links."""
    # Resolve numeric ID to UUID if available
    sid_str = str(screen_id)
    if sid_str in SCREEN_CACHE_BY_ID:
        target_id = SCREEN_CACHE_BY_ID[sid_str].get("uuid") or sid_str
    else:
        target_id = sid_str

    encoded_id = urllib.parse.quote(str(target_id))
    ep = "app_screenshots" if platform == "ios" else "screenshots"
    url = f"{REFERO_API_BASE}/v1/{ep}/{encoded_id}/similar"
    data = http_get(url, is_json=True)
    if isinstance(data, dict) and "records" in data:
        recs = data["records"][:limit]
        data["records"] = [enrich_screen_record(r) for r in recs]
        return data

    alt_ep = "screenshots" if ep == "app_screenshots" else "app_screenshots"
    url_alt = f"{REFERO_API_BASE}/v1/{alt_ep}/{encoded_id}/similar"
    data_alt = http_get(url_alt, is_json=True)
    if isinstance(data_alt, dict) and "records" in data_alt:
        recs = data_alt["records"][:limit]
        data_alt["records"] = [enrich_screen_record(r) for r in recs]
        return data_alt

    return {"error": "Failed to fetch similar screens", "screen_id": screen_id}


# =====================================================================
# 3. Image Extraction, Embeds, Instructions & Downloads
# =====================================================================

def refero_get_screen_image(screen_id: Union[str, int], image_size: str = "full") -> Dict[str, Any]:
    """
    Get raw screenshot image URLs, asset variants, embed code, and browser retrieval instructions.
    """
    screen = refero_get_screen(screen_id=screen_id)
    if isinstance(screen, dict) and "error" in screen:
        return screen

    img_urls = []
    raw_url = screen.get("url")
    if isinstance(raw_url, list):
        img_urls.extend(raw_url)
    elif isinstance(raw_url, str):
        img_urls.append(raw_url)

    lossless_url = img_urls[0] if img_urls else screen.get("preview_url")
    selected_url = lossless_url if image_size == "full" else (screen.get("thumbnail_url") or lossless_url)
    site_info = screen.get("site")
    site_name = site_info.get("name") if isinstance(site_info, dict) else screen.get("domain", f"Screen {screen_id}")

    return {
        "screen_id": screen_id,
        "uuid": screen.get("uuid"),
        "site_name": site_name,
        "image_size": image_size,
        "image_url": selected_url,
        "full_resolution_url": lossless_url,
        "thumbnail_url": screen.get("thumbnail_url"),
        "preview_url": screen.get("preview_url"),
        "all_slices_urls": img_urls,
        "slices_count": len(img_urls),
        "markdown_embed": f"![{site_name}]({selected_url})",
        "html_embed": f'<img src="{selected_url}" alt="{site_name}" />',
        "download_command": f"refero_download_screen(screen_id='{screen_id}')",
        "instructions_how_to_get_in_browser": {
            "method_1_direct_cdn_link": "Open 'full_resolution_url' directly in any browser tab. CloudFront delivers original lossless 2732px JPG with no cookies or login required. Right-click -> 'Save Image As...'.",
            "method_2_bypass_web_paywall": "If browsing on refero.design and encountering the '141 search results are hidden' overlay, open F12 Console and run:\n  document.body.classList.remove('o1Kr5');\n  document.querySelectorAll('div[class*=\"EXPhN\"]').forEach(e => e.remove());\n  document.body.style.overflow = 'auto';",
            "method_3_batch_extract_page_images": "To extract all image URLs on a Refero page via browser Console:\n  const urls = Array.from(document.querySelectorAll('img')).map(i => i.src).filter(s => s.includes('images.refero.design')).map(s => s.replace('/preview/', '/desktop/'));\n  copy(urls);\n  console.log(`Copied ${urls.length} full-resolution URLs!`);"
        }
    }


def refero_download_screen(
    screen_id: Optional[Union[str, int]] = None,
    screen_ids: Optional[List[Union[str, int]]] = None,
    output_dir: Optional[str] = None,
    all_slices: bool = False,
    stitch: bool = False
) -> Dict[str, Any]:
    """
    Download full-resolution screenshot image(s) directly to local disk.
    Supports single screen_id, multiple screen_ids, downloading all vertical slices, and optional vertical stitching.
    """
    targets = []
    if screen_ids:
        targets = [str(x) for x in screen_ids]
    elif screen_id is not None:
        targets = [str(screen_id)]

    if not targets:
        return {"error": "Either screen_id or screen_ids must be provided"}

    dest_dir = Path(output_dir) if output_dir else Path.cwd() / "screenshots"
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    failed = []

    for sid in targets:
        img_info = refero_get_screen_image(screen_id=sid, image_size="full")
        if "error" in img_info:
            failed.append({"screen_id": sid, "error": img_info.get("error")})
            continue

        slices = img_info.get("all_slices_urls", [])
        if not slices:
            url = img_info.get("full_resolution_url")
            if url:
                slices = [url]

        if not slices:
            failed.append({"screen_id": sid, "error": "No image URLs found"})
            continue

        urls_to_download = slices if (all_slices or stitch) else [slices[0]]
        for idx, url in enumerate(urls_to_download):
            suffix = f"_{idx}" if len(urls_to_download) > 1 else ""
            filename = f"screen_{sid}{suffix}.jpg"
            dest_path = dest_dir / filename
            try:
                size_bytes = download_file(url, dest_path)
                downloaded.append({
                    "screen_id": sid,
                    "slice_index": idx,
                    "saved_to": str(dest_path.resolve()),
                    "file_size_bytes": size_bytes,
                    "file_size_kb": round(size_bytes / 1024, 2),
                    "source_url": url
                })
            except Exception as e:
                failed.append({"screen_id": sid, "slice_index": idx, "error": str(e), "source_url": url})

        # Vertical stitching if requested and multiple slices exist
        if stitch and len(urls_to_download) > 1:
            try:
                from PIL import Image
                slice_paths = [dest_dir / f"screen_{sid}_{i}.jpg" for i in range(len(urls_to_download))]
                imgs = [Image.open(p) for p in slice_paths if p.exists()]
                if imgs:
                    max_w = max(im.width for im in imgs)
                    tot_h = sum(im.height for im in imgs)
                    stitched = Image.new("RGB", (max_w, tot_h))
                    y_offset = 0
                    for im in imgs:
                        stitched.paste(im, (0, y_offset))
                        y_offset += im.height
                    stitch_path = dest_dir / f"screen_{sid}_stitched.jpg"
                    stitched.save(stitch_path, quality=95)
                    downloaded.append({
                        "screen_id": sid,
                        "type": "stitched_image",
                        "saved_to": str(stitch_path.resolve()),
                        "file_size_bytes": stitch_path.stat().st_size,
                        "file_size_kb": round(stitch_path.stat().st_size / 1024, 2)
                    })
            except ImportError:
                pass

    return {
        "status": "completed",
        "output_directory": str(dest_dir.resolve()),
        "total_downloaded": len(downloaded),
        "total_failed": len(failed),
        "files": downloaded,
        "failures": failed
    }


def refero_get_image_instructions(topic: str = "all") -> Dict[str, Any]:
    """
    Returns step-by-step instructions, DevTools scripts, and CDN patterns for extracting images from Refero:
    - Direct CloudFront CDN URL pattern (lossless, zero-auth)
    - Browser console scripts to bypass the '141 search results are hidden' overlay
    - Bulk image grabber snippet for copying all screen URLs from the browser
    - Programmatic download commands
    """
    return {
        "topic": topic,
        "direct_cdn_architecture": {
            "web_screenshots": "https://images.refero.design/screenshots/{domain}/desktop/{uuid}/{slice_index}.jpg",
            "ios_screenshots": "https://images.refero.design/app_screenshots/{app_id}/{uuid}/{slice_index}.jpg",
            "resolution": "Lossless 2732px width JPG",
            "access_control": "Zero-Auth CloudFront CDN (no cookies, no session tokens, no CORS restrictions)",
            "usage": "Embed directly in Markdown, HTML, Figma, or download via curl / python"
        },
        "browser_paywall_bypass_method": {
            "root_cause": "The '141 search results are hidden' paywall is 100% client-side in React bundle (main.25db93ca.js). On card #12, Zd.setPaywallVisibility(true) triggers div.EXPhN and body.o1Kr5 blur.",
            "devtools_unlock_snippet": """
// Step 1: Open F12 -> Console on refero.design
// Step 2: Paste and press Enter:
document.body.classList.remove("o1Kr5");
document.querySelectorAll('div[class*="EXPhN"]').forEach(e => e.remove());
document.body.style.overflow = "auto";
// Result: Modal is destroyed, page unblurs, infinite scrolling is unlocked!
""".strip()
        },
        "bulk_image_extraction_snippet": {
            "description": "Extracts all high-resolution screenshot URLs from the currently open Refero search or page:",
            "javascript_code": """
const urls = Array.from(document.querySelectorAll('img'))
  .map(img => img.src)
  .filter(src => src.includes('images.refero.design'))
  .map(src => src.replace('/preview/', '/desktop/'));
const unique = [...new Set(urls)];
copy(unique);
console.log(`[Refero] Copied ${unique.length} full-resolution CDN URLs to clipboard!`);
console.table(unique);
""".strip()
        },
        "mcp_download_commands": {
            "single_download": "refero_download_screen(screen_id='184751')",
            "batch_download": "refero_download_screen(screen_ids=['184751', '184752', '184753'])",
            "download_all_page_slices": "refero_download_screen(screen_id='184751', all_slices=True)"
        }
    }


def refero_get_screen_content(screen_id: Union[str, int]) -> Dict[str, Any]:
    """Analyze screen content, layout structure, typography, color palette, design patterns, and UI elements."""
    screen = refero_get_screen(screen_id=screen_id)
    if isinstance(screen, dict) and "error" in screen:
        return screen

    return {
        "screen_id": screen_id,
        "uuid": screen.get("uuid"),
        "site": screen.get("site", {}),
        "page_url": screen.get("page_url"),
        "direct_image_url": screen.get("direct_image_url"),
        "dimensions": {"width": screen.get("width"), "height": screen.get("height")},
        "colors_palette_rgb": screen.get("colors", []),
        "fonts": [f.get("display_name") or f.get("name") for f in screen.get("fonts", []) if f],
        "design_patterns": [p.get("name") for p in screen.get("design_patterns", []) if p],
        "page_elements": [e.get("name") for e in screen.get("page_elements", []) if e],
        "page_types": [pt.get("name") for pt in screen.get("page_types", []) if pt],
        "flow_ids": screen.get("flow_ids", [])
    }


# =====================================================================
# 4. User Journey Flows (api.refero.design)
# =====================================================================

def refero_search_flows(query: str, platform: str = "web", page: int = 1) -> Dict[str, Any]:
    """Search multi-step user journey flows (onboarding, checkout, signup, settings)."""
    encoded_q = urllib.parse.quote(query)
    ep = "search_flow/apps" if platform == "ios" else "search_flow"
    url = f"{REFERO_API_BASE}/v1/{ep}?query={encoded_q}&page={page}"
    return http_get(url, is_json=True)


def refero_get_flow(flow_id: Optional[Union[int, str]] = None, flow_ids: Optional[List[Union[int, str]]] = None) -> Any:
    """Get full multi-step journey sequence, screenshots, and transition details for flow ID(s), enriched with image embeds."""
    targets = []
    if flow_ids:
        targets = flow_ids
    elif flow_id is not None:
        targets = [flow_id]

    results = []
    for fid in targets:
        url = f"{REFERO_API_BASE}/v1/flows/{fid}"
        data = http_get(url, is_json=True)
        if isinstance(data, dict):
            scrs = data.get("screenshots", [])
            if isinstance(scrs, list):
                data["screenshots"] = [enrich_screen_record(s) for s in scrs]
                data["step_count"] = len(scrs)
        results.append(data)

    if len(results) == 1:
        return results[0]
    return results


# =====================================================================
# 5. Sites & Apps Discovery & Static Catalogs
# =====================================================================

def refero_search_site(query: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """Search web sites, domains, and design collections."""
    index_sites_screens()
    raw = RAW_SITES_CACHE or []
    q_lower = query.lower().strip()
    filtered = []
    for s in raw:
        name = (s.get("name") or "").lower()
        domain = (s.get("domain") or "").lower()
        desc = (s.get("description") or "").lower()
        if not q_lower or q_lower in name or q_lower in domain or q_lower in desc:
            filtered.append(s)

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "query": query,
        "page": page,
        "per_page": per_page,
        "total_count": total,
        "records": filtered[start:end]
    }


def refero_search_app(query: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """Search mobile iOS applications and mobile design collections."""
    encoded_q = urllib.parse.quote(query)
    url = f"{REFERO_API_BASE}/v1/search/apps?query={encoded_q}&page={page}&per_page={per_page}"
    return http_get(url, is_json=True)


def refero_get_catalog(catalog_type: str = "sites", search: str = "", limit: int = 50) -> Dict[str, Any]:
    """
    Get instant static database dump of all Web sites or iOS applications from S3.
    Requires ZERO tokens and zero authentication.
    """
    global CATALOG_APPS_CACHE, CATALOG_SITES_CACHE
    c_lower = catalog_type.lower().strip()
    is_app = "app" in c_lower

    if is_app:
        if CATALOG_APPS_CACHE is None:
            CATALOG_APPS_CACHE = http_get(f"{REFERO_WEB_BASE}/json/apps.json", is_json=True)
        items = CATALOG_APPS_CACHE if isinstance(CATALOG_APPS_CACHE, list) else []
    else:
        if CATALOG_SITES_CACHE is None:
            CATALOG_SITES_CACHE = http_get(f"{REFERO_WEB_BASE}/json/sites.json", is_json=True)
        items = CATALOG_SITES_CACHE if isinstance(CATALOG_SITES_CACHE, list) else []

    if search:
        s_lower = search.lower().strip()
        items = [i for i in items if s_lower in i.get("name", "").lower() or s_lower in i.get("description", "").lower() or s_lower in i.get("domain", "").lower()]

    return {
        "catalog_type": "apps" if is_app else "sites",
        "search": search,
        "total_in_catalog": len(items),
        "results": items[:limit]
    }


# =====================================================================
# MCP Protocol Handlers & Tool Declarations
# =====================================================================

TOOLS = [
    {
        "name": "refero_search_styles",
        "description": "Search curated design systems and aesthetic styles from styles.refero.design (e.g. 'Apple', 'Cursor', 'Minimal').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword to filter styles by name or brand."},
                "limit": {"type": "integer", "description": "Max results to return (default 10)."}
            }
        }
    },
    {
        "name": "refero_get_style",
        "description": "Get complete DESIGN.md specification including philosophy, design tokens, color palette, typography rules, and component specs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "style_id": {"type": "string", "description": "Style UUID or name from refero_search_styles."},
                "style_ids": {"type": "array", "items": {"type": "string"}, "description": "Array of style UUIDs."},
                "response_format": {"type": "string", "enum": ["md", "json"], "description": "Format for output: md (default) or json."}
            }
        }
    },
    {
        "name": "refero_search_screens",
        "description": "Search real UI screens across web and iOS products. Returns records enriched with direct lossless CDN links and Markdown/HTML embeds. Supports sorting by 'trending', 'latest', or 'oldest' to bypass single-page limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search by product name, screen type, UI element, pattern, or state."},
                "platform": {"type": "string", "enum": ["web", "ios"], "description": "Target platform: web (default) or ios."},
                "order": {"type": "string", "enum": ["trending", "latest", "oldest"], "description": "Sort order to retrieve different screen slices."},
                "page": {"type": "integer", "description": "Page number. Default: 1."},
                "per_page": {"type": "integer", "description": "Items per page (max 50). Default: 10."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "refero_get_screen",
        "description": "Get full metadata, direct lossless CDN image URLs, and element hierarchy for one or more screens by numeric ID or UUID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "screen_id": {"type": ["string", "integer"], "description": "One screen numeric ID or UUID."},
                "screen_ids": {"type": "array", "items": {"type": ["string", "integer"]}, "description": "Multiple screen IDs/UUIDs."}
            }
        }
    },
    {
        "name": "refero_get_similar_screens",
        "description": "Get visually and functionally similar screens for a given screen ID, enriched with image links and embeds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "screen_id": {"type": ["string", "integer"], "description": "Screen numeric ID or UUID."},
                "limit": {"type": "integer", "description": "Max number of similar screens to return (default: 10)."},
                "platform": {"type": "string", "enum": ["web", "ios"], "description": "Platform of screen: web or ios."}
            },
            "required": ["screen_id"]
        }
    },
    {
        "name": "refero_get_screen_image",
        "description": "Get lossless full-resolution (2732px) screenshot image URLs, preview/thumb URLs, ready-to-use Markdown/HTML embed snippets, and browser retrieval instructions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "screen_id": {"type": ["string", "integer"], "description": "Screen numeric ID or UUID."},
                "image_size": {"type": "string", "enum": ["thumbnail", "full"], "description": "Image size: thumbnail or full (lossless 2732px)."}
            },
            "required": ["screen_id"]
        }
    },
    {
        "name": "refero_download_screen",
        "description": "Download full-resolution screenshot JPG(s) directly to local disk. Supports single ID, batch list of IDs, downloading all vertical slices, and optional vertical stitching.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "screen_id": {"type": ["string", "integer"], "description": "Screen numeric ID or UUID to download."},
                "screen_ids": {"type": "array", "items": {"type": ["string", "integer"]}, "description": "List of screen IDs to batch download."},
                "output_dir": {"type": "string", "description": "Target folder on disk (default: ./screenshots)."},
                "all_slices": {"type": "boolean", "description": "If true, downloads all vertical image slices for long scrollable pages."},
                "stitch": {"type": "boolean", "description": "If true and multiple slices exist, stitches them vertically into a single image."}
            }
        }
    },
    {
        "name": "refero_get_image_instructions",
        "description": "Get detailed step-by-step instructions, DevTools scripts, and CDN patterns for extracting images and bypassing client-side paywalls on Refero.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "enum": ["all", "cdn", "browser_bypass", "console_scripts", "downloads"], "description": "Instruction topic (default: all)."}
            }
        }
    },
    {
        "name": "refero_get_screen_content",
        "description": "Extract structured design metadata (palette colors, typography names, detected design patterns, and page elements) from Refero intelligence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "screen_id": {"type": ["string", "integer"], "description": "Screen numeric ID or UUID."}
            },
            "required": ["screen_id"]
        }
    },
    {
        "name": "refero_search_flows",
        "description": "Search multi-step user journey flows (onboarding, checkout, signup, settings) for web and iOS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Journey topic (e.g., 'onboarding', 'checkout', 'upgrade')."},
                "platform": {"type": "string", "enum": ["web", "ios"], "description": "Target platform: web or ios."},
                "page": {"type": "integer", "description": "Page number. Default: 1."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "refero_get_flow",
        "description": "Get full multi-step journey sequence, screenshots, and transition details for flow ID(s), enriched with image embeds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "flow_id": {"type": ["integer", "string"], "description": "Numeric flow ID."},
                "flow_ids": {"type": "array", "items": {"type": ["integer", "string"]}, "description": "Multiple flow IDs."}
            }
        }
    },
    {
        "name": "refero_search_site",
        "description": "Search web sites, domains, and design collections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Site name or domain (e.g. 'stripe.com', 'vercel')."},
                "page": {"type": "integer", "description": "Page number. Default: 1."},
                "per_page": {"type": "integer", "description": "Items per page. Default: 10."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "refero_search_app",
        "description": "Search mobile iOS applications, App Store profiles, and mobile design collections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "iOS app name or keyword (e.g. 'Coinbase', 'Revolut')."},
                "page": {"type": "integer", "description": "Page number. Default: 1."},
                "per_page": {"type": "integer", "description": "Items per page. Default: 10."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "refero_get_catalog",
        "description": "Instant dump of static catalogue databases (317+ iOS apps or 500+ web sites) from S3 without authentication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "catalog_type": {"type": "string", "enum": ["sites", "apps"], "description": "Catalog to fetch: 'sites' or 'apps'."},
                "search": {"type": "string", "description": "Optional search term to filter catalog entries."},
                "limit": {"type": "integer", "description": "Maximum entries to return (default: 50)."}
            }
        }
    }
]


def handle_call(name: str, args: Dict[str, Any]) -> Any:
    """Dispatches MCP tool call to the appropriate function."""
    if name == "refero_search_styles":
        return refero_search_styles(args.get("query", ""), args.get("limit", 10))
    elif name == "refero_get_style":
        return refero_get_style(args.get("style_id"), args.get("style_ids"), args.get("response_format", "md"))
    elif name == "refero_search_screens":
        return refero_search_screens(
            args.get("query", ""),
            args.get("platform", "web"),
            args.get("order", "trending"),
            args.get("page", 1),
            args.get("per_page", 10)
        )
    elif name == "refero_get_screen":
        return refero_get_screen(args.get("screen_id"), args.get("screen_ids"))
    elif name == "refero_get_similar_screens":
        return refero_get_similar_screens(args.get("screen_id", ""), args.get("limit", 10), args.get("platform", "web"))
    elif name == "refero_get_screen_image":
        return refero_get_screen_image(args.get("screen_id", ""), args.get("image_size", "full"))
    elif name == "refero_download_screen":
        return refero_download_screen(
            screen_id=args.get("screen_id"),
            screen_ids=args.get("screen_ids"),
            output_dir=args.get("output_dir"),
            all_slices=args.get("all_slices", False),
            stitch=args.get("stitch", False)
        )
    elif name == "refero_get_image_instructions":
        return refero_get_image_instructions(args.get("topic", "all"))
    elif name == "refero_get_screen_content":
        return refero_get_screen_content(args.get("screen_id", ""))
    elif name == "refero_search_flows":
        return refero_search_flows(args.get("query", ""), args.get("platform", "web"), args.get("page", 1))
    elif name == "refero_get_flow":
        return refero_get_flow(args.get("flow_id"), args.get("flow_ids"))
    elif name == "refero_search_site":
        return refero_search_site(args.get("query", ""), args.get("page", 1), args.get("per_page", 10))
    elif name == "refero_search_app":
        return refero_search_app(args.get("query", ""), args.get("page", 1), args.get("per_page", 10))
    elif name == "refero_get_catalog":
        return refero_get_catalog(args.get("catalog_type", "sites"), args.get("search", ""), args.get("limit", 50))
    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """Main JSON-RPC stdio loop for Model Context Protocol."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "ping":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}) + "\n")
            sys.stdout.flush()

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                data = handle_call(tool_name, tool_args)
                text_out = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text_out}]
                    }
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
