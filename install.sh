#!/bin/sh
# jakpost-scraper installer for macOS and Linux.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/pear25/scraper/main/install.sh | sh
set -eu

APP_NAME="jakpost-scraper"
CMD_NAME="jakpost-scrape"
UV_INSTALLER_URL="https://astral.sh/uv/install.sh"

note()   { printf '%s\n' "$1"; }
header() { printf '\n=== %s ===\n' "$1"; }
warn()   { printf '\033[33m%s\033[0m\n' "$1" >&2; }
fail()   { printf '\033[31mError: %s\033[0m\n' "$1" >&2; exit 1; }

header "Checking prerequisites"
if ! command -v curl >/dev/null 2>&1; then
    fail "curl is required but not found. Install curl and re-run."
fi
note "curl: ok"

header "Installing uv (Python tool manager)"
if command -v uv >/dev/null 2>&1; then
    note "uv: already installed ($(uv --version))"
else
    note "Installing uv from $UV_INSTALLER_URL ..."
    curl -LsSf "$UV_INSTALLER_URL" | sh
    # uv's installer puts the binary in ~/.local/bin or ~/.cargo/bin and
    # updates the user's shell rc files; expose it to THIS shell so the
    # next step finds it.
    if [ -d "$HOME/.local/bin" ]; then
        PATH="$HOME/.local/bin:$PATH"
    fi
    if [ -d "$HOME/.cargo/bin" ]; then
        PATH="$HOME/.cargo/bin:$PATH"
    fi
    export PATH
    if ! command -v uv >/dev/null 2>&1; then
        fail "uv installed but not on PATH. Open a new shell and re-run."
    fi
    note "uv: installed ($(uv --version))"
fi

header "Installing $APP_NAME"
uv tool install --upgrade "$APP_NAME"

header "Checking for the claude CLI (used for summarization)"
if command -v claude >/dev/null 2>&1; then
    note "claude: found ($(command -v claude))"
    CLAUDE_MISSING=0
else
    warn "claude CLI not found."
    warn "Summarization needs the claude CLI installed and authenticated."
    warn "Install: https://docs.claude.com/en/docs/claude-code/quickstart"
    warn "Without it, run jakpost-scrape with --no-summary."
    CLAUDE_MISSING=1
fi

header "Detecting config location"
OS_KERNEL=$(uname -s)
case "$OS_KERNEL" in
    Darwin)
        CONFIG_PATH="$HOME/Library/Application Support/$APP_NAME/config.yaml"
        ;;
    Linux)
        CONFIG_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME/config.yaml"
        ;;
    *)
        CONFIG_PATH="(see jakpost-scrape --help for path resolution)"
        ;;
esac

header "Install complete"
note ""
note "Command:  $CMD_NAME"
note "Config:   $CONFIG_PATH"
note "          (written automatically on first run)"
note ""
note "Try:      $CMD_NAME --help"
if [ "$CLAUDE_MISSING" -eq 1 ]; then
    note "          $CMD_NAME --no-summary           # works without claude CLI"
fi
note ""
note "Upgrade:  $CMD_NAME --upgrade"
note ""
