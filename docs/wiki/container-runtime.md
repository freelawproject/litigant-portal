# Container runtime: Docker Desktop and OrbStack

LP's local environment is plain `docker compose`, so any Docker-compatible runtime works. This page covers switching from Docker Desktop to [OrbStack](https://orbstack.dev/) on macOS, in the order that works, plus four traps that all present the same way.

**The one symptom to recognize:** `make docker` or `make test` reporting that Docker isn't running while the container is visibly running. Four unrelated causes produce it. Jump to [Troubleshooting](#troubleshooting).

## The switch, in order

Do these in sequence. Steps 3 and 6 are coupled: migrating requires Desktop to still be installed, and that is the same condition that stops OrbStack from writing its own CLI plugin links. Clean-uninstall-first and keep-your-volumes are mutually exclusive, so the plugins get repaired afterward rather than avoided.

### 1. Quit Docker Desktop

Quit the app rather than only stopping containers. Two runtimes cannot both own `/var/run/docker.sock`.

### 2. Install OrbStack, leaving Desktop installed

```sh
brew install --cask orbstack
```

Launch it once so it sets up its CLI and socket.

### 3. Migrate

OrbStack's migration **copies** rather than moves, so Desktop stays intact as a fallback:

```sh
orb migrate docker
```

Images and volumes come across. Locally built images cannot — they exist in no registry, so the migration tries to pull them and fails:

```
some data failed to migrate: pull container image: [Docker] pull access denied
for litigant-portal-django, repository does not exist or may require 'docker login'
```

That is expected for `litigant-portal-django`. It is built from this repo's Dockerfile and comes back on the next build (step 7).

**Decide what you actually need first.** Named volumes hold local Postgres data (disposable — `docker compose down -v` is the documented reset) and the local docassemble bench, which holds Playground work. Anonymous hash volumes and duplicate `postgres_data*` volumes from past upgrades are cruft. To see what is at stake:

```sh
docker volume ls
docker run --rm -v <volume>:/v alpine du -sh /v
```

### 4. Uninstall Docker Desktop

```sh
brew uninstall --cask docker-desktop
```

Use the cask uninstaller, not drag-to-trash — the cask handles the launchd agents and the `com.docker.vmnetd` privileged helper.

Then the data directories, which the uninstall leaves behind and which hold the disk space:

```sh
rm -rf ~/Library/Application\ Support/Docker\ Desktop
```

`~/Library/Containers/com.docker.docker` and `~/Library/Group Containers/group.com.docker` need Finder. See [TCC on the data directory](#tcc-on-the-data-directory).

**Never remove `~/.docker` wholesale.** It holds the contexts and `config.json` that OrbStack reads. Only the stale context needs clearing:

```sh
docker context rm desktop-linux
```

### 5. Remove a Homebrew `docker` formula, if you have one

```sh
brew list --formula | grep '^docker$'
```

If it is there, it will shadow OrbStack's `docker` on every login. See [PATH order](#path-order) for why, and for the alternative if you want to keep it.

```sh
brew uninstall docker
```

### 6. Repair the CLI plugins, then verify

```sh
ln -sf /Applications/OrbStack.app/Contents/MacOS/xbin/docker-compose ~/.docker/cli-plugins/docker-compose
```

List the plugin links still pointing into the deleted app:

```sh
find ~/.docker/cli-plugins -type l ! -exec test -e {} \; -print
```

Review that list before adding `-delete`. Then:

```sh
orbctl doctor
```

`doctor` checks the `docker` command's location, scans PATH for conflicts, and checks the CLI plugins. It is the fastest way to confirm the switch landed.

### 7. Rebuild and start

```sh
make docker-up-build
```

`--build` matters here: the app image is the one thing the migration could not carry.

## Troubleshooting

### `docker: unknown command: docker compose`

The compose CLI plugin is missing. `docker compose` (subcommand) resolves through `~/.docker/cli-plugins/`, which is separate from the standalone `docker-compose` binary — the standalone can work while the subcommand does not.

Docker Desktop installed that plugin as a symlink into `/Applications/Docker.app`, and OrbStack skips writing its own when a file is already present. Uninstall Desktop and the link dangles, with nothing behind it.

```sh
ls -l ~/.docker/cli-plugins/docker-compose
```

A target under `/Applications/Docker.app` is the dangling case. Fix with the `ln -sf` in step 6. Every other plugin in that directory (`docker-buildx`, `docker-scout`, `docker-init`, and the rest) dangles the same way and will fail whenever something invokes it.

### PATH order

OrbStack's installer appends to PATH rather than prepending. In `~/.zprofile`:

```sh
export PATH="$PATH":/Users/you/.orbstack/bin
```

`.zprofile` runs before `.zshrc`, and `brew shellenv` in `.zshrc` **prepends** `/opt/homebrew/bin`. So a Homebrew `docker` formula lands ahead of OrbStack's on every login:

```sh
which -a docker
```

Two paths listed with `/opt/homebrew/bin/docker` first is the shadowing case. Either remove the formula (step 5) or move the OrbStack `source` line out of `~/.zprofile` and into `~/.zshrc` below `brew shellenv`.

The Homebrew `docker` formula is a bare CLI: it ships no `cli-plugins` directory of its own, so once Desktop's plugins are gone it cannot run `docker compose` at all.

### TCC on the data directory

```
rm: /Users/you/Library/Containers/com.docker.docker: Operation not permitted
```

This is macOS TCC, not file permissions — `containermanagerd` protects `~/Library/Containers`, and `sudo` does not help. Delete it in Finder (Go → Go to Folder → `~/Library/Containers`), then empty the Trash to actually reclaim the space. Same for `~/Library/Group Containers/group.com.docker`.

Granting your terminal Full Disk Access in System Settings → Privacy & Security also works, if you would rather stay in the shell.

### "Django container isn't running" when it is

`make test` and the other container targets share a guard:

```make
require-docker = docker compose exec -T django true 2>/dev/null || \
  { echo "Django container isn't running — start it with: make docker"; exit 1; }
```

Anything that makes `docker compose exec` fail produces that message, a missing compose plugin included. Run the command yourself to see the real error:

```sh
docker compose exec -T django true; echo "exit=$?"
```

### Different behavior between two terminal windows

A shell opened before the switch carries the old PATH. `exec zsh` reloads the profile in place — note that it replaces the shell process, so anything chained after it with `&&` is discarded.
