import os

from django.db import models


class OpenAIModel(models.TextChoices):
    """OpenAI models as LiteLLM model strings, smallest first."""

    GPT_5_6_LUNA = "openai/gpt-5.6-luna", "GPT-5.6 Luna"
    GPT_5_6_TERRA = "openai/gpt-5.6-terra", "GPT-5.6 Terra"
    GPT_5_6_SOL = "openai/gpt-5.6-sol", "GPT-5.6 Sol"


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
        return OpenAIModel.GPT_5_6_LUNA
    return BedrockModel.HAIKU_4_5


class JurisdictionLevel(models.TextChoices):
    STATE = "state"
    COUNTY = "county"
    DISTRICT = "district"
    FEDERAL = "federal"
    TRIBAL = "tribal"


class State(models.TextChoices):
    ALABAMA = "AL", "Alabama"
    ALASKA = "AK", "Alaska"
    ARIZONA = "AZ", "Arizona"
    ARKANSAS = "AR", "Arkansas"
    CALIFORNIA = "CA", "California"
    COLORADO = "CO", "Colorado"
    CONNECTICUT = "CT", "Connecticut"
    DELAWARE = "DE", "Delaware"
    DISTRICT_OF_COLUMBIA = "DC", "District of Columbia"
    FLORIDA = "FL", "Florida"
    GEORGIA = "GA", "Georgia"
    HAWAII = "HI", "Hawaii"
    IDAHO = "ID", "Idaho"
    ILLINOIS = "IL", "Illinois"
    INDIANA = "IN", "Indiana"
    IOWA = "IA", "Iowa"
    KANSAS = "KS", "Kansas"
    KENTUCKY = "KY", "Kentucky"
    LOUISIANA = "LA", "Louisiana"
    MAINE = "ME", "Maine"
    MARYLAND = "MD", "Maryland"
    MASSACHUSETTS = "MA", "Massachusetts"
    MICHIGAN = "MI", "Michigan"
    MINNESOTA = "MN", "Minnesota"
    MISSISSIPPI = "MS", "Mississippi"
    MISSOURI = "MO", "Missouri"
    MONTANA = "MT", "Montana"
    NEBRASKA = "NE", "Nebraska"
    NEVADA = "NV", "Nevada"
    NEW_HAMPSHIRE = "NH", "New Hampshire"
    NEW_JERSEY = "NJ", "New Jersey"
    NEW_MEXICO = "NM", "New Mexico"
    NEW_YORK = "NY", "New York"
    NORTH_CAROLINA = "NC", "North Carolina"
    NORTH_DAKOTA = "ND", "North Dakota"
    OHIO = "OH", "Ohio"
    OKLAHOMA = "OK", "Oklahoma"
    OREGON = "OR", "Oregon"
    PENNSYLVANIA = "PA", "Pennsylvania"
    RHODE_ISLAND = "RI", "Rhode Island"
    SOUTH_CAROLINA = "SC", "South Carolina"
    SOUTH_DAKOTA = "SD", "South Dakota"
    TENNESSEE = "TN", "Tennessee"
    TEXAS = "TX", "Texas"
    UTAH = "UT", "Utah"
    VERMONT = "VT", "Vermont"
    VIRGINIA = "VA", "Virginia"
    WASHINGTON = "WA", "Washington"
    WEST_VIRGINIA = "WV", "West Virginia"
    WISCONSIN = "WI", "Wisconsin"
    WYOMING = "WY", "Wyoming"
    AMERICAN_SAMOA = "AS", "American Samoa"
    GUAM = "GU", "Guam"
    NORTHERN_MARIANA_ISLANDS = "MP", "Northern Mariana Islands"
    PUERTO_RICO = "PR", "Puerto Rico"
    VIRGIN_ISLANDS = "VI", "U.S. Virgin Islands"
