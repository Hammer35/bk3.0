from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import Business

from .models import Membership, Workspace


class OnboardingTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("owner", password="password-123")

    def test_onboarding_creates_workspace_owner_membership_and_business(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("workspaces:onboarding"),
            {
                "workspace_name": "Studio North",
                "business_name": "North Shop",
                "website": "https://example.com",
                "niche": "Home decor",
                "market": "RU",
            },
        )

        self.assertRedirects(response, reverse("core:home"))
        workspace = Workspace.objects.get(name="Studio North")
        self.assertEqual(workspace.created_by, self.user)
        self.assertEqual(
            Membership.objects.get(workspace=workspace, user=self.user).role,
            Membership.Role.OWNER,
        )
        self.assertTrue(Business.objects.filter(workspace=workspace, name="North Shop").exists())

    def test_onboarding_requires_authentication(self):
        response = self.client.get(reverse("workspaces:onboarding"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('workspaces:onboarding')}")

    def test_onboarding_explains_every_profile_field(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("workspaces:onboarding"))

        self.assertContains(response, 'class="field-help"', count=8)
        self.assertContains(response, "женская одежда")
        self.assertContains(response, "больше переходов на сайт")
