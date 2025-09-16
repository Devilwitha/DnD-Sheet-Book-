import random
from core.character import Character
from core.enemy import Enemy
from utils.non_ui_helpers import roll_dice
from utils.data_manager import ENEMY_DATA

class GameManager:
    """
    Manages the core game logic, state, and rules, decoupled from the UI.
    """
    def __init__(self, logger_func=print):
        self.logger = logger_func
        self.offline_players = []
        self.online_players = {} # addr -> Character
        self.enemies = []
        self.initiative_order = []
        self.map_data = None

        self.current_turn_index = -1
        self.turn_action_state = {}

    def get_character_or_enemy_by_name(self, name):
        """Retrieves a character or enemy instance by its unique name."""
        for char in self.online_players.values():
            if char.name == name:
                return char
        for enemy in self.enemies:
            if enemy.name == name:
                return enemy
        return None

    def roll_initiative_for_all(self):
        """Rolls initiative for all online players and enemies."""
        self.initiative_order = []
        for char in self.online_players.values():
            roll = random.randint(1, 20) + char.initiative
            self.initiative_order.append((roll, char.name))
        for enemy in self.enemies:
            # Enemies don't have an initiative attribute in the model, so roll d20
            roll = random.randint(1, 20)
            self.initiative_order.append((roll, enemy.name))

        self.initiative_order.sort(key=lambda x: x[0], reverse=True)
        self.logger("Initiative has been rolled.")

        if self.initiative_order:
            self.current_turn_index = 0
            self.start_next_turn()
        else:
            self.current_turn_index = -1

        return self.initiative_order

    def end_turn(self):
        """Ends the current turn and proceeds to the next in the initiative order."""
        if not self.initiative_order:
            return None
        self.current_turn_index = (self.current_turn_index + 1) % len(self.initiative_order)
        return self.start_next_turn()

    def start_next_turn(self):
        """Initializes the state for the start of the next turn."""
        if not self.initiative_order or self.current_turn_index == -1:
            return None

        _, current_char_name = self.initiative_order[self.current_turn_index]
        character = self.get_character_or_enemy_by_name(current_char_name)

        if character:
            self.turn_action_state = {
                'movement_left': character.speed,
                'attacks_left': character.actions_per_turn
            }
            self.logger(f"Next turn: {current_char_name}")
        else:
            # This might happen if the character was removed (e.g., defeated)
            # but the turn index wasn't adjusted. Let's try to advance.
            self.logger(f"Character {current_char_name} not found, advancing turn.")
            return self.end_turn()

        return self.get_current_turn_info()

    def get_current_turn_info(self):
        """Returns a dictionary with the current turn's state."""
        if self.current_turn_index == -1 or not self.initiative_order:
            return {
                "name": None,
                "pos": None,
                "state": self.turn_action_state
            }

        current_char_name = self.initiative_order[self.current_turn_index][1]
        current_pos = None
        if self.map_data and self.map_data.get('tiles'):
            for pos, tile in self.map_data['tiles'].items():
                if tile.get('object') == current_char_name:
                    current_pos = pos
                    break

        return {
            "name": current_char_name,
            "pos": current_pos,
            "state": self.turn_action_state
        }

    def move_object(self, obj_name, to_pos):
        """
        Moves an object on the map. Returns True on success, False on failure.
        """
        current_turn_name = self.get_current_turn_info()['name']
        if obj_name != current_turn_name:
            self.logger(f"Error: {obj_name} tried to move out of turn.")
            return False, "Cannot move out of turn."

        from_pos = None
        for pos, tile in self.map_data['tiles'].items():
            if tile.get('object') == obj_name:
                from_pos = pos
                break

        if not from_pos:
            return False, f"{obj_name} not found on map."

        dist = abs(to_pos[0] - from_pos[0]) + abs(to_pos[1] - from_pos[1])
        movement_left = self.turn_action_state.get('movement_left', 0)

        if dist > movement_left:
            return False, "Not enough movement left."

        self.map_data['tiles'][from_pos]['object'] = None
        self.map_data['tiles'][to_pos]['object'] = obj_name
        self.turn_action_state['movement_left'] -= dist

        self.logger(f"{obj_name} moved from {from_pos} to {to_pos}.")
        return True, "Move successful."

    def handle_attack(self, attacker_name, target_name, attack_roll=None, damage_roll=None):
        """
        Handles an attack from one character/enemy to another.
        Returns a dictionary with the outcome.
        """
        current_turn_name = self.get_current_turn_info()['name']
        if attacker_name != current_turn_name:
            return {"success": False, "reason": "Cannot attack out of turn."}

        if self.turn_action_state.get('attacks_left', 0) <= 0:
            return {"success": False, "reason": "No attacks left."}

        attacker = self.get_character_or_enemy_by_name(attacker_name)
        target = self.get_character_or_enemy_by_name(target_name)

        if not attacker or not target:
            return {"success": False, "reason": "Attacker or target not found."}

        # For DM-controlled enemies, we need to select an attack
        # For this generic handler, we assume the first attack if not specified
        attack_info = attacker.attacks[0] if isinstance(attacker, Enemy) and attacker.attacks else {"damage": "1d4"}

        # Use provided rolls for testing, otherwise roll randomly
        final_attack_roll = attack_roll if attack_roll is not None else random.randint(1, 20)

        outcome = {"success": True, "hit": False, "damage": 0, "target_hp": 0}

        if final_attack_roll >= target.armor_class:
            damage = damage_roll if damage_roll is not None else roll_dice(attack_info.get('damage', '1d4'))

            if isinstance(target, Character):
                target.hit_points -= damage
                outcome['target_hp'] = target.hit_points
            else: # Enemy
                target.hp -= damage
                outcome['target_hp'] = target.hp

            outcome['hit'] = True
            outcome['damage'] = damage
            self.logger(f"HIT! {target.name} takes {damage} damage. HP is now {outcome['target_hp']}.")

            if outcome['target_hp'] <= 0:
                self.handle_character_death(target.name)
                outcome['defeated'] = True
        else:
            self.logger(f"MISS! {attacker.name}'s attack on {target.name} failed.")

        self.turn_action_state['attacks_left'] -= 1
        return outcome

    def handle_character_death(self, character_name):
        """Handles the removal of a character or enemy from the game upon death."""
        self.logger(f"{character_name} has been defeated!")

        defeated_index = -1
        for i, (_, name) in enumerate(self.initiative_order):
            if name == character_name:
                defeated_index = i
                break

        char_or_enemy = self.get_character_or_enemy_by_name(character_name)
        if isinstance(char_or_enemy, Enemy):
            self.enemies.remove(char_or_enemy)
        # We don't remove players, just mark them as defeated or something later

        # Remove from initiative
        self.initiative_order = [item for item in self.initiative_order if item[1] != character_name]

        # Adjust turn index if the defeated character was before or at the current turn
        if defeated_index != -1 and defeated_index <= self.current_turn_index:
            self.current_turn_index -= 1

        # Remove from map
        for pos, tile in self.map_data['tiles'].items():
            if tile.get('object') == character_name:
                tile['object'] = None
                break

        # Check for victory
        if not any(isinstance(self.get_character_or_enemy_by_name(name), Enemy) for _, name in self.initiative_order):
            self.logger("VICTORY! All enemies have been defeated.")
            self.current_turn_index = -1 # End combat
            return "VICTORY"

        return "DEFEATED"

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
