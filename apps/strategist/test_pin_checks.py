"""Pin heavy validation: deterministic checks, verdict aggregation; no model, no network."""
from django.test import SimpleTestCase

from apps.strategist import pin_checks as pc
from apps.strategist.grounded_answers import pin_text_limits

CTX = dict(content_directions=["Образы с платьями"], boards=["Льняные платья"], keywords=["linen dress", "linen suit"],
           exclusions=["свадебн"], limits={"title": 100, "description": 800}, other_texts=[])
GOOD = {"title": "Как носить льняное платье летом", "description": "Три образа с льняным платьем: для офиса, прогулки и отпуска. Ткань дышит и не мнётся от одной поездки.",
        "alt_text": "Женщина в бежевом льняном платье на летней улице", "destination_url": "https://shop.example.com/linen-dress",
        "keyword": "linen dress", "board": "Льняные платья", "direction": "Образы с платьями"}
GOOD_TEXT_KEYWORD = {**GOOD, "description": GOOD["description"] + " Linen dress из натурального льна."}


def run(pin=None, **ctx):
    pin = {**GOOD_TEXT_KEYWORD, **(pin or {})}
    checks = pc.run_checks(pin, pc.CheckContext(**{**CTX, **ctx}))
    return {c["id"]: c for c in checks}


class ChecksTest(SimpleTestCase):
    def test_a_good_pin_passes_every_performed_check_and_lists_the_open_ones(self):
        checks = run()
        for check_id in ("text_present", "text_limits", "strategy_match", "keyword_use", "claims", "destination_url", "duplicates", "alt_text"):
            self.assertEqual(checks[check_id]["status"], pc.PASS, checks[check_id])
        verdict, open_checks = pc.verdict(list(checks.values()))
        self.assertEqual(verdict, "PASS")
        self.assertEqual(open_checks, ["product_source", "url_reachable", "account_history", "semantic_review"])

    def test_missing_data_is_not_checked_never_passed(self):
        self.assertEqual(run(limits={})["text_limits"]["status"], pc.NOT_CHECKED)
        self.assertEqual(run(product_facts="")["product_source"]["status"], pc.NOT_CHECKED)
        self.assertEqual(run(product_facts="Платье, длина 90 см")["product_source"]["status"], pc.PASS)

    def test_limits_and_empty_text(self):
        self.assertEqual(run({"title": "я" * 101})["text_limits"]["status"], pc.BLOCK)
        self.assertEqual(run({"description": "я" * 801})["text_limits"]["status"], pc.BLOCK)
        self.assertEqual(run({"title": "я" * 100, "description": "я " * 399})["text_limits"]["status"], pc.PASS)
        self.assertEqual(run({"title": "  "})["text_present"]["status"], pc.BLOCK)
        self.assertEqual(run({"description": ""})["text_present"]["status"], pc.REVIEW)

    def test_strategy_match(self):
        self.assertEqual(run({"direction": "Выдуманное"})["strategy_match"]["status"], pc.BLOCK)
        self.assertEqual(run({"title": "Свадебное платье изо льна"})["strategy_match"]["status"], pc.BLOCK)
        self.assertEqual(run({"board": ""})["strategy_match"]["status"], pc.REVIEW)
        self.assertEqual(run({"board": "Чужая доска"})["strategy_match"]["status"], pc.REVIEW)

    def test_keyword_use_and_stuffing(self):
        self.assertEqual(run({"keyword": ""})["keyword_use"]["status"], pc.REVIEW)
        self.assertEqual(run({"keyword": "unknown phrase"})["keyword_use"]["status"], pc.BLOCK)
        self.assertEqual(run({"description": "Красивое платье для отдыха.", "title": "Образ дня"})["keyword_use"]["status"], pc.REVIEW)
        listy = "льняное платье, льняной костюм, платье лето, платье офис, одежда лён, платье купить, linen dress"
        self.assertEqual(run({"description": listy})["keyword_use"]["status"], pc.BLOCK)
        repeated = "Linen dress лето лето лето лето и ещё раз лето для вас."
        self.assertEqual(run({"description": repeated})["keyword_use"]["status"], pc.BLOCK)

    def test_keyword_may_be_reflected_through_its_russian_equivalent(self):
        pin = {"title": "Как носить льняное платье", "description": "Три образа на лето для офиса и прогулки.", "alt_text": "Женщина в платье из льна"}
        self.assertEqual(run(pin)["keyword_use"]["status"], pc.REVIEW)
        self.assertEqual(run(pin, keyword_ru="льняное платье")["keyword_use"]["status"], pc.PASS)

    def test_claims(self):
        for text in ("Гарантируем рост продаж", "100% результат", "Товар №1 на рынке", "Без риска"):
            self.assertEqual(run({"description": text + " linen dress"})["claims"]["status"], pc.BLOCK, text)
        for text in ("Лучшее льняное платье", "Скидка на всё", "Бесплатная доставка", "Только сегодня", "Скидка 30%"):
            self.assertEqual(run({"description": text + " linen dress"})["claims"]["status"], pc.REVIEW, text)
        no_card = run({"description": "Длина 90 см, linen dress."})["claims"]
        self.assertEqual(no_card["status"], pc.REVIEW)
        self.assertIn("карточка товара не привязана", no_card["message"])
        self.assertEqual(run({"description": "Длина 90 см, linen dress."}, product_facts="Платье, длина 90 см")["claims"]["status"], pc.PASS)
        self.assertEqual(run({"description": "Длина 95 см, linen dress."}, product_facts="Платье, длина 90 см")["claims"]["status"], pc.REVIEW)

    def test_destination_url(self):
        cases = {"": pc.REVIEW, "ftp://x.com/a": pc.BLOCK, "https://": pc.BLOCK, "javascript:alert(1)": pc.BLOCK,
                 "https://bit.ly/abc": pc.BLOCK, "https://sub.t.co/x": pc.BLOCK, "https://pin.it/xyz": pc.BLOCK,
                 "https://user:pw@shop.example.com/": pc.BLOCK, "https://shop.example.com@evil.com/": pc.BLOCK,
                 "http://shop.example.com/a": pc.REVIEW, "https://shop.example.com/a?utm_source=pin": pc.PASS}
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(run({"destination_url": url})["destination_url"]["status"], expected)

    def test_duplicates(self):
        other = GOOD_TEXT_KEYWORD["title"] + "\n" + GOOD_TEXT_KEYWORD["description"]
        self.assertEqual(run(other_texts=[other])["duplicates"]["status"], pc.BLOCK)  # same title
        near = "Иной заголовок\n" + GOOD_TEXT_KEYWORD["description"]
        self.assertEqual(run(other_texts=[near])["duplicates"]["status"], pc.REVIEW if 0.6 <= pc.similarity(
            GOOD_TEXT_KEYWORD["title"] + " " + GOOD_TEXT_KEYWORD["description"], near.replace("\n", " ")) < 0.85 else pc.BLOCK)
        different = "Уход за кожей\nКрем для рук с маслом ши и пчелиным воском"
        self.assertEqual(run(other_texts=[different])["duplicates"]["status"], pc.PASS)
        self.assertEqual(pc.similarity("", "что-то"), 0.0)

    def test_alt_text(self):
        self.assertEqual(run({"alt_text": ""})["alt_text"]["status"], pc.REVIEW)
        self.assertEqual(run({"alt_text": "платье"})["alt_text"]["status"], pc.REVIEW)
        self.assertEqual(run({"alt_text": "платье, лён, лето, офис, купить, скидка"})["alt_text"]["status"], pc.REVIEW)

    def test_verdict_aggregation(self):
        self.assertEqual(pc.verdict([{"id": "a", "status": pc.PASS}, {"id": "b", "status": pc.NOT_CHECKED}]), ("PASS", ["b"]))
        self.assertEqual(pc.verdict([{"id": "a", "status": pc.REVIEW}, {"id": "b", "status": pc.PASS}])[0], "REVIEW")
        self.assertEqual(pc.verdict([{"id": "a", "status": pc.REVIEW}, {"id": "b", "status": pc.BLOCK}])[0], "BLOCK")

    def test_every_run_reports_all_twelve_checks_with_messages(self):
        checks = pc.run_checks(GOOD_TEXT_KEYWORD, pc.CheckContext(**CTX))
        self.assertEqual(len(checks), 12)
        self.assertEqual(len({c["id"] for c in checks}), 12)
        self.assertTrue(all(c["message"] and c["status"] in {pc.PASS, pc.REVIEW, pc.BLOCK, pc.NOT_CHECKED} for c in checks))


class LimitsSourceTest(SimpleTestCase):
    def test_limits_come_from_the_approved_source(self):
        from datetime import date
        from unittest.mock import patch
        with patch("apps.strategist.grounded_answers.timezone.localdate", return_value=date(2026, 10, 6)):  # source validity window
            self.assertEqual(pin_text_limits(), {"title": 100, "description": 800})
