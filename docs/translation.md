# Translation Guide

This project uses Django's built-in i18n framework. All user-facing strings are
wrapped with translation markers; translators work with `.po` files.

## Quick Reference

```bash
make messages          # Extract/update strings for all languages
make compilemessages   # Compile .po → .mo (build step)
```

## How It Works

- **Python**: `gettext()` / `gettext_lazy()` wraps strings
- **Templates**: `{% trans %}` / `{% blocktrans %}` marks strings
- **JavaScript**: `gettext()` / `interpolate()` via `JavaScriptCatalog`
- **Extraction**: `makemessages` scans code → `.po` files
- **Compilation**: `compilemessages` compiles `.po` → `.mo` (binary, gitignored)

## Adding a New Language

```bash
# Example: add French
SECRET_KEY=dev .venv/bin/python manage.py makemessages -l fr --no-location
SECRET_KEY=dev .venv/bin/python manage.py makemessages -d djangojs -l fr --no-location
```

Then add the language to `LANGUAGES` in `config/settings.py`:

```python
LANGUAGES = [
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),  # new
]
```

## Updating Translations After Code Changes

```bash
make messages          # Updates all .po files, marks changed strings as fuzzy
```

Translators then review fuzzy strings and provide translations.

## Translation Platform (Weblate)

We use [Weblate](https://hosted.weblate.org/) (free for open source) so
non-developers can contribute translations.

### Setup

1. Connect the repo to Weblate (hosted instance, free for OSS)
2. Configure two components:
   - **Django** — file mask: `locale/*/LC_MESSAGES/django.po`
   - **JavaScript** — file mask: `locale/*/LC_MESSAGES/djangojs.po`
3. Weblate auto-discovers languages from the `locale/` directory

### Court Partner Access

Court partners can get per-language access in Weblate to customize
legal terminology for their jurisdiction.

### Court Partner Overrides via `LOCALE_PATHS`

For deploy-specific translations (e.g., a court partner with custom
terminology), add a locale directory earlier in `LOCALE_PATHS`:

```python
# In settings or a deploy-specific override:
LOCALE_PATHS = [
    BASE_DIR / "locale_overrides",  # checked first
    BASE_DIR / "locale",            # project defaults
]
```

Place override `.po`/`.mo` files in `locale_overrides/<lang>/LC_MESSAGES/`.
Only the overridden strings need to be present — Django falls back to the
next path for everything else.

## Build Integration

`compilemessages` must run as part of the build/deploy pipeline.
The `.mo` files are gitignored (binary build artifacts).

In the Dockerfile, add before `collectstatic`:

```dockerfile
RUN python manage.py compilemessages
```
