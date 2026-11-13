"""Extract, check and compile UI translations without GNU gettext.

    python scripts/i18n.py extract   # rewrite locale/en/LC_MESSAGES/django.po from templates and Python
    python scripts/i18n.py compile   # build django.mo from django.po
    python scripts/i18n.py check     # non-zero exit if the catalog is stale, incomplete or broken

Source language is Russian; msgids are the Russian strings. Pure Python, no Django needed.
"""
import ast
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale" / "en" / "LC_MESSAGES"
PO, MO = LOCALE / "django.po", LOCALE / "django.mo"
PY_CALLS = {"_", "gettext", "gettext_lazy", "gettext_noop"}
PY_ROOTS = ("apps", "config")
HEADER = {
    "Project-Id-Version": "BOOSTKLIENT 3.0", "Language": "en",
    "MIME-Version": "1.0", "Content-Type": "text/plain; charset=UTF-8",
    "Content-Transfer-Encoding": "8bit", "Plural-Forms": "nplurals=2; plural=(n != 1);",
}
_TRANS = re.compile(r"^(?:trans|translate)\s+(?P<q>[\"'])(?P<s>.*?)(?P=q)")
_UNDERSCORE = re.compile(r"""\b_\(\s*(?P<q>["'])(?P<s>.*?)(?P=q)\s*\)""")
_PLACEHOLDER = re.compile(r"%\((\w+)\)s")
_TAG = re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})", re.S)  # same split Django's template Lexer uses


def _tokens(source: str):
    """Yield (kind, contents) with kind in TEXT/BLOCK/VAR; comments are skipped."""
    for part in _TAG.split(source):
        if part.startswith("{%"):
            yield "BLOCK", part[2:-2].strip()
        elif part.startswith("{{"):
            yield "VAR", part[2:-2].strip()
        elif part and not part.startswith("{#"):
            yield "TEXT", part


def _template_messages() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "templates").rglob("*.html")):
        rel, source = str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")
        block = None  # (options, parts) while inside blocktrans
        for kind, text in _tokens(source):
            if block is not None:
                if kind == "BLOCK" and text.split()[0] in ("endblocktrans", "endblocktranslate"):
                    msgid = "".join(block[1])
                    if "trimmed" in block[0].split():
                        msgid = re.sub(r"\s*\n\s*", " ", msgid).strip()
                    found.setdefault(msgid, []).append(rel)
                    block = None
                elif kind == "TEXT":
                    block[1].append(text.replace("%", "%%"))
                elif kind == "VAR":
                    block[1].append(f"%({text})s")
                continue
            if kind == "BLOCK":
                head = text.split()[0]
                if head in ("blocktrans", "blocktranslate"):
                    if re.search(r"\b(plural|count)\b", text):
                        raise SystemExit(f"{rel}: plural blocktrans is not supported by scripts/i18n.py")
                    block = (text, [])
                    continue
                match = _TRANS.match(text)
                if match:
                    found.setdefault(match["s"], []).append(rel)
            if kind in ("BLOCK", "VAR"):
                for match in _UNDERSCORE.finditer(text):
                    found.setdefault(match["s"], []).append(rel)
    return found


def _python_messages() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for root in PY_ROOTS:
        for path in sorted((ROOT / root).rglob("*.py")):
            if "migrations" in path.parts or path.name.startswith("test"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args or not isinstance(node.args[0], ast.Constant):
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                if name in PY_CALLS and isinstance(node.args[0].value, str):
                    found.setdefault(node.args[0].value, []).append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def extract_messages() -> dict[str, list[str]]:
    merged = _template_messages()
    for msgid, refs in _python_messages().items():
        merged.setdefault(msgid, []).extend(refs)
    return merged


def _unquote(chunk: str) -> str:
    return ast.literal_eval(chunk.strip())


def read_po(path: Path = PO) -> dict[str, str]:
    """Parse msgid/msgstr pairs (including the header entry); comments are ignored."""
    entries, msgid, msgstr, target = {}, None, None, None
    for raw in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        line = raw.strip()
        if line.startswith("msgid "):
            if msgid is not None:
                entries[msgid] = msgstr or ""
            msgid, msgstr, target = _unquote(line[6:]), "", "id"
        elif line.startswith("msgstr "):
            msgstr, target = _unquote(line[7:]), "str"
        elif line.startswith('"') and msgid is not None:
            if target == "id":
                msgid += _unquote(line)
            else:
                msgstr += _unquote(line)
    if msgid is not None:
        entries[msgid] = msgstr or ""
    return entries


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def write_po(messages: dict[str, list[str]], translations: dict[str, str]) -> None:
    LOCALE.mkdir(parents=True, exist_ok=True)
    header = "".join(f"{key}: {value}\n" for key, value in HEADER.items())
    out = ['# English interface strings. Source language: Russian.\n# Regenerate with: python scripts/i18n.py extract\n',
           f'msgid ""\nmsgstr {_quote(header)}\n']
    for msgid in sorted(messages):
        refs = sorted(set(messages[msgid]))
        out.append("\n".join(f"#: {ref}" for ref in refs[:3]))
        if _PLACEHOLDER.search(msgid):
            out.append("#, python-format")
        out.append(f"msgid {_quote(msgid)}\nmsgstr {_quote(translations.get(msgid, ''))}\n")
    PO.write_text("\n".join(out), encoding="utf-8")


def build_mo(entries: dict[str, str]) -> bytes:
    """GNU .mo (little endian) for the entries that have a translation, plus the header."""
    pairs = sorted((k, v) for k, v in entries.items() if v or k == "")
    ids = b"".join(k.encode() + b"\0" for k, _ in pairs)
    strs = b"".join(v.encode() + b"\0" for _, v in pairs)
    count, table = len(pairs), 7 * 4
    id_table, str_table = [], []
    offset = 0
    for k, _ in pairs:
        id_table.append((len(k.encode()), table + count * 16 + offset))
        offset += len(k.encode()) + 1
    base = table + count * 16 + len(ids)
    offset = 0
    for _, v in pairs:
        str_table.append((len(v.encode()), base + offset))
        offset += len(v.encode()) + 1
    data = struct.pack("<7I", 0x950412DE, 0, count, table, table + count * 8, 0, 0)  # no hash table
    body = b"".join(struct.pack("<2I", *e) for e in id_table) + b"".join(struct.pack("<2I", *e) for e in str_table)
    return data + body + ids + strs


def problems() -> list[str]:
    found = extract_messages()
    entries = read_po()
    issues = []
    for msgid in sorted(set(found) - set(entries)):
        issues.append(f"not in catalog (run extract): {msgid[:70]!r}")
    for msgid in sorted(set(entries) - set(found) - {""}):
        issues.append(f"obsolete in catalog (run extract): {msgid[:70]!r}")
    for msgid, msgstr in entries.items():
        if not msgid:
            continue
        if not msgstr.strip():
            issues.append(f"untranslated: {msgid[:70]!r}")
        elif sorted(_PLACEHOLDER.findall(msgid)) != sorted(_PLACEHOLDER.findall(msgstr)):
            issues.append(f"placeholders differ: {msgid[:50]!r} -> {msgstr[:50]!r}")
    if not MO.exists() or MO.read_bytes() != build_mo(entries):
        issues.append("django.mo is stale (run compile)")
    return issues


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "check"
    if command == "extract":
        write_po(extract_messages(), read_po())
        print(f"{len(read_po()) - 1} messages in {PO.relative_to(ROOT)}")
    elif command == "compile":
        MO.write_bytes(build_mo(read_po()))
        print(f"wrote {MO.relative_to(ROOT)}")
    elif command == "check":
        issues = problems()
        print("\n".join(issues) or "catalog is complete and in sync")
        return 1 if issues else 0
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
