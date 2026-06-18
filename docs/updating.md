# Updating a hosted Litigant Portal box

For self-hosters and court-partner IT: how to pull the latest fixes. **One
command**, no need to remember the compose syntax.

> **Updates are opt-in.** A normal restart or server reboot keeps your current
> versions — it reuses the images already on the box (the `restart: unless-stopped`
> policy). You only move to newer code when you run the update below.

## The one command

From the project directory (e.g. `/opt/litigant-portal`):

```bash
make update                 # or: ./scripts/update.sh
```

That runs the whole sequence and prints a health summary at the end:

1. **code** — `git pull` (latest compose, Caddy config, scripts).
2. **images** — pull the latest container images for the service(s).
3. **restart** — recreate the service(s). Brief interruption; the Django app
   applies any new database migrations automatically on start.
4. **health** — checks each service and prints a ✓/✗ summary, e.g.:

   ```
   ── status ─────────────────────────────────
   litigant portal  200 ✓
   docassemble      200 ✓
   ───────────────────────────────────────────
   ✓ all selected services healthy
   ```

## Update just one service

```bash
make update ARGS=--django         # only the Litigant Portal app
make update ARGS=--docassemble    # only the docassemble interview
```

`--all` (the default) updates both — docassemble only if this box actually hosts it.

## Run any single step on its own

Each step is its own command, so you can do just the part you need:

```bash
./scripts/update.sh health        # check status, change nothing
make health                       # same, via make
./scripts/update.sh code          # git pull only
./scripts/update.sh pull          # pull new images only
./scripts/update.sh restart       # recreate the service(s) only
./scripts/update.sh --help        # full usage
```

Add `--no-code` to skip the `git pull` during a full `update` (e.g. when you've
already pulled).

## If something looks wrong

- The health summary shows the HTTP code per service; `---` means it didn't
  respond. Re-run `./scripts/update.sh health` after a minute (docassemble takes
  a bit to boot).
- Container-level detail: `docker compose --profile prod ps` and
  `docker compose --profile prod logs -f <service>`.
- docassemble specifics (path routing, WebSocket): `docs/docassemble-qa-hosting.md`.
