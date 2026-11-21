#!/usr/bin/env python3
"""
Cross-platform MCP Client Configuration Helper for Refero MCP Proxy.
Configures Codex, Antigravity, Claude Code, and OpenCode safely without overwriting other servers.
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path

def get_home_dir() -> Path:
    return Path.home()

def get_python_exec(custom_py: str = None) -> str:
    if custom_py:
        return custom_py
    return sys.executable

def resolve_server_path() -> Path:
    return (Path(__file__).resolve().parent / "refero_mcp_server.py").resolve()

# =====================================================================
# 1. Antigravity Configuration (~/.gemini/config/mcp_config.json)
# =====================================================================
def configure_antigravity(server_path: Path, py_exec: str, data_dir: str = None, offline: bool = False, remove: bool = False):
    config_path = get_home_dir() / ".gemini" / "config" / "mcp_config.json"
    print(f"\n[Antigravity] Target config: {config_path}")
    
    config = {"mcpServers": {}}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"  ⚠️ Warning reading existing config: {e}. Backing up...")
            backup_p = config_path.with_suffix(".json.bak")
            config_path.rename(backup_p)
            config = {"mcpServers": {}}

    if "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
        config["mcpServers"] = {}

    if remove:
        if "refero" in config["mcpServers"]:
            del config["mcpServers"]["refero"]
            print("  Removed 'refero' from Antigravity config.")
    else:
        entry = {
            "command": py_exec,
            "args": [str(server_path)]
        }
        env = {}
        if data_dir:
            env["REFERO_DATA_DIR"] = data_dir
        if offline:
            env["REFERO_OFFLINE"] = "1"
        if env:
            entry["env"] = env

        config["mcpServers"]["refero"] = entry
        print("  Added/Updated 'refero' server entry.")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("  ✅ Saved Antigravity configuration.")

# =====================================================================
# 2. Claude Code Configuration (~/.claude.json)
# =====================================================================
def configure_claude(server_path: Path, py_exec: str, data_dir: str = None, offline: bool = False, remove: bool = False):
    config_path = get_home_dir() / ".claude.json"
    print(f"\n[Claude Code] Target config: {config_path}")
    
    config = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"  ⚠️ Warning reading existing config: {e}. Backing up...")
            backup_p = config_path.with_suffix(".json.bak")
            config_path.rename(backup_p)
            config = {}

    if "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
        config["mcpServers"] = {}

    if remove:
        if "refero" in config["mcpServers"]:
            del config["mcpServers"]["refero"]
            print("  Removed 'refero' from Claude Code config.")
    else:
        entry = {
            "command": py_exec,
            "args": [str(server_path)]
        }
        env = {}
        if data_dir:
            env["REFERO_DATA_DIR"] = data_dir
        if offline:
            env["REFERO_OFFLINE"] = "1"
        if env:
            entry["env"] = env

        config["mcpServers"]["refero"] = entry
        print("  Added/Updated 'refero' server entry.")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("  ✅ Saved Claude Code configuration.")

# =====================================================================
# 3. OpenCode Configuration (~/.config/opencode/opencode.json)
# =====================================================================
def configure_opencode(server_path: Path, py_exec: str, data_dir: str = None, offline: bool = False, remove: bool = False):
    config_path = get_home_dir() / ".config" / "opencode" / "opencode.json"
    print(f"\n[OpenCode] Target config: {config_path}")
    
    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {}
    }
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {"$schema": "https://opencode.ai/config.json", "mcp": {}}

    if "mcp" not in config or not isinstance(config["mcp"], dict):
        config["mcp"] = {}

    if remove:
        if "refero" in config["mcp"]:
            del config["mcp"]["refero"]
            print("  Removed 'refero' from OpenCode config.")
    else:
        entry = {
            "type": "local",
            "command": [py_exec, str(server_path)],
            "enabled": True
        }
        env = {}
        if data_dir:
            env["REFERO_DATA_DIR"] = data_dir
        if offline:
            env["REFERO_OFFLINE"] = "1"
        if env:
            entry["env"] = env

        config["mcp"]["refero"] = entry
        print("  Added/Updated 'refero' server entry.")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("  ✅ Saved OpenCode configuration.")

# =====================================================================
# 4. Codex Configuration (~/.codex/config.toml)
# =====================================================================
def configure_codex(server_path: Path, py_exec: str, data_dir: str = None, offline: bool = False, remove: bool = False):
    config_path = get_home_dir() / ".codex" / "config.toml"
    print(f"\n[Codex] Target config: {config_path}")

    content = ""
    if config_path.exists():
        content = config_path.read_text(encoding="utf-8", errors="ignore")

    # Regular expression to locate [mcp_servers.refero] block
    section_pattern = re.compile(
        r'(\[mcp_servers\.refero\][\s\S]*?)(?=\n\[|\Z)',
        re.MULTILINE
    )

    clean_server_path = str(server_path).replace("\\", "\\\\") if sys.platform == "win32" else str(server_path)
    clean_py = str(py_exec).replace("\\", "\\\\") if sys.platform == "win32" else str(py_exec)

    new_block = (
        f"[mcp_servers.refero]\n"
        f'command = "{clean_py}"\n'
        f'args = ["{clean_server_path}"]\n'
    )
    env_entries = []
    if data_dir:
        clean_data_dir = str(data_dir).replace("\\", "\\\\") if sys.platform == "win32" else str(data_dir)
        env_entries.append(f'REFERO_DATA_DIR = "{clean_data_dir}"')
    if offline:
        env_entries.append('REFERO_OFFLINE = "1"')
    if env_entries:
        new_block += f'env = {{ {", ".join(env_entries)} }}\n'

    if remove:
        if section_pattern.search(content):
            content = section_pattern.sub("", content).strip() + "\n"
            print("  Removed 'refero' from Codex config.toml.")
    else:
        if section_pattern.search(content):
            content = section_pattern.sub(new_block.strip(), content)
            print("  Updated existing [mcp_servers.refero] section.")
        else:
            if content and not content.endswith("\n\n"):
                content = content.rstrip() + "\n\n"
            content += new_block
            print("  Appended [mcp_servers.refero] section.")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")
    print("  ✅ Saved Codex configuration.")

# =====================================================================
# Status Inspector
# =====================================================================
def print_status():
    print("=" * 65)
    print(" ✦ Refero MCP Client Installation Status")
    print("=" * 65)
    
    # 1. Antigravity
    ag_p = get_home_dir() / ".gemini" / "config" / "mcp_config.json"
    ag_ok = False
    if ag_p.exists():
        try:
            with open(ag_p, "r", encoding="utf-8") as f:
                d = json.load(f)
                ag_ok = "refero" in d.get("mcpServers", {})
        except Exception:
            pass
    print(f"  Antigravity: {'✅ Configured' if ag_ok else '❌ Not configured'} ({ag_p})")

    # 2. Codex
    codex_p = get_home_dir() / ".codex" / "config.toml"
    codex_ok = False
    if codex_p.exists():
        c = codex_p.read_text(encoding="utf-8", errors="ignore")
        codex_ok = "[mcp_servers.refero]" in c
    print(f"  Codex:       {'✅ Configured' if codex_ok else '❌ Not configured'} ({codex_p})")

    # 3. Claude Code
    claude_p = get_home_dir() / ".claude.json"
    claude_ok = False
    if claude_p.exists():
        try:
            with open(claude_p, "r", encoding="utf-8") as f:
                d = json.load(f)
                claude_ok = "refero" in d.get("mcpServers", {})
        except Exception:
            pass
    print(f"  Claude Code: {'✅ Configured' if claude_ok else '❌ Not configured'} ({claude_p})")

    # 4. OpenCode
    oc_p = get_home_dir() / ".config" / "opencode" / "opencode.json"
    oc_ok = False
    if oc_p.exists():
        try:
            with open(oc_p, "r", encoding="utf-8") as f:
                d = json.load(f)
                oc_ok = "refero" in d.get("mcp", {}) or "refero" in d.get("mcpServers", {})
        except Exception:
            pass
    print(f"  OpenCode:    {'✅ Configured' if oc_ok else '❌ Not configured'} ({oc_p})")
    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="Configure Refero MCP Proxy across AI coding assistants.")
    parser.add_argument("--clients", nargs="+", default=["all"],
                        help="Target AI clients to configure: all, codex, antigravity, claude, opencode")
    parser.add_argument("--python", type=str, default=None, help="Custom Python executable path")
    parser.add_argument("--data-dir", type=str, default=None, help="Custom REFERO_DATA_DIR path for mirrored dataset")
    parser.add_argument("--offline", action="store_true", help="Set REFERO_OFFLINE=1 in client configurations")
    parser.add_argument("--remove", action="store_true", help="Uninstall refero MCP server from selected clients")
    parser.add_argument("--status", action="store_true", help="Inspect current configuration status without modifying")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    # Expand any comma-separated client values
    expanded_clients = []
    for c in args.clients:
        for sub in c.split(","):
            s = sub.strip().lower()
            if s:
                expanded_clients.append(s)
    args.clients = expanded_clients

    server_p = resolve_server_path()
    py_exec = get_python_exec(args.python)

    target_all = "all" in args.clients

    print("=" * 65)
    action_label = "Removing" if args.remove else "Configuring"
    print(f" ✦ Refero MCP Proxy — {action_label} Client Configurations")
    print("=" * 65)
    print(f"Server script: {server_p}")
    print(f"Python binary: {py_exec}")
    if args.data_dir:
        print(f"Dataset path:  {args.data_dir}")
    if args.offline:
        print(f"Offline mode:  Enforced (REFERO_OFFLINE=1)")
    print("=" * 65)

    if target_all or "antigravity" in args.clients:
        configure_antigravity(server_p, py_exec, args.data_dir, args.offline, args.remove)

    if target_all or "codex" in args.clients:
        configure_codex(server_p, py_exec, args.data_dir, args.offline, args.remove)

    if target_all or "claude" in args.clients:
        configure_claude(server_p, py_exec, args.data_dir, args.offline, args.remove)

    if target_all or "opencode" in args.clients:
        configure_opencode(server_p, py_exec, args.data_dir, args.offline, args.remove)

    print("\n" + "=" * 65)
    print("🎉 All requested clients successfully updated!")
    print("Please restart or reload MCP servers in your editor/CLI client.")
    print("=" * 65)

if __name__ == "__main__":
    main()
