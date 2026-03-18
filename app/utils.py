import re
import unicodedata


def clean_component(s: str) -> str:
    """Normaliza string para uso em nomes de arquivo."""
    if not s:
        return "item"
    norm = unicodedata.normalize("NFKD", s)
    s2 = "".join(ch for ch in norm if not unicodedata.combining(ch))
    s2 = re.sub(r"\s+", "_", s2)
    s2 = re.sub(r"[^A-Za-z0-9_\-]+", "", s2)
    return s2 or "item"
