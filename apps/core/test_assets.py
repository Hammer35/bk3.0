"""Versioned asset URLs and the generated CSS bundles stay in sync with their sources."""
import importlib.util
import tempfile
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.core.templatetags import assets


def load_builder():
    spec = importlib.util.spec_from_file_location("css_builder", Path(settings.BASE_DIR) / "scripts" / "build_css_bundles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AssetTagTest(SimpleTestCase):
    def test_version_follows_the_file_content(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(STATICFILES_DIRS=[directory]):
            assets._CACHE.clear()
            file = Path(directory) / "x.css"
            file.write_text("a { color: red }")
            first = assets.asset("x.css")
            self.assertRegex(first, r"^/static/x\.css\?v=[0-9a-f]{12}$")
            self.assertEqual(assets.asset("x.css"), first)  # stable while the file does not change
            file.write_text("a { color: blue }")
            self.assertNotEqual(assets.asset("x.css"), first)

    def test_missing_file_gives_the_plain_url(self):
        self.assertEqual(assets.asset("css/does-not-exist.css"), "/static/css/does-not-exist.css")

    def test_tag_renders_in_a_template(self):
        html = Template("{% load assets %}{% asset 'css/app.css' %}").render(Context({}))
        self.assertRegex(html, r"^/static/css/app\.css\?v=[0-9a-f]{12}$")


class PagesUseVersionedAssetsTest(TestCase):
    def test_base_and_landing_use_versioned_urls_for_styles_and_scripts(self):
        for url in (reverse("login"), "/"):
            html = self.client.get(url).content.decode()
            self.assertRegex(html, r'href="/static/css/(?:app|landing\.bundle)\.css\?v=[0-9a-f]{12}"', url)
            self.assertRegex(html, r'src="/static/js/core/theme\.js\?v=[0-9a-f]{12}"', url)


class BundlesInSyncTest(SimpleTestCase):
    def test_generated_bundles_match_their_sources(self):
        builder = load_builder()
        css = Path(settings.BASE_DIR) / "static" / "css"
        for output, sources in (("app.css", builder.APP_SOURCES), ("landing.bundle.css", builder.LANDING_SOURCES)):
            with self.subTest(bundle=output):
                self.assertEqual((css / output).read_text(encoding="utf-8"), builder.render(sources),
                                 f"{output} is stale: run python3 scripts/build_css_bundles.py and commit the result")
