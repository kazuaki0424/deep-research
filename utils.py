import re, unicodedata

def slugify(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9\-\s_]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:80]
