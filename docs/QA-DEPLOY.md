# QA Environment Setup

One-time setup for the QA/staging server at `qa.litigantportal.com`. After setup, deploys are automatic — merge to `main` triggers a new Docker image build and deploy via GitHub Actions.

## Architecture

- **Server**: DigitalOcean x86 droplet (Ubuntu 24.04, $12/mo — 2 vCPU, 2 GB RAM, 50 GB SSD) with automated weekly backups ($2.40/mo)
- **DNS**: Hurricane Electric free DNS (`ns1.he.net` through `ns5.he.net`)
- **Stack**: Same docker-compose prod profile as production
- **Image**: Pulled from `ghcr.io/freelawproject/litigant-portal:latest` (built by CI)
- **HTTPS**: Caddy auto-provisions via Let's Encrypt
- **Database**: Postgres (pgvector) on the same server via docker-compose
- **Deploy user**: `deploy` (non-root with sudo rights) — CI/CD uses a dedicated SSH key

## Provision the Server

1. Create a DigitalOcean droplet:
   - Image: Ubuntu 24.04 LTS
   - Plan: Basic $12/mo (2 vCPU, 2 GB RAM, 50 GB SSD)
   - Region: NYC or closest to demo audience
   - Add your SSH key during creation

2. Configure the firewall (DigitalOcean Cloud Firewall or `ufw`):
   - Allow: 22 (SSH), 80 (HTTP), 443 (HTTPS)
   - Block everything else

## Initial Server Setup

```bash
ssh root@<VPS_IP>

# Create deploy user
adduser deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh

# Clone repo
git clone https://github.com/freelawproject/litigant-portal.git /opt/litigant-portal
chown -R deploy:deploy /opt/litigant-portal

# Switch to deploy user
su - deploy
```

## Install Docker

```bash
cd /opt/litigant-portal
./scripts/init-server.sh
# Log out and back in (or `newgrp docker`) for group membership
```

## Configure Environment

````bash
cd /opt/litigant-portal

# Config
cat > .env << 'EOF'
SECRET_KEY=choose-a-strong-secret-key
DOMAIN=https://qa.litigantportal.com
ALLOWED_HOSTS=qa.litigantportal.com
DEPLOYMENT_ENV=qa
CHAT_ENABLED=true
CHAT_MODEL=openai/gpt-4o-mini
POSTGRES_PASSWORD=choose-a-strong-db-password
EOF

## First Deploy

```bash
# Pull the pre-built image from GHCR
docker compose pull django-prod

# Start the full prod stack
docker compose --profile prod up -d
````

Caddy will auto-provision a Let's Encrypt certificate once DNS resolves.

## DNS

Point an A record for `qa.litigantportal.com` at the VPS IP address.

## GitHub Actions Secrets

Add these to the repo at Settings → Secrets and variables → Actions:

| Secret       | Value                              |
| ------------ | ---------------------------------- |
| `QA_HOST`    | VPS IP address                     |
| `QA_USER`    | `deploy`                           |
| `QA_SSH_KEY` | Contents of the deploy private key |

Generate the deploy key:

```bash
# On your local machine
ssh-keygen -t ed25519 -C "lp-qa-deploy" -f ~/.ssh/lp_qa_deploy
ssh-copy-id -i ~/.ssh/lp_qa_deploy.pub deploy@<VPS_IP>

# Add the private key contents to GitHub as QA_SSH_KEY
cat ~/.ssh/lp_qa_deploy
```

## GHCR Package Visibility

After the first merge to `main` pushes an image, set the package to public:

1. Go to https://github.com/orgs/freelawproject/packages/container/litigant-portal/settings
2. Change visibility to **Public**

This allows the QA VPS to pull without authentication.

## Common Operations

```bash
# View logs
docker compose --profile prod logs -f

# Django shell
docker compose --profile prod exec django-prod python manage.py shell

# Restart
docker compose --profile prod restart

# Manual pull + deploy (same as what CI does)
cd /opt/litigant-portal
docker compose pull django-prod
docker compose --profile prod up -d --no-build

# Rollback to a specific SHA
docker pull ghcr.io/freelawproject/litigant-portal:sha-abc1234
docker compose --profile prod up -d --no-build
```

## How Deploys Work

1. Developer merges PR to `qa`
2. GitHub Actions `cd.yml` workflow triggers:
   - Builds Docker image
   - Pushes to GHCR with `latest` + SHA tags
   - SSHs to QA VPS
   - Runs `docker compose pull django-prod && docker compose --profile prod up -d --no-build`
3. The `web-prod` entrypoint runs `migrate` + `collectstatic` + starts Gunicorn
4. Caddy proxies traffic with HTTPS
