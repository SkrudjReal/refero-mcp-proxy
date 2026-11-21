<div align="center">

# ✦ Refero MCP Proxy

**Dual-engine Model Context Protocol (MCP) server for Refero design references, real-world UX journeys, and offline dataset mirrors.**

[![Issues](https://img.shields.io/github/issues/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=f0abfc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/pulls)
[![Stars](https://img.shields.io/github/stars/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=c4b5fd&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/stargazers)
[![Forks](https://img.shields.io/github/forks/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/forks)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

[Quick Start](#-quick-start) · [Dataset Mirror (Google Drive)](#-offline-dataset-mirror--download) · [Benchmarks](#-performance-benchmarks-local-mirror-vs-remote-api) · [Architecture & Engines](#-architecture--engines) · [Local CAS Storage](#-local-image-storage--reading-mechanism) · [Tools](#-tool-reference-14-tools) · [Setup Guide](docs/setup.md) · [Issues](https://github.com/SkrudjReal/refero-mcp-proxy/issues/new)

</div>

---

**Refero MCP Proxy** connects AI coding assistants (Codex, Antigravity, Claude Code, Cursor, Gemini CLI) directly to real-world UI screens, design systems, and multi-step UX journey flows.

It operates via standard I/O (JSON-RPC 2.0 stdio) and features a **dual-engine architecture**:
1. **Remote Bypass Engine**: Extracts high-resolution, unwatermarked design assets directly from upstream APIs and CloudFront CDNs without web paywall restrictions or active browser automation.
2. **Local Offline Engine**: A zero-dependency, air-gapped catalog engine bundled with **242,872 direct screenshot URLs across 778 products** (`refero_all_links_images.json`) and Content-Addressable Storage (CAS) for local image and UX flow resolution.

---

## ✧ Performance Benchmarks: Local Mirror vs. Remote API

Empirical benchmarks measured on live production workloads comparing direct upstream Refero REST API/CDN calls against local Content-Addressable Storage (CAS) and offline JSON catalogs:

| Operation | Remote Live API | Local Mirror (CAS / JSON) | Acceleration |
| :--- | :--- | :--- | :--- |
| **Product / Site Search** (`refero_search_site`) | 151.6 ms | 0.20 ms | **742x faster** |
| **UX Journey Flow Retrieval** (`refero_get_flow`) | 450.2 ms | 0.37 ms | **1,229x faster** |
| **Design System Spec Parsing** (`refero_get_style`) | 4,399.1 ms | 1.17 ms | **3,775x faster** |
| **Screenshot Asset Resolution** (`refero_download_screen`) | 52.1 – 124.6 ms | 0.95 – 1.36 ms | **38x – 131x faster** |
| **Catalog Query & Filtering** (`refero_get_catalog`) | 145.6 ms | 0.15 ms | **970x faster** |

### Live Benchmark Run Output
```text
$ python benchmark.py
============================================================
 ✦ Refero MCP Proxy: Remote vs Local Mirror Benchmarks
============================================================

[1/5] Benchmarking Product Search (`refero_search_site 'linear'`)...
      Remote: 146.2 ms | Local: 0.32 ms (455x faster)

[2/5] Benchmarking UX Journey Flow (`refero_get_flow 10006`)...
      Remote: 506.3 ms | Local: 2.22 ms (228x faster)

[3/5] Benchmarking Design System (`refero_get_style Apple`)...
      Remote: 4016.6 ms | Local: 2.10 ms (1910x faster)

[4/5] Benchmarking Screenshot Resolution (CloudFront CDN vs Local CAS)...
      Remote: 98.6 ms | Local: 4.92 ms (20x faster)

[5/5] Benchmarking Catalog Query (`refero_get_catalog 'sites'`)...
      Remote: 225.8 ms | Local: 0.15 ms (970x faster)

================================================================================
✦ ALL CHECKS COMPLETED: Local offline operations eliminate network latency,
  CloudFront round-trips, rate-limits, and paywall restrictions.
================================================================================
```

* Benchmarks executed on Windows 11 (Python 3.12, NVMe SSD, 100 Mbps broadband). Anyone cloning the repository can reproduce the benchmark in real time:
```bash
python benchmark.py
```

---

## ✧ Offline Dataset Mirror & Download

The complete Refero dataset archive (**360,332 files | ~41.5 GB**) is publicly hosted on Google Drive:

### 📦 [Download Complete Refero Archive (Google Drive)](https://drive.google.com/drive/folders/1w9kEhGqLZ70K0Sui2W5IEQnTAaSxAWLT)

The Google Drive repository is structured into modular packages so you can download only what you need:

| Package | Size | Description |
| :--- | :--- | :--- |
| `_catalogs/` (Folder) | ~55 MB | Direct viewable/searchable JSON catalogs (`refero_all_links_images.json`, `sites_available.json`, `apps_available.json`). |
| `refero_styles_design_systems.zip` | 124.9 MB | All 1,342 design systems (`DESIGN.md`, `spec.json`, `source.html`, and preview images). |
| `refero_flows.zip` | 10.9 MB | All 13,698 multi-step UX journey flows (`fleet/flows/*.json`). |
| `refero_site_assets_and_pages.zip` | 18.2 MB | Curated collection pages, design articles, and site assets. |
| `refero_fleet_images_00_3f.zip` | 7.61 GB | Full-resolution screenshot shard (`00` through `3f`). |
| `refero_fleet_images_40_7f.zip` | 7.52 GB | Full-resolution screenshot shard (`40` through `7f`). |
| `refero_fleet_images_80_bf.zip` | 7.53 GB | Full-resolution screenshot shard (`80` through `bf`). |
| `refero_fleet_images_c0_ff.zip` | 7.58 GB | Full-resolution screenshot shard (`c0` through `ff`). |
| `refero_web_screens.zip` | 7.35 GB | Web screenshots legacy archive. |
| `refero_ios_screens.zip` | 3.43 GB | iOS screenshots legacy archive. |
| `README_DATASET.md` | 2.7 KB | Dataset layout documentation and extraction guide. |

### Where to Extract for Automatic MCP Detection

To enable instant local resolution in `refero-mcp-proxy`, unpack the archives following this directory layout:

```text
your-project/
├── refero-mcp-proxy/
│   ├── refero_mcp_server.py
│   └── refero_all_links_images.json
└── outputs/refero-full-data/          <-- Auto-detected by default!
    ├── fleet/
    │   ├── flows/                     <-- Unpack refero_flows.zip here (*.json)
    │   └── images/                    <-- Unpack refero_fleet_images_*.zip here (00/..ff/)
    ├── styles/                        <-- Unpack refero_styles_design_systems.zip here
    ├── web/                           <-- Unpack refero_web_screens.zip here
    └── ios/                           <-- Unpack refero_ios_screens.zip here
```

#### Custom Storage Directory (`REFERO_DATA_DIR`)
If you store the dataset on another drive or folder, pass its path via the `REFERO_DATA_DIR` environment variable:
```bash
# Linux / macOS
export REFERO_DATA_DIR="/Volumes/ExternalDrive/refero-full-data"

# Windows (PowerShell)
$env:REFERO_DATA_DIR = "D:\Datasets\refero-full-data"
```

The server automatically scans `$REFERO_DATA_DIR/fleet/images` and `$REFERO_DATA_DIR/fleet/flows`. In offline mode (`REFERO_OFFLINE=1`), all image downloads and flow lookups resolve locally with zero latency.

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
      "args": ["/path/to/refero-mcp-proxy/refero_mcp_server.py"],
      "env": {
        "REFERO_DATA_DIR": "C:/Projects/outputs/refero-full-data"
      }
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
