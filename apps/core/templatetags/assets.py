"""Static asset URLs with a version taken from the file content, so browsers never reuse a stale stylesheet or script."""
import hashlib
from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()
_CACHE: dict[str, tuple[tuple[int, int], str]] = {}


def _version(path: str) -> str:
    """Short content hash; recomputed only when the file's mtime or size changes."""
    found = finders.find(path)
    if not found:
        return ""
    file = Path(found)
    stat = file.stat()
    signature = (stat.st_mtime_ns, stat.st_size)
    cached = _CACHE.get(path)
    if cached and cached[0] == signature:
        return cached[1]
    digest = hashlib.sha256(file.read_bytes()).hexdigest()[:12]
    _CACHE[path] = (signature, digest)
    return digest


@register.simple_tag
def asset(path: str) -> str:
    """{% asset 'css/app.css' %} -> /static/css/app.css?v=<hash>"""
    url = static(path)
    version = _version(path)
    return f"{url}?v={version}" if version else url
