"""Discovery #670: the v2 assistant knows the guided-flow links exist."""

from litigant_portal.agents_v2 import assistant as assistant_module
from litigant_portal.agents_v2.assistant import (
    BASE_PROMPT,
    LitigantAssistant,
    flow_prompt_section,
)

TRACKS = [
    {
        "court": "franklin-county-oh",
        "topic": "eviction",
        "role": "tenant",
        "label": "Responding to an Eviction in Franklin County, Ohio (Tenant)",
        "title": "Responding to an Eviction in Franklin County, Ohio (Tenant)",
    },
    {
        "court": "north-dakota",
        "topic": "adult-name-change",
        "role": "standard",
        "label": "Adult Name Change in North Dakota (Publication Required)",
        "title": "Adult Name Change in North Dakota (Publication Required)",
    },
]


def test_flow_section_lists_each_track(monkeypatch):
    monkeypatch.setattr(
        assistant_module.registry, "all_tracks", lambda: TRACKS
    )
    section = flow_prompt_section()
    for track in TRACKS:
        assert track["title"] in section
    # Must name the UI affordance the links live under.
    assert "Guided steps" in section


def test_flow_section_empty_when_no_corpora(monkeypatch):
    monkeypatch.setattr(assistant_module.registry, "all_tracks", lambda: [])
    assert flow_prompt_section() == ""


def test_system_prompt_appends_flow_section(monkeypatch):
    monkeypatch.setattr(
        assistant_module.registry, "all_tracks", lambda: TRACKS
    )
    prompt = LitigantAssistant().generate_system_prompt(thread_id=None)
    assert prompt.startswith(BASE_PROMPT)
    assert TRACKS[0]["title"] in prompt
