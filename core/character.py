import random
from data_manager import RACE_DATA, CLASS_DATA, SPELL_DATA

class Character:
    """Finale Version der Charakter-Klasse mit allen neuen Attributen."""
    def __init__(self, name, race, char_class):
        self.name = name
        self.race = race
        self.char_class = char_class
        self.level = 1
        self.base_abilities = {
            "Stärke": 10, "Geschicklichkeit": 10, "Konstitution": 10,
            "Intelligenz": 10, "Weisheit": 10, "Charisma": 10
        }
        self.abilities = self.base_abilities.copy()
        self.hit_points = 0
        self.max_hit_points = 0
        self.speed = 0
        self.initiative = 0
        self.armor_class = 10
        self.inventory = {}  # Geändert zu Dictionary für die Anzahl
        self.equipment = {}  # Ausrüstung mit AC-Bonus
        self.currency = {"KP": 0, "SP": 0, "EP": 0, "GM": 0, "PP": 0}
        self.equipped_weapon = "Unbewaffneter Schlag"
        self.background = ""
        self.alignment = ""
        self.personality_traits = ""
        self.ideals = ""
        self.bonds = ""
        self.flaws = ""
        self.features = []
        self.proficiencies = []
        self.languages = []
        self.spells = {}  # Für bekannte Zauber
        self.fighting_style = None

    def initialize_character(self):
        """Sammelt alle Daten bei der Erstellung oder beim Laden."""
        self.spells = {}
        self.fighting_style = None
        self.update_race_bonuses_and_speed()
        self.collect_proficiencies_and_languages()
        self.calculate_initial_hp()
        self.update_features()
        self.prepare_spellbook()
        self.calculate_initiative()
        self.calculate_armor_class()

    def update_race_bonuses_and_speed(self):
        self.abilities = self.base_abilities.copy()
        race_info = RACE_DATA.get(self.race, {})
        bonuses = race_info.get("ability_score_increase", {})
        for ability, bonus in bonuses.items():
            if ability in self.abilities:
                self.abilities[ability] += bonus
        self.speed = race_info.get("speed", 9)

    def collect_proficiencies_and_languages(self):
        """Sammelt Kompetenzen und Sprachen von Rasse und Klasse."""
        race_info = RACE_DATA.get(self.race, {})
        class_info = CLASS_DATA.get(self.char_class, {})
        # Verwendet Sets, um Duplikate automatisch zu entfernen
        proficiencies = set(race_info.get("proficiencies", []))
        proficiencies.update(class_info.get("proficiencies", []))
        self.proficiencies = sorted(list(proficiencies))

        languages = set(race_info.get("languages", []))
        languages.update(class_info.get("languages", []))
        self.languages = sorted(list(languages))

    def calculate_initial_hp(self):
        hit_die = CLASS_DATA.get(self.char_class, {}).get("hit_die", 8)
        con_modifier = (self.abilities["Konstitution"] - 10) // 2
        self.max_hit_points = hit_die + con_modifier
        self.hit_points = self.max_hit_points

    def update_features(self):
        self.features = []
        class_features = CLASS_DATA.get(self.char_class, {}).get("features", {})
        for lvl in range(1, self.level + 1):
            if lvl in class_features:
                self.features.extend(class_features[lvl])

    def prepare_spellbook(self):
        """Ensures the spells dictionary exists."""
        if not hasattr(self, 'spells'):
            self.spells = {}

    def level_up(self, choices):
        self.level += 1
        hit_die = CLASS_DATA.get(self.char_class, {}).get("hit_die", 8)
        con_modifier = (self.abilities["Konstitution"] - 10) // 2
        hp_increase = random.randint(1, hit_die) + con_modifier
        self.max_hit_points += max(1, hp_increase)
        self.hit_points = self.max_hit_points

        if "ability_increase" in choices:
            for ability in choices["ability_increase"]:
                self.base_abilities[ability] += 1

        # Handle spell choices
        if "new_cantrips" in choices and choices["new_cantrips"]:
            if 0 not in self.spells:
                self.spells[0] = []
            for cantrip in choices["new_cantrips"]:
                if cantrip not in self.spells[0]:
                    self.spells[0].append(cantrip)

        if "new_spells" in choices and choices["new_spells"]:
            for spell_name in choices["new_spells"]:
                spell_info = SPELL_DATA.get(spell_name, {})
                spell_level = spell_info.get("level", -1)
                if spell_level > 0:
                    if spell_level not in self.spells:
                        self.spells[spell_level] = []
                    if spell_name not in self.spells[spell_level]:
                        self.spells[spell_level].append(spell_name)

        if "replaced_spell" in choices and "replacement_spell" in choices:
            old_spell_name = choices["replaced_spell"]
            new_spell_name = choices["replacement_spell"]
            if old_spell_name and new_spell_name and old_spell_name != "Keiner" and new_spell_name != "Keiner":
                # Remove old spell
                for level, spell_list in self.spells.items():
                    if level > 0 and old_spell_name in spell_list:
                        spell_list.remove(old_spell_name)
                        # Add new spell
                        new_spell_info = SPELL_DATA.get(new_spell_name, {})
                        new_spell_level = new_spell_info.get("level", -1)
                        if new_spell_level > 0:
                            if new_spell_level not in self.spells:
                                self.spells[new_spell_level] = []
                            if new_spell_name not in self.spells[new_spell_level]:
                                self.spells[new_spell_level].append(new_spell_name)
                        break

        self.update_race_bonuses_and_speed()
        self.update_features()
        self.calculate_initiative()
        self.calculate_armor_class()

    def normalize_spells(self):
        """Converts spell dictionary keys to integers for compatibility."""
        normalized_spells = {}
        if hasattr(self, 'spells') and self.spells:
            for level_key, spell_list in self.spells.items():
                new_key = -1
                if isinstance(level_key, str):
                    if level_key == 'cantrips':
                        new_key = 0
                    elif 'level' in level_key:
                        try:
                            new_key = int(level_key.replace('level', ''))
                        except ValueError:
                            continue
                elif isinstance(level_key, int):
                    new_key = level_key

                if new_key != -1:
                    if new_key not in normalized_spells:
                        normalized_spells[new_key] = []
                    for spell in spell_list:
                        if spell not in normalized_spells[new_key]:
                            normalized_spells[new_key].append(spell)
        self.spells = normalized_spells

    def calculate_initiative(self):
        self.initiative = (self.abilities["Geschicklichkeit"] - 10) // 2

    def get_proficiency_bonus(self):
        return (self.level - 1) // 4 + 2

    def calculate_armor_class(self):
        dex_modifier = (self.abilities["Geschicklichkeit"] - 10) // 2
        ac = 10 + dex_modifier
        for item, bonus in self.equipment.items():
            ac += bonus
        self.armor_class = ac
