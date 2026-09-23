from django.test import TestCase
from django.urls import reverse


class LiveHealthTest(TestCase):
    def test_live_health_is_ok(self):
        response = self.client.get(reverse("core:health-live"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
