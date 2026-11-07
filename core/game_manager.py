import copy
import random
from collections import deque
from core.character import Character
from core.enemy import Enemy
from utils.non_ui_helpers import roll_dice
from utils.data_manager import ENEMY_DATA
from utils.map_actions import reachable_tiles

class GameManager:
    """
    Manages the core game logic, state, and rules, decoupled from the UI.
    """
    def __init__(self, logger_func=print):
        self.logger = logger_func
        self.offline_players = []
        self.online_players = {} # addr -> Character
        self.disconnected_players = {}  # Session characters remain controllable by the DM.
        self.enemies = []
        self.initiative_order = []
        self.map_data = None

        self.current_turn_index = -1
        self.turn_action_state = {}

    def get_character_or_enemy_by_name(self, name):
        """Retrieves a character or enemy instance by its unique name."""
        for char in list(self.online_players.values()) + list(self.disconnected_players.values()):
            if char.name == name:
                return char
        # Suche auch in offline_players
        for char in getattr(self, 'offline_players', []):
            if char.name == name:
                return char
        for enemy in self.enemies:
            if enemy.name == name:
                return enemy
        return None

    def roll_initiative_for_all(self, players=None):
        """Rolls initiative for all players (online+offline) and enemies."""
        self.initiative_order = []
        if players is None:
            players = list(self.online_players.values()) + list(self.disconnected_players.values())
            players += getattr(self, 'offline_players', [])
        for char in players:
            roll = random.randint(1, 20) + int(getattr(char, 'initiative', 0) or 0)
            self.initiative_order.append((roll, char.name))
        for enemy in self.enemies:
            roll = random.randint(1, 20) + int(getattr(enemy, 'initiative', 0) or 0)
            self.initiative_order.append((roll, enemy.name))

        self.initiative_order.sort(key=lambda x: x[0], reverse=True)
        self.logger('Initiative has been rolled.')

        if self.initiative_order:
            self.current_turn_index = 0
            self.start_next_turn()
        else:
            self.current_turn_index = -1
            self.turn_action_state = {}

        return self.initiative_order

    def end_turn(self):
        """Ends the current turn and proceeds to the next in the initiative order."""
        if not self.initiative_order:
            return None
        self.current_turn_index = (self.current_turn_index + 1) % len(self.initiative_order)
        return self.start_next_turn()

    def start_next_turn(self):
        """Initializes state for the current turn; skips missing actors, terminates if none exist."""
        if not self.initiative_order or self.current_turn_index == -1:
            return None
        n = len(self.initiative_order)
        for _ in range(n):
            if not (0 <= self.current_turn_index < n):
                self.current_turn_index = 0
            name = self.initiative_order[self.current_turn_index][1]
            actor = self.get_character_or_enemy_by_name(name)
            if actor:
                incapacitated = isinstance(actor, Character) and actor.hit_points <= 0
                self.turn_action_state = {
                    'movement_left': 0 if incapacitated else actor.speed,
                    'attacks_left': 0 if incapacitated else actor.actions_per_turn,
                }
                self.logger(f'Next turn: {name}')
                return self.get_current_turn_info()
            self.logger(f'Character {name} not found, advancing turn.')
            self.current_turn_index = (self.current_turn_index + 1) % n
        self.current_turn_index = -1
        self.turn_action_state = {}
        return None

    def get_current_turn_info(self):
        """Returns a dictionary with the current turn's state."""
        order = self.initiative_order
        idx = self.current_turn_index
        if not order or not isinstance(idx, int) or idx < 0 or idx >= len(order):
            return {'name': None, 'pos': None, 'state': self.turn_action_state}
        name = order[idx][1]
        return {'name': name, 'pos': self.find_object_pos(name), 'state': self.turn_action_state}

    def move_object(self, obj_name, to_pos, *, dm_override=False):
        """Validates fully, then moves. Returns (success, reason); failures change nothing."""
        actor = self.get_character_or_enemy_by_name(obj_name)
        if not dm_override and isinstance(actor, Character) and actor.hit_points <= 0:
            return False, 'Bei 0 TP kann die Figur nicht selbst handeln. Der DM kann eingreifen.'
        if not dm_override and obj_name != self.get_current_turn_info()['name']:
            self.logger(f'Error: {obj_name} tried to move out of turn.')
            return False, 'Cannot move out of turn.'
        md = self.map_data
        if not md or not isinstance(md.get('tiles'), dict):
            return False, 'No map loaded.'
        try:
            if isinstance(to_pos, (str, bytes, dict)) or len(to_pos) != 2:
                raise ValueError
            r, c = to_pos
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (r, c)):
                raise ValueError
        except (TypeError, ValueError):
            return False, 'Invalid target position.'
        to_pos = (r, c)
        tiles = md['tiles']
        rows, cols = md.get('rows'), md.get('cols')
        if r < 0 or c < 0 or (isinstance(rows, int) and r >= rows) or (isinstance(cols, int) and c >= cols):
            return False, 'Target out of bounds.'
        target = tiles.get(to_pos)
        if not isinstance(target, dict):
            return False, 'Target tile does not exist.'
        if target.get('type') == 'Wall':
            return False, 'Target is a wall.'
        if target.get('object'):
            return False, 'Target is occupied.'
        if target.get('furniture'):
            return False, 'Target is blocked by furniture.'
        from_pos = self.find_object_pos(obj_name)
        if not from_pos:
            return False, f'{obj_name} not found on map.'
        budget = self.turn_action_state.get('movement_left', 0)
        if not dm_override:
            cost = self._path_cost(from_pos, to_pos, budget)
            if cost is None:
                return False, 'Target not reachable with remaining movement.'
        tiles[from_pos]['object'] = None
        target['object'] = obj_name
        if not dm_override:
            self.turn_action_state['movement_left'] = budget - cost
        self.logger(f'{"DM: " if dm_override else ""}{obj_name} moved from {from_pos} to {to_pos}.')
        return True, 'Move successful.'

    def handle_attack(self, attacker_name, target_name, attack_roll=None, damage_roll=None, attack_name=None, *, dm_override=False, natural_roll=None):
        """Handles an attack. Explicit rolls (manual dice) must be bounded ints; otherwise server rolls."""
        if not dm_override and attacker_name != self.get_current_turn_info()['name']:
            return {'success': False, 'reason': 'Cannot attack out of turn.'}
        if not dm_override and self.turn_action_state.get('attacks_left', 0) <= 0:
            return {'success': False, 'reason': 'No attacks left.'}
        attacker = self.get_character_or_enemy_by_name(attacker_name)
        target = self.get_character_or_enemy_by_name(target_name)
        if not attacker or not target:
            return {'success': False, 'reason': 'Attacker or target not found.'}
        if not dm_override and isinstance(attacker, Character) and attacker.hit_points <= 0:
            return {'success': False, 'reason': 'Bei 0 TP kann die Figur nicht selbst angreifen.'}
        if attacker is target:
            return {'success': False, 'reason': 'Cannot attack self.'}

        def ok(v, lo, hi):
            return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi

        if attack_roll is not None and not ok(attack_roll, -20, 100):
            return {'success': False, 'reason': 'Invalid attack roll.'}
        if damage_roll is not None and not ok(damage_roll, 0, 1000):
            return {'success': False, 'reason': 'Invalid damage roll.'}

        if natural_roll is not None and (not ok(natural_roll, 1, 20) or attack_roll is not None):
            return {'success': False, 'reason': 'Invalid attack roll.'}

        attack_info = self._select_attack(attacker, attack_name)
        if self.map_data and self.map_data.get('tiles'):
            pa, pb = self.find_object_pos(attacker_name), self.find_object_pos(target_name)
            if pa is None or pb is None:
                return {'success': False, 'reason': 'Attacker or target not on map.'}
            try:
                rng = int(attack_info.get('range', 1))
            except (TypeError, ValueError):
                rng = 1
            if not dm_override and max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1])) > max(rng, 1):
                return {'success': False, 'reason': 'Target out of range.'}

        die = None
        if attack_roll is not None:
            final_roll = attack_roll
            detail = f'Manueller Gesamtwurf: {final_roll}'
        else:
            try:
                bonus = int(attack_info.get('to_hit', 0) or 0)
            except (TypeError, ValueError):
                bonus = 0
            die = random.randint(1, 20) if natural_roll is None else natural_roll
            final_roll = die + bonus
            detail = f'W20: {die} | Angriffsbonus: {bonus:+d} | Gesamt: {final_roll}'
        self.logger(f'{attacker.name} → {target.name}: {detail}')
        outcome = {'success': True, 'hit': False, 'damage': 0, 'target_hp': 0,
                   'attack_total': final_roll, 'roll_detail': detail}
        critical = die == 20
        outcome['critical'] = critical
        if critical or (die != 1 and final_roll >= target.armor_class):
            if damage_roll is not None:
                damage = damage_roll
            else:
                from utils.non_ui_helpers import parse_dice
                try:
                    count, sides, fixed = parse_dice(attack_info.get('damage', '1d4'))
                    modifier = attack_info.get('damage_modifier', 0)
                    if type(modifier) is not int or not -100 <= modifier <= 100:
                        raise ValueError('Invalid modifier')
                    dice_count = count * (2 if critical else 1)
                    damage = max(0, sum(random.randint(1, sides) for _ in range(dice_count)) + fixed + modifier)
                except (ValueError, TypeError):
                    return {'success': False, 'reason': 'Ungültiger Schadensausdruck. Bitte Angriff beim DM prüfen.'}
            if isinstance(target, Character):
                target.hit_points = max(0, target.hit_points - damage)
                outcome['target_hp'] = target.hit_points
            else:
                target.hp -= damage
                outcome['target_hp'] = target.hp
            outcome['hit'] = True
            outcome['damage'] = damage
            self.logger(f"HIT! {target.name} takes {damage} damage. HP is now {outcome['target_hp']}.")
            if not dm_override:
                self.turn_action_state['attacks_left'] -= 1
            if outcome['target_hp'] <= 0:
                if isinstance(target, Character):
                    outcome['incapacitated'] = True
                    self.logger(f'{target.name} hat 0 TP und bleibt auf der Karte. Zustand und Todesrettungswürfe: DM entscheidet.')
                    if self.get_current_turn_info()['name'] == target.name:
                        self.turn_action_state.update(movement_left=0, attacks_left=0)
                else:
                    outcome['combat_result'] = self.handle_character_death(target.name)
                    outcome['defeated'] = True
        else:
            self.logger(f"MISS! {attacker.name}'s attack on {target.name} failed.")
            if not dm_override:
                self.turn_action_state['attacks_left'] -= 1
        return outcome

    def handle_character_death(self, character_name):
        """Removes a defeated character/enemy from combat; safe without a map."""
        obj = self.get_character_or_enemy_by_name(character_name)
        if isinstance(obj, Character):
            obj.hit_points = max(0, obj.hit_points)
            if self.get_current_turn_info()['name'] == obj.name:
                self.turn_action_state.update(movement_left=0, attacks_left=0)
            return 'INCAPACITATED'
        self.logger(f'{character_name} has been defeated!')
        active_name = self.get_current_turn_info()['name']
        defeated_index = -1
        for i, item in enumerate(self.initiative_order):
            if item[1] == character_name:
                defeated_index = i
                break
        obj = self.get_character_or_enemy_by_name(character_name)
        if isinstance(obj, Enemy) and obj in self.enemies:
            self.enemies.remove(obj)
        if defeated_index != -1:
            self.initiative_order.pop(defeated_index)
        if defeated_index != -1 and defeated_index < self.current_turn_index:
            self.current_turn_index -= 1
        tiles = (self.map_data or {}).get('tiles') or {}
        for pos, tile in tiles.items():
            if isinstance(tile, dict) and tile.get('object') == character_name:
                tile['object'] = None
                break
        if not self.enemies:
            self.logger('VICTORY! All enemies have been defeated.')
            self.current_turn_index = -1
            self.turn_action_state = {}
            return 'VICTORY'
        if active_name == character_name:
            if self.initiative_order:
                self.current_turn_index = defeated_index % len(self.initiative_order)
                self.start_next_turn()
            else:
                self.current_turn_index = -1
                self.turn_action_state = {}
        return 'DEFEATED'

    def handle_dm_attack(self, attacker_name, target_name, attack_info):
        """
        Handles an attack initiated by the DM for one of their enemies.
        `attack_info` is a dictionary for a specific attack, e.g. from enemy.attacks.
        """
        # This reuses the same logic as a player attack, but the attack_info is provided directly.
        # It also rolls dice for attack and damage, as the DM doesn't provide them.

        attack_roll = random.randint(1, 20)
        # Add to_hit bonus if available
        total_attack_roll = attack_roll + attack_info.get('to_hit', 0)

        damage_roll = roll_dice(attack_info.get('damage', '1d4'))

        self.logger(f"{attacker_name} greift {target_name} mit {attack_info.get('name', 'einem Angriff')} an! Wurf: {total_attack_roll}")

        return self.handle_attack(
            attacker_name=attacker_name,
            target_name=target_name,
            attack_roll=total_attack_roll,
            damage_roll=damage_roll
        )
    @staticmethod
    def normalize_map(md):
        """Returns map data with tuple tile keys (decodes stored format if needed)."""
        if not isinstance(md, dict):
            return None
        tiles = md.get('tiles')
        needs = isinstance(tiles, list) or (isinstance(tiles, dict) and any(isinstance(k, str) for k in tiles))
        if needs:
            from utils.formats import decode_map
            return decode_map(md)
        return md
    def apply_session(self, session):
        """Restores a decoded session without rerolling or rebuilding enemies. Atomic commit."""
        offline = []
        for p in session.get('offline_players') or []:
            offline.append(p if isinstance(p, Character) else Character.from_dict(p))
        enemies = []
        for e in session.get('enemies') or []:
            enemies.append(e if isinstance(e, Enemy) else Enemy.from_dict(e))
        md = self.normalize_map(session.get('map_data'))
        raw_order = session.get('initiative_order')
        if raw_order is None:
            raw_order = session.get('initiative')
        order = [(x[0], x[1]) for x in (raw_order or []) if isinstance(x, (list, tuple)) and len(x) >= 2]
        idx = session.get('current_turn_index', -1)
        if isinstance(idx, bool) or not isinstance(idx, int) or not order or not (0 <= idx < len(order)):
            idx = -1
        state = session.get('turn_action_state')
        if not isinstance(state, dict):
            state = {}
        disconnected = {p.name: p for raw in session.get('online_players', [])
                        for p in [raw if isinstance(raw, Character) else Character.from_dict(raw)]}
        self.offline_players = offline
        self.online_players = {}
        self.disconnected_players = disconnected
        self.enemies = enemies
        self.map_data = md
        self.initiative_order = order
        self.current_turn_index = idx
        self.turn_action_state = dict(state)
    def capture_snapshot(self):
        return copy.deepcopy({
            'offline_players': self.offline_players,
            'online_players': self.online_players,
            'disconnected_players': self.disconnected_players,
            'enemies': self.enemies,
            'initiative_order': self.initiative_order,
            'map_data': self.map_data,
            'current_turn_index': self.current_turn_index,
            'turn_action_state': self.turn_action_state,
        })
    def restore_snapshot(self, snap):
        snap = copy.deepcopy(snap)
        self.offline_players = snap['offline_players']
        self.online_players = snap['online_players']
        self.disconnected_players = snap.get('disconnected_players', {})
        self.enemies = snap['enemies']
        self.initiative_order = snap['initiative_order']
        self.map_data = snap['map_data']
        self.current_turn_index = snap['current_turn_index']
        self.turn_action_state = snap['turn_action_state']
    def find_object_pos(self, name):
        md = self.map_data
        if not md or not isinstance(md.get('tiles'), dict):
            return None
        for pos, tile in md['tiles'].items():
            if isinstance(tile, dict) and tile.get('object') == name:
                return pos
        return None
    def _path_cost(self, start, goal, budget):
        return reachable_tiles(self.map_data, start, budget).get(goal)

    def place_object(self, name, position):
        """Explicit DM placement, separate from turn-based movement; never exposed as a client action."""
        if self.get_character_or_enemy_by_name(name) is None and self.find_object_pos(name) is None:
            return False, 'Figur nicht in dieser Sitzung vorhanden.'
        tiles = (self.map_data or {}).get('tiles', {})
        tile = tiles.get(position)
        if not tile or tile.get('type') == 'Wall' or tile.get('furniture') or tile.get('object'):
            return False, 'Bitte ein freies, begehbares Feld wählen.'
        previous = self.find_object_pos(name)
        if previous is not None:
            tiles[previous]['object'] = None
        tile['object'] = name
        return True, f'{name} wurde auf der Karte platziert.'

    def add_to_running_initiative(self, character):
        """Late entrants go at the end without rerolling the current actor or restoring spent actions."""
        if self.get_current_turn_info()['name'] is not None and not any(
                name == character.name for _, name in self.initiative_order):
            roll = random.randint(1, 20) + int(getattr(character, 'initiative', 0) or 0)
            self.initiative_order.append((roll, character.name))
    def _select_attack(self, attacker, attack_name=None):
        if isinstance(attacker, Character) and attacker in self.offline_players and getattr(attacker, 'attacks', []):
            selected = next((a for a in attacker.attacks if a.get('name') == attack_name), attacker.attacks[0])
            info = dict(selected)
            info['to_hit'] = getattr(attacker, 'attack_bonus', 0) + getattr(attacker, 'proficiency', 0)
            return info
        if isinstance(attacker, Character):
            from utils.data_manager import WEAPON_DATA
            info = dict(WEAPON_DATA.get(attacker.equipped_weapon, WEAPON_DATA.get('Unbewaffneter Schlag', {'damage': '1', 'range': 1})))
            ability = info.get('ability') or 'Stärke'
            modifier = (attacker.abilities.get(ability, 10) - 10) // 2
            info['to_hit'] = modifier + (2 + (attacker.level - 1) // 4)
            info['damage_modifier'] = modifier
            return info
        cands = [a for a in (getattr(attacker, 'attacks', None) or []) if isinstance(a, dict)]
        if attack_name:
            for a in cands:
                if a.get('name') == attack_name:
                    return a
        return cands[0] if cands else {'name': 'Angriff', 'damage': '1d4'}
