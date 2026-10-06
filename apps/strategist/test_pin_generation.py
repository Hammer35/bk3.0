"""Pin drafts from a confirmed content plan: generation, one retry, verdicts; the model is a stub."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.businesses.models import Business
from apps.strategist import content_plan as cp
from apps.strategist import pin_generation as pg
from apps.strategist import strategy as st
from apps.strategist.models import AIConversation, AIMessage, ContentPlan, Pin, PinVersion
from apps.workspaces.models import Membership, Workspace

STRATEGY = {"goals": ["Трафик"], "content_directions": ["Образы с платьями", "Гайды по уходу"],
            "recommended_boards": [{"name": "Льняные платья", "purpose": ""}],
            "keyword_clusters": [{"name": "Лён", "keywords": ["linen dress"]}]}
ITEMS = {"items": [
    {"target_week": w, "direction": "Образы с платьями", "board": "Льняные платья", "keyword": "linen dress", "idea": f"Идея {w} про льняное платье"}
    for w in (1, 2, 3, 4)] + [{"target_week": 4, "direction": "Гайды по уходу", "idea": "Как стирать лён"}]}
GOOD = {"title": "Как носить льняное платье летом", "description": "Три образа с льняным платьем для офиса, прогулки и отпуска. Ткань дышит и приятна в жару.",
        "alt_text": "Женщина в бежевом льняном платье на летней улице"}
DISTINCT = [
    {"title": "Как носить льняное платье летом", "description": "Три образа для офиса, прогулки и отпуска. Ткань дышит и приятна в жару.", "alt_text": "Женщина в бежевом льняном платье на летней улице"},
    {"title": "С чем сочетать льняной костюм", "description": "Сандалии, соломенная сумка и лёгкий шарф дополняют образ. Показываем сочетания по цветам.", "alt_text": "Светлый льняной костюм на вешалке рядом с сумкой"},
    {"title": "Уход за льном: стирка без усадки", "description": "Стирайте в прохладной воде и сушите на плечиках. Так изделие дольше сохраняет форму.", "alt_text": "Льняная блузка сушится на плечиках у окна"},
    {"title": "Льняное платье на выпускной вечер", "description": "Простой силуэт и мягкая ткань подойдут для праздника на открытом воздухе.", "alt_text": "Девушка в длинном платье из льна у реки"},
    {"title": "Три способа сложить лён в чемодан", "description": "Рулоны вместо стопок и мягкие прокладки между слоями помогают беречь складки.", "alt_text": "Открытый чемодан с аккуратно сложенной одеждой"},
    {"title": "Цвета натурального льна", "description": "Молочный, песочный и оливковый оттенки легко сочетаются между собой.", "alt_text": "Палитра тканей молочного песочного и оливкового цветов"},
]
BAD = {"title": "Лучшее платье", "description": "Гарантируем 100% результат для вашего образа.", "alt_text": "платье"}


def completion(payload):
    return SimpleNamespace(content=payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False), model="stub",
                           prompt_tokens=1, completion_tokens=1, total_tokens=10, function_call=None, functions_state_id=None)


class PinGenerationTest(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("pin-owner")
        self.workspace = Workspace.objects.create(name="P", slug="p", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        self.business = Business.objects.create(workspace=self.workspace, name="Shop", slug="shop", niche="Льняная одежда",
                                                audience="Женщины", goals="Трафик", website="https://shop.example.com/catalog")
        self.version = st.confirm_version(st.create_draft(
            self.business, self.owner, st.clean_payload(STRATEGY, allowed_refs=set(), allowed_keywords=None), sources=[]), self.owner)
        self.plan = cp.confirm_plan(cp.create_plan(self.business, self.owner, self.version, cp.clean_items(ITEMS, self.version)), self.owner)
        self.conversation = AIConversation.objects.create(business=self.business, created_by=self.owner)
        self.client.force_login(self.owner)
        self.url = reverse("strategist:session", kwargs={"workspace_slug": "p", "business_slug": "shop", "session_slug": self.conversation.slug})
        self.requests = []
        self.queue = []

        def fake(_provider, messages, **kwargs):
            self.requests.append(json.loads(messages[1]["content"]))
            if self.queue:
                return completion(self.queue.pop(0))
            return completion(DISTINCT[(len(self.requests) - 1) % len(DISTINCT)])
        self.enterContext(patch("apps.strategist.providers.GigaChatProvider.complete", fake))

    def say(self, text):
        response = self.client.post(self.url, {"message": text}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.url = response.json()["conversation_url"]
        return self.conversation.messages.filter(role=AIMessage.Role.ASSISTANT).latest("created_at")

    def test_batch_is_capped_validated_and_never_published(self):
        answer = self.say("Создай пины по контент-плану")
        self.assertEqual((answer.provider, answer.total_tokens, answer.prompt_version), ("pins", 30, "pin-2026-10-06.3"))
        self.assertEqual(Pin.objects.count(), pg.BATCH)
        self.assertIn("Осталось пунктов плана без пинов: 2", answer.content)
        self.assertIn("не одобрение Pinterest", answer.content)
        self.assertIn("я их не запускаю и ничего не публикую", answer.content)
        for pin in Pin.objects.all():
            self.assertIn(pin.status, (Pin.Status.WAITING_APPROVAL, Pin.Status.REWORK))
            version = pin.current_version
            self.assertEqual((version.number, version.created_by, version.destination_url), (1, self.owner, "https://shop.example.com/catalog"))
            self.assertEqual(len(version.checks), 12)
            self.assertIn("url_reachable", version.open_checks)
            self.assertEqual(version.generation["prompt_version"], "pin-2026-10-06.3")
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(self.requests[0]["item"]["keyword"], "linen dress")
        again = self.say("Создай пины по контент-плану")
        self.assertEqual(Pin.objects.count(), 5)
        self.assertNotIn("Осталось пунктов", again.content)
        self.assertIn("уже созданы", self.say("Создай пины по контент-плану").content)

    def test_blocked_first_attempt_is_retried_once_with_the_reasons(self):
        self.queue = [BAD, GOOD]
        answer = self.say("Создай пины по контент-плану")
        version = PinVersion.objects.order_by("pin__plan_item__position").first()
        self.assertEqual(version.generation["attempts"], 2)
        self.assertTrue(any("Обещание результата" in m for m in version.generation["first_attempt_blocked"]))
        self.assertTrue(any("Обещание результата" in m for m in self.requests[1]["feedback"]))
        self.assertEqual(self.requests[0]["feedback"], [])
        self.assertNotEqual(version.verdict, "BLOCK")
        self.assertIn("Первый вариант заблокирован проверкой, текст переписан один раз", answer.content)

    def test_two_blocked_attempts_end_in_rework_and_the_text_is_kept(self):
        self.queue = [BAD, BAD]
        answer = self.say("Создай пины по контент-плану")
        pin = Pin.objects.get(plan_item__position=1)
        self.assertEqual((pin.status, pin.current_version.verdict, pin.current_version.generation["attempts"]), (Pin.Status.REWORK, "BLOCK", 2))
        self.assertIn("заблокирован проверкой", answer.content)
        self.assertIn("[блок] Обещание результата", answer.content)
        self.assertEqual(len(self.requests), 2 + 1 + 1)  # 2 attempts for the first item, one each for the other two

    def test_identical_text_for_two_items_is_a_duplicate(self):
        self.queue = [GOOD, GOOD, GOOD, GOOD]
        self.say("Создай пины по контент-плану")
        second = Pin.objects.get(plan_item__position=2).current_version
        self.assertEqual(second.verdict, "BLOCK")
        self.assertTrue(any(c["id"] == "duplicates" and c["status"] == "block" for c in second.checks))

    def test_model_garbage_creates_no_pin(self):
        self.queue = ["не json"] * 3
        answer = self.say("Создай пины по контент-плану")
        self.assertIn("Не получилось собрать надёжный текст пина", answer.content)
        self.assertFalse(Pin.objects.exists())

    def test_html_is_stripped_and_limits_block(self):
        self.queue = [{"title": "<b>Заголовок</b> <script>x</script>", "description": "я " * 450, "alt_text": "Платье на плечиках в шкафу"}] * 2
        self.say("Создай пины по контент-плану")
        version = Pin.objects.get(plan_item__position=1).current_version
        self.assertNotIn("<", version.title)
        self.assertEqual(version.verdict, "BLOCK")
        self.assertTrue(any(c["id"] == "text_limits" and c["status"] == "block" for c in version.checks))

    def test_missing_website_needs_review_not_pass(self):
        self.business.website = ""
        self.business.save()
        self.say("Создай пины по контент-плану")
        version = Pin.objects.get(plan_item__position=1).current_version
        self.assertEqual(next(c["status"] for c in version.checks if c["id"] == "destination_url"), "review")

    def test_gates_plan_role_and_intent_collision(self):
        ContentPlan.objects.update(status="SUPERSEDED")
        self.assertIn("подтверждённому контент-плану", self.say("Создай пины по контент-плану").content)
        ContentPlan.objects.update(status="CONFIRMED")
        viewer = get_user_model().objects.create_user("pin-viewer")
        Membership.objects.create(workspace=self.workspace, user=viewer, role=Membership.Role.VIEWER)
        message = AIMessage.objects.create(conversation=self.conversation, role="USER", content="Создай пины по контент-плану")
        self.assertIn("владелец, администратор", pg.pin_reply(user_message=message, actor=viewer).content)
        self.assertEqual(Pin.objects.count(), 0)
        before = ContentPlan.objects.count()
        self.say("Создай пины по контент-плану")
        self.assertEqual(ContentPlan.objects.count(), before)  # not mistaken for "build a content plan"

    def test_show_command_does_not_hijack_other_pin_requests(self):
        for text in ("Покажи топ-5 пинов по кликам", "Покажи пины @alpha за 30 дней", "Какие пины лучше всего работают", "Покажи пины с лучшими показами"):
            with self.subTest(text=text):
                self.assertIsNone(pg.pin_reply(user_message=AIMessage.objects.create(
                    conversation=self.conversation, role="USER", content=text), actor=self.owner))
        for text in ("Покажи пины", "покажи черновики пинов", "Покажи мои пины.", "что с черновиками пинов?"):
            with self.subTest(text=text):
                self.assertIsNotNone(pg.pin_reply(user_message=AIMessage.objects.create(
                    conversation=self.conversation, role="USER", content=text), actor=self.owner))

    def test_show_lists_pins_and_empty_state(self):
        self.assertIn("Пинов пока нет", self.say("Покажи пины").content)
        self.say("Создай пины по контент-плану")
        shown = self.say("Покажи пины").content
        self.assertIn("Пины этого бизнеса:", shown)
        self.assertEqual(shown.count("- неделя"), 3)

    @override_settings(PINTEREST_AI_DATA_TRANSFER_ENABLED=False)
    def test_keyword_phrases_are_not_sent_when_transfer_is_off(self):
        self.say("Создай пины по контент-плану")
        for request in self.requests:
            self.assertEqual((request["item"]["keyword"], request["item"]["keyword_ru"]), ("", ""))
        self.assertNotIn("linen dress", json.dumps(self.requests, ensure_ascii=False))

    def test_business_with_pins_can_be_deleted(self):
        self.say("Создай пины по контент-плану")
        self.business.delete()
        self.assertEqual((Pin.objects.count(), PinVersion.objects.count()), (0, 0))
