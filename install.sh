#!/usr/bin/env bash
# ==============================================================================
#  ✦ Refero MCP Proxy — Installer for Linux & macOS
#  Configures Codex, Antigravity, Claude Code, and OpenCode seamlessly.
# ==============================================================================

set -e

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
echo " ✦ Refero MCP Proxy — Automated Client Installer (Linux / macOS)"
echo "=================================================================="
echo -e "${C_RESET}"

# 1. Detect Python 3
PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo -e "${C_RED}❌ Error: Python 3 was not found on PATH.${C_RESET}"
    echo "Please install Python 3.8+ (e.g., sudo apt install python3 python3-pip)."
    exit 1
fi

PY_VER=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${C_GRAY}Found Python:${C_RESET} ${PYTHON_BIN} (v${PY_VER})"

# Check Python version >= 3.8
$PYTHON_BIN -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || {
    echo -e "${C_RED}❌ Error: Python 3.8 or higher is required. Found v${PY_VER}.${C_RESET}"
    exit 1
}

# 2. Check & install Pillow (optional for stitching)
echo -e "\n${C_CYAN}[1/3] Checking optional dependencies...${C_RESET}"
if $PYTHON_BIN -c "import PIL" &>/dev/null; then
    echo -e "  ${C_GREEN}✔ Pillow is already installed (image stitching enabled).${C_RESET}"
else
    echo -e "  ${C_YELLOW}ℹ Pillow not found. Installing Pillow for screenshot stitching...${C_RESET}"
    $PYTHON_BIN -m pip install Pillow --quiet --break-system-packages 2>/dev/null || \
    $PYTHON_BIN -m pip install Pillow --quiet 2>/dev/null || \
    echo -e "  ${C_GRAY}Could not install Pillow automatically; basic operations will still work.${C_RESET}"
fi

# 3. Handle arguments
UNPACK_ARG=""
EXTRA_ARGS=()
CLIENTS_SPECIFIED=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --unpack)
            if [[ -n "$2" && ! "$2" =~ ^-- ]]; then
                UNPACK_ARG="$2"
                shift 2
            else
                UNPACK_ARG="default"
                shift 1
            fi
            ;;
        --data-dir)
            EXTRA_ARGS+=(--data-dir "$2")
            shift 2
            ;;
        --offline)
            EXTRA_ARGS+=(--offline)
            shift 1
            ;;
        --remove|--uninstall)
            EXTRA_ARGS+=(--remove)
            shift 1
            ;;
        --status)
            $PYTHON_BIN "$SCRIPT_DIR/configure_clients.py" --status
            exit 0
            ;;
        --codex|--antigravity|--claude|--opencode|--all)
            CLIENT_NAME="${1#--}"
            EXTRA_ARGS+=(--clients "$CLIENT_NAME")
            CLIENTS_SPECIFIED=true
            shift 1
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift 1
            ;;
    esac
done

# If no client specified, default to configuring all
if [ "$CLIENTS_SPECIFIED" = false ] && [[ ! " ${EXTRA_ARGS[*]} " =~ " --clients " ]] && [[ ! " ${EXTRA_ARGS[*]} " =~ " --status " ]]; then
    EXTRA_ARGS+=(--clients all)
fi

# 4. Run Unpack if requested
if [ -n "$UNPACK_ARG" ]; then
    echo -e "\n${C_CYAN}[Unpack] Running Refero dataset extractor...${C_RESET}"
    if [ "$UNPACK_ARG" = "default" ]; then
        $PYTHON_BIN "$SCRIPT_DIR/unpack_dataset.py"
    else
        $PYTHON_BIN "$SCRIPT_DIR/unpack_dataset.py" --src "$UNPACK_ARG"
    fi
fi

# 5. Configure clients
echo -e "\n${C_CYAN}[2/3] Configuring AI Coding Clients...${C_RESET}"
$PYTHON_BIN "$SCRIPT_DIR/configure_clients.py" --python "$PYTHON_BIN" "${EXTRA_ARGS[@]}"

# 6. Final Status check
echo -e "\n${C_CYAN}[3/3] Installation Verification:${C_RESET}"
$PYTHON_BIN "$SCRIPT_DIR/configure_clients.py" --status

echo -e "\n${C_GREEN}=================================================================="
echo " ✦ Installation Complete!"
echo " Restart or reload your AI assistant (Codex, Antigravity, Claude, OpenCode)."
echo "==================================================================${C_RESET}"
