"""Character actions operate on a copy of the DM state, never on client snapshots."""
import copy
import hashlib
import json
import random

from utils.data_manager import SPELL_DATA, WEAPON_DATA


def state_token(character):
    data = json.dumps(character.to_dict(), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def apply_character_action(character, action, args):
    """Validate intent against the host's data; caller commits only on success."""
    if not isinstance(args, dict):
        raise ValueError('Ungültige Aktion.')
    changed = copy.deepcopy(character)
    if action == 'equip_weapon':
        weapon = args.get('weapon')
        owned = {i['name'] for i in changed.inventory if i.get('quantity', 1) > 0}
        owned.update(changed.equipment)
        owned.update(('Unbewaffneter Schlag', changed.equipped_weapon))
        if not isinstance(weapon, str) or weapon not in WEAPON_DATA or weapon not in owned:
            raise ValueError('Diese Waffe ist nicht im Inventar des DM-Spielstands.')
        changed.equipped_weapon = weapon
        message = f'{changed.name} rüstet {weapon} aus.'
    elif action == 'healing_item':
        index = args.get('index')
        if type(index) is not int or not 0 <= index < len(changed.inventory):
            raise ValueError('Gegenstand nicht mehr vorhanden.')
        item = changed.inventory[index]
        healing = item.get('healing') or {}
        count, dice = healing.get('count'), healing.get('dice')
        if (item.get('quantity', 1) <= 0 or type(count) is not int or type(dice) is not int
                or not 1 <= count <= 100 or not 1 <= dice <= 1000):
            raise ValueError('Kein gültiger Heilgegenstand.')
        before = changed.hit_points
        changed.hit_points = min(changed.max_hit_points, before + sum(random.randint(1, dice) for _ in range(count)))
        item['quantity'] = item.get('quantity', 1) - 1
        if not item['quantity']:
            changed.inventory.pop(index)
        message = f"{changed.name} benutzt {item['name']}: +{changed.hit_points - before} HP."
    elif action == 'cast_spell':
        name = args.get('spell')
        if not isinstance(name, str) or name not in {s for spells in changed.spells.values() for s in spells}:
            raise ValueError('Dieser Zauber ist dem Charakter nicht bekannt.')
        level = SPELL_DATA.get(name, {}).get('level')
        if type(level) is not int:
            raise ValueError('Unbekannter Zaubergrad.')
        if level > 0:
            key = str(level)
            if changed.current_spell_slots.get(key, 0) <= 0:
                raise ValueError('Keine Zauberplätze auf diesem Grad verfügbar.')
            changed.current_spell_slots[key] -= 1
        message = f'{changed.name} wirkt {name}.'
    elif action == 'short_rest':
        count = args.get('dice', 1)
        if type(count) is not int or not 1 <= count <= changed.hit_dice:
            raise ValueError('Nicht genug Trefferwürfel für diese Rast.')
        healed = changed.short_rest(count)
        message = f'{changed.name} macht eine kurze Rast: +{healed} HP, {count} Trefferwürfel verbraucht.'
    elif action == 'long_rest':
        changed.long_rest()
        message = f'{changed.name} macht eine lange Rast.'
    else:
        raise ValueError('Diese Charakteränderung kann nur die Spielleitung vornehmen.')
    return changed, message
