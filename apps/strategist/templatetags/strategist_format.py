"""Safe, limited formatting for stored strategist replies."""

import re
from html import escape

from django import template
from django.utils.safestring import mark_safe


register = template.Library()


def _inline(value: str) -> str:
    safe = escape(value)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(
        r"\[([^\[\]\n]+)\]\((https?://[^\s<>()]+)\)",
        lambda match: (
            f'<a href="{match.group(2)}" target="_blank" rel="noopener noreferrer">'
            f'{match.group(1)}</a>'
        ),
        safe,
    )
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
    list_start_number = 1
    next_ordered_number = None

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag, list_start_number, next_ordered_number
        if list_items:
            start_attribute = (
                f' start="{list_start_number}"'
                if list_tag == "ol" and list_start_number > 1
                else ""
            )
            blocks.append(
                f"<{list_tag}{start_attribute}>"
                + "".join(f"<li>{_inline(item)}</li>" for item in list_items)
                + f"</{list_tag}>"
            )
            if list_tag == "ol":
                next_ordered_number = list_start_number + len(list_items)
            list_items.clear()
            list_tag = ""
            list_start_number = 1

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        if line == "---":
            flush_paragraph()
            flush_list()
            next_ordered_number = None
            blocks.append("<hr>")
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            next_ordered_number = None
            blocks.append(f"<h3>{_inline(heading.group(1))}</h3>")
            continue
        bullet = re.match(r"^[-*•]\s+(.+)$", line)
        numbered = re.match(r"^(\d+)[.)]\s+(.+)$", line)
        if bullet or numbered:
            flush_paragraph()
            target_tag = "ul" if bullet else "ol"
            if list_tag and list_tag != target_tag:
                flush_list()
            if not list_tag:
                list_tag = target_tag
                if numbered:
                    list_start_number = int(numbered.group(1))
                    if list_start_number == 1 and next_ordered_number is not None:
                        list_start_number = next_ordered_number
            list_items.append(bullet.group(1) if bullet else numbered.group(2))
            continue
        if list_items:
            list_items[-1] += " " + line
            continue
        flush_list()
        next_ordered_number = None
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    return mark_safe("".join(blocks))


@register.filter(name="provenance_lines")
def provenance_lines(manifest) -> list[str]:
    """Readable lines for the sources a reply was built from."""
    from apps.strategist.provenance import describe
    return describe(manifest)


@register.filter(name="get_item")
def get_item(mapping, key):
    """Template access to a dict value by a variable key."""
    return mapping.get(key, {}) if isinstance(mapping, dict) else {}


@register.filter(name="json_attr")
def json_attr(value) -> str:
    """JSON for a data-attribute (HTML-escaped by the template engine): data only, no inline script."""
    import json
    return json.dumps(value, ensure_ascii=False)
