class NewEngagementFlow:
    """
    This is the main flow for the new PortalAgent to engage with a user and
    proceed through a legal matter.

    Starting out now with just pseudo-code:
    - Look to see if the agent has a court and topic
    - If not, run triage
      - This will walk through a static flow to figure out which court without calling the actual bedrock model
        - For now, just make the agent respond that this is not implemented yet and they need to select a court

    """

    pass
