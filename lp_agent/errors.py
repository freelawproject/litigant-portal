"""
Caller-safe validation, access, and operational errors.
"""

from typing import Self

from pydantic import BaseModel, ValidationError

_ERROR_MESSAGES = {
    "extra_forbidden": "Unexpected field",
    "missing": "Required field",
    "string_type": "Must be text",
    "int_type": "Must be an integer",
    "float_type": "Must be a number",
    "bool_type": "Must be a boolean",
    "tuple_type": "Must be a sequence",
    "list_type": "Must be a sequence",
    "dict_type": "Must be an object",
    "greater_than": "Value is too small",
    "greater_than_equal": "Value is too small",
    "less_than": "Value is too large",
    "less_than_equal": "Value is too large",
    "finite_number": "Must be a finite number",
    "literal_error": "Unsupported option",
    "union_tag_invalid": "Unsupported option",
    "union_tag_not_found": "Missing option type",
}


def _safe_location(location: tuple, schema: dict) -> str:
    """
    Follow declared properties and sequence indices, never dictionary keys.
    """
    definitions = schema.get("$defs", {})
    path = []
    for segment in location:
        seen = set()
        while "$ref" in schema:
            reference = schema["$ref"]
            if reference in seen or not reference.startswith("#/$defs/"):
                return ".".join(path)
            seen.add(reference)
            schema = definitions.get(reference.removeprefix("#/$defs/"), {})
        if isinstance(segment, str) and segment in schema.get(
            "properties", {}
        ):
            schema = schema["properties"][segment]
        elif isinstance(segment, int) and isinstance(
            schema.get("items"), dict
        ):
            schema = schema["items"]
        else:
            break
        path.append(str(segment))
    return ".".join(path)


class AgentError(Exception):
    """
    Base exception for the public agent interface.
    """


class AgentStorageError(AgentError):
    """
    A checkpoint could not be saved; no terminal outcome is guaranteed.
    """

    def __init__(self) -> None:
        super().__init__("Unable to save the run state. Please try again.")


class AgentValidationError(AgentError, ValueError):
    """
    Configuration, a submission, or a question reply is invalid.
    """

    @classmethod
    def from_validation_error(
        cls,
        error: ValidationError,
        *,
        models: tuple[type[BaseModel], ...] = (),
    ) -> Self:
        """
        Use trusted model fields and fixed messages, with a generic fallback.

        Pydantic locations and messages can both contain submitted data.
        Only schemas generated from the caller's contract classes are trusted.
        """
        schemas = [model.model_json_schema() for model in models]
        problems = []
        for item in error.errors(
            include_url=False, include_context=False, include_input=False
        ):
            location = (
                max(
                    (
                        _safe_location(item["loc"], schema)
                        for schema in schemas
                    ),
                    key=len,
                    default="",
                )
                or "input"
            )
            message = _ERROR_MESSAGES.get(item["type"], "Invalid value")
            problems.append(f"{location}: {message}")
        return cls("; ".join(problems))


class AgentAccessError(AgentError):
    """
    The host's access context does not authorize the requested resource.
    """


class AgentBusyError(AgentError):
    """
    The conversation has an active run and its policy rejects new input.
    """
