"""
Temporary retrieval of the existing corpus YAML files, without parsing them.
"""

import asyncio
from pathlib import Path

from lp_agent.errors import AgentValidationError
from lp_agent.types import CorpusDocument, SourceReference


async def get_file_based_corpus(
    court: str, topic: str, *, resource_root: str | Path
) -> tuple[CorpusDocument, ...]:
    """
    Read court metadata and the selected topic's YAML subtree off the event loop.

    Source IDs and locators are paths relative to resource_root. Unknown scope,
    unreadable files, and paths escaping the selected scope raise validation
    errors. Files are returned in path order; no flow or guideline is selected.
    """
    return await asyncio.to_thread(_read_corpus, court, topic, resource_root)


def _walk_error(error: OSError) -> None:
    """
    Surface unreadable directories instead of returning incomplete corpus.
    """
    raise error


def _read_corpus(
    court: str, topic: str, resource_root: str | Path
) -> tuple[CorpusDocument, ...]:
    """
    Read only court metadata and files contained in the selected topic.
    """
    for key in (court, topic):
        if (
            not isinstance(key, str)
            or not key.strip()
            or key in {".", ".."}
            or any(character in key for character in ("/", "\\", "\0"))
        ):
            raise AgentValidationError(
                "Court and topic must be single path components."
            )
    try:
        root = Path(resource_root).resolve(strict=True)
        court_file = root / "corpus" / "courts" / court / "court.yml"
        topic_dir = court_file.parent / "topics" / topic
        if not topic_dir.resolve(strict=True).is_relative_to(topic_dir):
            raise AgentValidationError(
                "Corpus path escapes the selected scope."
            )
        paths = {court_file, topic_dir / "topic.yml"}
        for directory, _, filenames in topic_dir.walk(on_error=_walk_error):
            paths.update(
                directory / name
                for name in filenames
                if Path(name).suffix in {".yml", ".yaml"}
            )
        documents = []
        for path in sorted(paths):
            boundary = court_file if path == court_file else topic_dir
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(boundary):
                raise AgentValidationError(
                    "Corpus path escapes the selected scope."
                )
            relative_path = path.relative_to(root).as_posix()
            documents.append(
                CorpusDocument(
                    content=resolved.read_text(encoding="utf-8"),
                    source=SourceReference(
                        source_id=relative_path,
                        kind="corpus",
                        title=path.name,
                        locator=relative_path,
                    ),
                )
            )
        return tuple(documents)
    except FileNotFoundError:
        raise AgentValidationError(
            "No file-based corpus was found for the selected court and topic."
        ) from None
    except (OSError, UnicodeError):
        raise AgentValidationError(
            "The file-based corpus could not be read."
        ) from None
