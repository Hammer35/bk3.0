"""ArkSim adapter for the real Strategist service in an isolated test database."""

from __future__ import annotations

import uuid

from asgiref.sync import sync_to_async
from arksim.config import AgentConfig
from arksim.simulation_engine.agent.base import BaseAgent


class StrategistAgent(BaseAgent):
    def __init__(self, agent_config: AgentConfig) -> None:
        super().__init__(agent_config)
        self.chat_id = uuid.uuid4().hex
        self.conversation_id = None

    async def get_chat_id(self) -> str:
        return self.chat_id

    async def execute(self, user_query: str, **kwargs: object) -> str:
        return await sync_to_async(self._respond, thread_sensitive=True)(user_query)

    def _respond(self, user_query: str) -> str:
        from django.contrib.auth import get_user_model

        from apps.businesses.models import Business
        from apps.strategist.models import AIConversation, AIMessage
        from apps.strategist.services import respond_to_message
        from apps.workspaces.models import Workspace

        if self.conversation_id is None:
            user, _ = get_user_model().objects.get_or_create(username="strategist-eval")
            workspace, _ = Workspace.objects.get_or_create(
                slug="strategist-eval", defaults={"name": "Strategist Eval", "created_by": user}
            )
            business, _ = Business.objects.get_or_create(
                workspace=workspace,
                slug="ceramics-shop",
                defaults={
                    "name": "Тестовая мастерская керамики",
                    "niche": "керамика ручной работы",
                    "market": "Россия",
                    "audience": "покупатели подарков и декора",
                },
            )
            self.conversation_id = AIConversation.objects.create(
                business=business, created_by=user, title="ArkSim evaluation"
            ).pk

        message = AIMessage.objects.create(
            conversation_id=self.conversation_id,
            role=AIMessage.Role.USER,
            content=user_query,
        )
        return respond_to_message(user_message=message).content
