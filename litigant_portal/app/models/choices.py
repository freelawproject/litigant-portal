import os

from django.db import models
from django.utils.translation import gettext_lazy as _


class OpenAIModel(models.TextChoices):
    """OpenAI models as LiteLLM model strings, smallest first."""

    GPT_5_NANO = "openai/gpt-5-nano", "GPT-5 Nano"
    GPT_5_4_MINI = "openai/gpt-5.4-mini", "GPT-5.4 Mini"
    GPT_5_5 = "openai/gpt-5.5", "GPT-5.5"


class BedrockModel(models.TextChoices):
    """Claude models on AWS Bedrock as LiteLLM model strings, smallest
    first."""

    HAIKU_4_5 = (
        "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "Claude Haiku 4.5",
    )
    SONNET_5 = "bedrock/us.anthropic.claude-sonnet-5", "Claude Sonnet 5"
    OPUS_4_8 = "bedrock/us.anthropic.claude-opus-4-8", "Claude Opus 4.8"


AI_MODEL_CHOICES = [
    ("OpenAI", OpenAIModel.choices),
    ("AWS Bedrock", BedrockModel.choices),
]


def get_default_model() -> str:
    """The model used when a site hasn't chosen one: the smallest model
    from whichever provider is configured, preferring Bedrock. Falls back
    to the smallest Bedrock model when neither provider is configured."""
    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        return BedrockModel.HAIKU_4_5
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIModel.GPT_5_NANO
    return BedrockModel.HAIKU_4_5


class JurisdictionLevel(models.TextChoices):
    STATE = "state"
    COUNTY = "county"
    DISTRICT = "district"
    FEDERAL = "federal"
    TRIBAL = "tribal"


class State(models.TextChoices):
    ALABAMA = "AL", _("Alabama")
    ALASKA = "AK", _("Alaska")
    ARIZONA = "AZ", _("Arizona")
    ARKANSAS = "AR", _("Arkansas")
    CALIFORNIA = "CA", _("California")
    COLORADO = "CO", _("Colorado")
    CONNECTICUT = "CT", _("Connecticut")
    DELAWARE = "DE", _("Delaware")
    DISTRICT_OF_COLUMBIA = "DC", _("District of Columbia")
    FLORIDA = "FL", _("Florida")
    GEORGIA = "GA", _("Georgia")
    HAWAII = "HI", _("Hawaii")
    IDAHO = "ID", _("Idaho")
    ILLINOIS = "IL", _("Illinois")
    INDIANA = "IN", _("Indiana")
    IOWA = "IA", _("Iowa")
    KANSAS = "KS", _("Kansas")
    KENTUCKY = "KY", _("Kentucky")
    LOUISIANA = "LA", _("Louisiana")
    MAINE = "ME", _("Maine")
    MARYLAND = "MD", _("Maryland")
    MASSACHUSETTS = "MA", _("Massachusetts")
    MICHIGAN = "MI", _("Michigan")
    MINNESOTA = "MN", _("Minnesota")
    MISSISSIPPI = "MS", _("Mississippi")
    MISSOURI = "MO", _("Missouri")
    MONTANA = "MT", _("Montana")
    NEBRASKA = "NE", _("Nebraska")
    NEVADA = "NV", _("Nevada")
    NEW_HAMPSHIRE = "NH", _("New Hampshire")
    NEW_JERSEY = "NJ", _("New Jersey")
    NEW_MEXICO = "NM", _("New Mexico")
    NEW_YORK = "NY", _("New York")
    NORTH_CAROLINA = "NC", _("North Carolina")
    NORTH_DAKOTA = "ND", _("North Dakota")
    OHIO = "OH", _("Ohio")
    OKLAHOMA = "OK", _("Oklahoma")
    OREGON = "OR", _("Oregon")
    PENNSYLVANIA = "PA", _("Pennsylvania")
    RHODE_ISLAND = "RI", _("Rhode Island")
    SOUTH_CAROLINA = "SC", _("South Carolina")
    SOUTH_DAKOTA = "SD", _("South Dakota")
    TENNESSEE = "TN", _("Tennessee")
    TEXAS = "TX", _("Texas")
    UTAH = "UT", _("Utah")
    VERMONT = "VT", _("Vermont")
    VIRGINIA = "VA", _("Virginia")
    WASHINGTON = "WA", _("Washington")
    WEST_VIRGINIA = "WV", _("West Virginia")
    WISCONSIN = "WI", _("Wisconsin")
    WYOMING = "WY", _("Wyoming")
    AMERICAN_SAMOA = "AS", _("American Samoa")
    GUAM = "GU", _("Guam")
    NORTHERN_MARIANA_ISLANDS = "MP", _("Northern Mariana Islands")
    PUERTO_RICO = "PR", _("Puerto Rico")
    VIRGIN_ISLANDS = "VI", _("U.S. Virgin Islands")


class TopicFlowFormConditionOperator(models.TextChoices):
    EQUALS = "equals", "Equals"
    NOT_EQUALS = "not_equals", "Not equals"


class VariableDataType(models.TextChoices):
    TEXT = "text", "Text"
    DATE = "date", "Date"
    DATETIME = "datetime", "Datetime"
    NUMBER = "number", "Number"
    CHOICE = "choice", "Choice"
    BOOLEAN = "boolean", "Boolean"
