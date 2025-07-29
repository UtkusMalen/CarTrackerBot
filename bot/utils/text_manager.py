import yaml
from functools import lru_cache


@lru_cache(maxsize=None)
def _load_texts():
    """Loads the texts.yaml file."""
    with open("ru.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_text(key: str, **kwargs) -> str:
    texts = _load_texts()
    keys = key.split('.')
    try:
        value = texts
        for k in keys:
            value = value[k]

        if kwargs:
            return value.format(**kwargs)
        return value
    except KeyError:
        return key