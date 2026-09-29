"""User-triggered Pinterest reads and short-lived snapshots for the strategist."""

from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

from .strategist_tools import read_pinterest_data

SNAPSHOT_TTL_SECONDS = 60 * 60 * 24 * 7
SNAPSHOT_FRESH_SECONDS = 60 * 60 * 24
SYNC_LOCK_SECONDS = 300
SYNC_COOLDOWN_SECONDS = 30
MAX_BOARD_PAGES = 4


def snapshot_key(account):
    return f"pinterest:snapshot:{account.public_id}"


def sync_pinterest_account(*, account):
    """Read only profile, boards, and 30-day account analytics on explicit request."""
    lock_key = f"pinterest:sync-lock:{account.public_id}"
    cooldown_key = f"pinterest:sync-cooldown:{account.public_id}"
    if not cache.add(cooldown_key, "1", timeout=SYNC_COOLDOWN_SECONDS):
        return {"busy": True, "resources": {}}
    if not cache.add(lock_key, "1", timeout=SYNC_LOCK_SECONDS):
        return {"busy": True, "resources": {}}

    previous = cache.get(snapshot_key(account)) or {"data": {}, "resources": {}}
    data = dict(previous.get("data", {}))
    resources = dict(previous.get("resources", {}))
    now = timezone.now()
    account_key = str(account.public_id)

    def read(resource, *, options=None, bookmark=None):
        arguments = {
            "account_key": account_key,
            "resource": resource,
            "options": options or "{}",
            "page_size": 250,
        }
        if bookmark:
            arguments["bookmark"] = bookmark
        response = read_pinterest_data(business=account.business, arguments=arguments)
        if not isinstance(response, dict):
            return {"error": "Pinterest вернул ответ в неподдерживаемом формате."}
        return response

    if "user_accounts:read" in set(account.granted_scopes or []):
        profile = read("profile")
        _save_resource(data, resources, "profile", profile, now)

        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=29)
        analytics = read(
            "analytics",
            options={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "content_type": "ORGANIC",
            },
        )
        if not analytics.get("error"):
            analytics["period"] = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        _save_resource(data, resources, "analytics", analytics, now)
    else:
        resources["profile"] = {"error": "Нет scope user_accounts:read."}
        resources["analytics"] = {"error": "Нет scope user_accounts:read."}

    if "boards:read" in set(account.granted_scopes or []):
        boards = []
        bookmark = None
        board_error = None
        complete = False
        for _ in range(MAX_BOARD_PAGES):
            page = read("boards", bookmark=bookmark)
            if page.get("error"):
                board_error = page["error"]
                break
            page_items = page.get("items")
            if not isinstance(page_items, list):
                board_error = "Pinterest не вернул список досок."
                break
            boards.extend(page_items)
            bookmark = page.get("bookmark")
            if not bookmark:
                complete = True
                break
        if board_error:
            resources["boards"] = {"error": board_error}
        else:
            data["boards"] = {"items": boards, "complete": complete, "synced_at": now.isoformat()}
            resources["boards"] = {"ok": True, "complete": complete, "synced_at": now.isoformat()}
    else:
        resources["boards"] = {"error": "Нет scope boards:read."}

    synced = any(resource.get("ok") for resource in resources.values())
    cache.set(
        snapshot_key(account),
        {
            "data": data,
            "resources": resources,
            "synced_at": now.isoformat() if synced else previous.get("synced_at"),
            "last_attempt_at": now.isoformat(),
        },
        timeout=SNAPSHOT_TTL_SECONDS,
    )
    cache.delete(lock_key)
    return {"busy": False, "resources": resources, "synced": synced, "synced_at": now.isoformat()}


def _save_resource(data, resources, resource, response, synced_at):
    if response.get("error"):
        resources[resource] = {"error": response["error"]}
        return
    data[resource] = {"response": response, "synced_at": synced_at.isoformat()}
    resources[resource] = {"ok": True, "synced_at": synced_at.isoformat()}


def fresh_snapshot_resource(*, account, resource):
    snapshot = cache.get(snapshot_key(account)) or {}
    resource_state = snapshot.get("resources", {}).get(resource, {})
    if not resource_state.get("ok"):
        return None
    data = snapshot.get("data", {}).get(resource)
    if not data:
        return None
    try:
        synced_at = datetime.fromisoformat(data.get("synced_at", ""))
    except (TypeError, ValueError):
        return None
    if timezone.is_naive(synced_at):
        synced_at = timezone.make_aware(synced_at, timezone.get_current_timezone())
    if timezone.now() - synced_at > timedelta(seconds=SNAPSHOT_FRESH_SECONDS):
        return None
    if resource == "boards" and not data.get("complete"):
        return None
    return data
