<div align="center">

# ✦ Refero MCP Proxy

Python stdio tools for Refero design references and local mirrors.

[![Issues](https://img.shields.io/github/issues/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=f0abfc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/issues)
[![Pull requests](https://img.shields.io/github/issues-pr/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/pulls)
[![Stars](https://img.shields.io/github/stars/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=c4b5fd&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/stargazers)
[![Forks](https://img.shields.io/github/forks/SkrudjReal/refero-mcp-proxy?style=for-the-badge&color=a5b4fc&labelColor=19152e)](https://github.com/SkrudjReal/refero-mcp-proxy/forks)

[Quick start](#-quick-start) · [Features](#-features) · [Documentation](#-documentation) · [Issues](https://github.com/SkrudjReal/refero-mcp-proxy/issues/new)

</div>

---

**14 MCP tools** for Refero screens, UX flows, design specifications and local mirrors. Works with Codex, Antigravity, Cursor and Gemini CLI through stdio.

## ✧ Quick start

Requires **Python 3.8+**. The server uses the standard library; multi-image stitching additionally requires **Pillow**.

```bash
git clone https://github.com/SkrudjReal/refero-mcp-proxy.git
cd refero-mcp-proxy
```

Connect Codex on Linux/WSL:

```bash
codex mcp add refero -- python3 "$PWD/refero_mcp_server.py"
codex mcp get refero
```

[Windows, Antigravity and other clients →](docs/setup.md#installation--integration)

> [!NOTE]
> Live data depends on endpoint access and account entitlement. Offline mode serves only previously mirrored data.

## ✧ Features

| Capability | Includes |
| :--- | :--- |
| Screens | Web/iOS search, metadata, palettes and image URLs |
| UX flows | Journey search and screen sequences |
| Design systems | Style search and Markdown/JSON specifications |
| Images | Batch downloads, cached files and optional stitching |
| Offline use | SQLite catalogs and local media; `REFERO_OFFLINE=1` blocks network calls |

## ✧ Documentation

- [Client setup and offline mirrors](docs/setup.md)
- [All 14 tools and download examples](docs/reference.md)

## ✧ Checks

```bash
python3 -m unittest -v test_regressions
```

The regression suite runs without network access. [Live smoke tests](docs/setup.md#testing) are separate.

---

[MIT License](LICENSE)
