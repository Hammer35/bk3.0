"""Policy switches: competitor research is off by default, AI transfer follows the setting."""
from django.test import SimpleTestCase, override_settings

from apps.pinterest import policy


class PolicySwitchTest(SimpleTestCase):
    def test_defaults_are_the_documented_ones(self):
        self.assertFalse(policy.competitor_research_enabled())
        self.assertTrue(policy.pinterest_ai_transfer_enabled())
        self.assertEqual(policy.retention_days(), 30)

    def test_competitor_guard_blocks_before_any_data_access(self):
        with self.assertRaisesMessage(PermissionError, "требует письменного разрешения Pinterest"):
            policy.require_competitor_research_enabled()
        with override_settings(PINTEREST_COMPETITOR_RESEARCH_ENABLED=True):
            policy.require_competitor_research_enabled()  # explicit opt-in only

    @override_settings(PINTEREST_AI_DATA_TRANSFER_ENABLED=False, RESEARCH_SNAPSHOT_RETENTION_DAYS=0)
    def test_switches_follow_settings_and_retention_never_drops_below_a_day(self):
        self.assertFalse(policy.pinterest_ai_transfer_enabled())
        self.assertEqual(policy.retention_days(), 1)
