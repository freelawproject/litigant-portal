# Docker Secrets

This directory contains secret files for production Docker deployment.

**Never commit actual secret files to git.**

## Required Files (for production)

Create these files with your secret values:

```bash
# Generate Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" > django_secret_key.txt

# Set database password
echo "your-secure-password-here" > db_password.txt

# Secure the files
chmod 600 *.txt
```

## Usage

```bash
# Production deployment
docker compose --profile prod up
```

The secrets are mounted read-only at `/run/secrets/` inside containers.
