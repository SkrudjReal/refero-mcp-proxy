# ✧ Setup and offline use

[← README](../README.md) · [Tool reference](reference.md)

## Installation & Integration

### Claude Code (`~/.claude.json` or command line)
```bash
claude mcp add refero python /path/to/refero_mcp_server.py
```

Python 3.8+ is required. Use an absolute path to the script and a Python executable visible to the client. A Linux/WSL client needs Linux paths; a native Windows client needs Windows paths. No lifecycle hook is required: the client launches this stdio server itself.

### Codex (CLI and IDE)

Add the entry to `~/.codex/config.toml` on Linux/WSL, or `%USERPROFILE%\.codex\config.toml` on Windows. Replace the example paths with your installation paths.

Linux/WSL:

```toml
[mcp_servers.refero]
command = "python3"
args = ["/absolute/path/refero-mcp-proxy/refero_mcp_server.py"]
```

Windows (TOML literal strings preserve backslashes):

```toml
[mcp_servers.refero]
command = 'C:\Path\To\Python\python.exe'
args = ['C:\Projects\refero-mcp-proxy\refero_mcp_server.py']
```

Alternatively, on Linux/WSL:

```bash
codex mcp add refero -- python3 /absolute/path/refero-mcp-proxy/refero_mcp_server.py
codex mcp get refero
```

See [official Codex MCP documentation](https://developers.openai.com/codex/mcp).

### Cursor (`~/.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "refero": {
      "command": "python3",
      "args": ["/path/to/refero-mcp-proxy/refero_mcp_server.py"]
    }
  }
}
```

### Antigravity (CLI and IDE)

Use `~/.gemini/config/mcp_config.json` on Linux/WSL or `%USERPROFILE%\.gemini\config\mcp_config.json` on Windows. In the IDE, **MCP Servers → Manage MCP Servers → View raw config** opens the configuration used by that installation. Preserve existing entries in `mcpServers`.

Linux/WSL:
```json
{
  "mcpServers": {
    "refero": {
      "command": "python3",
      "args": ["/path/to/refero-mcp-proxy/refero_mcp_server.py"]
    }
  }
}
```

Windows (JSON requires escaped backslashes, or use forward slashes):

```json
{
  "mcpServers": {
    "refero": {
      "command": "C:/Path/To/Python/python.exe",
      "args": ["C:/Projects/refero-mcp-proxy/refero_mcp_server.py"]
    }
  }
}
```

Reload MCP servers after editing. See [Antigravity MCP documentation](https://antigravity.google/docs/mcp).

### Gemini CLI

Use the same `mcpServers` JSON structure in `~/.gemini/settings.json` (Windows: `%USERPROFILE%\.gemini\settings.json`), not Antigravity's `mcp_config.json`. See [Gemini CLI MCP documentation](https://geminicli.com/docs/tools/mcp-server/).

### OpenCode

Add to `~/.config/opencode/opencode.json` (Windows: `%USERPROFILE%\.config\opencode\opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "refero": {
      "type": "local",
      "command": ["python", "/absolute/path/to/refero-mcp-proxy/refero_mcp_server.py"],
      "enabled": true
    }
  }
}
```

---

## Automated 1-Click Installation (`install.sh` / `install.ps1`)

The repository includes cross-platform installers that automatically update configs for Codex, Antigravity, Claude Code, and OpenCode:

```bash
# Linux / macOS
chmod +x install.sh
./install.sh

# Windows (PowerShell)
.\install.ps1
```

Supported flags:
- `--clients codex,antigravity,claude,opencode`: Target specific clients.
- `--unpack [path]`: Extract downloaded Google Drive archives.
- `--data-dir <path>`: Set custom dataset storage path.
- `--offline`: Enforce 100% offline air-gapped mode.
- `--status`: Check configuration status without altering files.

---

## Offline Dataset Mirror Download & Setup

The complete Refero dataset archive (**360,332 files | ~41.5 GB**) is available on Google Drive:

🔗 **[Google Drive Complete Dataset Repository](https://drive.google.com/drive/folders/1w9kEhGqLZ70K0Sui2W5IEQnTAaSxAWLT)**

### Available Packages

- `_catalogs/` (Folder): Direct JSON files (`refero_all_links_images.json`, `sites_available.json`, `apps_available.json`).
- `refero_styles_design_systems.zip` (124.9 MB): 1,342 design systems with `DESIGN.md`, tokens, and previews.
- `refero_flows.zip` (10.9 MB): 13,698 UX journey flows (`fleet/flows/*.json`).
- `refero_fleet_images_00_3f.zip` (7.61 GB): Shards `00`–`3f`.
- `refero_fleet_images_40_7f.zip` (7.52 GB): Shards `40`–`7f`.
- `refero_fleet_images_80_bf.zip` (7.53 GB): Shards `80`–`bf`.
- `refero_fleet_images_c0_ff.zip` (7.58 GB): Shards `c0`–`ff`.
- `refero_web_screens.zip` (7.35 GB) & `refero_ios_screens.zip` (3.43 GB).

### Extraction Guide & Directory Placement

To have the proxy auto-detect the offline data without configuring environment variables, place it in an `outputs/refero-full-data` directory adjacent to your project or repository:

```text
workspace/
├── refero-mcp-proxy/
│   ├── refero_mcp_server.py
│   └── refero_all_links_images.json
└── outputs/refero-full-data/
    ├── fleet/
    │   ├── flows/                     <-- Extract refero_flows.zip
    │   └── images/                    <-- Extract refero_fleet_images_*.zip (00/..ff/)
    ├── styles/                        <-- Extract refero_styles_design_systems.zip
    ├── web/                           <-- Extract refero_web_screens.zip
    └── ios/                           <-- Extract refero_ios_screens.zip
```

Alternatively, extract anywhere and set `REFERO_DATA_DIR`:
```bash
export REFERO_DATA_DIR="/path/to/extracted/refero-full-data"
```

---

## Performance Benchmarks: Local Mirror vs. Remote API

Empirical benchmarks measured with `python benchmark.py` (every check verifies a valid, non-error payload):

| Operation | Remote Live API | Local Mirror | Acceleration |
| :--- | :--- | :--- | :--- |
| **Product / Site Search** (`refero_search_site`) | 6,596.2 ms | 0.17 ms warm (224.6 ms cold) | **39,832x faster (warm) / 29x (cold)** |
| **UX Journey Flow Retrieval** (`refero_get_flow`) | 398.0 ms | 2.42 ms | **164x faster** |
| **Design System Spec Parsing** (`refero_get_style`) | 4,120.9 ms | 3.78 ms | **1,090x faster** |
| **Screenshot Asset Resolution** (`download_file` CAS) | 95.5 ms | 5.35 ms | **18x faster** |
| **Catalog Load** (`refero_get_catalog`) | 312.4 ms | 2.75 ms | **113x faster** |

To run these comparative benchmarks on your machine:
```bash
python benchmark.py
```

---

## Offline Catalogs & Content-Addressable Image Storage (CAS)

The server supports two levels of offline operation:
1. **Zero-Config Bundled Catalog (`refero_all_links_images.json`)**:
   - Ships directly with the repository at root.
   - Contains 242,872 unique direct screenshot URLs across 778 products (463 web sites, 315 iOS apps).
   - If no SQLite database exists in `data/refero_local.db`, the server automatically activates this catalog as a fallback for `refero_get_catalog`, `refero_search_site`, `refero_search_app`, and screen URL searches.
2. **Relational SQLite Mirror (`data/refero_local.db`)**:
   - Built optionally using `mirror_refero.py` or provided via external download.
   - Indexes comprehensive relational metadata: search tags, UI patterns, color palettes, and individual flow steps.

### Content-Addressable Storage (CAS) Layout
Images downloaded or mirrored locally are stored deterministically using the SHA-256 hash of their raw CloudFront CDN URL:

$$\text{hash} = \text{SHA-256}(\text{CDN URL})$$
$$\text{Path} = \texttt{fleet/images/}\{\text{hash}[0:2]\}\texttt{/}\{\text{hash}\}\texttt{.jpg}$$

Example:
- CDN URL: `https://images.refero.design/screenshots/cursor.com/desktop/a1b2c3d4/0.jpg`
- SHA-256 Digest: `3f8a91c2e4...`
- Stored At: `fleet/images/3f/3f8a91c2e4...jpg`

The 256 two-character prefix shards (`00/` through `ff/`) ensure fast filesystem inode lookups and prevent single-directory saturation on filesystems like NTFS, ext4, and APFS.

When `refero_download_screen` or `refero_get_screen_image` is invoked, the proxy computes the hash of the requested screen's CloudFront URL and checks the local CAS directory:
- If present, the image is immediately copied or referenced from disk with zero network delay.
- If missing, it falls back to an HTTP download (unless `REFERO_OFFLINE=1` is active).

### Local UX Journey Flows
Multi-step user flows are stored as standalone JSON files under:
```
fleet/flows/{flow_id}.json
```
In offline mode, `refero_search_flows` and `refero_get_flow` automatically read from this directory.

---

## Environment Variables

Configure these variables in your shell or AI client MCP configuration:

| Variable | Description |
| :--- | :--- |
| `REFERO_OFFLINE` | Set to `1` or `true` to disable all outbound network requests. All tools will rely strictly on local catalogs, SQLite mirrors, and CAS images. |
| `REFERO_DATA_DIR` | Absolute path to the directory hosting the `fleet/` assets directory and `data/` database. If omitted, the server checks `outputs/refero-full-data/`, `./fleet`, or the repository directory. |
| `REFERO_TOKEN` | Optional Refero bearer authentication token for private or authenticated API endpoints. |

### Client Configuration with Environment Variables

#### Codex (`config.toml`)
```toml
[mcp_servers.refero]
command = "python"
args = ["/path/to/refero-mcp-proxy/refero_mcp_server.py"]
env = { REFERO_OFFLINE = "1", REFERO_DATA_DIR = "/path/to/refero-full-data" }
```

#### Antigravity / Cursor (`mcp_config.json` / `mcp.json`)
```json
{
  "mcpServers": {
    "refero": {
      "command": "python",
      "args": ["/path/to/refero-mcp-proxy/refero_mcp_server.py"],
      "env": {
        "REFERO_OFFLINE": "1",
        "REFERO_DATA_DIR": "C:/Projects/refero-full-data"
      }
    }
  }
}
```

---

## Full Local Mirror & Autonomous Offline Operation

To generate or refresh a full local mirror using the built-in orchestrator (`mirror_refero.py`):

```bash
# 1. Mirror catalogs, frontend bundles, and index screens
python mirror_refero.py --catalogs

# 2. Dump all design systems & AI prompt specs (DESIGN.md + JSON tokens)
python mirror_refero.py --styles --workers 12

# 3. Mirror all AI prompt collections (/ai-agents/...)
python mirror_refero.py --collections

# 4. Scrape UX journey flows across all core product patterns
python mirror_refero.py --flows --workers 10

# 5. Check local database status
python mirror_refero.py --status
```

### Media Assets Downloader (Screenshots & Slices)
The mirror engine builds an atomic, resumable SQLite queue (`data/refero_local.db`) tracking all 2732px lossless image URLs:
```bash
# Download only hero/primary screenshots for each screen (~20-40 GB)
python mirror_refero.py --download-images --hero-only --workers 10

# Download all vertical slices of every screen
python mirror_refero.py --download-images --workers 12
```

---

---

## Testing

Run deterministic regression tests without network access or additional dependencies:

```bash
python -m unittest -v test_regressions
```

Run the separate live smoke suite when network access and optional Pillow are available. It uses a temporary download directory and exits with code 1 on failure:
```bash
python test_server.py
```

## Access

Set `REFERO_TOKEN` only for endpoints your account is entitled to access. Public endpoints may work without authentication. MCP connectivity does not guarantee full catalog access.
