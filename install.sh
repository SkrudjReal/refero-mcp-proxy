#!/usr/bin/env bash
# ==============================================================================
#  Refero MCP Proxy — Installer for Linux & macOS
#  Configures Codex, Antigravity, Claude Code, and OpenCode safely.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
C_RESET='\033[0m'
C_CYAN='\033[1;36m'
C_GREEN='\033[1;32m'
C_YELLOW='\033[1;33m'
C_RED='\033[1;31m'
C_GRAY='\033[0;90m'

echo -e "${C_CYAN}"
echo "=================================================================="
echo " Refero MCP Proxy — Automated Client Installer (Linux / macOS)"
echo "=================================================================="
echo -e "${C_RESET}"

# 1. Detect Python 3 (resolve absolute path for GUI clients)
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python &>/dev/null; then
    PYTHON_BIN="$(command -v python)"
else
    echo -e "${C_RED}[ERROR] Python 3 was not found on PATH.${C_RESET}"
    echo "Install Python 3.8+ (e.g., sudo apt install python3 python3-pip)."
    exit 1
fi

PY_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${C_GRAY}Found Python:${C_RESET} ${PYTHON_BIN} (v${PY_VER})"

# Check Python version >= 3.8
"$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || {
    echo -e "${C_RED}[ERROR] Python 3.8 or higher is required. Found v${PY_VER}.${C_RESET}"
    exit 1
}

# 2. Parse arguments cleanly
UNPACK_REQUESTED=false
UNPACK_SRC=""
DATA_DIR=""
OFFLINE_FLAG=false
REMOVE_FLAG=false
STATUS_FLAG=false
CLIENTS_LIST=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --unpack)
            UNPACK_REQUESTED=true
            if [[ $# -ge 2 && -n "$2" && ! "$2" =~ ^-- ]]; then
                UNPACK_SRC="$2"
                shift 2
            else
                shift 1
            fi
            ;;
        --data-dir)
            if [[ $# -lt 2 || -z "$2" ]]; then
                echo -e "${C_RED}[ERROR] --data-dir requires a path argument.${C_RESET}" >&2
                exit 1
            fi
            DATA_DIR="$2"
            shift 2
            ;;
        --clients)
            if [[ $# -lt 2 || -z "$2" ]]; then
                echo -e "${C_RED}[ERROR] --clients requires at least one client name.${C_RESET}" >&2
                exit 1
            fi
            shift 1
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                CLIENTS_LIST+=("$1")
                shift 1
            done
            ;;
        --codex|--antigravity|--claude|--opencode|--all)
            CLIENTS_LIST+=("${1#--}")
            shift 1
            ;;
        --offline)
            OFFLINE_FLAG=true
            shift 1
            ;;
        --remove|--uninstall)
            REMOVE_FLAG=true
            shift 1
            ;;
        --status)
            STATUS_FLAG=true
            shift 1
            ;;
        -h|--help)
            echo "Usage: ./install.sh [OPTIONS]"
            echo "  --clients LIST   Comma/space-separated: all, codex, antigravity, claude, opencode"
            echo "  --codex / --antigravity / --claude / --opencode / --all"
            echo "  --unpack [DIR]   Extract downloaded refero_*.zip archives"
            echo "  --data-dir DIR   Set REFERO_DATA_DIR (also used as --dest for --unpack)"
            echo "  --offline        Set REFERO_OFFLINE=1 in client configs"
            echo "  --remove         Remove refero from selected clients"
            echo "  --status         Show current configuration status"
            exit 0
            ;;
        *)
            echo -e "${C_RED}[ERROR] Unknown option: $1${C_RESET}" >&2
            exit 1
            ;;
    esac
done

if [ "$STATUS_FLAG" = true ]; then
    "$PYTHON_BIN" "$SCRIPT_DIR/configure_clients.py" --status
    exit 0
fi

# 3. Check & install Pillow (optional for stitching)
echo -e "\n${C_CYAN}[1/3] Checking optional dependencies...${C_RESET}"
if "$PYTHON_BIN" -c "import PIL" &>/dev/null; then
    echo -e "  ${C_GREEN}[OK] Pillow is already installed (image stitching enabled).${C_RESET}"
else
    echo -e "  ${C_YELLOW}[INFO] Pillow not found. Installing Pillow for screenshot stitching...${C_RESET}"
    "$PYTHON_BIN" -m pip install Pillow --quiet --break-system-packages 2>/dev/null || \
    "$PYTHON_BIN" -m pip install Pillow --quiet 2>/dev/null || \
    echo -e "  ${C_GRAY}Could not install Pillow automatically; basic operations still work.${C_RESET}"
fi

# 4. Run Unpack if requested
if [ "$UNPACK_REQUESTED" = true ]; then
    echo -e "\n${C_CYAN}[Unpack] Running Refero dataset extractor...${C_RESET}"
    UNPACK_CMD=("$PYTHON_BIN" "$SCRIPT_DIR/unpack_dataset.py")
    if [ -n "$UNPACK_SRC" ]; then
        UNPACK_CMD+=(--src "$UNPACK_SRC")
    fi
    if [ -n "$DATA_DIR" ]; then
        UNPACK_CMD+=(--dest "$DATA_DIR")
    fi
    "${UNPACK_CMD[@]}"
fi

# 5. Build arguments for configure_clients.py
CONFIG_CMD=("$PYTHON_BIN" "$SCRIPT_DIR/configure_clients.py" --python "$PYTHON_BIN")
if [ ${#CLIENTS_LIST[@]} -eq 0 ]; then
    CONFIG_CMD+=(--clients all)
else
    CONFIG_CMD+=(--clients "${CLIENTS_LIST[@]}")
fi
if [ -n "$DATA_DIR" ]; then
    CONFIG_CMD+=(--data-dir "$DATA_DIR")
fi
if [ "$OFFLINE_FLAG" = true ]; then
    CONFIG_CMD+=(--offline)
fi
if [ "$REMOVE_FLAG" = true ]; then
    CONFIG_CMD+=(--remove)
fi

echo -e "\n${C_CYAN}[2/3] Configuring AI Coding Clients...${C_RESET}"
"${CONFIG_CMD[@]}"

# 6. Final status check
echo -e "\n${C_CYAN}[3/3] Installation Verification:${C_RESET}"
"$PYTHON_BIN" "$SCRIPT_DIR/configure_clients.py" --status

echo -e "\n${C_GREEN}=================================================================="
echo " Installation Complete!"
echo " Restart or reload your AI assistant (Codex, Antigravity, Claude, OpenCode)."
echo "==================================================================${C_RESET}"
