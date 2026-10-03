# RESULT-012

Исполнитель: opencode-cli; модель: `openrouter/cohere/north-mini-code:free`.
Сессия: ses_eff34d36bffefdvntb7alJTKA2.
Статус: ожидает приёмки Codex.

Here are the 3 new test methods to add to `apps/strategist/test_evaluation_runner.py`:

```python
    def test_messages_expected_whitespace_and_non_string_rejected(self):
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test1",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test2",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["", "valid"],
                        "expected": ["valid"],
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test3",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": [""],
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                    }
                ],
            },
        )

    def test_history_validations_reject_invalid_data(self):
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test1",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                        "history": None,
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test2",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                        "history": "invalid",
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test3",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                        "history": [{"role": "SYSTEM", "content": "test"}],
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test4",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                        "history": [{"role": "USER"}],
                    }
                ],
            },
        )

    def test_knowledge_mode_validations_reject_invalid_data(self):
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test1",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                        "knowledge_mode": None,
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test2",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                        "knowledge_mode": {"invalid": "dict"},
                    }
                ],
            },
        )
        self.assertRaises(
            ValueError,
            self.load,
            {
                "indexed_in_rag": False,
                "cases": [
                    {
                        "id": "test3",
                        "family": "context",
                        "business_profile": "known",
                        "messages": ["valid"],
                        "expected": ["valid"],
                        "knowledge_mode": "invalid",
                    }
                ],
            },
        )
```
