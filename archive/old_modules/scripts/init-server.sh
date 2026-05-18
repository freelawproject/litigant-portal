#!/usr/bin/env bash
set -euo pipefail

# Initialize a bare server for running the litigant-portal with Docker Compose.
# Supports: Debian/Ubuntu (apt), RHEL/Fedora (dnf), Alpine (apk).
# Idempotent — safe to run multiple times.
#
# Usage: ./scripts/init-server.sh

# ---------------------------------------------------------------------------
# Sudo handling
# ---------------------------------------------------------------------------

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "Error: Not running as root and sudo is not available." >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Docker installation functions (one per package manager)
# ---------------------------------------------------------------------------

install_docker_apt() {
    echo "==> Detected Debian/Ubuntu (apt)"

    $SUDO apt-get update
    $SUDO apt-get install -y ca-certificates curl gnupg

    # Add Docker's official GPG key (idempotent)
    $SUDO install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.asc ]; then
        curl -fsSL "https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg" \
            | $SUDO tee /etc/apt/keyrings/docker.asc > /dev/null
        $SUDO chmod a+r /etc/apt/keyrings/docker.asc
    fi

    # Add Docker apt repository (idempotent)
    if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
            | $SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null
    fi

    $SUDO apt-get update
    $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
}

install_docker_dnf() {
    echo "==> Detected RHEL/Fedora (dnf)"

    $SUDO dnf -y install dnf-plugins-core

    # Add Docker repo (idempotent — dnf config-manager won't duplicate)
    if ! $SUDO dnf repolist | grep -q docker-ce; then
        $SUDO dnf config-manager --add-repo \
            "https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/docker-ce.repo"
    fi

    $SUDO dnf install -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
}

install_docker_apk() {
    echo "==> Detected Alpine (apk)"
    $SUDO apk add --no-cache docker docker-cli-compose
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "Docker and Docker Compose plugin already installed."
    docker --version
    docker compose version
else
    if command -v apt-get >/dev/null 2>&1; then
        install_docker_apt
    elif command -v dnf >/dev/null 2>&1; then
        install_docker_dnf
    elif command -v apk >/dev/null 2>&1; then
        install_docker_apk
    else
        echo "Error: No supported package manager found (apt, dnf, apk)." >&2
        echo "Install Docker manually: https://docs.docker.com/engine/install/" >&2
        exit 1
    fi
fi

# Enable and start Docker service (systemd-based distros)
if command -v systemctl >/dev/null 2>&1; then
    $SUDO systemctl enable docker
    $SUDO systemctl start docker
fi

# Add current user to docker group so sudo isn't needed for docker commands
if [ -n "${USER:-}" ] && ! groups "$USER" 2>/dev/null | grep -qw docker; then
    echo "Adding $USER to docker group..."
    $SUDO usermod -aG docker "$USER"
    echo "NOTE: Log out and back in (or run 'newgrp docker') for group change to take effect."
fi

echo ""
echo "==> Docker setup complete."
docker --version
docker compose version
