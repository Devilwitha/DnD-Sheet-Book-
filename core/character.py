import random
from utils.data_manager import RACE_DATA, CLASS_DATA, SPELL_DATA

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
        self.inventory = []  # Geändert zu einer Liste von Dictionaries
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
        self.max_spell_slots = {}
        self.current_spell_slots = {}
        self.max_hit_dice = 0
        self.hit_dice = 0
        self.fighting_style = None

    def initialize_character(self):
        """Sammelt alle Daten bei der Erstellung oder beim Laden."""
        self.update_race_bonuses_and_speed()
        self.collect_proficiencies_and_languages()
        self.calculate_initial_hp()
        self.initialize_hit_dice()
        self.update_features()
        self.prepare_spellbook()
        self.initialize_spell_slots()
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

    def initialize_hit_dice(self):
        """Initialisiert die Trefferwürfel des Charakters."""
        self.max_hit_dice = self.level
        self.hit_dice = self.level

    def initialize_spell_slots(self):
        """Initialisiert die Zauberplätze basierend auf Klasse und Level."""
        class_info = CLASS_DATA.get(self.char_class, {})
        progression = class_info.get("progression", {})
        level_progression = progression.get(self.level, {})
        self.max_spell_slots = level_progression.get("spell_slots", {})
        self.current_spell_slots = self.max_spell_slots.copy()

    def long_rest(self):
        """Führt eine lange Rast aus."""
        self.hit_points = self.max_hit_points
        self.current_spell_slots = self.max_spell_slots.copy()
        # Man erhält die Hälfte der maximalen Trefferwürfel zurück (mindestens 1)
        recovered_dice = max(1, self.max_hit_dice // 2)
        self.hit_dice = min(self.max_hit_dice, self.hit_dice + recovered_dice)
        # Hier könnten weitere Dinge zurückgesetzt werden, z.B. bestimmte Klassen-Features

    def short_rest(self, dice_to_spend):
        """Führt eine kurze Rast aus und gibt die Menge der geheilten HP zurück."""
        if self.hit_dice <= 0:
            return 0

        dice_to_spend = min(dice_to_spend, self.hit_dice)
        healed_amount = 0
        hit_die_type = CLASS_DATA.get(self.char_class, {}).get("hit_die", 8)
        con_modifier = (self.abilities["Konstitution"] - 10) // 2

        for _ in range(dice_to_spend):
            roll = random.randint(1, hit_die_type)
            healed_amount += max(0, roll + con_modifier) # Heilung kann nicht negativ sein

        self.hit_points = min(self.max_hit_points, self.hit_points + healed_amount)
        self.hit_dice -= dice_to_spend
        return healed_amount

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
        self.max_hit_dice = self.level
        self.hit_dice = self.max_hit_dice # Volle Trefferwürfel bei Levelaufstieg

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
        self.initialize_spell_slots()
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

    def to_dict(self):
        """Serializes the character object to a dictionary."""
        # self.spells keys can be integers, convert them to strings for JSON
        spells_str_keys = {str(k): v for k, v in self.spells.items()}
        return {
            "name": self.name,
            "race": self.race,
            "char_class": self.char_class,
            "level": self.level,
            "base_abilities": self.base_abilities,
            "abilities": self.abilities,
            "hit_points": self.hit_points,
            "max_hit_points": self.max_hit_points,
            "speed": self.speed,
            "initiative": self.initiative,
            "armor_class": self.armor_class,
            "inventory": self.inventory,
            "equipment": self.equipment,
            "currency": self.currency,
            "equipped_weapon": self.equipped_weapon,
            "background": self.background,
            "alignment": self.alignment,
            "personality_traits": self.personality_traits,
            "ideals": self.ideals,
            "bonds": self.bonds,
            "flaws": self.flaws,
            "features": self.features,
            "proficiencies": self.proficiencies,
            "languages": self.languages,
            "spells": spells_str_keys,
            "max_spell_slots": self.max_spell_slots,
            "current_spell_slots": self.current_spell_slots,
            "max_hit_dice": self.max_hit_dice,
            "hit_dice": self.hit_dice,
            "fighting_style": self.fighting_style,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a character object from a dictionary."""
        char = cls(data["name"], data["race"], data["char_class"])
        for key, value in data.items():
            # Spells need to be converted back to int keys
            if key == "spells":
                value = {int(k): v for k, v in value.items()}
            setattr(char, key, value)
        return char
