"""Bounded validators and codecs for characters, maps and sessions."""
import math
import uuid

# A supported 100x100 map has over 80,000 primitive nodes before artwork.
# Byte limits in storage/wire and the schema's collection limits still apply.
MAX_DEPTH, MAX_COUNT, MAX_STR, TEXT_MAX = 20, 1000000, 65536, 16000
ABILITIES = ('Stärke', 'Geschicklichkeit', 'Konstitution', 'Intelligenz', 'Weisheit', 'Charisma')
TILE_TYPES = ('Floor', 'Wall', 'Door', 'Trigger')
CURRENCIES = ('KP', 'SP', 'EP', 'GM', 'PP')
TEXT_FIELDS = ('background', 'alignment', 'personality_traits', 'ideals', 'bonds', 'flaws', 'fighting_style')


class ValidationError(ValueError):
    pass


def _prim(v, depth=0, cnt=None):
    cnt = cnt if cnt is not None else [0]
    cnt[0] += 1
    if cnt[0] > MAX_COUNT or depth > MAX_DEPTH:
        raise ValidationError('data too large or too deep')
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, int):
        if abs(v) > 10 ** 18:
            raise ValidationError('integer out of range')
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValidationError('NaN/inf not allowed')
        return v
    if isinstance(v, str):
        if len(v) > MAX_STR:
            raise ValidationError('string too long')
        return v
    if isinstance(v, (list, tuple)):
        return [_prim(x, depth + 1, cnt) for x in v]
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if not isinstance(k, str):
                raise ValidationError('keys must be strings')
            out[k] = _prim(x, depth + 1, cnt)
        return out
    raise ValidationError('unsupported type ' + type(v).__name__)


def validate_primitive(value):
    return _prim(value)


def _int(v, lo, hi, name, strict=False):
    if not strict and isinstance(v, float) and math.isfinite(v) and v == int(v):
        v = int(v)
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ValidationError(f'{name} must be an int in {lo}..{hi}')
    return v


def _str(v, name, lo=0, hi=TEXT_MAX):
    if not isinstance(v, str) or not lo <= len(v) <= hi:
        raise ValidationError(f'{name} must be a string of {lo}..{hi} chars')
    return v


def _dict(v, name):
    if not isinstance(v, dict):
        raise ValidationError(f'{name} must be a dict')
    return v


def _list(v, name, n):
    if not isinstance(v, (list, tuple)) or len(v) > n:
        raise ValidationError(f'{name} must be a list of at most {n} items')
    return list(v)


def _slist(v, name, n=200, hi=200):
    return [_str(x, name, 0, hi) for x in _list(v, name, n)]


def _features(v):
    res = []
    for f in _list(v, 'features', 200):
        d = _dict(f, 'feature')
        key = 'description' if 'description' in d and 'desc' not in d else 'desc'
        res.append({'name': _str(d.get('name'), 'feature.name', 1, 120),
                    key: _str(d.get(key, ''), 'feature.' + key)})
    return res


def _spells(v):
    out = {}
    for k, x in _dict(v, 'spells').items():
        if isinstance(k, str) and k.isascii() and k.isdecimal():
            k = int(k)
        lvl = _int(k, 0, 9, 'spell level', True)
        if lvl in out:
            raise ValidationError('duplicate spell level')
        out[lvl] = _slist(x, 'spells')
    return out


def _slots(v, name):
    out = {}
    for k, x in _dict(v, name).items():
        if type(k) is int:
            k = str(k)
        if k in out:
            raise ValidationError('duplicate spell slot level')
        if not (isinstance(k, str) and len(k) == 1 and k in '123456789'):
            raise ValidationError(name + ' keys must be strings 1..9')
        out[k] = _int(x, 0, 100, name)
    return out


def validate_character(data):
    d = _dict(data, 'character')

    def g(key, default):
        v = d.get(key)
        return default if v is None else v

    name = _str(d.get('name'), 'name', 1, 120)
    race = _str(d.get('race'), 'race', 0, 120)
    cls = _str(d.get('char_class'), 'char_class', 0, 120)
    out = {'name': name, 'race': race, 'char_class': cls}
    cid = None
    try:
        if isinstance(d.get('character_id'), str):
            cid = str(uuid.UUID(d['character_id']))
    except ValueError:
        cid = None
    out['character_id'] = cid or str(uuid.uuid5(uuid.NAMESPACE_URL, f'{name}|{race}|{cls}'))
    level = out['level'] = _int(g('level', 1), 1, 20, 'level')

    def abil(key, default):
        v = d.get(key)
        if v is None:
            return dict(default)
        a = _dict(v, key)
        return {n: _int(a.get(n, default[n]), 1, 30, key + '.' + n) for n in ABILITIES}

    base = abil('base_abilities', {n: 10 for n in ABILITIES})
    out['base_abilities'] = base
    out['abilities'] = abil('abilities', base)
    mhp = out['max_hit_points'] = _int(g('max_hit_points', 10), 0, 10000, 'max_hit_points')
    out['hit_points'] = _int(g('hit_points', mhp), -10000, 10000, 'hit_points')
    out['speed'] = _int(g('speed', 6), 0, 200, 'speed')
    out['armor_class'] = _int(g('armor_class', 10), 0, 100, 'armor_class')
    out['actions_per_turn'] = _int(g('actions_per_turn', 1), 1, 20, 'actions_per_turn')
    out['initiative'] = _int(g('initiative', 0), -100, 100, 'initiative')
    mhd = out['max_hit_dice'] = _int(g('max_hit_dice', level), 0, 20, 'max_hit_dice')
    out['hit_dice'] = _int(g('hit_dice', mhd), 0, 20, 'hit_dice')
    out['features'] = _features(g('features', []))
    for key in ('proficiencies', 'languages', 'selected_skills', 'selected_languages'):
        legacy = d.get('proficiencies', []) if key == 'selected_skills' else d.get('languages', []) if key == 'selected_languages' else []
        out[key] = _slist(g(key, legacy), key)
    out['spells'] = _spells(g('spells', {}))
    out['max_spell_slots'] = _slots(g('max_spell_slots', {}), 'max_spell_slots')
    out['current_spell_slots'] = _slots(g('current_spell_slots', {}), 'current_spell_slots')
    eq = _dict(g('equipment', {}), 'equipment')
    if len(eq) > 200:
        raise ValidationError('too many equipment entries')
    out['equipment'] = {_str(k, 'equipment key', 1, 120): _int(x, -20, 100, 'equipment') for k, x in eq.items()}
    cnt = [0]
    inv = []
    for item in _list(g('inventory', []), 'inventory', 1000):
        inv.append(_dict(_prim(item, 0, cnt), 'inventory item'))
    out['inventory'] = inv
    cur = _dict(g('currency', {}), 'currency')
    out['currency'] = {c: _int(cur.get(c, 0), 0, 10 ** 9, 'currency.' + c) for c in CURRENCIES}
    w = d.get('equipped_weapon')
    out['equipped_weapon'] = None if w is None else _str(w, 'equipped_weapon', 0, 120)
    for key in TEXT_FIELDS:
        out[key] = None if key == 'fighting_style' and d.get(key) is None else _str(g(key, ''), key)
    hb = g('half_elf_bonuses', [])
    if not isinstance(hb, (list, dict)):
        raise ValidationError('half_elf_bonuses must be list or dict')
    if isinstance(hb, list):
        hb = {'abilities': hb, 'skills': []}
    abilities = _slist(hb.get('abilities', []), 'half_elf abilities', 2)
    if len(set(abilities)) != len(abilities) or any(a not in ABILITIES or a == 'Charisma' for a in abilities):
        raise ValidationError('invalid half-elf ability choices')
    out['half_elf_bonuses'] = {'abilities': abilities, 'skills': _slist(hb.get('skills', []), 'half_elf skills', 2)} if hb else {}
    ic = g('initialization_complete', mhp > 0)
    if not isinstance(ic, bool):
        raise ValidationError('initialization_complete must be bool')
    out['initialization_complete'] = ic
    out['attacks'] = validate_attacks(g('attacks', []))
    out['attack_bonus'] = _int(g('attack_bonus', 0), -100, 100, 'attack_bonus')
    out['proficiency'] = _int(g('proficiency', 0), 0, 20, 'proficiency')
    return out


def _check_version(d, fmt):
    if 'format' in d and d['format'] != fmt:
        raise ValidationError('unknown format')
    if 'version' in d and (type(d['version']) is not int or d['version'] != 1):
        raise ValidationError('unsupported version')


def _coord(k):
    if isinstance(k, tuple) and len(k) == 2:
        return k
    if isinstance(k, str):
        s = k.strip()
        if s.startswith('(') and s.endswith(')'):
            parts = [p.strip() for p in s[1:-1].split(',')]
            if len(parts) == 2 and all(p.isascii() and p.isdecimal() for p in parts):
                return int(parts[0]), int(parts[1])
    raise ValidationError('malformed tile key')


def _opt_str(v, name, hi=TEXT_MAX):
    return None if v is None else _str(v, name, 0, hi)


def _tile(t):
    d = _dict(t, 'tile')
    ty = d.get('type', 'Floor')
    if not isinstance(ty, str) or ty not in TILE_TYPES:
        raise ValidationError('unknown tile type')
    fur = d.get('furniture')
    if fur is not None:
        f = _dict(fur, 'furniture')
        mimic = f.get('is_mimic', False)
        if not isinstance(mimic, bool):
            raise ValidationError('is_mimic must be bool')
        fur = {'type': _str(f.get('type'), 'furniture.type', 0, 120), 'is_mimic': mimic}
    return {'type': ty, 'object': _opt_str(d.get('object'), 'object', 120), 'furniture': fur,
            'trigger_message': _opt_str(d.get('trigger_message'), 'trigger_message')}


def validate_attacks(value):
    from utils.non_ui_helpers import parse_dice
    result = []
    for attack in _list(value, 'attacks', 50):
        a = _dict(attack, 'attack')
        damage = _str(a.get('damage', '1'), 'damage', 1, 40)
        parse_dice(damage)
        item = {'name': _str(a.get('name', 'Angriff'), 'attack name', 1, 120), 'damage': damage}
        for key, lo, hi in [('to_hit', -100, 100), ('damage_modifier', -100, 100), ('range', 1, 1000)]:
            if key in a:
                item[key] = _int(a[key], lo, hi, key)
        result.append(item)
    return result


def validate_enemy(value):
    e = _dict(_prim(value), 'enemy')
    e['name'] = _str(e.get('name'), 'enemy name', 1, 120)
    e['attacks'] = validate_attacks(e.get('attacks', []))
    for k in ('hp', 'max_hp', 'hit_points', 'max_hit_points'):
        if e.get(k) is not None:
            e[k] = _int(e[k], -10000, 10000, k)
    for k in ('ac', 'armor_class', 'armorclass'):
        if e.get(k) is not None:
            e[k] = _int(e[k], 0, 100, k)
    return e


def _enemies(v, n=1000):
    res = []
    cnt = [0]
    for e in _list(v, 'enemies', n):
        res.append(_str(e, 'enemy', 0, 120) if isinstance(e, str) else validate_enemy(e))
    return res


def _chars(v, name):
    if v is None:
        return []
    if isinstance(v, dict):
        v = list(v.values())
    res = []
    for e in _list(v, name, 1000):
        if isinstance(e, dict) and isinstance(e.get('character'), dict):
            e = e['character']
        res.append(validate_character(e))
    return res


def decode_map(data):
    if data is None or data == {}:
        return None
    d = _dict(data, 'map')
    _check_version(d, 'dnd-map')
    rows = _int(d.get('rows'), 1, 100, 'rows', True)
    cols = _int(d.get('cols'), 1, 100, 'cols', True)
    raw = d.get('tiles', {})
    if raw is None:
        raw = {}
    if isinstance(raw, dict):
        items = [(_coord(k), t) for k, t in raw.items()]
    elif isinstance(raw, list):
        items = []
        for e in raw:
            e = _dict(e, 'tile entry')
            items.append(((e.get('row'), e.get('col')), e.get('tile')))
    else:
        raise ValidationError('tiles must be dict or list')
    if len(items) > rows * cols:
        raise ValidationError('too many tiles')
    tiles = {}
    for (r, c), t in items:
        pos = (_int(r, 0, rows - 1, 'row', True), _int(c, 0, cols - 1, 'col', True))
        if pos in tiles:
            raise ValidationError('duplicate tile')
        tiles[pos] = _tile(t)
    out = {'rows': rows, 'cols': cols, 'tiles': tiles,
           'enemies': _enemies(d.get('enemies', [])),
           'offline_players': _chars(d.get('offline_players', []), 'offline_players'),
           'online_players': _chars(d.get('online_players', []), 'online_players')}
    if 'artwork' in d:
        from utils.map_document import validate_artwork
        try:
            out['artwork'] = validate_artwork(d['artwork'])
            if any(x > cols or y > rows for e in out['artwork']['elements'] for x, y in e['points']):
                raise ValueError('Zeichnung liegt ausserhalb der Karte')
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc
    if 'cartography_scale' in d:
        from utils.map_scale import validate_scale
        out['cartography_scale'] = validate_scale(d['cartography_scale'])
    if 'region_context' in d:
        from utils.map_region_context import validate_context
        out['region_context'] = validate_context(d['region_context'], rows, cols)
    cnt = [0]
    for k, v in d.items():
        if k not in out and k not in ('format', 'version'):
            out[_str(k, 'key', 1, 120)] = _prim(v, 0, cnt)
    return out


def encode_map(map_data):
    d = decode_map(map_data)
    if d is None:
        return None
    tiles = [{'row': r, 'col': c, 'tile': t} for (r, c), t in sorted(d.pop('tiles').items())]
    out = {'format': 'dnd-map', 'version': 1, 'rows': d.pop('rows'), 'cols': d.pop('cols'), 'tiles': tiles}
    out.update(d)
    return out


def _session_enemies(v):
    res = []
    for e in _enemies(v, 1000):
        if isinstance(e, str):
            e = {'name': e}
        for k in ('hp', 'max_hp', 'hit_points', 'max_hit_points'):
            if e.get(k) is not None:
                e[k] = _int(e[k], -10000, 10000, k)
        for k in ('ac', 'armor_class', 'armorclass'):
            if e.get(k) is not None:
                e[k] = _int(e[k], 0, 100, k)
        res.append(e)
    return res


def _initiative(v):
    res = []
    for e in _list(v or [], 'initiative', 1000):
        pair = _list(e, 'initiative entry', 2)
        if len(pair) != 2:
            raise ValidationError('initiative entries are [roll, name]')
        res.append([_int(pair[0], -1000, 1000, 'roll'), _str(pair[1], 'initiative name', 0, 120)])
    return res


def _turn_state(v):
    out = {}
    for k, x in _dict(v or {}, 'turn_action_state').items():
        _str(k, 'key', 1, 120)
        if isinstance(x, bool) or x is None:
            out[k] = x
        elif 'move' in k.lower():
            out[k] = _int(x, 0, 1000, k)
        elif 'attack' in k.lower():
            out[k] = _int(x, 0, 100, k)
        else:
            out[k] = _prim(x)
    return out


def decode_session(data):
    if data is None:
        data = {}
    if isinstance(data, list):
        data = {'online_players': data}
    d = _dict(data, 'session')
    _check_version(d, 'dnd-session')
    out = {}
    if d.get('type') is not None:
        out['type'] = _str(d['type'], 'type', 1, 32)
    if d.get('archive_id') is not None:
        try:
            out['archive_id'] = str(uuid.UUID(_str(d['archive_id'], 'archive_id', 36, 36)))
        except (ValueError, AttributeError) as exc:
            raise ValidationError('invalid archive_id') from exc
    if d.get('_plan_id') is not None:
        try:
            out['_plan_id'] = str(uuid.UUID(_str(d['_plan_id'], '_plan_id', 36, 36)))
        except (ValueError, AttributeError) as exc:
            raise ValidationError('invalid preparation id') from exc
    out['online_players'] = _chars(d.get('online_players'), 'online_players')
    out['offline_players'] = _chars(d.get('offline_players'), 'offline_players')
    out['enemies'] = _session_enemies(d.get('enemies', []) or [])
    init = out['initiative'] = _initiative(d.get('initiative_order', d.get('initiative')))
    out['initiative_order'] = init
    found = False
    for k in ('current_turn_index', 'initiative_index', 'index'):
        if k in d:
            out[k] = _int(-1 if d[k] is None else d[k], -1, len(init) - 1, k)
            found = True
    if not found:
        out['current_turn_index'] = -1
    out['turn_action_state'] = _turn_state(d.get('turn_action_state'))
    cnt = [0]
    logs = []
    for e in _list(d.get('logs') or [], 'logs', 10000):
        logs.append(_str(e, 'log', 0, MAX_STR) if isinstance(e, str) else _dict(_prim(e, 0, cnt), 'log'))
    out['logs'] = logs
    out['log'] = _str(d.get('log', '\n'.join(e for e in logs if isinstance(e, str))), 'log', 0, MAX_STR)
    for k in ('notes', 'summary', 'quests', 'next_steps', 'decisions', 'npcs'):
        v = d.get(k)
        out[k] = '' if v is None else _str(v, k, 0, MAX_STR)
    out['map_data'] = decode_map(d.get('map_data'))
    return out


def encode_session(data):
    s = decode_session(data)
    out = {'format': 'dnd-session', 'version': 1}
    out.update(s)
    out['map_data'] = encode_map(s.get('map_data'))
    return out
