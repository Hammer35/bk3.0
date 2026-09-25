from dataclasses import dataclass
from enum import StrEnum


class TaskCapability(StrEnum):
    CHAT = "chat"
    FUNCTIONS = "functions"


@dataclass(frozen=True)
class GigaChatModelDefinition:
    identifier: str
    capabilities: frozenset[TaskCapability]

    def supports(self, capability: TaskCapability) -> bool:
        return capability in self.capabilities


_TEXT_AND_FUNCTIONS = frozenset({TaskCapability.CHAT, TaskCapability.FUNCTIONS})

# This intentionally lists only capabilities confirmed for the routing contract.
# Broader multimodal routing is added only after its request/response flow exists.
GIGACHAT_MODELS = {
    identifier: GigaChatModelDefinition(identifier=identifier, capabilities=_TEXT_AND_FUNCTIONS)
    for identifier in (
        "GigaChat-2",
        "GigaChat-2-Pro",
        "GigaChat-2-Max",
        "GigaChat-3-Lightning",
        "GigaChat-3-Pro",
        "GigaChat-3-Ultra",
    )
}
