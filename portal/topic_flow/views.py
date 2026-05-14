"""Topic Flow views — generic dispatch + section POST endpoints.

Real implementation lands with #391. This stub exists so the do-no-harm
shim in ``portal.views.deep_link`` can import the symbol; the registry
returns False for everything in v1 so this function is never reached.
"""


def topic_flow(request, court, topic):
    raise NotImplementedError(
        f"Topic Flow dispatch is not yet wired for {court}/{topic} — "
        "registry.has_corpus must return False until the engine (#391+) lands."
    )
