"""Explicit conversion of old Character pickles into inert, validated JSON data.

Normal loading and LAN imports never invoke this module. No original file is changed.
"""
import io
import pickle
import pickletools
from pathlib import Path

from utils.formats import validate_character
from utils.storage import atomic_write_json, unique_import_path, safe_save_path

MAX_LEGACY_BYTES = 1024 * 1024
SAFE_OPS = frozenset('PROTO FRAME SHORT_BINUNICODE BINUNICODE BINUNICODE8 UNICODE '
                     'EMPTY_TUPLE NEWOBJ EMPTY_DICT DICT MEMOIZE BINGET LONG_BINGET '
                     'BINPUT LONG_BINPUT PUT GET MARK BININT1 BININT2 BININT INT '
                     'LONG1 LONG4 LONG FLOAT BINFLOAT EMPTY_LIST LIST APPEND APPENDS '
                     'SETITEM SETITEMS NONE NEWTRUE NEWFALSE TUPLE TUPLE1 TUPLE2 '
                     'TUPLE3 STOP STACK_GLOBAL GLOBAL BUILD'.split())


class _InertCharacter:
    pass


class _Reader(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) != ('core.character', 'Character'):
            raise ValueError('Das alte Format enthält nicht erlaubte Objekttypen.')
        return _InertCharacter

    def persistent_load(self, pid):
        raise ValueError('Externe Referenzen sind nicht erlaubt.')


def decode_legacy_character(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_LEGACY_BYTES:
        raise ValueError('Alte Charakterdatei ist zu groß oder leer.')
    counts = {}
    last = None
    for count, (op, argument, position) in enumerate(pickletools.genops(raw), 1):
        if count > 50000 or op.name not in SAFE_OPS:
            raise ValueError('Nicht erlaubte Anweisung im alten Charakterformat.')
        if op.name == 'FRAME' and argument > len(raw):
            raise ValueError('Ungültige Blockgröße.')
        if op.name in ('BINPUT', 'LONG_BINPUT', 'PUT', 'BINGET', 'LONG_BINGET', 'GET') and not 0 <= argument < 50000:
            raise ValueError('Ungültiger Referenzindex.')
        counts[op.name] = counts.get(op.name, 0) + 1
        if op.name in ('BUILD', 'NEWOBJ', 'GLOBAL', 'STACK_GLOBAL') and counts[op.name] > 1:
            raise ValueError('Unerwartete Objektstruktur.')
        last = (op.name, position)
    if last != ('STOP', len(raw) - 1) or counts.get('NEWOBJ') != 1 or counts.get('BUILD') != 1:
        raise ValueError('Unvollständige alte Charakterdatei.')
    if counts.get('GLOBAL', 0) + counts.get('STACK_GLOBAL', 0) != 1:
        raise ValueError('Unerwartete Objekttypen.')
    record = _Reader(io.BytesIO(raw)).load()
    if type(record) is not _InertCharacter:
        raise ValueError('Kein alter Charakter enthalten.')
    return validate_character(record.__dict__)


def convert_legacy_character(folder, filename):
    source = safe_save_path(folder, filename)
    with open(source, 'rb') as stream:
        raw = stream.read(MAX_LEGACY_BYTES + 1)
    data = decode_legacy_character(raw)
    target = unique_import_path(folder, '.char')
    atomic_write_json(target, {'format': 'dnd-character', 'version': 1, 'character': data})
    return Path(target).name
