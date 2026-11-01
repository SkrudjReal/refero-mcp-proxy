# Refero MCP Proxy (`refero-mcp-proxy`)

[![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-blue.svg)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green.svg)](https://python.org)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Standard%20Lib)-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

A standalone, zero-dependency Python Model Context Protocol (MCP) server providing reverse-engineered access to the entire **Refero Design** (`refero.design` and `styles.refero.design`) UI/UX intelligence catalog:

- **Real Product Screens**: Web & iOS application screens with direct lossless 2732px CloudFront CDN links.
- **Multi-Step User Journeys**: Complete multi-screen UX flows (onboarding, checkout, signup, settings).
- **Curated Design Systems**: Automated extraction of `DESIGN.md` specs (colors, typography, spacing, guidelines) from `styles.refero.design`.
- **Zero-Auth Asset Pipeline**: Direct CDN image links, Markdown/HTML embeds, local disk batch downloading, and multi-slice stitching.
- **Paywall Bypass Architecture**: Complete client-side paywall breakdown, DevTools unlock snippets, and API sorting rotation.

---

## Architecture & How It Works

```
                                      ┌────────────────────────────────────────┐
                                      │        Client LLM / AI Agent           │
                                      │  (Claude Code / Cursor / Antigravity)  │
                                      └──────────────────┬─────────────────────┘
                                                         │ JSON-RPC 2.0 (stdio)
                                                         ▼
                                      ┌────────────────────────────────────────┐
                                      │          refero_mcp_server.py          │
                                      │      (Pure Python, Zero External)      │
                                      └───────┬──────────────┬──────────────┬──┘
                                              │              │              │
                   ┌──────────────────────────┘              │              └────────────────────────┐
                   ▼                                         ▼                                       ▼
    ┌─────────────────────────────┐        ┌──────────────────────────────────┐        ┌──────────────────────────┐
    │     api.refero.design       │        │      styles.refero.design        │        │   images.refero.design   │
    │  - /v1/search (web screens) │        │  - Next.js RSC Streaming         │        │  - Unauthenticated CDN   │
    │  - /v1/search/apps (iOS)    │        │  - self.__next_f extraction      │        │  - Lossless 2732px JPGs  │
    │  - /v1/screenshots/{uuid}   │        │  - DESIGN.md specs & tokens      │        │  - Multi-slice assets    │
    │  - /v1/flows/{id}           │        └──────────────────────────────────┘        └──────────────────────────┘
    │  - /v1/sites                │
    └─────────────────────────────┘
```

### 1. Zero External Dependencies
The server is written in standard Python 3.8+ using exclusively `urllib.request`, `json`, `re`, `pathlib`, and `os`. No `pip install`, no virtual environments, and no bloat.

### 2. Zero-Auth Direct CloudFront CDN
Refero's web frontend restricts access to screenshots after card #12, but the underlying media assets are hosted on an unauthenticated AWS CloudFront CDN:
- Web: `https://images.refero.design/screenshots/{domain}/desktop/{uuid}/{slice_index}.jpg`
- iOS: `https://images.refero.design/app_screenshots/{app_id}/{uuid}/{slice_index}.jpg`

These files can be requested directly by any client, loaded in `<img>` tags, or downloaded to disk without authentication cookies, session headers, or subscription gates.

### 3. The "141 search results are hidden" Paywall Breakdown
In Refero's frontend bundle (`main.25db93ca.js`):
- When an unauthenticated user scrolls past screen #12, the client-side scroll listener triggers:
  ```javascript
  if (!Xd.isSignedIn() || !Xd.hasSubscription()) {
    Zd.setPaywallVisibility(true);
  }
  ```
- This injects a modal overlay `<div class="EXPhN">` and applies the CSS class `body.o1Kr5` (`filter: blur(8px); overflow: hidden;`).
- **The backend has no such restriction**: `/v1/search` and `/v1/search/apps` return all 24 records per page without gating.
- **Pagination Bypass via Sorting Rotation**: Rotating `order=trending`, `order=latest`, and `order=oldest` pulls up to 72 unique, highly relevant screens per search term.

---

## Tool Reference (14 Tools)

| Tool | Parameters | Description |
|---|---|---|
| `refero_search_styles` | `query`, `limit` | Searches curated design systems from `styles.refero.design` (e.g. Apple, Cursor, Minimal). |
| `refero_get_style` | `style_id` / `style_ids`, `response_format` (`md`/`json`) | Fetches complete `DESIGN.md` spec (colors, fonts, layout rules, component guidelines). |
| `refero_search_screens` | `query`, `platform` (`web`/`ios`), `order` (`trending`/`latest`/`oldest`), `page`, `per_page` | Searches real UI screens. Automatically enriches all records with direct CDN URLs and embeds. |
| `refero_get_screen` | `screen_id` / `screen_ids` (numeric ID or UUID) | Retrieves full metadata, dimensions, font tokens, RGB palettes, and high-res image URLs. |
| `refero_get_similar_screens` | `screen_id`, `limit`, `platform` | Finds visually and functionally similar screens based on UI layout. |
| `refero_get_screen_image` | `screen_id`, `image_size` (`full`/`thumbnail`) | Returns lossless 2732px CDN link, preview/thumb links, Markdown/HTML embeds, and instructions. |
| `refero_download_screen` | `screen_id` / `screen_ids`, `output_dir`, `all_slices` (bool) | Downloads full-resolution JPG(s) to local disk. Supports multi-slice screens. |
| `refero_get_image_instructions` | `topic` (`all`/`cdn`/`browser_bypass`/`console_scripts`/`downloads`) | Returns complete instructions, DevTools scripts, and CDN patterns. |
| `refero_get_screen_content` | `screen_id` | Analyzes screen layout, typography list, color palette, design patterns, and page elements. |
| `refero_search_flows` | `query`, `platform`, `page` | Searches multi-step user journey flows (onboarding, checkout, signup, settings). |
| `refero_get_flow` | `flow_id` / `flow_ids` | Retrieves the entire multi-step screen sequence with transitions and image links. |
| `refero_search_site` | `query`, `page`, `per_page` | Searches web services, domains, and design collections. |
| `refero_search_app` | `query`, `page`, `per_page` | Searches iOS mobile apps and App Store design collections. |
| `refero_get_catalog` | `catalog_type` (`sites`/`apps`), `search`, `limit` | Static database dump of 317+ iOS apps or 500+ web sites from S3 without auth. |

---

## Image Retrieval & Paywall Bypass Guide

### 1. In Browser: DevTools Paywall Unlock
If you are browsing `refero.design` in Chrome/Firefox and hit the "141 search results are hidden" banner:
1. Press `F12` to open DevTools, then switch to the **Console** tab.
2. Paste and run:
```javascript
document.body.classList.remove("o1Kr5");
document.querySelectorAll('div[class*="EXPhN"]').forEach(e => e.remove());
document.body.style.overflow = "auto";
```
3. The paywall banner is removed, cards are unblurred, and scrolling is restored.

### 2. In Browser: Bulk High-Res Image Extraction
To copy all full-resolution screenshot URLs from the open Refero page:
```javascript
const urls = Array.from(document.querySelectorAll('img'))
  .map(img => img.src)
  .filter(src => src.includes('images.refero.design'))
  .map(src => src.replace('/preview/', '/desktop/'));
const unique = [...new Set(urls)];
copy(unique);
console.log(`Copied ${unique.length} full-resolution CDN URLs to clipboard!`);
```

### 3. Programmatic Download via MCP
```python
# Single screenshot download
refero_download_screen(screen_id="184751")

# Batch download multiple screens
refero_download_screen(screen_ids=["184751", "184752", "184753"])

# Download all vertical slices of a long scrollable screen
refero_download_screen(screen_id="184751", all_slices=True)
```

---

## Installation & Integration

### Claude Code (`~/.claude.json` or command line)
```bash
claude mcp add refero python /path/to/refero_mcp_server.py
```

### Cursor / Codex (`~/.cursor/mcp.json` or `config.toml`)
```json
{
  "mcpServers": {
    "refero": {
      "command": "python",
      "args": ["/path/to/refero-mcp-proxy/refero_mcp_server.py"]
    }
  }
}
```

### Antigravity / Gemini CLI (`mcp_config.json`)
```json
{
  "mcpServers": {
    "refero": {
      "command": "python",
      "args": ["/path/to/refero-mcp-proxy/refero_mcp_server.py"]
    }
  }
}
```

---

## Testing

Run the included standalone test suite:
```bash
python test_server.py
```

Output:
```text
Testing refero-mcp-proxy v2.2.0...
Total tools registered: 14
1. refero_search_styles: OK
3. refero_search_screens: OK
   Enriched image links in search: OK
4. refero_get_screen: OK
5. refero_get_similar_screens: OK
6. refero_get_screen_image: OK
7. refero_get_image_instructions: OK
8. refero_download_screen: OK
9. refero_get_screen_content: OK
10. refero_search_flows: OK
11. refero_get_flow: OK
12. refero_search_site: OK
13. refero_search_app: OK
14. refero_get_catalog: OK

All 14 tools verified successfully!
```

---

## Security & Privacy Verification

- **Zero Hardcoded Secrets**: This repository contains no personal tokens, JWTs, usernames, cookies, or session keys.
- **Optional Authentication**: If you own a Refero Pro account and wish to pass an auth token, set the `REFERO_TOKEN` environment variable. The proxy functions fully with zero authentication.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
