"""Phase prompts — flow conventions for the three phases of a legal flow.

The three phases (Triage / Prepare / Resolve) come from
`docs/overview-mapped-legal-flow.md`. They exist in every legal flow across
every topic and court. Sub-stages within each phase can grow, shrink, or be
replaced depending on topic, but the phases themselves are invariant.

Each phase prompt layers flow conventions on top of the universal Base
prompt — how blockers render, how sidebars populate, how deadline math
hydrates, how cascades get sequenced, etc. Topic and Court prompts provide
the domain and jurisdictional content that fills in the structure.
"""
