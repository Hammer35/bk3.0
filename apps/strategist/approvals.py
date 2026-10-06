"""User decisions on pin versions. The only code path that creates an Approval is a web action by a person
with edit rights; there is deliberately no chat command and no model involvement."""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_noop

from . import memory
from .models import Approval, Pin

ACTIONS = {"approve": Approval.Decision.APPROVED, "reject": Approval.Decision.REJECTED, "rework": Approval.Decision.REWORK}
STATUS_AFTER = {Approval.Decision.APPROVED: Pin.Status.APPROVED, Approval.Decision.REJECTED: Pin.Status.REJECTED,
                Approval.Decision.REWORK: Pin.Status.REWORK}
DECISION_TEXT = {Approval.Decision.APPROVED: "Одобрен пин", Approval.Decision.REJECTED: "Отклонён пин",
                 Approval.Decision.REWORK: "Пин отправлен на переделку"}


class ApprovalError(Exception):
    """Safe-to-show reason a decision was refused (marked for translation, shown by the view)."""


@transaction.atomic
def decide(pin: Pin, user, *, action: str, version_number: int, comment: str = "", acknowledged: bool = False) -> Approval:
    if action not in ACTIONS:
        raise ApprovalError(gettext_noop("Неизвестное действие."))
    pin = Pin.objects.select_for_update().get(pk=pin.pk)  # no select_related: FOR UPDATE cannot lock the nullable side of a join
    version = pin.current_version
    if version is None or version.number != version_number:
        raise ApprovalError(gettext_noop("Версия пина изменилась. Обновите страницу и проверьте новую версию."))
    decision = ACTIONS[action]
    if decision == Approval.Decision.APPROVED and version.verdict == "BLOCK":
        raise ApprovalError(gettext_noop("Пин заблокирован проверкой: одобрить его нельзя, отправьте на переделку или отклоните."))
    if pin.status != Pin.Status.WAITING_APPROVAL and not (pin.status == Pin.Status.REWORK and action != "approve"):
        raise ApprovalError(gettext_noop("По этой версии пина решение уже принято."))
    if hasattr(version, "approval"):
        raise ApprovalError(gettext_noop("По этой версии пина решение уже принято."))
    if decision == Approval.Decision.APPROVED:
        if not acknowledged:
            raise ApprovalError(gettext_noop("Подтвердите, что вы прочитали замечания и знаете, какие проверки не выполнены."))
    comment = " ".join(comment.split())[:300]
    noted = [c["id"] for c in version.checks if c["status"] in ("review", "not_checked")] if decision == Approval.Decision.APPROVED else []
    approval = Approval.objects.create(
        pin_version=version, decision=decision, decided_by=user, decided_at=timezone.now(), channel="WEB",
        comment=comment, acknowledged_checks=noted)
    pin.status = STATUS_AFTER[decision]
    pin.save(update_fields=["status", "updated_at"])
    memory.record_decision(pin.business, user, f"{DECISION_TEXT[decision]}: {version.title[:120]} (версия {version.number})",
                           reason=comment, source_ref=f"pin_version:{version.pk}")
    return approval
