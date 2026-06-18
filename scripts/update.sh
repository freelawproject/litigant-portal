#!/usr/bin/env bash
#
# Litigant Portal — update tool for a self-hosted / partner box (#551).
#
# One command instead of the multi-file compose incantation. Pulls latest code +
# images, recreates the selected service(s), and reports health.
#
# OPT-IN updates only: a normal restart or reboot never changes versions — that's
# the `restart: unless-stopped` policy reusing the existing images (#548). Run
# this when you actually want the latest fixes.
#
# Usage:
#   scripts/update.sh [command] [--all | --django | --docassemble] [--no-code]
#
# Commands — run the whole flow, or any single step on its own:
#   update    (default)  code → images → recreate → health
#   code                 git pull only
#   pull                 pull new images only
#   restart              recreate the service(s) only (Django auto-migrates on boot)
#   health               health / validation summary only
#
# Service selector (default --all):
#   --django             only the Litigant Portal app
#   --docassemble        only the docassemble interview
#   --all                both (docassemble only if it's actually hosted here)
#   --no-code            skip `git pull` during `update`
#
# Examples:
#   scripts/update.sh                      # update everything
#   scripts/update.sh --docassemble        # update just docassemble
#   scripts/update.sh health               # check health, change nothing
#   scripts/update.sh restart --django     # restart just the app

set -euo pipefail

# Run from the repo root regardless of where it's invoked.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── args ─────────────────────────────────────────────────────────────────────
COMMAND="update"
MODE="all"
PULL_CODE=true

for arg in "$@"; do
	case "$arg" in
		update | code | pull | restart | health) COMMAND="$arg" ;;
		--all) MODE="all" ;;
		--django) MODE="django" ;;
		--docassemble) MODE="docassemble" ;;
		--no-code) PULL_CODE=false ;;
		-h | --help)
			sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
			exit 0
			;;
		*)
			echo "Unknown argument: $arg (try --help)" >&2
			exit 2
			;;
	esac
done

# ── what to act on ───────────────────────────────────────────────────────────
DA_OVERRIDE="docker-compose.docassemble.qa.yml"

da_running() { docker ps --format '{{.Names}}' | grep -qx 'docassemble-qa'; }

WANT_DJANGO=false
WANT_DA=false
case "$MODE" in
	django) WANT_DJANGO=true ;;
	docassemble) WANT_DA=true ;;
	all)
		WANT_DJANGO=true
		if da_running; then WANT_DA=true; fi
		;;
esac

if $WANT_DA && [[ ! -f "$DA_OVERRIDE" ]]; then
	echo "✗ docassemble selected but $DA_OVERRIDE is missing — this box doesn't host docassemble." >&2
	exit 1
fi

# Compose invocation: base always; docassemble override only when in scope, so a
# Django-only box never accidentally starts docassemble.
COMPOSE_FILES=(-f docker-compose.yml)
if $WANT_DA; then COMPOSE_FILES+=(-f "$DA_OVERRIDE"); fi
DC=(docker compose "${COMPOSE_FILES[@]}" --profile prod)

SERVICES=()
$WANT_DJANGO && SERVICES+=(django-prod)
$WANT_DA && SERVICES+=(docassemble)

# ── steps ────────────────────────────────────────────────────────────────────
step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }

do_code() {
	step "Pulling latest code (git)"
	git pull --ff-only
}

do_pull() {
	step "Pulling latest images: ${SERVICES[*]}"
	"${DC[@]}" pull "${SERVICES[@]}"
}

do_restart() {
	for svc in "${SERVICES[@]}"; do
		step "Restarting $svc — this briefly interrupts it…"
		"${DC[@]}" up -d "$svc"
	done
	# Django's entrypoint runs migrate + collectstatic on every start, so a
	# recreate already applies any new migrations — no separate step needed.
}

# Health: hit each service's own endpoint from inside its container, so the check
# needs no host networking and works the same on every box.
http_status() { # service, url
	"${DC[@]}" exec -T "$1" curl -fsS -o /dev/null -w '%{http_code}' "$2" 2>/dev/null || echo "---"
}

do_health() {
	step "Health / validation"
	printf '\n  ── status ─────────────────────────────────\n'
	local ok=true code
	if $WANT_DJANGO; then
		code=$(http_status django-prod http://localhost:8000/api/health/)
		_report "litigant portal" "$code" || ok=false
	fi
	if $WANT_DA; then
		code=$(http_status docassemble http://localhost/interview/)
		_report "docassemble    " "$code" || ok=false
	fi
	printf '  ───────────────────────────────────────────\n'
	if $ok; then
		printf '  \033[32m✓ all selected services healthy\033[0m\n\n'
	else
		printf '  \033[31m✗ one or more services unhealthy — check the codes above\033[0m\n\n' >&2
		return 1
	fi
}

_report() { # label, code  → 0 if 2xx/3xx
	local label="$1" code="$2"
	if [[ "$code" =~ ^[23][0-9][0-9]$ ]]; then
		printf '  %s  \033[32m%s ✓\033[0m\n' "$label" "$code"
	else
		printf '  %s  \033[31m%s ✗\033[0m\n' "$label" "$code"
		return 1
	fi
}

# ── dispatch ─────────────────────────────────────────────────────────────────
case "$COMMAND" in
	update)
		$PULL_CODE && do_code
		do_pull
		do_restart
		do_health
		;;
	code) do_code ;;
	pull) do_pull ;;
	restart) do_restart ;;
	health) do_health ;;
esac
