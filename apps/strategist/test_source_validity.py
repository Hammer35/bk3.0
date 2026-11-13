"""Explicit offline coverage of stale and unapproved knowledge boundaries."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.strategist.grounded_answers import _approved_source, grounded_pinterest_answer


class SourceValidityTests(SimpleTestCase):
    def test_stale_source_cannot_produce_official_length_answer(self):
        source = _approved_source("pinterest-pin-text-specs.md")
        self.assertIsNotNone(source)
        with patch("apps.strategist.grounded_answers.timezone.localdate", return_value=source.effective_until + timedelta(days=1)):
            self.assertIsNone(grounded_pinterest_answer("Какой официальный лимит длины описания Pin?"))

    def test_future_or_unapproved_source_is_not_used(self):
        source = _approved_source("pinterest-pin-text-specs.md")
        self.assertIsNotNone(source)
        for invalid in (
            replace(source, status="draft"),
            replace(source, scope="business"),
            replace(source, source_checked=timezone.localdate() + timedelta(days=1)),
        ):
            with self.subTest(source=invalid), patch("apps.strategist.grounded_answers.load_source", return_value=invalid):
                self.assertIsNone(grounded_pinterest_answer("Какой лимит длины заголовка Pin?"))
