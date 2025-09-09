from kivy.config import Config
# Konfiguration für Kivy, bevor andere Module importiert werden
Config.set('kivy', 'keyboard_mode', 'dock')
Config.set('graphics', 'rotation', 0)
# Setzt die Höhe der Bildschirmtastatur auf 600 Pixel
Config.set('kivy', 'keyboard_height', '600')

import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.checkbox import CheckBox
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.slider import Slider
from kivy.uix.switch import Switch
from kivy.uix.filechooser import FileChooserListView
from kivy.core.window import Window
from kivy.clock import Clock
import random
import pickle
import os
import subprocess
import sys
from functools import partial
import json

SETTINGS_FILE = 'settings.json'

def load_settings():
    """Lädt die Einstellungen aus der JSON-Datei."""
    defaults = {
        'button_transparency': 1.0,
        'transparency_enabled': True,
        'background_enabled': True,
        'background_path': 'osbackground/hmbg.png'
    }
    if not os.path.exists(SETTINGS_FILE):
        return defaults
    try:
        with open(SETTINGS_FILE, 'r') as f:
            loaded_settings = json.load(f)
        # Fügt die geladenen Einstellungen zu den Standardeinstellungen hinzu, um fehlende Schlüssel zu ergänzen
        defaults.update(loaded_settings)
        return defaults
    except (IOError, json.JSONDecodeError):
        return defaults

def save_settings(settings):
    """Speichert die Einstellungen in der JSON-Datei."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def apply_transparency_to_widget(widget):
    """Durchläuft ein Widget und seine Kinder und wendet die Transparenzeinstellung auf alle Buttons an."""
    settings = load_settings()
    
    # Prüfen, ob die Transparenz überhaupt aktiviert ist
    if not settings.get('transparency_enabled', True):
        transparency = 1.0
    else:
        transparency = settings.get('button_transparency', 1.0)
        
    color = (1, 1, 1, transparency)

    # Diese innere Funktion wird rekursiv aufgerufen
    def apply_to_children(w):
        if isinstance(w, Button):
            w.background_color = color
            if transparency < 1.0:
                w.background_normal = ''
            else:
                w.background_normal = 'atlas://data/images/defaulttheme/button'
        
        # Rekursiv auf alle Kinder anwenden
        if hasattr(w, 'children'):
            for child in w.children:
                apply_to_children(child)

    apply_to_children(widget)

def apply_background(screen):
    """Fügt den Hintergrund zu einem Bildschirm hinzu oder entfernt ihn, basierend auf den Einstellungen."""
    settings = load_settings()
    
    # Entferne zuerst einen eventuell vorhandenen alten Hintergrund
    old_bg = getattr(screen, '_background_image', None)
    if old_bg and old_bg.parent:
        screen.remove_widget(old_bg)
    
    if settings.get('background_enabled', True):
        bg_path = settings.get('background_path', 'osbackground/hmbg.png')
        if os.path.exists(bg_path):
            try:
                background = Image(source=bg_path, allow_stretch=True, keep_ratio=False)
                screen._background_image = background
                screen.add_widget(background, index=len(screen.children))
            except Exception as e:
                print(f"Fehler beim Laden des Hintergrundbildes: {e}")


# Importiert die Daten aus der separaten Datei
from dnd_data import CLASS_DATA, RACE_DATA, WEAPON_DATA, SPELL_DATA, ALIGNMENT_DATA, BACKGROUND_DATA, SKILL_LIST, FIGHTING_STYLE_DATA

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

class MainMenu(Screen):
    """Hauptmenü-Bildschirm zum Erstellen oder Laden eines Charakters."""
    def __init__(self, **kwargs):
        super(MainMenu, self).__init__(**kwargs)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Image(source='logo/logo.png'))
        
        self.new_char_button = Button(text="Neuen Charakter erstellen", on_press=self.switch_to_creator)
        layout.add_widget(self.new_char_button)
        
        self.load_char_button = Button(text="Charakter laden", on_press=self.show_load_popup)
        layout.add_widget(self.load_char_button)

        self.options_button = Button(text="Optionen", on_press=self.switch_to_options)
        layout.add_widget(self.options_button)

        self.add_widget(layout)

    def on_pre_enter(self, *args):
        """Wird ausgeführt, bevor der Bildschirm angezeigt wird."""
        apply_background(self)
        apply_transparency_to_widget(self)

    def switch_to_options(self, instance):
        self.manager.current = 'options'

    def restart_app(self, dt):
        os.execv(sys.executable, ['python'] + sys.argv)

    def switch_to_creator(self, instance):
        self.manager.current = 'creator'
        
    def show_load_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))
        
        files = [f for f in os.listdir('.') if f.endswith('.char')]
        for filename in files:
            char_layout = BoxLayout(size_hint_y=None, height=40)
            
            load_btn = Button(text=filename)
            load_btn.bind(on_release=lambda btn, fn=filename: self.load_character(fn))
            
            delete_btn = Button(text="Löschen", size_hint_x=0.3)
            delete_btn.bind(on_release=lambda btn, fn=filename: self.delete_character_popup(fn))
            
            char_layout.add_widget(load_btn)
            char_layout.add_widget(delete_btn)
            popup_layout.add_widget(char_layout)
            
        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(popup_layout)
        content.add_widget(scroll_view)
        
        apply_transparency_to_widget(content)
        self.popup = Popup(title="Charakter laden", content=content, size_hint=(0.8, 0.8))
        self.popup.open()

    def delete_character_popup(self, filename):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Möchtest du {filename} wirklich löschen?"))
        
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=lambda x: self.delete_character(filename))
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss())
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        
        content.add_widget(btn_layout)
        
        apply_transparency_to_widget(content)
        self.confirmation_popup = Popup(title="Löschen bestätigen", content=content, size_hint=(0.6, 0.4))
        self.confirmation_popup.open()

    def delete_character(self, filename):
        try:
            os.remove(filename)
            self.confirmation_popup.dismiss()
            self.popup.dismiss()
            self.show_load_popup(None) # Refresh the list
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Löschen des Charakters: {e}")

    def load_character(self, filename):
        try:
            with open(filename, 'rb') as f:
                character = pickle.load(f)
            self.manager.get_screen('sheet').load_character(character)
            self.manager.current = 'sheet'
            self.popup.dismiss()
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Laden des Charakters: {e}")
            
    def show_popup(self, title, message):
        Popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()

class CharacterCreator(Screen):
    """Creator mit +/- Buttons für Attribute."""
    def __init__(self, **kwargs):
        super(CharacterCreator, self).__init__(**kwargs)
        
        scroll_view = ScrollView(size_hint=(1, 1))
        layout = GridLayout(cols=2, padding=10, spacing=10, size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # Add a back button to the top left
        back_button = Button(text="Zurück zum Hauptmenü",
                             on_press=lambda x: setattr(self.manager, 'current', 'main'),
                             size_hint_y=None,
                             height=44)
        layout.add_widget(back_button)
        layout.add_widget(Label(text="", size_hint_y=None, height=44)) # Placeholder

        self.inputs = {}
        default_height = 44
        multiline_height = 120
        
        fields = [
            ("Name", "TextInput", default_height, []),
            ("Rasse", "Spinner", default_height, sorted(RACE_DATA.keys())),
            ("Klasse", "Spinner", default_height, sorted(CLASS_DATA.keys())),
            ("Gesinnung", "Spinner", default_height, sorted(ALIGNMENT_DATA.keys())),
            ("Hintergrund", "Spinner", default_height, sorted(BACKGROUND_DATA.keys())),
            ("Persönliche Merkmale", "TextInput", multiline_height, []),
            ("Ideale", "TextInput", multiline_height, []),
            ("Bindungen", "TextInput", multiline_height, []),
            ("Makel", "TextInput", multiline_height, [])
        ]

        for field_name, widget_type, height, values in fields:
            label = Label(text=f"{field_name}:", size_hint=(None, None), width=180, height=height, halign='left', valign='middle')
            label.bind(size=label.setter('text_size'))
            layout.add_widget(label)

            if widget_type == "TextInput":
                widget = TextInput(size_hint_y=None, height=height, multiline=(height > default_height))
            else:
                widget = Spinner(text=values[0], values=values, size_hint_y=None, height=height)
            
            self.inputs[field_name] = widget
            layout.add_widget(widget)

        self.ability_scores_labels = {}
        abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
        for ability in abilities:
            label = Label(text=ability, size_hint=(None, None), width=180, height=default_height, halign='left', valign='middle')
            layout.add_widget(label)
            
            stat_box = BoxLayout(size_hint_y=None, height=default_height)
            minus_btn = Button(text="-", on_press=partial(self.adjust_ability, ability, -1))
            score_label = Label(text="10")
            plus_btn = Button(text="+", on_press=partial(self.adjust_ability, ability, 1))
            
            stat_box.add_widget(minus_btn)
            stat_box.add_widget(score_label)
            stat_box.add_widget(plus_btn)
            
            self.ability_scores_labels[ability] = score_label
            layout.add_widget(stat_box)
        
        layout.add_widget(Label(size_hint_y=None, height=10))
        layout.add_widget(Label(size_hint_y=None, height=10))
        
        roll_button = Button(text="Attribute auswürfeln", on_press=self.roll_abilities, size_hint_y=None, height=default_height)
        create_button = Button(text="Charakter erstellen", on_press=self.create_character, size_hint_y=None, height=default_height)
        layout.add_widget(roll_button)
        layout.add_widget(create_button)

        scroll_view.add_widget(layout)
        self.add_widget(scroll_view)

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_transparency_to_widget(self)

    def adjust_ability(self, ability, amount, instance):
        current_score = int(self.ability_scores_labels[ability].text)
        new_score = max(1, min(20, current_score + amount))
        self.ability_scores_labels[ability].text = str(new_score)

    def roll_abilities(self, instance):
        for ability in self.ability_scores_labels:
            rolls = sorted([random.randint(1, 6) for _ in range(4)])
            score = sum(rolls[1:])
            self.ability_scores_labels[ability].text = str(score)

    def create_character(self, instance):
        name = self.inputs["Name"].text.strip()
        if not name:
            self.show_popup("Fehler", "Bitte gib einen Namen für den Charakter ein.")
            return

        character = Character(name, self.inputs["Rasse"].text, self.inputs["Klasse"].text)
        
        for ability, label in self.ability_scores_labels.items():
            character.base_abilities[ability] = int(label.text)
        
        character.alignment = self.inputs["Gesinnung"].text
        character.background = self.inputs["Hintergrund"].text
        character.personality_traits = self.inputs["Persönliche Merkmale"].text
        character.ideals = self.inputs["Ideale"].text
        character.bonds = self.inputs["Bindungen"].text
        character.flaws = self.inputs["Makel"].text

        class_data = CLASS_DATA.get(character.char_class, {})
        
        # Check for fighting style choice
        if "Kampfstil" in [f['name'] for f in class_data.get("features", {}).get(1, [])]:
             self.show_fighting_style_popup(character)
        elif character.race == "Halbelf":
            self.show_half_elf_choices_popup(character)
        elif "progression" in class_data:
            self.show_initial_spell_selection_popup(character)
        else:
            self.finish_character_creation(character)

    def show_half_elf_choices_popup(self, character):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text="Wähle deine Halbelf-Boni", font_size='20sp', size_hint_y=None, height=44)
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        # Ability Score Choices
        scroll_content.add_widget(Label(text="Erhöhe zwei Attributswerte um 1", size_hint_y=None, height=30, font_size='18sp'))
        ability_grid = GridLayout(cols=3, size_hint_y=None, spacing=5)
        ability_grid.bind(minimum_height=ability_grid.setter('height'))
        self.half_elf_ability_checkboxes = {}
        abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit"] # Charisma is already +2
        for ability in abilities:
            box = BoxLayout(size_hint_y=None, height=30)
            cb = CheckBox()
            self.half_elf_ability_checkboxes[ability] = cb
            box.add_widget(Label(text=ability))
            box.add_widget(cb)
            ability_grid.add_widget(box)
        scroll_content.add_widget(ability_grid)

        # Skill Versatility
        scroll_content.add_widget(Label(text="Wähle zwei neue Fertigkeiten", size_hint_y=None, height=30, font_size='18sp'))
        skill_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
        skill_grid.bind(minimum_height=skill_grid.setter('height'))
        self.half_elf_skill_checkboxes = {}
        for skill in sorted(SKILL_LIST.keys()):
            if skill not in character.proficiencies: # Don't show skills they already have
                box = BoxLayout(size_hint_y=None, height=30)
                cb = CheckBox()
                self.half_elf_skill_checkboxes[skill] = cb
                box.add_widget(Label(text=skill))
                box.add_widget(cb)
                skill_grid.add_widget(box)
        scroll_content.add_widget(skill_grid)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        confirm_btn = Button(text="Bestätigen", size_hint_y=None, height=50)
        popup_content.add_widget(confirm_btn)

        popup = Popup(title="Halbelf-Anpassung", content=popup_content, size_hint=(0.9, 0.9), auto_dismiss=False)

        def confirm_choices(instance):
            # Validate ability scores
            selected_abilities = [name for name, cb in self.half_elf_ability_checkboxes.items() if cb.active]
            if len(selected_abilities) != 2:
                self.show_popup("Fehler", "Bitte wähle genau zwei Attributswerte.")
                return

            # Validate skills
            selected_skills = [name for name, cb in self.half_elf_skill_checkboxes.items() if cb.active]
            if len(selected_skills) != 2:
                self.show_popup("Fehler", "Bitte wähle genau zwei Fertigkeiten.")
                return

            # Apply choices
            for ability in selected_abilities:
                character.base_abilities[ability] += 1
            
            character.proficiencies.extend(selected_skills)
            character.proficiencies = sorted(list(set(character.proficiencies)))

            popup.dismiss()

            # Continue creation process
            class_data = CLASS_DATA.get(character.char_class, {})
            if "progression" in class_data:
                self.show_initial_spell_selection_popup(character)
            else:
                self.finish_character_creation(character)

        confirm_btn.bind(on_press=confirm_choices)
        apply_transparency_to_widget(popup_content)
        popup.open()

    def show_fighting_style_popup(self, character):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text="Wähle deinen Kampfstil", font_size='20sp', size_hint_y=None, height=44)
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        # Fighter gets a specific list of styles
        fighter_styles = ["Defense", "Dueling", "Great Weapon Fighting", "Protection"]
        
        style_checkboxes = {}
        for style_name in fighter_styles:
            if style_name in FIGHTING_STYLE_DATA:
                box = BoxLayout(size_hint_y=None, height=40)
                cb = CheckBox(group='fighting_style', size_hint_x=0.1)
                style_checkboxes[style_name] = cb
                
                desc = FIGHTING_STYLE_DATA[style_name]
                info_btn = Button(text=f"{style_name}: {desc}", text_size=(self.width - 150, None), halign='left')
                
                box.add_widget(cb)
                box.add_widget(info_btn)
                scroll_content.add_widget(box)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        confirm_btn = Button(text="Bestätigen", size_hint_y=None, height=50)
        popup_content.add_widget(confirm_btn)
        
        popup = Popup(title="Kampfstil auswählen", content=popup_content, size_hint=(0.9, 0.9), auto_dismiss=False)

        def confirm_choice(instance):
            selected_style = None
            for name, cb in style_checkboxes.items():
                if cb.active:
                    selected_style = name
                    break
            
            if not selected_style:
                self.show_popup("Fehler", "Bitte wähle einen Kampfstil.")
                return

            character.fighting_style = selected_style
            # Add the chosen style as a feature
            character.features.append({"name": f"Kampfstil: {selected_style}", "desc": FIGHTING_STYLE_DATA[selected_style]})
            
            popup.dismiss()

            # After fighting style, check for spells (for archetypes like Eldritch Knight, though not in SRD)
            class_data = CLASS_DATA.get(character.char_class, {})
            if "progression" in class_data:
                self.show_initial_spell_selection_popup(character)
            else:
                self.finish_character_creation(character)

        confirm_btn.bind(on_press=confirm_choice)
        apply_transparency_to_widget(popup_content)
        popup.open()

    def show_initial_spell_selection_popup(self, character):
        class_data = CLASS_DATA.get(character.char_class, {})
        progression = class_data.get("progression", {})
        level_1_prog = progression.get(1, {})
        if not level_1_prog:
            self.finish_character_creation(character)
            return

        cantrips_to_learn = level_1_prog.get("cantrips_known", 0)
        spells_to_learn = level_1_prog.get("spells_known", 0)
        all_available_spells = class_data.get("spell_list", {})

        # --- UI Building ---
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text=f"Wähle deine Startzauber für {character.char_class}", font_size='20sp', size_hint_y=None, height=44)
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        
        cantrip_checkboxes = {}
        if cantrips_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {cantrips_to_learn} Zaubertrick/s", size_hint_y=None, height=30, font_size='18sp'))
            cantrip_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
            cantrip_grid.bind(minimum_height=cantrip_grid.setter('height'))
            for spell_name in sorted(all_available_spells.get(0, [])):
                box = BoxLayout(size_hint_y=None, height=30)
                cb = CheckBox(size_hint_x=0.1)
                cantrip_checkboxes[spell_name] = cb
                info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                box.add_widget(cb)
                box.add_widget(info_btn)
                cantrip_grid.add_widget(box)
            scroll_content.add_widget(cantrip_grid)

        spell_checkboxes = {}
        if spells_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {spells_to_learn} Zauber des 1. Grades", size_hint_y=None, height=30, font_size='18sp'))
            spell_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
            spell_grid.bind(minimum_height=spell_grid.setter('height'))
            for spell_name in sorted(all_available_spells.get(1, [])):
                box = BoxLayout(size_hint_y=None, height=30)
                cb = CheckBox(size_hint_x=0.1)
                spell_checkboxes[spell_name] = cb
                info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                box.add_widget(cb)
                box.add_widget(info_btn)
                spell_grid.add_widget(box)
            scroll_content.add_widget(spell_grid)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        confirm_btn = Button(text="Bestätigen")
        btn_box.add_widget(confirm_btn)
        popup_content.add_widget(btn_box)

        popup = Popup(title="Startzauber auswählen", content=popup_content, size_hint=(0.9, 0.9), auto_dismiss=False)

        def confirm_choices(instance):
            selected_cantrips = [name for name, cb in cantrip_checkboxes.items() if cb.active]
            if cantrips_to_learn > 0 and len(selected_cantrips) != cantrips_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {cantrips_to_learn} Zaubertrick/s.")
                return

            selected_spells = [name for name, cb in spell_checkboxes.items() if cb.active]
            if spells_to_learn > 0 and len(selected_spells) != spells_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {spells_to_learn} Zauber des 1. Grades.")
                return

            character.spells[0] = selected_cantrips
            character.spells[1] = selected_spells
            
            popup.dismiss()
            self.finish_character_creation(character)

        confirm_btn.bind(on_press=confirm_choices)
        
        apply_transparency_to_widget(popup_content)
        popup.open()

    def finish_character_creation(self, character):
        character.initialize_character()
        self.manager.get_screen('sheet').load_character(character)
        self.manager.current = 'sheet'

    def show_spell_info_popup(self, spell_name, instance):
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )
        self.show_popup(spell_name, text)

    def show_popup(self, title, message):
        content = ScrollView()
        label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.8))
        apply_transparency_to_widget(popup.content)
        popup.open()

class CharacterSheet(Screen):
    """Finaler Charakterbogen mit allen neuen Features."""
    def __init__(self, **kwargs):
        super(CharacterSheet, self).__init__(**kwargs)
        self.character = None
        self.main_layout = BoxLayout(orientation='vertical')
        self.add_widget(self.main_layout)

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_transparency_to_widget(self)

    def load_character(self, character):
        self.character = character
        if self.character:
            # This ensures old character files are compatible with new spell logic
            if hasattr(self.character, 'normalize_spells'):
                self.character.normalize_spells()
        self.update_sheet()

    def update_sheet(self):
        self.main_layout.clear_widgets()
        if not self.character:
            return

        header = GridLayout(cols=3, size_hint_y=None, height=60)
        header.add_widget(Label(text=f"{self.character.name}", font_size='20sp'))
        header.add_widget(Label(text=f"{self.character.race} {self.character.char_class} {self.character.level}"))
        header.add_widget(Label(text=f"Gesinnung: {self.character.alignment}"))
        self.main_layout.add_widget(header)

        scroll_view = ScrollView()
        content_layout = GridLayout(cols=2, spacing=10, padding=10, size_hint_y=None)
        content_layout.bind(minimum_height=content_layout.setter('height'))

        # --- Linke Spalte ---
        left_column = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        left_column.bind(minimum_height=left_column.setter('height'))
        
        stats_box = GridLayout(cols=2, size_hint_y=None, height=280)
        for ability, score in self.character.abilities.items():
            modifier = (score - 10) // 2
            sign = "+" if modifier >= 0 else ""
            stats_box.add_widget(Label(text=f"{ability}:"))
            stats_box.add_widget(Label(text=f"{score} ({sign}{modifier})"))
        stats_box.add_widget(Label(text="Rüstungsklasse:"))
        stats_box.add_widget(Label(text=f"{self.character.armor_class}"))
        stats_box.add_widget(Label(text="Initiative:"))
        stats_box.add_widget(Label(text=f"{self.character.initiative:+}"))
        stats_box.add_widget(Label(text="Bewegungsrate:"))
        stats_box.add_widget(Label(text=f"{self.character.speed}m ({int(self.character.speed / 1.5)} Felder)"))
        left_column.add_widget(stats_box)
        
        hp_box = BoxLayout(size_hint_y=None, height=50)
        hp_box.add_widget(Button(text="-", on_press=partial(self.change_hp, -1)))
        self.hp_label = Label(text=f"HP: {self.character.hit_points} / {self.character.max_hit_points}")
        hp_box.add_widget(self.hp_label)
        hp_box.add_widget(Button(text="+", on_press=partial(self.change_hp, 1)))
        left_column.add_widget(hp_box)
        
        combat_box = GridLayout(cols=1, size_hint_y=None, height=150, spacing=5)
        self.weapon_spinner = Spinner(text=self.character.equipped_weapon, values=sorted(WEAPON_DATA.keys()))
        self.weapon_spinner.bind(text=self.update_weapon)
        combat_box.add_widget(Label(text="Ausrüstete Waffe:"))
        combat_box.add_widget(self.weapon_spinner)
        combat_box.add_widget(Button(text="Schaden auswürfeln", on_press=self.roll_damage))
        left_column.add_widget(combat_box)

        currency_box = GridLayout(cols=3, size_hint_y=None, height=200, spacing=5)
        currency_box.add_widget(Label(text="Währung", size_hint_x=None, width=100))
        currency_box.add_widget(Label())
        currency_box.add_widget(Label())
        self.currency_labels = {}
        for curr in ["KP", "SP", "EP", "GM", "PP"]:
            currency_box.add_widget(Label(text=f"{curr}:"))
            self.currency_labels[curr] = Label(text=str(self.character.currency[curr]))
            currency_box.add_widget(self.currency_labels[curr])
            btn_box = BoxLayout()
            btn_box.add_widget(Button(text="-", on_press=partial(self.change_currency, curr, -1)))
            btn_box.add_widget(Button(text="+", on_press=partial(self.change_currency, curr, 1)))
            currency_box.add_widget(btn_box)
        left_column.add_widget(currency_box)
        content_layout.add_widget(left_column)

        # --- Rechte Spalte ---
        right_column = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
        right_column.bind(minimum_height=right_column.setter('height'))
        
        right_column.add_widget(Label(text="Fähigkeiten", font_size='20sp', size_hint_y=None, height=40))
        features_layout = GridLayout(cols=1, spacing=5, size_hint_y=None)
        features_layout.bind(minimum_height=features_layout.setter('height'))
        for feature in self.character.features:
            btn = Button(text=feature['name'], size_hint_y=None, height=40, halign='left', valign='middle', padding=(10, 0))
            btn.bind(on_press=partial(self.show_feature_popup, feature))
            features_layout.add_widget(btn)
        
        right_column.add_widget(features_layout)
        
        right_column.add_widget(Label(text="Inventar", font_size='20sp', size_hint_y=None, height=40))
        self.inventory_layout = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.inventory_layout.bind(minimum_height=self.inventory_layout.setter('height'))
        self.update_inventory_display()
        right_column.add_widget(self.inventory_layout)
        right_column.add_widget(Button(text="Item hinzufügen", on_press=self.show_add_item_popup, size_hint_y=None, height=44))

        right_column.add_widget(Label(text="Ausrüstung", font_size='20sp', size_hint_y=None, height=40))
        self.equipment_layout = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.equipment_layout.bind(minimum_height=self.equipment_layout.setter('height'))
        self.update_equipment_display()
        right_column.add_widget(self.equipment_layout)
        right_column.add_widget(Button(text="Ausrüstung hinzufügen", on_press=self.show_add_equipment_popup, size_hint_y=None, height=44))

        content_layout.add_widget(right_column)
        
        scroll_view.add_widget(content_layout)
        self.main_layout.add_widget(scroll_view)

        footer = BoxLayout(size_hint_y=None, height=50, spacing=5)
        footer.add_widget(Button(text="Info", on_press=self.show_info_popup))
        footer.add_widget(Button(text="Zauber", on_press=self.show_spells_popup))
        footer.add_widget(Button(text="Level Up", on_press=self.open_level_up_screen))
        footer.add_widget(Button(text="Speichern", on_press=self.save_character))
        footer.add_widget(Button(text="Hauptmenü", on_press=lambda x: setattr(self.manager, 'current', 'main')))
        self.main_layout.add_widget(footer)

    def show_popup(self, title, message):
        content = ScrollView()
        label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        Popup(title=title, content=content, size_hint=(0.8, 0.8)).open()

    def update_weapon(self, spinner, text):
        self.character.equipped_weapon = text

    def change_hp(self, amount, instance):
        self.character.hit_points += amount
        self.character.hit_points = max(0, min(self.character.hit_points, self.character.max_hit_points))
        self.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"

    def change_currency(self, currency, amount, instance):
        self.character.currency[currency] += amount
        self.character.currency[currency] = max(0, self.character.currency[currency])
        self.currency_labels[currency].text = str(self.character.currency[currency])

    def update_inventory_display(self):
        self.inventory_layout.clear_widgets()
        for item_name, quantity in self.character.inventory.items():
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            item_row.add_widget(Label(text=f"{item_name} ({quantity})", halign='left', valign='middle'))
            
            btn_box = BoxLayout(size_hint_x=0.4)
            btn_box.add_widget(Button(text="-", on_press=partial(self.adjust_item_quantity, item_name, -1)))
            btn_box.add_widget(Button(text="+", on_press=partial(self.adjust_item_quantity, item_name, 1)))
            
            item_row.add_widget(btn_box)
            self.inventory_layout.add_widget(item_row)

    def adjust_item_quantity(self, item_name, amount, instance):
        self.character.inventory[item_name] += amount
        if self.character.inventory[item_name] <= 0:
            del self.character.inventory[item_name]
        self.update_inventory_display()

    def update_equipment_display(self):
        self.equipment_layout.clear_widgets()
        for item_name, ac_bonus in self.character.equipment.items():
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            item_row.add_widget(Label(text=f"{item_name} (AC: +{ac_bonus})", halign='left', valign='middle'))
            
            remove_btn = Button(text="-", size_hint_x=0.2)
            remove_btn.bind(on_press=partial(self.remove_equipment, item_name))
            
            item_row.add_widget(remove_btn)
            self.equipment_layout.add_widget(item_row)

    def remove_equipment(self, item_name, instance):
        if item_name in self.character.equipment:
            del self.character.equipment[item_name]
            self.character.calculate_armor_class()
            self.update_sheet()

    def show_add_equipment_popup(self, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        name_input = TextInput(hint_text="Ausrüstungsname", multiline=False)
        ac_input = TextInput(hint_text="AC Bonus", multiline=False)
        content.add_widget(name_input)
        content.add_widget(ac_input)
        
        add_btn = Button(text="Hinzufügen")
        content.add_widget(add_btn)
        
        popup = Popup(title="Ausrüstung hinzufügen", content=content, size_hint=(0.8, 0.5))
        
        def add_action(instance):
            name = name_input.text.strip()
            try:
                ac_bonus = int(ac_input.text.strip())
                if name:
                    self.character.equipment[name] = ac_bonus
                    self.character.calculate_armor_class()
                    self.update_sheet()
                    popup.dismiss()
                else:
                    self.show_popup("Fehler", "Bitte einen Namen eingeben.")
            except ValueError:
                self.show_popup("Fehler", "AC Bonus muss eine Zahl sein.")
                
        add_btn.bind(on_press=add_action)
        apply_transparency_to_widget(content)
        popup.open()

    def show_add_item_popup(self, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        item_input = TextInput(hint_text="Gegenstand eingeben", multiline=False)
        content.add_widget(item_input)
        
        add_btn = Button(text="Hinzufügen")
        content.add_widget(add_btn)
        
        popup = Popup(title="Item hinzufügen", content=content, size_hint=(0.8, 0.4))
        
        def add_action(instance):
            item_name = item_input.text.strip()
            if item_name:
                if item_name in self.character.inventory:
                    self.character.inventory[item_name] += 1
                else:
                    self.character.inventory[item_name] = 1
                self.update_inventory_display()
                popup.dismiss()
                
        add_btn.bind(on_press=add_action)
        apply_transparency_to_widget(content)
        popup.open()

    def roll_damage(self, instance):
        weapon_name = self.character.equipped_weapon
        weapon_info = WEAPON_DATA.get(weapon_name, WEAPON_DATA["Unbewaffneter Schlag"])
        ability_name = weapon_info["ability"]
        modifier = (self.character.abilities[ability_name] - 10) // 2
        
        parts = weapon_info["damage"].split('d')
        num_dice = int(parts[0])
        dice_type = int(parts[1])
        
        roll_total = sum(random.randint(1, dice_type) for _ in range(num_dice))
        total_damage = roll_total + modifier
        
        self.show_popup(
            "Schadenswurf",
            f"{weapon_info['damage']} ({roll_total}) + {ability_name[:3]}-Mod ({modifier}) = {max(1, total_damage)} Schaden"
        )

    def show_feature_popup(self, feature, instance):
        self.show_popup(feature['name'], feature['desc'])

    def show_info_popup(self, instance):
        prof_text = ", ".join(self.character.proficiencies)
        lang_text = ", ".join(self.character.languages)

        features_text = ""
        if self.character.features:
            features_text = "\n\n[b]Klassenmerkmale:[/b]\n"
            for feature in self.character.features:
                features_text += f"- {feature['name']}\n"

        skills_text = "\n\n[b]Fähigkeiten:[/b]\n"
        for skill, ability in SKILL_LIST.items():
            modifier = (self.character.abilities[ability] - 10) // 2
            if skill in self.character.proficiencies:
                modifier += self.character.get_proficiency_bonus()
            sign = "+" if modifier >= 0 else ""
            skills_text += f"- {skill}: {sign}{modifier}\n"

        text = (
            f"[b]Gesinnung:[/b] {self.character.alignment}\n\n"
            f"[b]Hintergrund:[/b] {self.character.background}\n\n"
            f"[b]Kompetenzen:[/b]\n{prof_text}\n\n"
            f"[b]Sprachen:[/b]\n{lang_text}\n\n"
            f"{skills_text}"
            f"[b]Persönliche Merkmale:[/b]\n{self.character.personality_traits}\n\n"
            f"[b]Ideale:[/b]\n{self.character.ideals}\n\n"
            f"[b]Bindungen:[/b]\n{self.character.bonds}\n\n"
            f"[b]Makel:[/b]\n{self.character.flaws}"
            f"{features_text}"
        )
        self.show_popup("Charakter-Informationen", text)

    def show_spells_popup(self, instance):
        content = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=10)
        grid.bind(minimum_height=grid.setter('height'))

        if not self.character.spells:
            grid.add_widget(Label(text="Dieser Charakter kann nicht zaubern.", size_hint_y=None, height=40))
        else:
            # Sort by spell level
            for spell_level in sorted(self.character.spells.keys()):
                spell_list = self.character.spells[spell_level]
                if not spell_list: continue # Skip empty levels
                
                level_name = "Zaubertricks" if spell_level == 0 else f"Level {spell_level} Zauber"
                grid.add_widget(Label(text=level_name, font_size='18sp', size_hint_y=None, height=40))
                for spell_name in sorted(spell_list):
                    btn = Button(text=spell_name, size_hint_y=None, height=40)
                    btn.bind(on_press=partial(self.show_spell_details_popup, spell_name))
                    grid.add_widget(btn)
        
        content.add_widget(grid)
        apply_transparency_to_widget(content)
        Popup(title="Zauberbuch", content=content, size_hint=(0.8, 0.9)).open()

    def show_spell_details_popup(self, spell_name, instance):
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )
        self.show_popup(spell_name, text)

    def open_level_up_screen(self, instance):
        self.manager.get_screen('level_up').set_character(self.character)
        self.manager.current = 'level_up'
        
    def save_character(self, instance):
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter als '{filename}' gespeichert.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Speichern: {e}")

class OptionsScreen(Screen):
    """Bildschirm für Optionen, Updates und Versionsanzeige."""
    def __init__(self, **kwargs):
        super(OptionsScreen, self).__init__(**kwargs)
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text="Optionen", font_size='30sp', size_hint_y=None, height=80)
        layout.add_widget(title)
        
        settings = load_settings()

        # --- Transparenz-Einstellungen ---
        self.transparency_label = Label(text=f"Button Transparenz: {int(settings.get('button_transparency', 1.0) * 100)}%", size_hint_y=None, height=40)
        layout.add_widget(self.transparency_label)
        
        self.transparency_slider = Slider(min=0.1, max=1.0, value=settings.get('button_transparency', 1.0), size_hint_y=None, height=40)
        self.transparency_slider.bind(value=self.on_transparency_change)
        layout.add_widget(self.transparency_slider)

        transparency_switch_layout = BoxLayout(size_hint_y=None, height=40)
        transparency_switch_layout.add_widget(Label(text="Transparenz an/aus"))
        self.transparency_switch = Switch(active=settings.get('transparency_enabled', True))
        self.transparency_switch.bind(active=self.on_transparency_toggle)
        transparency_switch_layout.add_widget(self.transparency_switch)
        layout.add_widget(transparency_switch_layout)

        # --- Hintergrund-Einstellungen ---
        background_switch_layout = BoxLayout(size_hint_y=None, height=40)
        background_switch_layout.add_widget(Label(text="Hintergrund anzeigen"))
        self.background_switch = Switch(active=settings.get('background_enabled', True))
        self.background_switch.bind(active=self.on_background_toggle)
        background_switch_layout.add_widget(self.background_switch)
        layout.add_widget(background_switch_layout)

        choose_bg_button = Button(text="Hintergrundbild wählen", on_press=self.show_background_chooser_popup, size_hint_y=None, height=60)
        layout.add_widget(choose_bg_button)

        layout.add_widget(BoxLayout(size_hint_y=0.2))  # Spacer

        # --- Allgemeine Buttons ---
        button_height = 80
        font_size = '20sp'
        update_button = Button(text="Nach Updates suchen", on_press=self.update_app, size_hint_y=None, height=button_height, font_size=font_size)
        layout.add_widget(update_button)
        version_button = Button(text="Version", on_press=self.show_version_popup, size_hint_y=None, height=button_height, font_size=font_size)
        layout.add_widget(version_button)
        shutdown_button = Button(text="System herunterfahren", on_press=self.shutdown_system, size_hint_y=None, height=button_height, font_size=font_size)
        layout.add_widget(shutdown_button)
        layout.add_widget(BoxLayout(size_hint_y=1.0))  # Spacer
        back_button = Button(text="Zurück zum Hauptmenü", on_press=lambda x: setattr(self.manager, 'current', 'main'), size_hint_y=None, height=button_height, font_size=font_size)
        layout.add_widget(back_button)
        self.add_widget(layout)

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_transparency_to_widget(self)

    def on_transparency_change(self, instance, value):
        settings = load_settings()
        settings['button_transparency'] = value
        save_settings(settings)
        self.transparency_label.text = f"Button Transparenz: {int(value * 100)}%"
        apply_transparency_to_widget(self.manager)

    def on_transparency_toggle(self, instance, value):
        settings = load_settings()
        settings['transparency_enabled'] = value
        save_settings(settings)
        apply_transparency_to_widget(self.manager)

    def on_background_toggle(self, instance, value):
        settings = load_settings()
        settings['background_enabled'] = value
        save_settings(settings)
        for screen in self.manager.screens:
            apply_background(screen)

    def show_background_chooser_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=10)
        
        initial_path = os.path.abspath(".")
        
        filechooser = FileChooserListView(path=initial_path, filters=['*.png', '*.jpg', '*.jpeg', '*.bmp'])
        content.add_widget(filechooser)
        
        button_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        select_btn = Button(text="Auswählen")
        cancel_btn = Button(text="Abbrechen")
        button_layout.add_widget(select_btn)
        button_layout.add_widget(cancel_btn)
        content.add_widget(button_layout)
        
        popup = Popup(title="Hintergrundbild auswählen", content=content, size_hint=(0.9, 0.9))

        def select_file(instance):
            if filechooser.selection:
                selected_path = filechooser.selection[0]
                if os.path.isfile(selected_path):
                    settings = load_settings()
                    settings['background_path'] = selected_path
                    save_settings(settings)
                    popup.dismiss()
                    for screen in self.manager.screens:
                        apply_background(screen)
                else:
                    self.show_popup("Fehler", "Bitte eine Datei auswählen.")
            else:
                self.show_popup("Fehler", "Keine Datei ausgewählt.")

        select_btn.bind(on_press=select_file)
        cancel_btn.bind(on_press=popup.dismiss)
        
        popup.open()

    def shutdown_system(self, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Möchten Sie das System wirklich herunterfahren?'))
        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=self.do_shutdown, height=80, font_size='20sp')
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss(), height=80, font_size='20sp')
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)
        content.add_widget(btn_layout)
        apply_transparency_to_widget(content)
        self.confirmation_popup = Popup(title="Herunterfahren bestätigen", content=content, size_hint=(0.6, 0.5))
        self.confirmation_popup.open()

    def do_shutdown(self, instance):
        self.confirmation_popup.dismiss()
        try:
            if sys.platform == "win32":
                os.system("shutdown /s /t 1")
            elif sys.platform.startswith('linux'):
                os.system("shutdown now")
            else:
                self.show_popup("Nicht unterstützt", f"Herunterfahren wird auf '{sys.platform}' nicht unterstützt.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Herunterfahren:\n{e}")

    def show_popup(self, title, message):
        popup = Popup(title=title, content=Label(text=message), size_hint=(0.7, 0.5))
        popup.open()

    def update_app(self, instance):
        self.popup = Popup(title='Update', content=Label(text='Suche nach Updates...'), size_hint=(0.6, 0.4), auto_dismiss=False)
        self.popup.open()
        Clock.schedule_once(self._update_task, 0.1)

    def _update_task(self, dt):
        try:
            self.popup.content.text = "Updater wird gestartet...\nDie Anwendung wird sich nun schließen."
            subprocess.Popen([sys.executable, "updater.py"])
            Clock.schedule_once(lambda x: App.get_running_app().stop(), 0.5)
        except Exception as e:
            self.popup.content.text = f"Fehler beim Starten des Updaters:\n{e}"
            Clock.schedule_once(lambda x: self.popup.dismiss(), 5)

    def show_version_popup(self, instance):
        try:
            with open("version.txt", "r", encoding="utf-8") as f:
                version_info = f.read()
        except FileNotFoundError:
            version_info = "version.txt nicht gefunden."
        except Exception as e:
            version_info = f"Fehler beim Lesen der Version:\n{e}"
        popup = Popup(title="Version", content=Label(text=version_info), size_hint=(0.7, 0.5))
        popup.open()

class LevelUpScreen(Screen):
    """Bildschirm für den Stufenaufstieg."""
    def __init__(self, **kwargs):
        super(LevelUpScreen, self).__init__(**kwargs)
        self.character = None
        self.main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        self.add_widget(self.main_layout)
        self.spell_choices = {}
        self.ability_choices = {}

    def on_pre_enter(self, *args):
        apply_transparency_to_widget(self)

    def set_character(self, character):
        self.character = character
        self.update_view()

    def update_view(self):
        self.main_layout.clear_widgets()
        if not self.character:
            return

        new_level = self.character.level + 1
        self.main_layout.add_widget(Label(text=f"Stufenaufstieg zu Level {new_level}", font_size='24sp', size_hint_y=None, height=50))

        scroll_view = ScrollView()
        level_up_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        level_up_layout.bind(minimum_height=level_up_layout.setter('height'))

        # HP Increase
        hit_die = CLASS_DATA.get(self.character.char_class, {}).get("hit_die", 8)
        con_modifier = (self.character.abilities["Konstitution"] - 10) // 2
        hp_increase = random.randint(1, hit_die) + con_modifier
        level_up_layout.add_widget(Label(text=f"HP-Erhöhung: +{max(1, hp_increase)}", size_hint_y=None, height=40))

        # New Features
        features = CLASS_DATA.get(self.character.char_class, {}).get("features", {}).get(new_level, [])
        if features:
            level_up_layout.add_widget(Label(text="Neue Fähigkeiten:", font_size='20sp', size_hint_y=None, height=40))
            for feature in features:
                feature_label = Label(text=f"[b]{feature['name']}[/b]\n{feature['desc']}", markup=True, size_hint_y=None)
                feature_label.bind(
                    width=lambda *x: feature_label.setter('text_size')(feature_label, (feature_label.width, None)),
                    texture_size=lambda *x: feature_label.setter('height')(feature_label, feature_label.texture_size[1])
                )
                level_up_layout.add_widget(feature_label)

        # Ability Score Improvement
        self.ability_choices = {}
        if any("Attributswerterhöhung" in f['name'] for f in features):
            level_up_layout.add_widget(Label(text="Attributsverbesserung (wähle 2):", font_size='20sp', size_hint_y=None, height=40))
            abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
            for ability in abilities:
                box = BoxLayout(size_hint_y=None, height=40)
                box.add_widget(Label(text=ability))
                checkbox = CheckBox()
                self.ability_choices[ability] = checkbox
                box.add_widget(checkbox)
                level_up_layout.add_widget(box)
        
        # Spell Selection
        class_data = CLASS_DATA.get(self.character.char_class, {})
        if "progression" in class_data:
            progression = class_data.get("progression", {})
            if self.character.level + 1 in progression:
                manage_spells_btn = Button(text="Zauber auswählen", on_press=self.show_spell_selection_popup, size_hint_y=None, height=40)
                level_up_layout.add_widget(manage_spells_btn)

        scroll_view.add_widget(level_up_layout)
        self.main_layout.add_widget(scroll_view)

        # Confirm/Cancel Buttons
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        confirm_btn = Button(text="Bestätigen", on_press=self.confirm_level_up)
        cancel_btn = Button(text="Abbrechen", on_press=self.cancel_level_up)
        btn_layout.add_widget(confirm_btn)
        btn_layout.add_widget(cancel_btn)
        self.main_layout.add_widget(btn_layout)

    def show_spell_selection_popup(self, instance):
        class_data = CLASS_DATA.get(self.character.char_class, {})
        if not class_data or "progression" not in class_data:
            return

        progression = class_data["progression"]
        current_level = self.character.level
        new_level = current_level + 1

        old_prog = progression.get(current_level, {})
        new_prog = progression.get(new_level, {})
        if not old_prog or not new_prog:
            return

        # --- Calculations ---
        cantrips_to_learn = new_prog["cantrips_known"] - old_prog["cantrips_known"]
        spells_to_learn = new_prog["spells_known"] - old_prog["spells_known"]
        can_replace_spell = self.character.char_class == "Barde"

        max_spell_level = 0
        for level, slots in new_prog["spell_slots"].items():
            if slots > 0:
                max_spell_level = max(max_spell_level, int(level))

        known_cantrips = self.character.spells.get(0, [])
        known_spells_flat = [spell for lvl, spells in self.character.spells.items() if lvl > 0 for spell in spells]
        
        all_available_spells = class_data.get("spell_list", {})

        # --- UI Building ---
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        
        new_cantrip_checkboxes = {}
        if cantrips_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {cantrips_to_learn} neue/n Zaubertrick/s", size_hint_y=None, height=30, font_size='18sp'))
            cantrip_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
            cantrip_grid.bind(minimum_height=cantrip_grid.setter('height'))
            available_cantrips = all_available_spells.get(0, [])
            for spell_name in sorted(available_cantrips):
                if spell_name not in known_cantrips:
                    box = BoxLayout(size_hint_y=None, height=30)
                    cb = CheckBox(size_hint_x=0.1)
                    new_cantrip_checkboxes[spell_name] = cb
                    info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                    box.add_widget(cb)
                    box.add_widget(info_btn)
                    cantrip_grid.add_widget(box)
            scroll_content.add_widget(cantrip_grid)

        new_spell_checkboxes = {}
        if spells_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {spells_to_learn} neue/n Zauber (bis Grad {max_spell_level})", size_hint_y=None, height=30, font_size='18sp'))
            spell_grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
            spell_grid.bind(minimum_height=spell_grid.setter('height'))
            for spell_level in range(1, max_spell_level + 1):
                available_spells_at_level = all_available_spells.get(spell_level, [])
                if available_spells_at_level:
                    spell_grid.add_widget(Label(text=f"Grad {spell_level}", font_size='16sp', size_hint_y=None, height=25))
                    for spell_name in sorted(available_spells_at_level):
                        if spell_name not in known_spells_flat:
                            box = BoxLayout(size_hint_y=None, height=30)
                            cb = CheckBox(size_hint_x=0.1)
                            new_spell_checkboxes[spell_name] = cb
                            info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                            box.add_widget(cb)
                            box.add_widget(info_btn)
                            spell_grid.add_widget(box)
            scroll_content.add_widget(spell_grid)

        spell_to_replace_spinner = None
        replacement_spell_spinner = None
        if can_replace_spell and known_spells_flat:
            scroll_content.add_widget(Label(text="Ersetze einen bekannten Zauber", size_hint_y=None, height=30, font_size='18sp'))
            replace_box = BoxLayout(size_hint_y=None, height=40, spacing=10)
            
            spell_to_replace_spinner = Spinner(text="Wähle Zauber...", values=["Keiner"] + sorted(known_spells_flat))
            
            all_possible_replacements = ["Keiner"]
            for spell_level in range(1, max_spell_level + 1):
                all_possible_replacements.extend(sorted(all_available_spells.get(spell_level, [])))
            
            replacement_spell_spinner = Spinner(text="Wähle Ersatz...", values=list(dict.fromkeys(all_possible_replacements)))
            
            info_btn1 = Button(text="?", size_hint_x=0.2, on_press=lambda x: self.show_spell_info_popup(spell_to_replace_spinner.text, x))
            info_btn2 = Button(text="?", size_hint_x=0.2, on_press=lambda x: self.show_spell_info_popup(replacement_spell_spinner.text, x))

            replace_box.add_widget(spell_to_replace_spinner)
            replace_box.add_widget(info_btn1)
            replace_box.add_widget(Label(text="durch", size_hint_x=0.3))
            replace_box.add_widget(replacement_spell_spinner)
            replace_box.add_widget(info_btn2)
            scroll_content.add_widget(replace_box)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        confirm_btn = Button(text="Bestätigen")
        cancel_btn = Button(text="Abbrechen")
        btn_box.add_widget(confirm_btn)
        btn_box.add_widget(cancel_btn)
        popup_content.add_widget(btn_box)

        popup = Popup(title="Zauber für Stufenaufstieg auswählen", content=popup_content, size_hint=(0.9, 0.9))

        def confirm_choices(instance):
            selected_cantrips = [name for name, cb in new_cantrip_checkboxes.items() if cb.active]
            if cantrips_to_learn > 0 and len(selected_cantrips) != cantrips_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {cantrips_to_learn} Zaubertrick/s.")
                return

            selected_spells = [name for name, cb in new_spell_checkboxes.items() if cb.active]
            if spells_to_learn > 0 and len(selected_spells) != spells_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {spells_to_learn} neue/n Zauber.")
                return
            
            spell_to_replace = spell_to_replace_spinner.text if spell_to_replace_spinner else "Keiner"
            replacement_spell = replacement_spell_spinner.text if replacement_spell_spinner else "Keiner"

            if spell_to_replace != "Keiner" and replacement_spell == "Keiner":
                self.show_popup("Fehler", "Bitte wähle einen Ersatzzauber aus.")
                return
            if spell_to_replace == "Keiner" and replacement_spell != "Keiner":
                self.show_popup("Fehler", "Bitte wähle einen Zauber zum Ersetzen aus.")
                return
            if replacement_spell in known_spells_flat and replacement_spell != spell_to_replace:
                 self.show_popup("Fehler", f"Du kennst '{replacement_spell}' bereits.")
                 return

            self.spell_choices['new_cantrips'] = selected_cantrips
            self.spell_choices['new_spells'] = selected_spells
            if spell_to_replace != "Keiner" and replacement_spell != "Keiner":
                self.spell_choices['replaced_spell'] = spell_to_replace
                self.spell_choices['replacement_spell'] = replacement_spell
            
            popup.dismiss()

        confirm_btn.bind(on_press=confirm_choices)
        cancel_btn.bind(on_press=popup.dismiss)
        
        apply_transparency_to_widget(popup_content)
        popup.open()

    def show_spell_info_popup(self, spell_name, instance):
        if spell_name in ["Keiner", "Wähle Zauber...", "Wähle Ersatz..."]:
            return
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )
        self.show_popup(spell_name, text)

    def confirm_level_up(self, instance):
        choices = {}

        # Collect ability score increases
        selected_abilities = [ability for ability, checkbox in self.ability_choices.items() if checkbox.active]
        if self.ability_choices and len(selected_abilities) != 2:
            self.show_popup("Fehler", "Bitte wähle genau 2 Attribute zur Verbesserung aus.")
            return

        if selected_abilities:
            choices["ability_increase"] = selected_abilities
        
        # Collect spell choices
        if self.spell_choices:
            choices.update(self.spell_choices)

        self.character.level_up(choices)
        self.manager.get_screen('sheet').load_character(self.character)
        self.manager.current = 'sheet'

    def cancel_level_up(self, instance):
        self.manager.current = 'sheet'
    
    def show_popup(self, title, message):
        content = ScrollView()
        label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.8))
        apply_transparency_to_widget(popup.content)
        popup.open()

class DnDApp(App):
    """Haupt-App-Klasse."""
    def build(self):
        Window.fullscreen = 'auto'
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        
        root = FloatLayout()

        sm = ScreenManager()
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterSheet(name='sheet'))
        sm.add_widget(OptionsScreen(name='options'))
        sm.add_widget(LevelUpScreen(name='level_up'))

        root.add_widget(sm)

        return root

if __name__ == '__main__':
    DnDApp().run()