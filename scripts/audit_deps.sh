#!/usr/bin/env bash
# Audit the packages the image installs for known vulnerabilities.
set -euo pipefail

# Reviewed advisories. See docs/wiki/SECURITY.md before adding one.
IGNORED=(
  # CVE-0000-00000  # 2026-12-01 name: why it is safe for us. Review 2027-01-15.
)

args=()
for id in "${IGNORED[@]+"${IGNORED[@]}"}"; do
  args+=(--ignore-vuln "$id")
done

reqs="$(mktemp)"
trap 'rm -f "$reqs"' EXIT

# Same extras as docker/django/Dockerfile.
uv export --frozen --no-dev --extra test --no-emit-project \
  --format requirements-txt -q -o "$reqs"
uvx pip-audit==2.10.1 -r "$reqs" --require-hashes --disable-pip \
  "${args[@]+"${args[@]}"}"
