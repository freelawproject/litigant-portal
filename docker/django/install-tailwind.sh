#!/usr/bin/env bash
set -euo pipefail

# Install Tailwind CSS standalone CLI binary.
#
# Environment variables:
#   TAILWIND_VERSION  - Version to install (default: v4.1.16)
#   TAILWIND_DEST     - Destination path (default: ./tailwindcss)

TAILWIND_VERSION="${TAILWIND_VERSION:-v4.1.16}"
TAILWIND_DEST="${TAILWIND_DEST:-./tailwindcss}"

# Detect OS
case "$(uname -s)" in
    Linux*)  OS=linux ;;
    Darwin*) OS=macos ;;
    *)
        echo "Error: Unsupported OS: $(uname -s)" >&2
        exit 1
        ;;
esac

# Detect architecture
case "$(uname -m)" in
    x86_64|amd64)  ARCH=x64 ;;
    aarch64|arm64) ARCH=arm64 ;;
    *)
        echo "Error: Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

BINARY_NAME="tailwindcss-${OS}-${ARCH}"
URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/${BINARY_NAME}"

# Skip download if binary already exists with the correct version
if [ -x "$TAILWIND_DEST" ]; then
    CURRENT=$("$TAILWIND_DEST" --version 2>&1 || true)
    if echo "$CURRENT" | grep -q "${TAILWIND_VERSION#v}"; then
        echo "Tailwind CSS ${TAILWIND_VERSION} already installed at ${TAILWIND_DEST}"
        exit 0
    fi
    echo "Updating Tailwind CSS to ${TAILWIND_VERSION}..."
fi

echo "Downloading Tailwind CSS ${TAILWIND_VERSION} (${OS}-${ARCH})..."
curl -fsSL -o "$TAILWIND_DEST" "$URL"
chmod +x "$TAILWIND_DEST"
echo "Installed Tailwind CSS ${TAILWIND_VERSION} at ${TAILWIND_DEST}"
