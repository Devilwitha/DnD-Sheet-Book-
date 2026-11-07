import random
import uuid
import copy
from utils.data_manager import RACE_DATA, CLASS_DATA, SPELL_DATA, FIGHTING_STYLE_DATA

class Character:
    """Finale Version der Charakter-Klasse mit allen neuen Attributen."""
    def __init__(self, name, race, char_class):
        self.character_id = str(uuid.uuid4())
        self.name = name
        self.race = race
        self.char_class = char_class
        self.level = 1
        self.base_abilities = {
            'Stärke': 10, 'Geschicklichkeit': 10, 'Konstitution': 10,
            'Intelligenz': 10, 'Weisheit': 10, 'Charisma': 10
        }
        self.abilities = self.base_abilities.copy()
        self.hit_points = 0
        self.max_hit_points = 0
        self.speed = 6
        self.actions_per_turn = 1
        self.initiative = 0
        self.armor_class = 10
        self.inventory = []
        self.equipment = {}
        self.currency = {'KP': 0, 'SP': 0, 'EP': 0, 'GM': 0, 'PP': 0}
        self.equipped_weapon = 'Unbewaffneter Schlag'
        self.background = ''
        self.alignment = ''
        self.personality_traits = ''
        self.ideals = ''
        self.bonds = ''
        self.flaws = ''
        self.features = []
        self.proficiencies = []
        self.languages = []
        self.spells = {}
        self.max_spell_slots = {}
        self.current_spell_slots = {}
        self.max_hit_dice = 0
        self.hit_dice = 0
        self.fighting_style = None
        self.selected_skills = []
        self.selected_languages = []
        self.half_elf_bonuses = {}
        self.initialization_complete = False

    def initialize_character(self):
        """Full initialization exactly once; afterwards only derived values are recalculated."""
        if self.initialization_complete:
            self.recalculate_derived()
            return
        self.update_race_bonuses_and_speed()
        self.collect_proficiencies_and_languages()
        self.calculate_initial_hp()
        self.initialize_hit_dice()
        self.update_features()
        self.prepare_spellbook()
        self.initialize_spell_slots()
        self.calculate_initiative()
        self.calculate_armor_class()
        self.initialization_complete = True

    def update_race_bonuses_and_speed(self):
        self.abilities = self.base_abilities.copy()
        race_info = RACE_DATA.get(self.race, {})
        bonuses = race_info.get('ability_score_increase', {})
        for ability, bonus in bonuses.items():
            if ability in self.abilities:
                self.abilities[ability] += bonus
        # Half-elf bonuses are stored separately and applied here only (never in base_abilities)
        for ability in (self.half_elf_bonuses or {}).get('abilities', []):
            if ability in self.abilities:
                self.abilities[ability] += 1
        speed_in_meters = race_info.get('speed', 9)
        self.speed = int(speed_in_meters / 1.5)

    def collect_proficiencies_and_languages(self):
        """Collects proficiencies and languages from race, class and stored choices."""
        race_info = RACE_DATA.get(self.race, {})
        class_info = CLASS_DATA.get(self.char_class, {})
        proficiencies = set(race_info.get('proficiencies', []))
        proficiencies.update(class_info.get('proficiencies', []))
        proficiencies.update(self.selected_skills or [])
        proficiencies.update((self.half_elf_bonuses or {}).get('skills', []))
        self.proficiencies = sorted(proficiencies)

        languages = set(race_info.get('languages', []))
        languages.update(class_info.get('languages', []))
        languages.update(self.selected_languages or [])
        self.languages = sorted(languages)

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
        """Initializes spell slots (string keys) based on class and level."""
        progression = CLASS_DATA.get(self.char_class, {}).get('progression', {})
        slots = progression.get(self.level, {}).get('spell_slots', {})
        self.max_spell_slots = {str(k): v for k, v in slots.items()}
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
        class_features = CLASS_DATA.get(self.char_class, {}).get('features', {})
        class_names = {f['name'] for features in class_features.values() for f in features}
        self.features = [dict(f) for f in self.features if f.get('name') not in class_names
                         and not f.get('name', '').startswith('Kampfstil:')]
        for lvl in range(1, self.level + 1):
            if lvl in class_features:
                self.features.extend(dict(f) for f in class_features[lvl])
        if self.fighting_style:
            self.features.append({
                'name': f'Kampfstil: {self.fighting_style}',
                'desc': FIGHTING_STYLE_DATA.get(self.fighting_style, '')
            })

    def prepare_spellbook(self):
        """Ensures the spells dictionary exists."""
        if not hasattr(self, 'spells'):
            self.spells = {}

    def level_up(self, choices):
        """Validates first, then levels up. Raises ValueError without changing anything."""
        data = self._validate_level_up(choices)
        old_level = self.level
        old_mod = (self.abilities['Konstitution'] - 10) // 2

        for ability in data['increases']:
            self.base_abilities[ability] += 1
        self.update_race_bonuses_and_speed()
        new_mod = (self.abilities['Konstitution'] - 10) // 2
        retro = (new_mod - old_mod) * old_level

        self.level = old_level + 1
        gain = max(1, data['hp_roll'] + new_mod) + retro
        self.max_hit_points = max(1, self.max_hit_points + gain)
        self.hit_points = min(self.max_hit_points, max(0, self.hit_points + gain))
        self.max_hit_dice = self.level
        self.hit_dice = min(self.max_hit_dice, self.hit_dice + 1)

        spells = data['known']
        for cantrip in data['cantrips']:
            spells.setdefault(0, []).append(cantrip)
        for name in data['spells']:
            spells.setdefault(SPELL_DATA[name]['level'], []).append(name)
        if data['rep_old']:
            for lvl, lst in spells.items():
                if lvl > 0 and data['rep_old'] in lst:
                    lst.remove(data['rep_old'])
            spells.setdefault(SPELL_DATA[data['rep_new']]['level'], []).append(data['rep_new'])
        self.spells = spells

        self.collect_proficiencies_and_languages()
        self.update_features()
        self._sync_spell_slots(grant_new=True)
        self.calculate_initiative()
        self.calculate_armor_class()
        return {'hp_gain': gain}

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
                    else:
                        # Handle numeric-string keys like '2'
                        try:
                            new_key = int(level_key)
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
        dex_modifier = (self.abilities['Geschicklichkeit'] - 10) // 2
        ac = 10 + dex_modifier
        # Unarmored Defense (equipment values are additive AC bonuses)
        armor_words = ('rüstung', 'armor', 'ketten', 'leder', 'platten', 'brustpanzer', 'schienen', 'schuppen')
        armored = any(any(word in item.casefold() for word in armor_words) for item in self.equipment)
        shield = any('schild' in item.casefold() or 'shield' in item.casefold() for item in self.equipment)
        if not armored and self.char_class in ('Barbar', 'Barbarian'):
            ac += (self.abilities['Konstitution'] - 10) // 2
        elif not armored and not shield and self.char_class in ('Mönch', 'Monk'):
            ac += (self.abilities['Weisheit'] - 10) // 2
        for item, bonus in (self.equipment or {}).items():
            try:
                ac += int(bonus)
            except (TypeError, ValueError):
                continue
        self.armor_class = ac

    def to_dict(self):
        """Serializes the character object to a dictionary."""
        spells_str_keys = {str(k): list(v) for k, v in self.spells.items()}
        return {
            'character_id': self.character_id,
            'name': self.name,
            'race': self.race,
            'char_class': self.char_class,
            'level': self.level,
            'base_abilities': self.base_abilities,
            'abilities': self.abilities,
            'hit_points': self.hit_points,
            'max_hit_points': self.max_hit_points,
            'speed': self.speed,
            'actions_per_turn': getattr(self, 'actions_per_turn', 1),
            'initiative': self.initiative,
            'armor_class': self.armor_class,
            'inventory': self.inventory,
            'equipment': self.equipment,
            'currency': self.currency,
            'equipped_weapon': self.equipped_weapon,
            'background': self.background,
            'alignment': self.alignment,
            'personality_traits': self.personality_traits,
            'ideals': self.ideals,
            'bonds': self.bonds,
            'flaws': self.flaws,
            'features': self.features,
            'proficiencies': self.proficiencies,
            'languages': self.languages,
            'spells': spells_str_keys,
            'max_spell_slots': self.max_spell_slots,
            'current_spell_slots': self.current_spell_slots,
            'max_hit_dice': self.max_hit_dice,
            'hit_dice': self.hit_dice,
            'fighting_style': self.fighting_style,
            'selected_skills': self.selected_skills,
            'selected_languages': self.selected_languages,
            'half_elf_bonuses': self.half_elf_bonuses,
            'initialization_complete': self.initialization_complete,
            'attacks': getattr(self, 'attacks', []),
            'attack_bonus': getattr(self, 'attack_bonus', 0),
            'proficiency': getattr(self, 'proficiency', 0),
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a character from validated data (whitelisted fields only)."""
        from utils.formats import validate_character  # lazy import avoids import cycle
        data = validate_character(data)
        char = cls(data['name'], data['race'], data['char_class'])
        if data.get('character_id'):
            char.character_id = str(data['character_id'])
        fields = [
            'attacks', 'attack_bonus', 'proficiency',
            'level', 'base_abilities', 'abilities', 'hit_points', 'max_hit_points', 'speed',
            'actions_per_turn', 'initiative', 'armor_class', 'inventory', 'equipment',
            'currency', 'equipped_weapon', 'background', 'alignment', 'personality_traits',
            'ideals', 'bonds', 'flaws', 'features', 'proficiencies', 'languages', 'spells',
            'max_spell_slots', 'current_spell_slots', 'max_hit_dice', 'hit_dice',
            'fighting_style', 'selected_skills', 'selected_languages', 'half_elf_bonuses',
        ]
        for key in fields:
            if key in data:
                setattr(char, key, copy.deepcopy(data[key]))
        char.normalize_spells()
        char.max_spell_slots = {str(k): v for k, v in (char.max_spell_slots or {}).items()}
        char.current_spell_slots = {str(k): v for k, v in (char.current_spell_slots or {}).items()}
        char.initialization_complete = bool(data.get('initialization_complete')) or data.get('max_hit_points', 0) > 0
        if 'abilities' not in data:
            char.update_race_bonuses_and_speed()
        return char
    def recalculate_derived(self):
        """Recalculates derived values while preserving HP, resources, choices and inventory."""
        old_mod = (self.abilities.get('Konstitution', 10) - 10) // 2
        self.update_race_bonuses_and_speed()
        new_mod = (self.abilities.get('Konstitution', 10) - 10) // 2
        delta = (new_mod - old_mod) * self.level
        if delta:
            self.max_hit_points = max(1, self.max_hit_points + delta)
            self.hit_points = max(0, self.hit_points + delta)
        self.hit_points = min(self.hit_points, self.max_hit_points)
        self.collect_proficiencies_and_languages()
        self.update_features()
        self.prepare_spellbook()
        self.max_hit_dice = self.level
        self.hit_dice = max(0, min(self.hit_dice, self.max_hit_dice))
        self._sync_spell_slots()
        self.calculate_initiative()
        self.calculate_armor_class()
    def _sync_spell_slots(self, grant_new=False):
        """Updates max slots to the current level without refilling used slots."""
        progression = CLASS_DATA.get(self.char_class, {}).get('progression', {})
        raw = progression.get(self.level, {}).get('spell_slots', {})
        new_max = {str(k): v for k, v in raw.items()}
        old_max = {str(k): v for k, v in (self.max_spell_slots or {}).items()}
        cur = {str(k): v for k, v in (self.current_spell_slots or {}).items()}
        result = {}
        for k, v in new_max.items():
            if grant_new:
                c = cur.get(k, 0) + max(0, v - old_max.get(k, 0))
            else:
                c = cur.get(k, v)
            result[k] = max(0, min(v, c))
        self.max_spell_slots = new_max
        self.current_spell_slots = result
    def _spell_dict_copy(self):
        """Non-mutating copy of self.spells with integer keys."""
        result = {}
        for key, spell_list in (self.spells or {}).items():
            try:
                k = 0 if key == 'cantrips' else int(str(key).replace('level', ''))
            except ValueError:
                continue
            bucket = result.setdefault(k, [])
            for spell in spell_list:
                if spell not in bucket:
                    bucket.append(spell)
        return result
    def _validate_level_up(self, choices):
        """Validates all level-up choices without mutating the character."""
        if not isinstance(choices, dict):
            raise ValueError('Ungültige Auswahl für den Stufenaufstieg.')
        if self.level >= 20:
            raise ValueError('Maximalstufe 20 ist bereits erreicht.')
        new_level = self.level + 1
        class_data = CLASS_DATA.get(self.char_class, {})
        hit_die = class_data.get('hit_die', 8)

        increases = list(choices.get('ability_increase') or [])
        if len(increases) not in (0, 2):
            raise ValueError('Es müssen genau 2 Attributspunkte verteilt werden.')
        eligible = any('Attributswerterhöhung' in f.get('name', '') for f in class_data.get('features', {}).get(new_level, []))
        if bool(increases) != eligible:
            raise ValueError('Attributsauswahl passt nicht zu dieser Stufe.')
        for ability in set(increases):
            if ability not in self.base_abilities:
                raise ValueError(f'Unbekanntes Attribut: {ability}')
            if self.abilities[ability] + increases.count(ability) > 20:
                raise ValueError(f'{ability} kann nicht über 20 steigen.')

        roll = choices.get('hp_roll')
        if roll is None:
            roll = random.randint(1, hit_die)
        elif isinstance(roll, bool) or not isinstance(roll, int) or not 1 <= roll <= hit_die:
            raise ValueError('Ungültiger HP-Wurf.')

        spells = self._spell_dict_copy()
        known = {s for lvl, lst in spells.items() if lvl > 0 for s in lst}
        known_cantrips = set(spells.get(0, []))
        new_cantrips = list(choices.get('new_cantrips') or [])
        new_spells = list(choices.get('new_spells') or [])
        rep_old = choices.get('replaced_spell')
        rep_new = choices.get('replacement_spell')
        none_vals = (None, '', 'Keiner')
        if rep_old in none_vals and rep_new in none_vals:
            rep_old = rep_new = None
        elif rep_old in none_vals or rep_new in none_vals:
            raise ValueError('Zauberwechsel benötigt alten und neuen Zauber.')

        progression = class_data.get('progression', {})
        old_prog = progression.get(self.level, {})
        new_prog = progression.get(new_level, {})
        if new_cantrips or new_spells or rep_old:
            if not new_prog:
                raise ValueError('Diese Klasse lernt auf dieser Stufe keine Zauber.')
            cantrip_limit = new_prog.get('cantrips_known', 0) - old_prog.get('cantrips_known', 0)
            spell_limit = new_prog.get('spells_known', 0) - old_prog.get('spells_known', 0)
            if self.char_class in ('Kleriker', 'Druide'):
                spell_limit = 1
            elif self.char_class == 'Paladin':
                cha = (self.abilities['Charisma'] - 10) // 2
                spell_limit = max(0, (cha + new_level // 2) - (cha + self.level // 2))
                if new_level == 2:
                    spell_limit = cha + 1
            max_level = 0
            for lvl, n in new_prog.get('spell_slots', {}).items():
                if n > 0:
                    max_level = max(max_level, int(lvl))
            spell_list = class_data.get('spell_list', {})

            def names_at(level):
                return spell_list.get(level) or spell_list.get(str(level)) or []

            if len(new_cantrips) != len(set(new_cantrips)) or len(new_cantrips) > max(0, cantrip_limit):
                raise ValueError('Zu viele Zaubertricks gewählt.')
            for c in new_cantrips:
                if c not in names_at(0) or c in known_cantrips:
                    raise ValueError(f'Zaubertrick nicht erlaubt: {c}')
            if len(new_spells) != len(set(new_spells)) or len(new_spells) > max(0, spell_limit):
                raise ValueError('Zu viele Zauber gewählt.')

            def check_new(name):
                lvl = SPELL_DATA.get(name, {}).get('level', -1)
                if not 1 <= lvl <= max_level or name not in names_at(lvl):
                    raise ValueError(f'Zauber nicht erlaubt: {name}')

            for s in new_spells:
                check_new(s)
                if s in known:
                    raise ValueError(f'Zauber bereits bekannt: {s}')
            if rep_old:
                if self.char_class != 'Barde':
                    raise ValueError('Diese Klasse darf keine Zauber tauschen.')
                if rep_old not in known:
                    raise ValueError(f'Zauber nicht bekannt: {rep_old}')
                check_new(rep_new)
                if rep_new == rep_old or rep_new in known or rep_new in new_spells:
                    raise ValueError(f'Ungültiger Ersatzzauber: {rep_new}')

        return {'increases': increases, 'hp_roll': roll, 'cantrips': new_cantrips,
                'spells': new_spells, 'rep_old': rep_old, 'rep_new': rep_new, 'known': spells}
