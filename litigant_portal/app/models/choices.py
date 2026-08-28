from django.db import models
from django.utils.translation import gettext_lazy as _


class BedrockModel(models.TextChoices):
    """Models on AWS Bedrock as LiteLLM model strings."""

    GPT_5_6_LUNA = "bedrock_mantle/openai.gpt-5.6-luna", "GPT-5.6 Luna"
    GPT_5_6_TERRA = "bedrock_mantle/openai.gpt-5.6-terra", "GPT-5.6 Terra"
    GPT_5_6_SOL = "bedrock_mantle/openai.gpt-5.6-sol", "GPT-5.6 Sol"
    CLAUDE_HAIKU_4_5 = (
        "bedrock_mantle/anthropic.claude-haiku-4-5",
        "Claude Haiku 4.5",
    )
    GLM_4_7_FLASH = "bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"


DEFAULT_BEDROCK_MODEL = BedrockModel.GPT_5_6_LUNA


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
