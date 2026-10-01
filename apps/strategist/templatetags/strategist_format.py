"""Safe, limited formatting for stored strategist replies."""

import re
from html import escape

from django import template
from django.utils.safestring import mark_safe


register = template.Library()


def _inline(value: str) -> str:
    safe = escape(value)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    return safe.replace("**", "")


@register.filter(name="strategist_reply")
def strategist_reply(value: str) -> str:
    """Render headings, paragraphs and lists while escaping model-supplied HTML."""
    source = str(value or "")
    source = re.sub(r"\\([#*_-])", r"\1", source)
    source = re.sub(r"[ \t]+---[ \t]+", "\n---\n", source)
    blocks = []
    paragraph = []
    list_items = []
    list_tag = ""

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_items:
            blocks.append(f"<{list_tag}>" + "".join(f"<li>{_inline(item)}</li>" for item in list_items) + f"</{list_tag}>")
            list_items.clear()
            list_tag = ""

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        if line == "---":
            flush_paragraph()
            flush_list()
            blocks.append("<hr>")
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            blocks.append(f"<h3>{_inline(heading.group(1))}</h3>")
            continue
        bullet = re.match(r"^[-*•]\s+(.+)$", line)
        numbered = re.match(r"^\d+[.)]\s+(.+)$", line)
        if bullet or numbered:
            flush_paragraph()
            target_tag = "ul" if bullet else "ol"
            if list_tag and list_tag != target_tag:
                flush_list()
            list_tag = target_tag
            list_items.append((bullet or numbered).group(1))
            continue
        if list_items:
            list_items[-1] += " " + line
            continue
        flush_list()
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    return mark_safe("".join(blocks))
