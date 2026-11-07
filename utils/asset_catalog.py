"""Allowlisted bundled map art. Map documents carry IDs, never image paths."""
import json
import re
from functools import lru_cache
from pathlib import Path
from utils.paths import resource_path

ASSET_ID = re.compile(r'[A-Z]{3}-[0-9]{3}')


def valid_asset_id(value):
    return isinstance(value, str) and ASSET_ID.fullmatch(value) is not None


@lru_cache(maxsize=1)
def catalog():
    path = Path(resource_path('assets/map_assets/catalog.json'))
    if path.stat().st_size > 262144:
        raise ValueError('Asset-Katalog ist zu groß.')
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError('Ungültiger Asset-Katalog.')
    records = raw.get('assets')
    if raw.get('version') != 1 or not isinstance(records, list) or len(records) > 1000:
        raise ValueError('Ungültiger Asset-Katalog.')
    result, seen = [], set()
    for item in records:
        if not isinstance(item, dict):
            raise ValueError('Ungültiger Asset-Eintrag.')
        key = item.get('id')
        if not valid_asset_id(key) or key in seen or item.get('filename') != key + '.jpg':
            raise ValueError('Ungültiger Asset-Eintrag.')
        if not all(isinstance(item.get(k), str) and 0 < len(item[k]) <= 120 for k in ('name', 'category', 'qa')):
            raise ValueError('Ungültige Asset-Beschriftung.')
        result.append(dict(item))
        seen.add(key)
    return tuple(result)


def asset_info(key):
    if not valid_asset_id(key):
        return None
    return next((item for item in catalog() if item['id'] == key), None)


def asset_path(key):
    if asset_info(key) is None:
        raise ValueError('Dieses Asset ist nicht installiert.')
    return resource_path('assets/map_assets/' + key + '.jpg')
