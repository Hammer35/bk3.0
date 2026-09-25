from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.workspaces.models import Membership, Workspace

from .models import Business


class BusinessCreationTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user("owner", password="password-123")
        self.viewer = user_model.objects.create_user("viewer", password="password-123")
        self.outsider = user_model.objects.create_user("outsider", password="password-123")
        self.workspace = Workspace.objects.create(name="Owner space", slug="owner-space", created_by=self.owner)
        Membership.objects.create(workspace=self.workspace, user=self.owner, role=Membership.Role.OWNER)
        Membership.objects.create(workspace=self.workspace, user=self.viewer, role=Membership.Role.VIEWER)

    def test_owner_can_create_business(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("businesses:create", kwargs={"workspace_slug": self.workspace.slug}),
            {"name": "Owner business", "website": "", "niche": "", "market": ""},
        )

        self.assertRedirects(response, reverse("core:home"))
        self.assertTrue(Business.objects.filter(workspace=self.workspace, name="Owner business").exists())

    def test_viewer_cannot_create_business(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("businesses:create", kwargs={"workspace_slug": self.workspace.slug}))

        self.assertEqual(response.status_code, 404)

    def test_user_outside_workspace_cannot_create_business(self):
        self.client.force_login(self.outsider)

        response = self.client.get(reverse("businesses:create", kwargs={"workspace_slug": self.workspace.slug}))

        self.assertEqual(response.status_code, 404)
