"""Links in strategist replies preserve escaping and only support HTTP(S)."""
from django.test import SimpleTestCase

from .templatetags.strategist_format import strategist_reply


class LinkFormattingTest(SimpleTestCase):
    def test_https_link_in_numbered_list(self):
        html = strategist_reply("1. [Пин](https://www.pinterest.com/pin/12345/) — клики: 12.")
        self.assertIn('href="https://www.pinterest.com/pin/12345/"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn("<ol>", html)

    def test_active_protocols_do_not_become_links(self):
        for url in ("javascript:alert(1)", "data:text/html,test", "//example.com"):
            with self.subTest(url=url):
                self.assertNotIn("<a ", strategist_reply(f"[Ссылка]({url})"))

    def test_link_label_and_url_quotes_stay_escaped(self):
        html = strategist_reply('[<img src=x onerror=evil>](https://example.com/?q="test"&x=1)')
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)
        self.assertIn("&quot;test&quot;&amp;x=1", html)
