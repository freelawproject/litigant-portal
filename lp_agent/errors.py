"""
Errors raised before a run or input is accepted.
"""

from typing import Self

from pydantic import ValidationError


class AgentError(Exception):
    """
    Base exception for the public agent interface.
    """


class AgentValidationError(AgentError, ValueError):
    """
    Configuration, a submission, or a question reply is invalid.
    """

    @classmethod
    def from_validation_error(cls, error: ValidationError) -> Self:
        """
        Describe invalid fields without including the submitted values.
        """
        problems = []
        for item in error.errors(
            include_url=False, include_context=False, include_input=False
        ):
            location = ".".join(map(str, item["loc"])) or "input"
            problems.append(f"{location}: {item['msg']}")
        return cls("; ".join(problems))


class AgentAccessError(AgentError):
    """
    The host's access context does not authorize the requested resource.
    """


class AgentBusyError(AgentError):
    """
    The conversation has an active run and its policy rejects new input.
    """
