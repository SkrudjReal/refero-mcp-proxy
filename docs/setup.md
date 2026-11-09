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

---

## Full Local Mirror & Autonomous Offline Operation

To operate completely independently of `refero.design` and `styles.refero.design`, use the built-in mirroring orchestrator (`mirror_refero.py`):

```bash
# 1. Mirror catalogs, frontend bundles, and index 3,000+ screens
python mirror_refero.py --catalogs

# 2. Dump all 1,342 design systems & AI prompt specs (DESIGN.md + JSON tokens)
python mirror_refero.py --styles --workers 12

# 3. Mirror all 52 AI prompt collections (/ai-agents/...)
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

### Running the MCP Server in 100% Offline Mode
Set `REFERO_OFFLINE=1` to prohibit network calls. Tools use local catalogs, SQLite and style files; image downloads copy cached media from the mirror. Missing local data produces an error. Image instructions return static text.
```bash
REFERO_OFFLINE=1 python refero_mcp_server.py
```

For Codex, add `env = { REFERO_OFFLINE = "1" }` under `[mcp_servers.refero]`. For Antigravity/Gemini, add `"env": {"REFERO_OFFLINE": "1"}` to the server entry. This works on both operating systems and avoids shell-specific environment syntax.
In normal mode, tools can use local data or live endpoints. Screen and flow searches fall back to SQLite after a failed live request; this can take the network timeout. Cached screen/style details may be returned before attempting the network.

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
