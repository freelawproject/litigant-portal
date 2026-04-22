"""Tests for the Base + Phase + Topic + Court prompt composition (#314, #318)."""

from django.test import TestCase

from chat.prompts import (
    _VALID_PHASES,
    BASE_PROMPT,
    build_system_prompt,
    phase_for_session,
)


class BuildSystemPromptTests(TestCase):
    """Tests for build_system_prompt layer composition."""

    def test_default_phase_is_triage(self):
        result = build_system_prompt()

        self.assertIn(BASE_PROMPT, result)
        self.assertIn("TRIAGE PHASE", result)

    def test_explicit_phase_prepare(self):
        result = build_system_prompt(phase="prepare")

        self.assertIn("PREPARE PHASE", result)
        self.assertNotIn("TRIAGE PHASE", result)
        self.assertNotIn("RESOLVE PHASE", result)

    def test_explicit_phase_resolve(self):
        result = build_system_prompt(phase="resolve")

        self.assertIn("RESOLVE PHASE", result)
        self.assertNotIn("TRIAGE PHASE", result)
        self.assertNotIn("PREPARE PHASE", result)

    def test_invalid_phase_raises(self):
        with self.assertRaises(ValueError):
            build_system_prompt(phase="not-a-phase")

    def test_topic_layer_included(self):
        result = build_system_prompt(topic="eviction")

        self.assertIn("EVICTION", result)

    def test_missing_topic_omits_layer(self):
        result = build_system_prompt()

        self.assertNotIn("EVICTION", result)
        self.assertNotIn("ADULT NAME CHANGE", result)

    def test_court_layer_included(self):
        result = build_system_prompt(court="dupage_il")

        self.assertIn("DUPAGE COUNTY", result)

    def test_missing_court_omits_layer(self):
        result = build_system_prompt(topic="eviction")

        self.assertIn("EVICTION", result)
        self.assertNotIn("DUPAGE COUNTY", result)

    def test_full_four_layer_composition(self):
        result = build_system_prompt(
            phase="prepare",
            topic="adult_name_change",
            court="nd",
        )

        self.assertIn(BASE_PROMPT, result)
        self.assertIn("PREPARE PHASE", result)
        self.assertIn("ADULT NAME CHANGE", result)
        self.assertIn("NORTH DAKOTA", result)

    def test_jurisdiction_backward_compat_il(self):
        # Callers that pass jurisdiction="il" should resolve to dupage_il court.
        result = build_system_prompt(topic="eviction", jurisdiction="il")

        self.assertIn("EVICTION", result)
        self.assertIn("DUPAGE COUNTY", result)

    def test_jurisdiction_backward_compat_nd(self):
        result = build_system_prompt(
            topic="adult_name_change", jurisdiction="nd"
        )

        self.assertIn("ADULT NAME CHANGE", result)
        self.assertIn("NORTH DAKOTA", result)

    def test_explicit_court_wins_over_jurisdiction(self):
        result = build_system_prompt(court="nd", jurisdiction="il")

        self.assertIn("NORTH DAKOTA", result)
        self.assertNotIn("DUPAGE COUNTY", result)

    def test_unknown_jurisdiction_omits_court(self):
        result = build_system_prompt(jurisdiction="xx")

        self.assertNotIn("DUPAGE COUNTY", result)
        self.assertNotIn("NORTH DAKOTA", result)

    def test_phase_ordering_base_first_then_phase(self):
        result = build_system_prompt(phase="triage")
        base_idx = result.find(BASE_PROMPT)
        phase_idx = result.find("TRIAGE PHASE")

        self.assertLess(base_idx, phase_idx)

    def test_valid_phases_tuple_covers_expected(self):
        self.assertEqual(set(_VALID_PHASES), {"triage", "prepare", "resolve"})


class PhaseForSessionTests(TestCase):
    """Tests for phase_for_session session-state mapping."""

    def test_none_session_returns_triage(self):
        self.assertEqual(phase_for_session(None), "triage")

    def test_no_case_info_no_resolution_returns_triage(self):
        class FakeSession:
            case_info = None
            resolution = None

        self.assertEqual(phase_for_session(FakeSession()), "triage")

    def test_case_info_without_resolution_returns_prepare(self):
        class FakeSession:
            case_info = {"petitioner_name": "Sandra"}
            resolution = None

        self.assertEqual(phase_for_session(FakeSession()), "prepare")

    def test_resolution_returns_resolve(self):
        class FakeSession:
            case_info = {"petitioner_name": "Sandra"}
            resolution = {"status": "granted"}

        self.assertEqual(phase_for_session(FakeSession()), "resolve")

    def test_resolution_without_case_info_still_resolves(self):
        class FakeSession:
            case_info = None
            resolution = {"status": "granted"}

        self.assertEqual(phase_for_session(FakeSession()), "resolve")
