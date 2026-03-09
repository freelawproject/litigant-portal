#!/usr/bin/env bash
# Download the Tailwind CSS standalone CLI if it doesn't already exist.
#
# The binary is placed at the repo root as ``tailwindcss`` and is
# git-ignored.  Set TAILWIND_VERSION to override the default version.

set -euo pipefail

TAILWIND_VERSION="${TAILWIND_VERSION:-v4.1.16}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${REPO_ROOT}/tailwindcss"

if [ -x "$DEST" ]; then
    echo "tailwindcss already exists at ${DEST}, skipping download."
    exit 0
fi

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$OS" in
    linux)  OS_PART="linux" ;;
    darwin) OS_PART="macos" ;;
    *)
        echo "Unsupported OS: $OS" >&2
        exit 1
        ;;
esac

case "$ARCH" in
    x86_64)  ARCH_PART="x64" ;;
    aarch64|arm64) ARCH_PART="arm64" ;;
    armv7l)  ARCH_PART="armv7" ;;
    *)
        echo "Unsupported architecture: $ARCH" >&2
        exit 1
        ;;
esac

FILENAME="tailwindcss-${OS_PART}-${ARCH_PART}"
URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/${FILENAME}"

echo "Downloading Tailwind CSS ${TAILWIND_VERSION} for ${OS_PART}-${ARCH_PART}..."
curl -fsSL -o "$DEST" "$URL"
chmod +x "$DEST"
echo "Installed tailwindcss to ${DEST}"