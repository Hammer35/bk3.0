"""Pin generation settings and the background job; the model is a stub, Celery is not involved."""
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.pinterest.models import PinterestAccount
from apps.strategist import pin_jobs as pj
from apps.strategist import pin_settings as ps
from apps.strategist.models import AIJob, Pin, PinVersion
from apps.strategist.providers import GigaChatProviderError
from apps.strategist.test_approvals import ApprovalBase
from apps.strategist.test_pin_generation import BAD, DISTINCT, completion


class SettingsTest(SimpleTestCase):
    def test_normalize_keeps_only_allowed_values(self):
        out = ps.normalize({"tone": "friendly", "cta": "evil", "length": "short", "keyword_mode": "ru", "rewrite": False,
                            "instruction": "  дружелюбно \n и коротко ", "destination_url": " https://x.example/a ",
                            "forbidden_words": "дёшево, Дёшево ;акция\n  ", "boards": {"1": "Доска", "2": " "},
                            "account_id": "7", "product_facts": "x" * 5000})
        self.assertEqual((out["tone"], out["cta"], out["length"], out["keyword_mode"], out["rewrite"]), ("friendly", "none", "short", "ru", False))
        self.assertEqual(out["instruction"], "дружелюбно и коротко")
        self.assertEqual((out["destination_url"], out["forbidden_words"], out["boards"]), ("https://x.example/a", ["дёшево", "акция"], {"1": "Доска"}))
        self.assertIsNone(out["account_id"])  # only a real integer id is accepted
        self.assertEqual(len(out["product_facts"]), 1500)
        self.assertEqual(ps.normalize(None), ps.normalize({}))
        self.assertEqual(len(ps.normalize({"instruction": "я" * 900})["instruction"]), ps.MAX_INSTRUCTION)

    def test_words_are_bounded(self):
        self.assertEqual(len(ps.clean_words(",".join(f"w{i}" for i in range(50)))), ps.MAX_WORDS)
        self.assertEqual(len(ps.clean_words("я" * 100)[0]), ps.MAX_WORD_LENGTH)
        self.assertEqual(ps.clean_words(["a", "A", " ", "b"]), ["a", "b"])

    def test_utm_values_and_url_building(self):
        self.assertEqual(ps.clean_utm({"source": "pinterest", "medium": "bad value!", "campaign": "spring_26"}),
                         {"source": "pinterest", "medium": "", "campaign": "spring_26"})
        self.assertEqual(ps.build_url("https://shop.example/a?x=1&utm_source=old", {"source": "pinterest", "medium": "", "campaign": "c1"}),
                         "https://shop.example/a?x=1&utm_source=pinterest&utm_campaign=c1")
        self.assertEqual(ps.build_url("https://shop.example/a", {}), "https://shop.example/a")
        for base in ("javascript:alert(1)", "ftp://x/y", "", "https://"):
            self.assertEqual(ps.build_url(base, {"source": "p"}), base)

    def test_style_for_model_depends_on_keyword_availability(self):
        options = ps.normalize({"tone": "expert", "cta": "soft", "length": "short", "instruction": "без эмодзи", "forbidden_words": ["дёшево"]})
        with_ru = ps.style_for_model(options, "льняное платье")
        self.assertIn("экспертный", with_ru["tone"])
        self.assertEqual((with_ru["user_instruction"], with_ru["forbidden_words"]), ("без эмодзи", ["дёшево"]))
        self.assertEqual(ps.style_for_model(options, "")["keyword_mode"], ps.KEYWORD_MODES["en"])


class JobTest(ApprovalBase):
    def start(self, count=None, **options):
        ids = [i.pk for i in self.plan.items.order_by("position")][:count]
        return pj.start_job(self.business, self.owner, ids, options)

    def test_start_validates_the_run(self):
        with self.assertRaisesMessage(pj.JobError, "Выберите хотя бы один пункт"):
            pj.start_job(self.business, self.owner, [], {})
        with self.assertRaisesMessage(pj.JobError, "Выберите хотя бы один пункт"):
            pj.start_job(self.business, self.owner, [999999], {})
        with patch.object(ps, "MAX_ITEMS", 2), self.assertRaisesMessage(pj.JobError, "не больше 2 пинов"):
            self.start()
        with self.assertRaisesMessage(pj.JobError, "не подключён"):
            self.start(1, account_id=123456)
        job = self.start(2)
        self.assertEqual((job.status, job.total, job.created_by, len(job.params["item_ids"])), ("PENDING", 2, self.owner, 2))
        self.assertNotIn("product_facts", job.params["options"])
        with self.assertRaisesMessage(pj.JobError, "Генерация уже идёт"):
            self.start(1)

    def test_items_with_pins_are_not_offered_again_except_rework(self):
        done = self.make_pins(1)[0]
        ids = [i.pk for i in self.plan.items.all()]
        job = pj.start_job(self.business, self.owner, ids, {})
        self.assertNotIn(done.plan_item_id, job.params["item_ids"])
        AIJob.objects.all().delete()
        Pin.objects.filter(pk=done.pk).update(status=Pin.Status.REWORK)
        self.assertIn(done.plan_item_id, pj.start_job(self.business, self.owner, ids, {}).params["item_ids"])

    def test_run_creates_pins_with_the_chosen_settings(self):
        item = self.plan.items.order_by("position").first()
        account = PinterestAccount.objects.create(
            business=self.business, connected_by=self.owner, username="alpha", pinterest_user_id="a",
            access_token_encrypted="x", access_token_expires_at="2030-01-01T00:00:00Z", granted_scopes=[], status="CONNECTED")
        job = pj.start_job(self.business, self.owner, [item.pk], {
            "tone": "expert", "destination_url": "https://shop.example.com/new", "utm": {"source": "pinterest", "campaign": "may"},
            "boards": {str(item.pk): "Чужая доска"}, "account_id": account.pk, "instruction": "Коротко"})
        result = pj.run_job(job.pk, provider=self.provider)
        self.assertEqual((result.status, result.done, result.failed), ("COMPLETED", 1, 0))
        version = PinVersion.objects.get()
        self.assertEqual(version.destination_url, "https://shop.example.com/new?utm_source=pinterest&utm_campaign=may")
        self.assertEqual(version.board, "Чужая доска")
        self.assertEqual(next(c["status"] for c in version.checks if c["id"] == "strategy_match"), "review")
        self.assertEqual(version.generation["settings"]["tone"], "expert")
        self.assertEqual(version.generation["settings"]["account_id"], account.pk)
        request = self.requests[0]
        self.assertEqual((request["item"]["board"], request["style"]["user_instruction"]), ("Чужая доска", "Коротко"))
        self.assertIn("экспертный", request["style"]["tone"])

    def test_forbidden_words_are_enforced_by_a_check(self):
        self.queue = [{**DISTINCT[0], "description": "Ткань дышит и приятна в жару, берите дёшево."}] * 2
        job = self.start(1, forbidden_words=["дёшево"])
        pj.run_job(job.pk, provider=self.provider)
        version = PinVersion.objects.get()
        self.assertEqual(version.verdict, "BLOCK")
        self.assertTrue(any(c["id"] == "strategy_match" and "дёшево" in c["message"] for c in version.checks))
        self.assertEqual(version.generation["attempts"], 2)
        self.assertEqual(self.requests[0]["style"]["forbidden_words"], ["дёшево"])

    def test_rewrite_off_means_no_second_attempt(self):
        self.queue = [BAD, BAD]
        pj.run_job(self.start(1, rewrite=False).pk, provider=self.provider)
        self.assertEqual((PinVersion.objects.get().generation["attempts"], len(self.requests)), (1, 1))

    def test_product_card_facts_reach_the_checks_and_the_prompt(self):
        self.queue = [{**DISTINCT[0], "description": "Платье длиной 90 см из льна."}]
        job = self.start(1, product_url="https://www.wildberries.ru/catalog/123456/detail.aspx")
        with patch.object(pj, "_product_facts", return_value=("Платье льняное, длина 90 см", "")):
            pj.run_job(job.pk, provider=self.provider)
        version = PinVersion.objects.get()
        self.assertEqual(next(c["status"] for c in version.checks if c["id"] == "product_source"), "pass")
        self.assertEqual(next(c["status"] for c in version.checks if c["id"] == "claims"), "pass")
        self.assertEqual(self.requests[0]["product_facts"], "Платье льняное, длина 90 см")
        self.assertTrue(version.generation["settings"]["product_checked"])

    def test_unreadable_product_card_adds_a_note_and_does_not_stop_the_run(self):
        job = self.start(1, product_url="not a link")
        result = pj.run_job(job.pk, provider=self.provider)
        self.assertEqual((result.status, result.done), ("COMPLETED", 1))
        self.assertTrue(any("не распознана" in n for n in result.notes))

    def test_run_is_idempotent_and_cancel_works(self):
        job = self.start(2)
        pj.run_job(job.pk, provider=self.provider)
        calls = len(self.requests)
        self.assertEqual(pj.run_job(job.pk, provider=self.provider).status, "COMPLETED")
        self.assertEqual(len(self.requests), calls)
        from apps.strategist.pin_generation import pending_items
        pending = pj.start_job(self.business, self.owner, [pending_items(self.plan)[0].pk], {})  # a finished job no longer blocks a new one
        pj.request_cancel(pending)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "CANCELLED")
        self.assertIsNone(pj.run_job(pending.pk, provider=self.provider).started_at)

    def test_cancel_during_run_stops_after_the_current_pin(self):
        job = self.start(3)

        def complete(messages, **kwargs):
            self.requests.append(json.loads(messages[1]["content"]))
            pj.request_cancel(AIJob.objects.get(pk=job.pk))  # the user presses "cancel" while the first pin is written
            return completion(DISTINCT[len(self.requests) % len(DISTINCT)])
        result = pj.run_job(job.pk, provider=type("P", (), {"complete": staticmethod(complete)})())
        self.assertEqual((result.status, result.done, Pin.objects.count()), ("CANCELLED", 1, 1))

    def test_failures_are_reported_with_fixed_sentences_only(self):
        self.queue = ["не json", DISTINCT[1]]  # garbage is not retried: only a blocking verdict is
        result = pj.run_job(self.start(2).pk, provider=self.provider)
        self.assertEqual((result.status, result.done, result.failed), ("COMPLETED", 1, 1))
        self.assertTrue(result.notes[0].startswith("Не получилось собрать надёжный текст для пункта"))

        def boom(messages, **kwargs):
            raise RuntimeError("secret-token-leak 12345")
        AIJob.objects.all().delete()
        failed = pj.run_job(self.start(1).pk, provider=type("P", (), {"complete": staticmethod(boom)})())
        self.assertEqual((failed.status, failed.failed), ("FAILED", 1))
        self.assertNotIn("secret-token-leak", json.dumps(failed.notes, ensure_ascii=False))

    def test_unavailable_model_aborts_the_rest_with_a_clear_note(self):
        def down(messages, **kwargs):
            raise GigaChatProviderError("provider is down")
        result = pj.run_job(self.start(3).pk, provider=type("P", (), {"complete": staticmethod(down)})())
        self.assertEqual((result.status, result.failed, Pin.objects.count()), ("FAILED", 1, 0))
        self.assertIn("Модель сейчас недоступна", result.notes[0])

    def test_celery_task_delegates_to_the_runner(self):
        from apps.strategist.tasks import run_pin_generation
        job = self.start(1)
        with patch("apps.strategist.pin_generation.GigaChatProvider.complete", side_effect=lambda m, **k: completion(DISTINCT[0])):
            run_pin_generation.run(job.pk)
        job.refresh_from_db()
        self.assertEqual((job.status, job.done), ("COMPLETED", 1))
