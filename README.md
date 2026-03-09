# Litigant Portal

Access to justice portal for self-represented litigants. Built by [Free Law Project](https://free.law).

## Quick Start

```bash
cp .env.example .env      # Add your OPENAI_API_KEY
make docker-dev           # Start dev environment
```

Visit: http://portal.localhost

### Docker Production

Spin up a server, it is recommended that you firewall all ports except the following:

- 80 (HTTP)
- 443 (HTTPS)
- 22 (SSH)

SSH into the server clone the repo in `/opt`

```bash
cd /opt
git clone https://github.com/freelawproject/litigant-portal.git
cd litigant-portal
```

Create a `.env` in the root of the repo and add the following:

```bash
DB_PASSWORD=your-database-password
SECRET_KEY=something-random
DOMAIN=https://your-domain.com
ALLOWED_HOSTS=your-domain.com
OPENAI_API_KEY=your-openai-api-key-here
```

Then run the following commands:

```bash
./scripts/init-server.sh
./scripts/deploy.sh
```

## Documentation

| Doc                                     | Description                      |
| --------------------------------------- | -------------------------------- |
| [Architecture](docs/ARCHITECTURE.md)    | Tech stack, patterns, Docker     |
| [Components](docs/COMPONENT_LIBRARY.md) | UI component library             |
| [Security](docs/SECURITY.md)            | CSP, secrets, production headers |

## Tech Stack

- **Backend:** Django 5.2 LTS
- **Components:** Django Cotton (server-rendered)
- **Styling:** Tailwind CSS (standalone CLI)
- **Reactivity:** Alpine.js (standard build)
- **Database:** SQLite

## License

AGPL-3.0. See [LICENSE](LICENSE).
