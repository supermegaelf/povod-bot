import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_LOCALE = os.getenv("BOT_LOCALE", "ru")


@lru_cache()
def _load_locale(locale: str) -> dict[str, str]:
    base_path = Path(__file__).resolve().parent.parent
    locale_path = base_path / "locales" / f"{locale}.json"
    if not locale_path.exists():
        raise FileNotFoundError(f"Locale file not found: {locale_path}")
    with locale_path.open(encoding="utf-8") as fp:
        return json.load(fp)


def t(key: str, *, locale: str | None = None, **kwargs) -> str:
    data = _load_locale(locale or DEFAULT_LOCALE)
    if key not in data:
        raise KeyError(f"Missing locale key '{key}' for locale '{locale or DEFAULT_LOCALE}'")
    value = data[key]
    if kwargs:
        return value.format(**kwargs)
    return value

