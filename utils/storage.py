"""Safe, atomic storage and transfer validation helpers."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
import uuid
from pathlib import Path

from utils.paths import get_user_saves_dir
from utils.formats import (validate_character, encode_map, decode_map,
                           encode_session, decode_session)

MAX_BYTES = 16 * 1024 * 1024
MAX_DEPTH, MAX_NODES = 20, 1000000
IMPORT_SUFFIXES = {".char", ".json", ".enemies", ".png", ".jpg", ".log"}
_RESERVED = re.compile(r"^(con|prn|aux|nul|conin\$|conout\$|(com|lpt)[0-9\u00b9\u00b2\u00b3])$", re.I)
_BADCH = set('/\\:<>"|?*')
_DMG = re.compile(r"^[1-9][0-9]{0,2}d[1-9][0-9]{0,3}([+-][0-9]{1,4})?$")


def _is_link(p: Path) -> bool:
    try:
        st = os.lstat(p)
    except OSError:
        return False
    if p.is_symlink():
        return True
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)  # Windows reparse point


def _check_chain(path: Path) -> None:
    for p in [path, *path.parents]:
        if _is_link(p):
            raise ValueError(f"Refusing symlink/reparse path component: {p}")


def atomic_write_bytes(path, data: bytes) -> None:
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("Path must be absolute")
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    _check_chain(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _check_chain(path)
    if path.exists() and not path.is_file():
        raise ValueError("Destination is not a regular file")
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        _check_chain(path)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _dumps(obj, sort_keys=False) -> bytes:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, sort_keys=sort_keys,
                      separators=(",", ":")).encode("utf-8")


def atomic_write_json(path, obj) -> None:
    data = _dumps(obj)  # serialize fully before touching the filesystem
    atomic_write_bytes(path, data)


def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"Duplicate JSON key: {k!r}")
        d[k] = v
    return d


def _bad_const(name):
    raise ValueError(f"Non-finite number not allowed: {name}")


def _parse_float(s):
    v = float(s)
    if not math.isfinite(v):
        raise ValueError("Non-finite number not allowed")
    return v


def _check_generic(obj, max_nodes=MAX_NODES) -> None:
    stack, nodes = [(obj, 1)], 0
    while stack:
        o, depth = stack.pop()
        nodes += 1
        if nodes > max_nodes or depth > MAX_DEPTH + 1:
            raise ValueError("JSON too large or too deeply nested")
        if isinstance(o, dict):
            if depth > MAX_DEPTH:
                raise ValueError("JSON too deeply nested")
            for k, v in o.items():
                if not isinstance(k, str):
                    raise ValueError("JSON keys must be strings")
                stack.append((v, depth + 1))
        elif isinstance(o, list):
            if depth > MAX_DEPTH:
                raise ValueError("JSON too deeply nested")
            stack.extend((v, depth + 1) for v in o)
        elif o is not None and not isinstance(o, (str, int, float, bool)):
            raise ValueError("Unsupported JSON value type")


def parse_json_bytes(raw: bytes, max_bytes: int = MAX_BYTES, *, max_nodes=MAX_NODES):
    if len(raw) > max_bytes:
        raise ValueError("JSON data too large")
    try:
        text = bytes(raw).decode("utf-8")
        obj = json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_bad_const,
                         parse_float=_parse_float)
    except RecursionError:
        raise ValueError("JSON too deeply nested") from None
    except UnicodeDecodeError:
        raise ValueError("Data is not valid UTF-8 JSON") from None
    _check_generic(obj, max_nodes=max_nodes)
    return obj


def _read_raw(path, max_bytes: int) -> bytes:
    path = Path(path)
    _check_chain(path)
    with open(path, "rb") as fh:
        raw = fh.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("File too large")
    return raw


def read_json(path, max_bytes: int = MAX_BYTES, *, max_nodes=MAX_NODES):
    return parse_json_bytes(_read_raw(path, max_bytes), max_bytes, max_nodes=max_nodes)


def safe_save_path(absolute_folder, filename: str) -> Path:
    folder = Path(absolute_folder)
    if not folder.is_absolute():
        raise ValueError("Folder must be absolute")
    if not isinstance(filename, str) or not filename or len(filename) > 180:
        raise ValueError("Invalid filename length")
    if (any(c in _BADCH or ord(c) < 32 or ord(c) == 127 for c in filename)
            or ".." in filename or filename in (".", "..")
            or filename[-1] in ". " or filename != os.path.basename(filename)):
        raise ValueError(f"Unsafe filename: {filename!r}")
    if _RESERVED.match(filename.split(".")[0].rstrip(" ")):
        raise ValueError("Reserved device filename")
    _check_chain(folder)
    root = folder.resolve()
    target = root / filename
    if _is_link(target):
        raise ValueError("Refusing symlink target")
    if target.resolve().parent != root:
        raise ValueError("Path escapes save folder")
    return target


def unique_import_path(folder, suffix: str) -> Path:
    if suffix not in IMPORT_SUFFIXES:
        raise ValueError(f"Unsupported import suffix: {suffix!r}")
    return safe_save_path(folder, uuid.uuid4().hex + suffix)


def _legacy(raw: bytes) -> bool:
    return raw[:1] == b"\x80" or raw[:1] in (b"(", b"]", b"}") and b"\x00" in raw[:64]


LEGACY_MSG = ("Legacy pickle character files are not supported and are never loaded; "
              "the character must be migrated/re-exported to the new .char JSON format.")


class CharacterRepository:
    def __init__(self, directory=None):
        base = Path(directory) if directory is not None else Path(get_user_saves_dir('characters'))
        if not base.is_absolute():
            raise ValueError("Repository directory must be absolute")
        self.base = base

    def list_files(self) -> list[str]:
        if not self.base.is_dir() or _is_link(self.base):
            return []
        return sorted(p.name for p in self.base.iterdir()
                      if p.suffix == ".char" and p.is_file() and not _is_link(p))

    def save(self, character) -> str:
        data = validate_character(character.to_dict())
        try:
            cid = str(uuid.UUID(str(data.get("character_id"))))
        except ValueError:
            raise ValueError("Character needs a valid UUID id") from None
        name = getattr(character, "_local_save_name", None) or cid + ".char"
        path = safe_save_path(self.base, name)
        atomic_write_json(path, {"format": "dnd-character", "version": 1, "character": data})
        return str(path)

    def load(self, filename: str):
        from core.character import Character  # local import avoids cycles
        path = safe_save_path(self.base, filename)
        if path.suffix != ".char":
            raise ValueError("Not a .char file")
        if not path.is_file():
            raise FileNotFoundError(f"Character file not found: {filename}")
        raw = _read_raw(path, MAX_BYTES)
        if _legacy(raw):
            raise ValueError(LEGACY_MSG)
        try:
            env = parse_json_bytes(raw)
        except ValueError as e:
            raise ValueError(f"Character file is corrupt or in an unsupported format: {e}") from None
        data = _unwrap_character(env)
        character = Character.from_dict(data)
        character._local_save_name = path.name
        return character


def _unwrap_character(env) -> dict:
    if (not isinstance(env, dict) or env.get("format") != "dnd-character"
            or env.get("version") != 1 or not isinstance(env.get("character"), dict)):
        raise ValueError("Unsupported character envelope (expected dnd-character v1)")
    return validate_character(env["character"])


def _int(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ValueError(f"Invalid enemy {what}")
    return v


def _enemy(e) -> None:
    from core.enemy import Enemy
    from utils.non_ui_helpers import parse_dice
    if not isinstance(e, dict):
        raise ValueError('Invalid enemy entry')
    name = e.get('name')
    if not isinstance(name, str) or not 1 <= len(name) <= 120:
        raise ValueError('Invalid enemy name')
    _int(e.get('hp'), -10000, 100000, 'hp')
    _int(e.get('armor_class', e.get('ac')), 0, 100, 'armor_class')
    attacks = e.get('attacks', [])
    if not isinstance(attacks, list) or len(attacks) > 50:
        raise ValueError('Invalid enemy attacks')
    for attack in attacks:
        if not isinstance(attack, dict) or not isinstance(attack.get('name'), str):
            raise ValueError('Invalid enemy attack')
        parse_dice(attack.get('damage', '1'))
        _int(attack.get('to_hit', 0), -100, 100, 'to_hit')


def _obj(x):
    return parse_json_bytes(x.encode("utf-8") if isinstance(x, str) else x) if isinstance(x, (str, bytes)) else x


def validate_transfer(kind: str, data: bytes) -> bytes:
    """Validate untrusted transfer data; return canonical JSON bytes."""
    kind = {"characters": "character", "maps": "map", "sessions": "session"}.get(kind, kind)
    if kind not in ("character", "map", "session", "enemies"):
        raise ValueError(f"Transfer kind not allowed: {kind!r}")
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    if _legacy(bytes(data)):
        raise ValueError("Legacy pickle data is rejected")
    obj = parse_json_bytes(bytes(data))
    if kind == "character":
        out = {"format": "dnd-character", "version": 1, "character": _unwrap_character(obj)}
    elif kind == "map":
        out = _obj(encode_map(decode_map(obj)))
    elif kind == "session":
        out = _obj(encode_session(decode_session(obj)))
    else:
        if not isinstance(obj, list) or len(obj) > 1000:
            raise ValueError("Enemy list must be a list of at most 1000 entries")
        for e in obj:
            _enemy(e)
        out = obj
    _check_generic(out)
    return _dumps(out, sort_keys=True)
