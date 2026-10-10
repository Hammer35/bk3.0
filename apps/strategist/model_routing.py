from django.conf import settings

from .model_catalog import GIGACHAT_MODELS, TaskCapability


class GigaChatModelRouter:
    """Select a documented model that is available to the current API key."""

    def __init__(self, model_priority: tuple[str, ...] | None = None):
        self.model_priority = model_priority

    def candidates(
        self,
        *,
        capability: TaskCapability,
        available_model_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        available = set(available_model_ids)
        return tuple(
            model_id
            for model_id in (self.model_priority or settings.GIGACHAT_MODEL_PRIORITY)
            if model_id in GIGACHAT_MODELS
            and GIGACHAT_MODELS[model_id].supports(capability)
            and (not available or model_id in available)
        )
