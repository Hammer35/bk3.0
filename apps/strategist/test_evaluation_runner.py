"""Offline validation of the paid evaluation runner; no provider calls."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
import yaml


class EvaluationRunnerValidationTests(SimpleTestCase):
    def setUp(self):
        self.namespace = {"EVALUATION_LOAD_ONLY": True}
        exec((settings.BASE_DIR / "scripts/evaluate_strategist_release.py").read_text(), self.namespace)
        self.case = {"id": "fixture", "family": "context", "business_profile": "known", "messages": ["Вопрос"], "expected": ["Критерий"]}

    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.yaml"
            path.write_text(yaml.safe_dump(data, allow_unicode=True))
            return self.namespace["load_cases"](path)

    def test_valid_case_is_loaded_without_model_or_database(self):
        self.assertEqual(self.load({"indexed_in_rag": False, "cases": [self.case]}), [self.case])

    def test_invalid_datasets_are_rejected(self):
        for data in (
            {"indexed_in_rag": True, "cases": [self.case]},
            {"indexed_in_rag": False, "cases": []},
            {"indexed_in_rag": False, "cases": [self.case, self.case]},
            {"indexed_in_rag": False, "cases": [{**self.case, "messages": ["a", "b", "c"]}]},
            {"indexed_in_rag": False, "cases": [{**self.case, "business_profile": {}}]},
            {"indexed_in_rag": False, "cases": [{**self.case, "expected": [None]}]},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.load(data)

    def test_invalid_repetition_does_not_start_database_setup(self):
        with patch.dict(self.namespace, {"setup_databases": lambda **kwargs: self.fail("Database setup must not run")}):
            for repetition in (0, -1, True, 4):
                with self.subTest(repetition=repetition), self.assertRaises(ValueError):
                    self.namespace["evaluate"](repetitions=repetition)

    def test_history_validations_reject_invalid_data(self):
        for history in (None, "invalid", [{"role": "SYSTEM", "content": "test"}], [{"role": "USER"}]):
            with self.subTest(history=history), self.assertRaises(ValueError):
                self.load({"indexed_in_rag": False, "cases": [{**self.case, "history": history}]})

    def test_knowledge_mode_validations_reject_invalid_data(self):
        for mode in (None, {}, "invalid"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.load({"indexed_in_rag": False, "cases": [{**self.case, "knowledge_mode": mode}]})

    def test_tool_fixture_validations(self):
        for mode in ({}, "invalid", 1):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.load({"indexed_in_rag": False, "cases": [{**self.case, "tool_fixture": mode}]})
        for mode in ("followers", "failure", "missing_scope", "paginated", "page_failure"):
            case = {**self.case, "tool_fixture": mode}
            self.assertEqual(self.load({"indexed_in_rag": False, "cases": [case]}), [case])

    def test_blank_or_non_string_case_fields_are_rejected(self):
        for field, value in (("messages", [" "]), ("messages", [None]), ("expected", [" "]), ("expected", [1]), ("id", ""), ("family", " ")):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.load({"indexed_in_rag": False, "cases": [{**self.case, field: value}]})
