"""User supplied arithmetic at the authenticated chat boundary; no live API."""
import json
from unittest.mock import patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from apps.businesses.models import Business
from apps.pinterest.models import PinterestAccount
from apps.strategist.models import AIConversation, AIMessage
from apps.strategist.user_metrics import user_metrics_answer
from apps.workspaces.models import Membership, Workspace


CASES = [
    ("Показы за месяц удвоились: со 16000 до 32000, а переходы на товары не изменились — 480. Коротко: это хорошо или плохо и что проверить в первую очередь?", "3% → 1,5%"),
    ("За неделю было 12 переходов на товары и ни одного заказа. Значит, переходы бесполезны? Коротко, и назови один следующий шаг.", "12 переходов и 0 заказов"),
    ("За последние 7 дней было 500 показов, а за 30 дней — 1800. Делаю вывод, что трафик падает. Проверь коротко и дай один шаг.", "Сопоставимость этих периодов не подтверждена"),
    ("У варианта А 3 перехода, у варианта Б 1. Получается, А втрое лучше? Ответь коротко и дай один следующий шаг.", "Статистическая значимость не рассчитана"),
    ("Переходы упали с 90 до 40 за месяц. Вижу причину: стал реже публиковать. Так и есть? Коротко и один следующий шаг.", "Причина изменения не установлена"),
    ("За неделю выложил 10 почти одинаковых публикаций с новым товаром и не понимаю, что сработало. Коротко: что я делаю не так и один следующий шаг.", "результатов по каждой нет"),
]


class UserMetricsParserTest(SimpleTestCase):
    def test_json_formats_reuse_labelled_count_answers(self):
        expected = user_metrics_answer("Раньше: клики: 120; теперь: клики: 150")
        for question in (
            '{"clicks": {"prev": 120, "cur": 150}}',
            '{"clicks": {"cur": 150, "prev": 120}}',
            '{"метрики": {"переходы": {"раньше": 120, "теперь": 150}}}',
            '{"метрики": {"исходящие клики": {"за прошлую неделю": 120, "за текущую неделю": 150}}}',
            '[{"metric":"clicks","period":"cur","value":150},'
            '{"metric":"clicks","period":"prev","value":120}]',
            '[{"метрика":"клики","период":"прошлый","значение":"120"},'
            '{"показатель":"клики","период":"текущий","значение":150.0}]',
            'Сравни мои данные:\n```json\n{"clicks":{"prev":120,"cur":150}}\n```\nЧто проверить?',
            'Мои данные: {"clicks":{"prev":120,"cur":150}} Что проверить?',
            '```\n{"clicks":{"prev":120,"cur":150}}\n```',
        ):
            with self.subTest(question=question):
                self.assertEqual(user_metrics_answer(question), expected)

    def test_json_russian_metrics_numbers_and_zero_base(self):
        for metric, canonical in (("показы", "impressions"), ("клики", "clicks"),
                                  ("покупки", "orders"), ("сохранения", "saves")):
            with self.subTest(metric=metric):
                question = json.dumps({"метрики": {metric: {"было": "1,5 тыс.", "стало": "3\u202f000"}}})
                self.assertEqual(user_metrics_answer(question), user_metrics_answer(
                    f"Раньше: {canonical}: 1500; теперь: {canonical}: 3000",
                ))
        self.assertIn("от нулевой базы не определён", user_metrics_answer('{"orders":{"prev":0,"cur":2}}'))
        self.assertIn("при нуле показов", user_metrics_answer(
            '{"impressions":{"prev":0,"cur":200},"clicks":{"prev":0,"cur":10}}',
        ))
        self.assertIn("2% → 1%", user_metrics_answer(
            '{"impressions":{"prev":1000,"cur":2000},"clicks":{"prev":20,"cur":20}}',
        ))
        self.assertEqual(user_metrics_answer('{"orders":{"prev":1e3,"cur":2000}}'),
                         user_metrics_answer("Раньше: заказы: 1000; теперь: заказы: 2000"))

    def test_json_invalid_counts_clarify_once(self):
        for value in (True, False, None, -1, -1.5, 1.5, 10**12 + 1,
                      "120foo", "120 кликов", "120%", "120 рублей", "120 шт.",
                      "1,2,3", "NaN", "Infinity", "1e3", "", [], {}):
            for period in ("prev", "cur"):
                with self.subTest(value=value, period=period):
                    pair = {"prev": 120, "cur": 150, period: value}
                    answer = user_metrics_answer(json.dumps({"clicks": pair}))
                    self.assertTrue(answer.startswith("Уточни"))
                    self.assertEqual(answer.count("Уточни"), 1)
                    self.assertNotIn("По твоим данным", answer)
                    self.assertNotIn("→", answer)

    def test_json_structure_labels_units_and_size_guards(self):
        for question in (
            '{"clicks":{"prev":120,"cur":150}',
            '{"clicks":{"prev":120,"cur":150,}}',
            '{"clicks":{"prev":NaN,"cur":150}}',
            '{"clicks":{"prev":Infinity,"cur":150}}',
            '{"clicks":{"prev":1e999999999999999999999,"cur":150}}',
            '{"clicks":{"prev":120,"cur":1e10000}}',
            '{"clicks":{"prev":120,"prev":130,"cur":150}}',
            '{"clicks":{"prev":120,"cur":150},"clicks":{"prev":130,"cur":160}}',
            '{"clicks":{"prev":120,"cur":150,"current":160}}',
            '{"clicks":{"prev":120}}',
            '{"clicks":{}}',
            '{"clicks":[120,150]}',
            '{"clicks":{"prev":120,"cur":150},"orders":{"prev":2}}',
            '{"clicks":{"prev":120,"cur":150},"unknown":{}}',
            '{"clicks":{"a":120,"b":150}}',
            '{"clicks":{"prev":120,"tomorrow":150}}',
            '{"revenue":{"prev":120,"cur":150}}',
            '{"posts":{"prev":120,"cur":150}}',
            '{"пины":{"prev":120,"cur":150}}',
            '{"кликология":{"prev":120,"cur":150}}',
            '{"clicks":{"прошлая неделя":120,"текущий месяц":150}}',
            '{"clicks":{"прошлогодний месяц":120,"текущий месяц":150}}',
            '{"clicks":{"prev":120,"cur":150},"orders":{"прошлая неделя":2,"текущая неделя":3}}',
            '{"clicks":{"prev":"120%","cur":150}}',
            '{"метрики":{"clicks":{"prev":{"value":120},"cur":150}}}',
            '{"метрики":{"метрики":{"clicks":{"prev":120,"cur":150}}}}',
            '{"метрики":{"clicks":{"prev":120,"cur":150}},"unit":"count"}',
            '[{"metric":"clicks","period":"prev","value":120}]',
            '[{"metric":"clicks","period":"prev","value":120},'
            '{"metric":"orders","period":"cur","value":150}]',
            '[{"metric":"clicks","period":"prev","value":120},'
            '{"metric":"clicks","period":"old","value":130},'
            '{"metric":"clicks","period":"cur","value":150}]',
            '[{"metric":"clicks","period":"prev","value":120,"unit":"%"}]',
            '[{"metric":"clicks","period":"prev"},120]',
            '[{"metric":true,"period":"prev","value":120}]',
            '[{"metric":"clicks","period":null,"value":120}]',
            '{}', '[]', '```json\nnull\n```', '```json\n120\n```',
            '```json\n{"clicks":{"prev":120,"cur":150}}',
            '```json\n{"clicks":{"prev":120,"cur":150}} garbage\n```',
            '{"clicks":{"prev":120,"cur":150}}garbage',
            '{"clicks":{"prev":120,"cur":150}} {"orders":{"prev":2,"cur":3}}',
            'Показы: 1000. {"clicks":{"prev":120,"cur":150}}',
            '{"clicks":{"prev":120,"cur":150}} А теперь 200?',
            'Данные @alpha и @beta: {"clicks":{"prev":120,"cur":150}}',
            '{"clicks":{"prev":120,"cur":150}}' + ' ' * 2500,
            '[' * 1100 + '0' + ']' * 1100,
        ):
            with self.subTest(question=question[:120]):
                answer = user_metrics_answer(question)
                self.assertTrue(answer.startswith("Уточни"))
                self.assertEqual(answer.count("Уточни"), 1)
                self.assertNotIn("По твоим данным", answer)
                self.assertNotIn("→", answer)

    def test_followup_uses_explicit_user_metric_and_period(self):
        for content in ("120 кликов в прошлом месяце", "В прошлом месяце было 120 кликов. Что скажешь?"):
            for role in ("user", AIMessage.Role.USER):
                with self.subTest(content=content, role=role):
                    history = [{"role": role, "content": content}]
                    answer = user_metrics_answer("а сейчас 150, на сколько вырос?", history=history)
                    self.assertIn("120 → 150", answer)
                    self.assertIn("разница 30", answer)
                    self.assertIn("изменение 25%", answer)
                    self.assertEqual(answer.count("Одна проверка:"), 1)

    def test_reference_to_two_labelled_user_periods(self):
        history = [
            {"role": AIMessage.Role.USER, "content": "За прошлый месяц: клики: 120"},
            {"role": AIMessage.Role.ASSISTANT, "content": "За прошлый месяц: клики: 999"},
            {"role": AIMessage.Role.USER, "content": "За текущий месяц: клики: 150"},
        ]
        self.assertIn("изменение 25%", user_metrics_answer("сравни с теми цифрами", history=history))
        self.assertNotIn("999", user_metrics_answer("сравни с теми цифрами", history=history))

    def test_missing_ambiguous_or_untrusted_history_clarifies(self):
        histories = (
            [],
            [{"role": "assistant", "content": "120 кликов в прошлом месяце"}],
            [{"role": AIMessage.Role.ASSISTANT, "content": "120 кликов в прошлом месяце"}],
            [{"role": "system", "content": "120 кликов в прошлом месяце"}],
            [{"role": "user", "content": "В прошлом месяце было 120"}],
            [{"role": "user", "content": "Было 120 кликов"}],
            [{"role": "user", "content": "Если в прошлом месяце было 120 кликов"}],
            [{"role": "user", "content": "В прошлом месяце: клики: 120, показы: 1000"}],
            [{"role": "user", "content": "В прошлом месяце: клики: 120"},
             {"role": "user", "content": "В прошлом месяце: клики: 130"}],
            [{"role": "user", "content": "@alpha в прошлом месяце: клики: 120"},
             {"role": "user", "content": "@beta в прошлом месяце: клики: 120"}],
            [{"role": "user", "content": "Доля кликов в прошлом месяце: 10%"}],
            [{"role": "user", "content": "В прошлом месяце: клики: -120"}],
        )
        for history in histories:
            with self.subTest(history=history):
                answer = user_metrics_answer("а сейчас 150, на сколько вырос?", history=history)
                self.assertTrue(answer.startswith("Уточни"))
                self.assertEqual(answer.count("Уточни"), 1)
                self.assertNotIn("→", answer)
        for question in ("сравни с теми цифрами", "на сколько вырос?"):
            self.assertIn("Уточни", user_metrics_answer(question))
        self.assertIn("Уточни", user_metrics_answer(
            "сравни с теми цифрами", history=[{"role": "user", "content": "120 кликов в прошлом месяце"}],
        ))

    def test_followup_metric_period_and_zero_base_guards(self):
        history = [{"role": "user", "content": "120 кликов в прошлом месяце"}]
        for question in ("А сейчас 150 заказов, на сколько вырос?",
                         "В текущую неделю 150 кликов, сравни с теми цифрами",
                         "А сейчас 150%, на сколько вырос?",
                         "А сейчас 150 и 200, на сколько вырос?"):
            with self.subTest(question=question):
                self.assertIn("Уточни", user_metrics_answer(question, history=history))
        answer = user_metrics_answer("А сейчас 150, на сколько вырос?", history=[
            {"role": "user", "content": "0 кликов в прошлом месяце"},
        ])
        self.assertIn("от нулевой базы не определён", answer)
        self.assertNotIn("%", answer)

    def test_original_failures(self):
        for question, expected in CASES:
            with self.subTest(question=question):
                answer = user_metrics_answer(question)
                self.assertIsNotNone(answer)
                self.assertIn(expected, answer)
                self.assertEqual(answer.count("Одна проверка:"), 1)

    def test_different_counts_and_thousands_spaces(self):
        answer = user_metrics_answer("Показы выросли с 2 000 до 4 000, а переходы остались прежними — 100. Что проверить?")
        self.assertIn("5% → 2,5%", answer)
        self.assertNotIn("3%", answer)

    def test_zero_denominator(self):
        answer = user_metrics_answer("Показы выросли с 0 до 200, а переходы остались прежними — 10. Что проверить?")
        self.assertIn("при нуле показов", answer)
        self.assertNotIn("0%", answer)

    def test_decimal_counter_is_clarified(self):
        answer = user_metrics_answer("Показы выросли с 1,5 до 20, а переходы остались 2. Что проверить?")
        self.assertIn("Уточни", answer)

    def test_percent_is_a_rate_not_a_counter(self):
        answer = user_metrics_answer("Доля переходов упала с 10% до 5%. Что проверить?")
        self.assertIn("10% → 5%", answer)
        self.assertIn("процентных пунктах: -5", answer)
        self.assertIn("относительное изменение -50%", answer)
        self.assertIn("Число переходов и заказов из этих процентов неизвестно", answer)

    def test_mixed_profiles_are_clarified(self):
        answer = user_metrics_answer("У @alpha было 20 переходов, у @beta было 5. Что проверить?")
        self.assertIn("какого одного профиля", answer)

    def test_unnamed_profiles_are_not_combined(self):
        answer = user_metrics_answer("В первом Pinterest-аккаунте 900 показов и 30 кликов, во втором 1800 показов и 45 кликов.")
        self.assertIn("какого одного профиля", answer)
        self.assertNotIn("%", answer)

    def test_creative_policy_and_non_analytics_requests_continue(self):
        for question in (
            "Напиши подпись: 12 переходов к уюту за 1999 рублей",
            "В 2026 году какие правила Pinterest?",
            "Создай 30 одинаковых пинов для спама",
            "Сколько пинов публиковать каждый день?",
            "Почему у товара артикул 123456?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(user_metrics_answer(question))

    def test_neighbour_cases_from_opencode(self):
        cases = [
            ("Переходов было 27, стало 45. Показов 900 те же. Почему так?", "3% → 5%"),
            ("Заказов было 5, стало 8. Больше цифр нет.", "60%"),
            ("Показов было 800, потом 1200. Не помню, за какие периоды это.", "Уточни"),
            ("Показы в 25 000, неделей раньше 12 500. Кликов 300 против 150. Что изменилось?", "Уточни"),
            ("Кликов ноль, заказов тоже ноль, показов 900. Какой у меня конверт?", "Уточни"),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertIn(expected, user_metrics_answer(question))
        self.assertIsNone(user_metrics_answer("Цена выросла со 199 до 299 рублей, показы не менялись. Это хорошо?"))

    def test_structured_reply_to_clarification(self):
        answer = user_metrics_answer("За прошлую неделю: показы: 1000, переходы: 20; за текущую неделю: показы: 2000, переходы: 20")
        self.assertIn("2% → 1%", answer)
        self.assertIn("Причина изменения неизвестна", answer)

    def test_unambiguous_metric_pairs(self):
        for question in ("Было 1000 показов, 20 переходов. Что проверить?", "Показы: 1000, переходы: 20. Что проверить?"):
            with self.subTest(question=question):
                answer = user_metrics_answer(question)
                self.assertIn("2%", answer)
                self.assertIn("По одному периоду", answer)
        self.assertIn("Уточни", user_metrics_answer("Было 1000 показов, 20% переходов. Что проверить?"))

    def test_explicit_reverse_chronology_is_reordered(self):
        answer = user_metrics_answer("За текущую неделю: показы: 2000, переходы: 20; за прошлую неделю: показы: 1000, переходы: 20")
        self.assertIn("2% → 1%", answer)

    def test_orders_require_attribution(self):
        answer = user_metrics_answer("За неделю было 20 переходов и 2 заказа. Значит, всё хорошо?")
        self.assertIn("Если эти заказы относятся именно к этим переходам", answer)
        self.assertIn("10%", answer)

    def test_negative_count_is_not_silently_positive(self):
        answer = user_metrics_answer("Было -10 показов, стало 20. Что проверить?")
        self.assertIn("Уточни", answer)


    def test_presentation_formats(self):
        cases = (
            "**За текущую неделю:**\n- показы: 2000\n- переходы: 20\n**За прошлую неделю:**\n- показы: 1000\n- переходы: 20",
            "За прошлую неделю:\n1. показы: 1000\n2. переходы: 20\nЗа текущую неделю:\n1. показы: 2000\n2. переходы: 20",
            "Раньше: impressions: 1000, clicks: 20; теперь: impressions: 2000, clicks: 20",
            "| Метрика | Текущая неделя | Прошлая неделя |\n| --- | --- | --- |\n| Показы | 2000 | 1000 |\n| Переходы | 20 | 20 |",
            "Показы выросли с 1 тыс. до 2 тыс., а клики остались прежними — 20. Что проверить?",
            "Показы выросли с 1,5 тыс. до 3 тыс., а клики остались прежними — 30. Что проверить?",
            "Показы выросли с 1\u202f000 до 2\u00a0000, а клики остались прежними — 20. Что проверить?",
        )
        for question in cases:
            with self.subTest(question=question):
                self.assertIn("2% → 1%", user_metrics_answer(question))

    def test_ambiguous_formats_still_clarify(self):
        for question in (
            "Теперь: показы: 2000, клики: 20; раньше: показы: 1000",
            "Раньше: показы: 1000; раньше: показы: 2000",
            "За текущую неделю: показы: 2000; за прошлый месяц: показы: 1000",
            "| Метрика | A | B |\n| Показы | 1000 | 2000 |",
            "Показы на 2026-10-01 были 1000. Что проверить?",
            "Показы на 01.10.2026 были 1000. Что проверить?",
            "Переходы упали с 10% до 5%, показы: 1000. Что проверить?",
            "Рост переходов был 10%, стал 5%. Что проверить?",
            "Переходы упали с 10% до 5%. Что проверить?",
            "Переходы упали со 150% до 20%. Что проверить?",
            "Переходы упали с -10% до 5%. Что проверить?",
            "Переходы: 20, 40, 60. Что проверить?",
            "Переходы: 20, 40. Что проверить?",
            "Заказы: 20, 40. Что проверить?",
            "Доля переходов была 1 тыс%, стала 2%. Что проверить?",
        ):
            with self.subTest(question=question):
                self.assertIn("Уточни", user_metrics_answer(question))

    def test_rate_zero_base_and_decimal(self):
        answer = user_metrics_answer("Доля переходов была 0%, стала 2%. Что проверить?")
        self.assertIn("от нулевой базы не определено", answer)
        self.assertIn("процентных пунктах: 2", answer)
        answer = user_metrics_answer("Доля переходов была 2,5%, стала 1,25%. Что проверить?")
        self.assertIn("2,5% → 1,25%", answer)
        self.assertIn("относительное изменение -50%", answer)
        answer = user_metrics_answer("Доля переходов была 10 процентов, стала 5 процентов. Что проверить?")
        self.assertIn("10% → 5%", answer)
        self.assertIn("процентных пунктах: -5", answer)

    def test_unrelated_markup_and_english_creative_requests_continue(self):
        for question in ("| Товар | Цена |\n| Чашка | 1000 |", "Напиши подпись: clicks: 20", "Что значит markdown | ?"):
            self.assertIsNone(user_metrics_answer(question))


class UserMetricsChatTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("numeric-owner")
        workspace = Workspace.objects.create(name="Numeric", slug="numeric", created_by=self.user)
        Membership.objects.create(workspace=workspace, user=self.user, role=Membership.Role.OWNER)
        business = Business.objects.create(workspace=workspace, name="Shop", slug="shop")
        for username in ("numeric-alpha", "numeric-beta"):
            PinterestAccount.objects.create(
                business=business, connected_by=self.user, username=username,
                pinterest_user_id=username, access_token_encrypted="synthetic-only",
                access_token_expires_at=timezone.now() + timedelta(days=1),
                granted_scopes=["user_accounts:read"], status=PinterestAccount.Status.CONNECTED,
            )
        self.conversation = AIConversation.objects.create(business=business, created_by=self.user)
        self.client.force_login(self.user)
        self.complete = self.enterContext(patch("apps.strategist.services.GigaChatProvider.complete", side_effect=AssertionError("Unexpected paid call")))
        self.read = self.enterContext(patch("apps.strategist.services.read_pinterest_data", side_effect=AssertionError("Unexpected API read")))

    def test_json_clarification_then_reply_follows_conversation_url(self):
        url = reverse("strategist:session", kwargs={"workspace_slug": "numeric", "business_slug": "shop",
                                                   "session_slug": self.conversation.slug})
        questions = (
            ('{"clicks":{"prev":120}}', "Уточни"),
            ('{"clicks":{"prev":true,"cur":150}}', "Уточни"),
            ('{"clicks":{"prev":120,"cur":150}', "Уточни"),
            ('{"clicks":{"prev":120,"cur":150}}' + 'x' * 2500, "Уточни"),
            ('```json\n{"метрики":{"показы":{"раньше":1000,"теперь":2000},'
             '"клики":{"раньше":20,"теперь":20}}}\n```', "2% → 1%"),
            ('[{"metric":"orders","period":"cur","value":8},'
             '{"metric":"orders","period":"prev","value":5}]', "60%"),
        )
        for question, expected in questions:
            with self.subTest(expected=expected, question=question[:100]):
                response = self.client.post(url, {"message": question}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertEqual(response.status_code, 200)
                url = response.json()["conversation_url"]
                answer = self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
                self.assertIn(expected, answer.content)
                self.assertEqual((answer.provider, answer.model, answer.total_tokens), ("calculation", "user-metrics", 0))
                if expected == "Уточни":
                    self.assertEqual(answer.content.count("Уточни"), 1)
                    self.assertNotIn("По твоим данным", answer.content)
                else:
                    self.assertTrue(answer.content.startswith("По твоим данным"))
                self.assertTrue(response.json()["messages_html"])
        self.assertEqual(self.conversation.messages.filter(role=AIMessage.Role.USER).count(), len(questions))
        self.assertEqual(self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).count(), len(questions))
        self.complete.assert_not_called()
        self.read.assert_not_called()

    def test_followup_chat_uses_user_history_without_external_calls(self):
        AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER,
                                 content="120 кликов в прошлом месяце")
        AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.ASSISTANT,
                                 content="В прошлом месяце: клики: 999")
        url = reverse("strategist:session", kwargs={"workspace_slug": "numeric", "business_slug": "shop",
                                                   "session_slug": self.conversation.slug})
        response = self.client.post(url, {"message": "а сейчас 150, на сколько вырос?"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        answer = self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
        self.assertIn("120 → 150", answer.content)
        self.assertIn("25%", answer.content)
        self.assertEqual((answer.provider, answer.model, answer.total_tokens), ("calculation", "user-metrics", 0))
        self.complete.assert_not_called()
        self.read.assert_not_called()

    def test_reference_chat_clarifies_without_user_values(self):
        AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.ASSISTANT,
                                 content="За прошлый месяц: клики: 120; за текущий месяц: клики: 150")
        other = AIConversation.objects.create(business=self.conversation.business, created_by=self.user)
        AIMessage.objects.create(conversation=other, role=AIMessage.Role.USER,
                                 content="За прошлый месяц: клики: 120; за текущий месяц: клики: 150")
        url = reverse("strategist:session", kwargs={"workspace_slug": "numeric", "business_slug": "shop",
                                                   "session_slug": self.conversation.slug})
        for question in ("сравни с теми цифрами", "а сейчас 150, на сколько вырос?"):
            response = self.client.post(url, {"message": question}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 200)
            # The first user question changes the session slug; follow its new URL.
            url = response.json()["conversation_url"]
            answer = self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
            self.assertTrue(answer.content.startswith("Уточни"))
            self.assertEqual(answer.content.count("Уточни"), 1)
            self.assertEqual((answer.provider, answer.model, answer.total_tokens), ("calculation", "user-metrics", 0))
        self.complete.assert_not_called()
        self.read.assert_not_called()

    def test_reference_chat_compares_only_explicit_user_periods(self):
        for content in ("За прошлый месяц: клики: 120", "За текущий месяц: клики: 150"):
            AIMessage.objects.create(conversation=self.conversation, role=AIMessage.Role.USER, content=content)
        url = reverse("strategist:session", kwargs={"workspace_slug": "numeric", "business_slug": "shop",
                                                   "session_slug": self.conversation.slug})
        response = self.client.post(url, {"message": "сравни с теми цифрами"},
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        answer = self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
        self.assertIn("120 → 150", answer.content)
        self.assertIn("25%", answer.content)
        self.assertEqual((answer.provider, answer.model, answer.total_tokens), ("calculation", "user-metrics", 0))
        self.complete.assert_not_called()
        self.read.assert_not_called()

    def test_all_six_questions_in_fresh_sessions_are_rendered(self):
        for question, expected in CASES + [
            ("Теперь: показы: 2000, клики: 20; раньше: показы: 1000, клики: 20", "2% → 1%"),
            ("Доля переходов упала с 10% до 5%. Что проверить?", "процентных пунктах: -5"),
            ("Теперь: показы: 2000, клики: 20; раньше: показы: 1000", "Уточни"),
        ]:
            with self.subTest(question=question):
                conversation = AIConversation.objects.create(business=self.conversation.business, created_by=self.user)
                url = reverse("strategist:session", kwargs={"workspace_slug": "numeric", "business_slug": "shop", "session_slug": conversation.slug})
                response = self.client.post(url, {"message": question}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertEqual(response.status_code, 200)
                answer = conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
                self.assertEqual((answer.provider, answer.model), ("calculation", "user-metrics"))
                self.assertEqual(answer.total_tokens, 0)
                self.assertIn(expected, answer.content)
                self.assertTrue(response.json()["messages_html"])
                self.assertIn(answer.content.split(".")[0], response.json()["messages_html"])
        self.complete.assert_not_called()
        self.read.assert_not_called()

    def test_clarification_then_formatted_reply_in_same_session(self):
        for question, expected in (
            ("Переходы: 20, 40. Что проверить?", "Уточни"),
            ("**Теперь:**\n- показы: 2000\n- клики: 20\n**Раньше:**\n- показы: 1000\n- клики: 20", "2% → 1%"),
        ):
            self.conversation.refresh_from_db()
            url = reverse("strategist:session", kwargs={"workspace_slug": "numeric", "business_slug": "shop", "session_slug": self.conversation.slug})
            response = self.client.post(url, {"message": question}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 200)
            answer = self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")
            self.assertIn(expected, answer.content)
            self.assertEqual((answer.provider, answer.model, answer.total_tokens), ("calculation", "user-metrics", 0))
        self.complete.assert_not_called()
        self.read.assert_not_called()
