# PythonAnywhere Deployment Guide

Free staging deployment using PythonAnywhere + Groq for AI chat.

## Prerequisites

1. [PythonAnywhere account](https://www.pythonanywhere.com/) (free tier works)
2. [Groq API key](https://console.groq.com/) (free tier)
3. Git repository (GitHub/GitLab)

## Initial Setup

### 1. Open a Bash Console

From PythonAnywhere dashboard → Consoles → Bash

### 2. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/litigant-portal.git
cd litigant-portal
```

### 3. Create Virtual Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt  # Or: pip install uv && uv sync
```

### 4. Build Tailwind CSS

PythonAnywhere doesn't have the Tailwind CLI, so build locally first:

```bash
# On your local machine:
tailwindcss -i static/css/main.css -o static/css/main.built.css --minify
git add static/css/main.built.css
git commit -m "build: pre-built tailwind for deployment"
git push
```

Then pull on PythonAnywhere:
```bash
git pull
```

### 5. Set Environment Variables

Go to Web tab → your web app → click on the WSGI configuration file link, then go back.

In the "Virtualenv" section, set: `/home/YOUR_USERNAME/litigant-portal/.venv`

Create a `.env` file or set in WSGI file:

```bash
# In bash console:
cat > ~/litigant-portal/.env << 'EOF'
SECRET_KEY=your-secret-key-here-generate-a-long-random-string
DEBUG=false
ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
CHAT_ENABLED=true
CHAT_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key-here
CHAT_MODEL=llama-3.3-70b-versatile
EOF
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 6. Configure WSGI

Go to Web tab → WSGI configuration file → Edit:

```python
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project to path
project_home = '/home/YOUR_USERNAME/litigant-portal'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables
env_path = Path(project_home) / '.env'
load_dotenv(env_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**Note:** Install python-dotenv if not in requirements:
```bash
pip install python-dotenv
```

### 7. Run Migrations & Collect Static

```bash
cd ~/litigant-portal
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

### 8. Configure Static Files

In Web tab → Static files:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/YOUR_USERNAME/litigant-portal/staticfiles` |

### 9. Reload Web App

Click the green "Reload" button on the Web tab.

## Updating the Deployment

```bash
cd ~/litigant-portal
source .venv/bin/activate
git pull
pip install -r requirements.txt  # If dependencies changed
python manage.py migrate
python manage.py collectstatic --noinput
```

Then click "Reload" on the Web tab.

## Groq Models

Available models on Groq free tier:

| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| `llama-3.3-70b-versatile` | Fast | Best | Default choice |
| `llama-3.1-8b-instant` | Fastest | Good | High volume |
| `mixtral-8x7b-32768` | Fast | Good | Long context |

Change model via `CHAT_MODEL` environment variable.

## Troubleshooting

### "Module not found" errors

Check virtualenv path in Web tab matches your `.venv` location.

### Static files not loading

1. Verify `STATIC_ROOT` path in settings
2. Run `collectstatic`
3. Check static file mapping in Web tab

### Chat not working

1. Verify `GROQ_API_KEY` is set correctly
2. Check error logs: Web tab → Error log
3. Test Groq API key locally first

### Database errors

SQLite file location: `~/litigant-portal/db.sqlite3`

Reset if needed:
```bash
rm db.sqlite3
python manage.py migrate
```

## Free Tier Limits

**PythonAnywhere:**
- 1 web app
- 512 MB disk
- Limited CPU seconds/day
- `*.pythonanywhere.com` domain only

**Groq:**
- Rate limits apply (generous for testing)
- See [Groq pricing](https://groq.com/pricing/) for current limits

## Production Considerations

For production, consider:

1. **Custom domain:** Requires paid PythonAnywhere
2. **PostgreSQL:** PythonAnywhere offers MySQL; use Railway/Render for Postgres
3. **Monitoring:** Add error tracking (Sentry)
4. **Backups:** SQLite file needs manual backup
