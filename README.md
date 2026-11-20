<div align="center">

# ✦ Refero MCP Proxy

**Dual-engine Model Context Protocol (MCP) server for Refero design references, real-world UX journeys, and offline dataset mirrors.**

[![Issues](https://img.shields.io/github/issues/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=f0abfc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/pulls)
[![Stars](https://img.shields.io/github/stars/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=c4b5fd&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/stargazers)
[![Forks](https://img.shields.io/github/forks/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/forks)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

[Quick Start](#-quick-start) · [Architecture & Engines](#-architecture--engines) · [Local Image Storage (CAS)](#-local-image-storage--reading-mechanism) · [Tools](#-tool-reference-14-tools) · [Setup Guide](docs/setup.md) · [Issues](https://github.com/SkrudjReal/refero-mcp-proxy/issues/new)

</div>

---

**Refero MCP Proxy** connects AI coding assistants (Codex, Antigravity, Claude Code, Cursor, Gemini CLI) directly to real-world UI screens, design systems, and multi-step UX journey flows.

It operates via standard I/O (JSON-RPC 2.0 stdio) and features a **dual-engine architecture**:
1. **Remote Bypass Engine**: Extracts high-resolution, unwatermarked design assets directly from upstream APIs and CloudFront CDNs without web paywall restrictions or active browser automation.
2. **Local Offline Engine**: A zero-dependency, air-gapped catalog engine bundled with **242,872 direct screenshot URLs across 778 products** (`refero_all_links_images.json`) and Content-Addressable Storage (CAS) for local image and UX flow resolution.

---

## ✧ Architecture & Engines

```
                      ┌─────────────────────────────────────────┐
                      │    AI Client (Codex / Antigravity /     │
                      │       Claude Code / Cursor / etc.)      │
                      └────────────────────┬────────────────────┘
                                           │ JSON-RPC stdio
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │          refero_mcp_server.py           │
                      └─────────────┬─────────────────────┬─────┘
                                    │                     │
               ┌────────────────────┴───┐             ┌───┴─────────────────────┐
               ▼                        ▼             ▼                         ▼
   [Remote Bypass Engine]               [Local Offline Engine]
   • Direct REST API calls              • Bundled Catalog (refero_all_links_images.json)
   • Unwatermarked CloudFront CDNs      • SQLite Database (data/refero_local.db)
   • 2732px retina image URLs           • CAS Local Image Store (fleet/images/xx/hash.jpg)
   • Live UX flows & design tokens      • Local UX Flow Sequences (fleet/flows/*.json)
```

### 1. Remote Bypass Engine
In standard operation, `refero-mcp-proxy` acts as a specialized proxy between the AI model and Refero’s infrastructure:
* **Paywall & Watermark Elimination**: Bypasses client-side subscription checks, obfuscation scripts, and UI blur layers by querying direct backend REST endpoints (`/v1/screenshots/{id}`, `/v1/flows/{id}`).
* **Full-Resolution Assets**: Automatically derives raw CloudFront CDN URLs delivering original 2732px retina screenshots and individual scroll slices instead of downsampled thumbnails.
* **Zero Token Requirements for Basic Research**: Retrieves publicly indexed design systems, curated collections, and UI patterns without requiring session cookies or API keys.

### 2. Local Offline Engine & Zero-Config Mode
When offline or running in private/air-gapped environments, the server provides full functionality without external network dependencies:
* **Bundled Catalog (`refero_all_links_images.json`)**: Comes pre-packaged with complete metadata and direct CDN links for **778 curated products (463 web sites and 315 iOS applications)** and **242,872 unique screenshots**.
* **Zero-Config Fallback**: If the optional SQLite database (`data/refero_local.db`) is not present, the server transparently parses and serves catalog queries directly from `refero_all_links_images.json`.
* **Air-Gapped Enforcement**: Setting `REFERO_OFFLINE=1` guarantees zero outbound network requests; queries are strictly fulfilled from the local catalog and mirrored assets.

---

## ✧ Local Image Storage & Reading Mechanism

The offline mirror stores media and UX flows using **Content-Addressable Storage (CAS)** to ensure atomic deduplication and high filesystem performance across hundreds of thousands of files.

### 1. Content-Addressable Image Layout
Images are stored deterministically based on the SHA-256 hash of their canonical CDN URL:

$$\text{hash} = \text{SHA-256}(\text{Image CDN URL})$$

$$\text{Path} = \texttt{fleet/images/}\{\text{hash}[0:2]\}\texttt{/}\{\text{hash}\}\texttt{.jpg}$$

```
fleet/
└── images/
    ├── 00/
    │   ├── 0001a7bf...9c.jpg
    │   └── ...
    ├── 3f/
    │   ├── 3f8a91c2...1b.jpg
    │   └── ...
    └── ff/
        └── ff98b2c4...e0.jpg
```

* **256 Prefix Shards (`00/` – `ff/`)**: Distributing files across 256 subdirectories prevents directory entry limits and inode traversal bottlenecks on NTFS, ext4, and APFS filesystems when storing 250,000+ images.
* **Deterministic Resolution**: When `refero_download_screen` or `refero_get_screen_image` is invoked:
  1. The server identifies the target screenshot's CloudFront URL.
  2. It computes the SHA-256 digest of the URL.
  3. It verifies whether `fleet/images/<hash[:2]>/<hash>.jpg` exists in the local data directory.
  4. If found, the image is immediately copied or served from disk with zero network latency. If absent and `REFERO_OFFLINE` is not set, it downloads and caches the file.

### 2. UX Flow Sequences
Flows are stored as standalone atomic JSON structures under:
```
fleet/flows/{flow_id}.json
```
Each flow contains the step-by-step user journey, route transitions, action descriptions, and references to all involved screen assets. In offline mode, `refero_get_flow` directly resolves from this folder.

### 3. Configuring Local Mirror Storage (`REFERO_DATA_DIR`)
You can point the MCP server to your local archive or external storage mount using the `REFERO_DATA_DIR` environment variable:
```bash
export REFERO_DATA_DIR="/path/to/refero-full-data"
```
The server automatically searches for:
1. `$REFERO_DATA_DIR/fleet/images` and `$REFERO_DATA_DIR/fleet/flows`
2. Neighbor directory `outputs/refero-full-data/fleet`
3. Repository-relative `./fleet` or `./data`

---

## ✧ Quick Start

Requires **Python 3.8+**. Core features rely entirely on the Python standard library; multi-image slice stitching optionally utilizes `Pillow`.

```bash
git clone https://github.com/SkrudjReal/refero-mcp-proxy.git
cd refero-mcp-proxy
```

### Client Integration Examples

#### Codex (CLI / IDE)
Add to `~/.codex/config.toml` (Linux/macOS) or `%USERPROFILE%\.codex\config.toml` (Windows):

```toml
[mcp_servers.refero]
command = "python"
args = ["/path/to/refero-mcp-proxy/refero_mcp_server.py"]
# Optional: Enforce 100% offline mode
# env = { REFERO_OFFLINE = "1", REFERO_DATA_DIR = "/path/to/refero-full-data" }
```

#### Antigravity (CLI / IDE)
Add to `~/.gemini/config/mcp_config.json` (Windows: `%USERPROFILE%\.gemini\config\mcp_config.json`):

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

#### Claude Code
```bash
claude mcp add refero python /path/to/refero_mcp_server.py
```

#### Cursor (`~/.cursor/mcp.json`)
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

Detailed client setup, Windows escaping rules, and environment flags are documented in [docs/setup.md](docs/setup.md).

---

## ✧ Tool Reference (14 Tools)

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `refero_search_screens` | `query`, `platform`, `order`, `page`, `per_page` | Search real UI screens. Automatically enriched with direct CDN URLs and preview embeds. |
| `refero_get_screen` | `screen_id` / `screen_ids` | Retrieve full screen metadata, dimensions, font tokens, RGB color palettes, and high-res image URLs. |
| `refero_get_similar_screens`| `screen_id`, `limit`, `platform` | Find design-similar screens (remote similarity or offline catalog grouping). |
| `refero_get_screen_image` | `screen_id`, `image_size` (`full`/`thumbnail`) | Return full-resolution source image URLs, local cached file paths, and Markdown preview embeds. |
| `refero_download_screen` | `screen_id`, `output_dir`, `all_slices`, `stitch` | Download lossless JPG(s) to local disk. Resolves from local CAS storage when available. Supports multi-slice stitching. |
| `refero_get_image_instructions`| `topic` (`all`/`cdn`/`browser_bypass`/`console_scripts`) | Comprehensive guide and snippets for direct CDN derivation and browser paywall bypass. |
| `refero_get_screen_content`| `screen_id` | Extract visual design breakdown: typography tokens, 5-color palette, UI components, and layout geometry. |
| `refero_search_flows` | `query`, `platform`, `page` | Search multi-step user flows (onboarding, checkout, authentication, settings). |
| `refero_get_flow` | `flow_id` / `flow_ids` | Fetch complete UX flow step sequences with transition annotations and screen URLs. |
| `refero_search_styles` | `query`, `limit` | Search design systems from `styles.refero.design` (Apple, Linear, Cursor, Stripe, etc.). |
| `refero_get_style` | `style_id`, `response_format` (`md`/`json`) | Retrieve complete design specification (`DESIGN.md` or JSON tokens). |
| `refero_search_site` | `query`, `page`, `per_page` | Search web services, SaaS products, and landing page collections. |
| `refero_search_app` | `query`, `page`, `per_page` | Search iOS mobile applications and App Store product collections. |
| `refero_get_catalog` | `catalog_type` (`sites`/`apps`), `search`, `limit` | Query indexed products from local JSON catalog or remote upstream. |

Detailed examples and parameters can be found in [docs/reference.md](docs/reference.md).

---

## ✧ Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `REFERO_OFFLINE` | `0` | When set to `1` or `true`, blocks all external HTTP calls and relies purely on local catalogs and CAS storage. |
| `REFERO_DATA_DIR`| Auto-detected | Path to the directory containing local `fleet/` assets and `refero_local.db`. |
| `REFERO_TOKEN` | *None* | Optional Refero bearer authentication token for authenticated API requests. |

---

## ✧ Verification & Tests

Run the deterministic regression suite (executes 100% offline without external network access or extra dependencies):

```bash
python -m unittest -v test_regressions
```

Run the live server smoke test suite:

```bash
python test_server.py
```

---

## ✧ License

This project is licensed under the [MIT License](LICENSE).
