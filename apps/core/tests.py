from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import Business
from apps.workspaces.models import Membership, Workspace


class LiveHealthTest(TestCase):
    def test_live_health_is_ok(self):
        response = self.client.get(reverse("core:health-live"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class PublicLandingTest(TestCase):
    def test_root_is_public_landing(self):
        response = self.client.get(reverse("core:landing"))

        self.assertContains(response, "Каталог")
        self.assertContains(response, "Попробовать бесплатно")
        self.assertNotContains(response, "Рабочие пространства")
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "js/core/theme.js")


class DashboardAccessTest(TestCase):
    def test_dashboard_does_not_show_businesses_from_other_workspaces(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user("owner", password="password-123")
        outsider = user_model.objects.create_user("outsider", password="password-123")
        owner_workspace = Workspace.objects.create(name="Owner space", slug="owner-space", created_by=owner)
        outsider_workspace = Workspace.objects.create(name="Outsider space", slug="outsider-space", created_by=outsider)
        Membership.objects.create(workspace=owner_workspace, user=owner, role=Membership.Role.OWNER)
        Membership.objects.create(workspace=outsider_workspace, user=outsider, role=Membership.Role.OWNER)
        Business.objects.create(workspace=owner_workspace, name="Visible business", slug="visible-business")
        Business.objects.create(workspace=outsider_workspace, name="Hidden business", slug="hidden-business")
        self.client.force_login(owner)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "Visible business")
        self.assertNotContains(response, "Hidden business")
        self.assertContains(response, 'class="button button-primary" href="/strategist/')
        self.assertContains(response, 'href="/" class="brand"')
        self.assertContains(response, "data-theme-toggle")
