from typing import Annotated, Literal

import pytest
from pydantic import Field, ValidationError, field_validator

from lp_agent import AgentValidationError, LPAgent
from lp_agent.types import ContractModel

SECRET = "private-person@example.invalid"


def test_constructor_retains_known_paths_without_echoing_extra_keys(
    environment,
):
    with pytest.raises(AgentValidationError) as error:
        LPAgent(
            environment=environment,
            limits={"max_steps": 0, SECRET: "private value"},
        )
    assert str(error.value) == (
        "limits.max_steps: Value is too small; limits: Unexpected field"
    )


class TypedOption(ContractModel):
    type: Literal["known"]


class SensitiveInput(ContractModel):
    values: dict[str, int] = {}
    option: Annotated[TypedOption, Field(discriminator="type")] | None = None
    message: str = ""

    @field_validator("message")
    @classmethod
    def reject_message(cls, value):
        """
        Simulate a validator that echoes submitted text in its exception.
        """
        raise ValueError(value)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({SECRET: 1}, "input: Unexpected field"),
        ({"values": {SECRET: "invalid"}}, "values: Invalid value"),
        ({"option": {"type": SECRET}}, "option: Unsupported option"),
        ({"message": SECRET}, "message: Invalid value"),
    ],
)
def test_error_locations_and_messages_do_not_echo_input(data, expected):
    with pytest.raises(ValidationError) as error:
        SensitiveInput.model_validate(data)
    public_error = AgentValidationError.from_validation_error(
        error.value, models=(SensitiveInput,)
    )
    assert str(public_error) == expected
    assert SECRET not in str(public_error)


def test_missing_schema_uses_safe_generic_location():
    with pytest.raises(ValidationError) as error:
        SensitiveInput.model_validate({"option": {"type": SECRET}})
    assert str(AgentValidationError.from_validation_error(error.value)) == (
        "input: Unsupported option"
    )
