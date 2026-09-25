from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


class RegistrationTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_registration_creates_and_authenticates_user(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new-user",
                "email": "new-user@example.com",
                "password1": "Str0ng-password-123",
                "password2": "Str0ng-password-123",
            },
        )

        self.assertRedirects(response, reverse("workspaces:onboarding"))
        self.assertTrue(get_user_model().objects.filter(username="new-user").exists())
        self.assertEqual(self.client.session["_auth_user_id"], str(get_user_model().objects.get(username="new-user").pk))

    def test_registration_is_rate_limited(self):
        for _ in range(3):
            response = self.client.post(reverse("accounts:register"), {})
            self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse("accounts:register"), {})

        self.assertEqual(response.status_code, 429)
