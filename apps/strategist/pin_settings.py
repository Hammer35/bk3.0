"""Settings of one pin generation run: allowed values, cleaning, and what the model is told.

The same cleaning is used by the form and by the background task, so a stored job can never carry
a value the page would have refused. A user's free-text instruction is passed as data and never
changes the rules or the validation; forbidden words are enforced by a check, not by the prompt.
"""
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

MAX_ITEMS = 6
MAX_WORDS = 20
MAX_WORD_LENGTH = 40
MAX_INSTRUCTION = 500
TONES = {"neutral": "нейтральный и спокойный", "friendly": "дружелюбный и тёплый",
         "expert": "экспертный, по делу, без лишних эмоций", "premium": "сдержанный, премиальный"}
CTAS = {"none": "без призыва к действию", "soft": "мягкий призыв узнать подробности",
        "direct": "короткий прямой призыв перейти по ссылке"}
LENGTHS = {"short": "описание до 200 символов", "standard": "описание 200–450 символов",
           "detailed": "описание 450–750 символов"}
KEYWORD_MODES = {"both": "русский эквивалент или английская фраза, как звучит естественнее",
                 "ru": "только русский эквивалент ключа", "en": "английская фраза ключа"}
UTM_KEYS = ("source", "medium", "campaign")
_UTM_VALUE = re.compile(r"^[A-Za-z0-9._\-]{1,60}$")

DEFAULTS = {
    "tone": "neutral", "cta": "none", "length": "standard", "keyword_mode": "both",
    "forbidden_words": [], "instruction": "", "destination_url": "", "utm": {k: "" for k in UTM_KEYS},
    "rewrite": True, "product_url": "", "remember": True, "account_id": None, "boards": {}, "product_facts": "",
}


def clean_words(text) -> list[str]:
    """Words or phrases separated by commas or new lines; bounded and de-duplicated."""
    parts = text if isinstance(text, list) else re.split(r"[,\n;]", str(text or ""))
    words = []
    for part in parts:
        word = " ".join(str(part).split())[:MAX_WORD_LENGTH]
        if word and word.casefold() not in {w.casefold() for w in words}:
            words.append(word)
    return words[:MAX_WORDS]


def clean_utm(values) -> dict:
    values = values if isinstance(values, dict) else {}
    return {k: (str(values.get(k, "")).strip() if _UTM_VALUE.match(str(values.get(k, "")).strip()) else "") for k in UTM_KEYS}


def build_url(base: str, utm: dict) -> str:
    """The destination with utm parameters appended; anything that is not an http(s) address stays as is."""
    parsed = urlparse((base or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return (base or "").strip()
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.startswith("utm_")]
    query += [(f"utm_{k}", utm[k]) for k in UTM_KEYS if utm.get(k)]
    return urlunparse(parsed._replace(query=urlencode(query)))


def normalize(raw: dict | None) -> dict:
    """A complete, safe settings dict from whatever was stored or posted."""
    raw = raw if isinstance(raw, dict) else {}
    result = {**DEFAULTS, "utm": dict(DEFAULTS["utm"]), "boards": {}}
    for key, allowed in (("tone", TONES), ("cta", CTAS), ("length", LENGTHS), ("keyword_mode", KEYWORD_MODES)):
        if raw.get(key) in allowed:
            result[key] = raw[key]
    result["forbidden_words"] = clean_words(raw.get("forbidden_words", []))
    result["instruction"] = " ".join(str(raw.get("instruction") or "").split())[:MAX_INSTRUCTION]
    result["destination_url"] = str(raw.get("destination_url") or "").strip()[:500]
    result["product_url"] = str(raw.get("product_url") or "").strip()[:500]
    result["product_facts"] = str(raw.get("product_facts") or "")[:1500]  # filled by the task, never taken from a form
    result["utm"] = clean_utm(raw.get("utm"))
    result["rewrite"] = bool(raw.get("rewrite", True))
    result["remember"] = bool(raw.get("remember", True))
    result["account_id"] = raw.get("account_id") if isinstance(raw.get("account_id"), int) else None
    boards = raw.get("boards")
    result["boards"] = {str(k): str(v)[:300] for k, v in boards.items() if str(v).strip()} if isinstance(boards, dict) else {}
    return result


def style_for_model(options: dict, keyword_ru: str) -> dict:
    return {
        "tone": TONES[options["tone"]], "cta": CTAS[options["cta"]], "length_hint": LENGTHS[options["length"]],
        "keyword_mode": KEYWORD_MODES[options["keyword_mode"] if keyword_ru else "en"],
        "forbidden_words": options["forbidden_words"], "user_instruction": options["instruction"],
    }
