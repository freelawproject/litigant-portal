"""Django system checks for the corpus in ``litigant_portal/corpus/``."""

from django.core.checks import Error, Tags, register

from litigant_portal.app.selectors.corpus import (
    CORPUS_DIR,
    COURTS_DIR,
    FORMS_DIR,
    SLUG_PATTERN,
    VARIABLES_PATH,
    corpus_load,
)


def check_corpus_directory_structure():
    """Validates:
    - variables.yml exists
    - every file under forms/ and courts/ is a recognized document
    - every path segment is a valid slug
    - every court directory carries a court.yml
    - every topic directory carries a topic.yml
    """
    if not VARIABLES_PATH.is_file():
        raise ValueError(f"{VARIABLES_PATH} is missing")
    recognized = {
        VARIABLES_PATH,
        *FORMS_DIR.glob("*.yml"),
        *FORMS_DIR.glob("*.pdf"),
        *COURTS_DIR.glob("*/court.yml"),
        *COURTS_DIR.glob("*/topics/*/topic.yml"),
        *COURTS_DIR.glob("*/topics/*/flows/*.yml"),
    }
    for root in (FORMS_DIR, COURTS_DIR):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            parts = path.relative_to(CORPUS_DIR).parts
            if not path.is_file() or any(
                part.startswith(".") for part in parts
            ):
                continue
            if path not in recognized:
                raise ValueError(f"{path}: unrecognized file")
            if not all(
                SLUG_PATTERN.fullmatch(part)
                for part in (*parts[:-1], path.stem)
            ):
                raise ValueError(f"{path}: name is not a valid slug")
    for court_dir in sorted(COURTS_DIR.glob("*/")):
        if not (court_dir / "court.yml").is_file():
            raise ValueError(f"{court_dir / 'court.yml'} is missing")
        for topic_dir in sorted((court_dir / "topics").glob("*/")):
            if not (topic_dir / "topic.yml").is_file():
                raise ValueError(f"{topic_dir / 'topic.yml'} is missing")


@register(Tags.compatibility)
def check_corpus(app_configs, **kwargs):
    """Surface an invalid corpus as a deploy-time error."""
    try:
        check_corpus_directory_structure()
        corpus_load()
    except ValueError as exc:
        return [
            Error(str(exc), id="corpus.E001", obj="litigant_portal/corpus")
        ]
    return []
