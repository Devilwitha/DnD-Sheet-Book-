# main.py

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
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
import random
import pickle
import os
from functools import partial

# Importiert die Daten aus der separaten Datei
from dnd_data import CLASS_DATA, RACE_DATA, WEAPON_DATA, SPELL_DATA

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
        self.inventory = {}  # Geändert zu Dictionary für die Anzahl
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

    def initialize_character(self):
        """Sammelt alle Daten bei der Erstellung oder beim Laden."""
        self.update_race_bonuses_and_speed()
        self.collect_proficiencies_and_languages()
        self.calculate_initial_hp()
        self.update_features()
        self.prepare_spellbook()

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
        """Stellt das Zauberbuch für den Charakter zusammen."""
        self.spells = CLASS_DATA.get(self.char_class, {}).get("spells", {})

    def level_up(self):
        self.level += 1
        hit_die = CLASS_DATA.get(self.char_class, {}).get("hit_die", 8)
        con_modifier = (self.abilities["Konstitution"] - 10) // 2
        hp_increase = random.randint(1, hit_die) + con_modifier
        self.max_hit_points += max(1, hp_increase)
        self.hit_points = self.max_hit_points
        self.update_features()

class MainMenu(Screen):
    """Hauptmenü-Bildschirm zum Erstellen oder Laden eines Charakters."""
    def __init__(self, **kwargs):
        super(MainMenu, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Label(text="D&D Charakterblatt", font_size='32sp'))
        new_char_button = Button(text="Neuen Charakter erstellen", on_press=self.switch_to_creator)
        layout.add_widget(new_char_button)
        load_char_button = Button(text="Charakter laden", on_press=self.show_load_popup)
        layout.add_widget(load_char_button)
        self.add_widget(layout)
    def switch_to_creator(self, instance):
        self.manager.current = 'creator'
    def show_load_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))
        files = [f for f in os.listdir('.') if f.endswith('.char')]
        for filename in files:
            btn = Button(text=filename, size_hint_y=None, height=40)
            btn.bind(on_release=lambda btn_instance, fn=filename: self.load_character(fn))
            popup_layout.add_widget(btn)
        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(popup_layout)
        content.add_widget(scroll_view)
        self.popup = Popup(title="Charakter laden", content=content, size_hint=(0.8, 0.8))
        self.popup.open()
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

        self.inputs = {}
        default_height = 44
        multiline_height = 120
        
        fields = [
            ("Name", "TextInput", default_height, []),
            ("Rasse", "Spinner", default_height, sorted(RACE_DATA.keys())),
            ("Klasse", "Spinner", default_height, sorted(CLASS_DATA.keys())),
            ("Gesinnung", "TextInput", default_height, []),
            ("Hintergrund", "TextInput", default_height, []),
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

        character.initialize_character()
        
        self.manager.get_screen('sheet').load_character(character)
        self.manager.current = 'sheet'
    
    def show_popup(self, title, message):
        Popup(title=title, content=Label(text=message), size_hint=(0.5, 0.5)).open()

class CharacterSheet(Screen):
    """Finaler Charakterbogen mit allen neuen Features."""
    def __init__(self, **kwargs):
        super(CharacterSheet, self).__init__(**kwargs)
        self.character = None
        self.main_layout = BoxLayout(orientation='vertical')
        self.add_widget(self.main_layout)

    def load_character(self, character):
        self.character = character
        self.update_sheet()

    def update_sheet(self):
        self.main_layout.clear_widgets()
        if not self.character: return

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
        
        stats_box = GridLayout(cols=2, size_hint_y=None, height=220)
        for ability, score in self.character.abilities.items():
            modifier = (score - 10) // 2
            sign = "+" if modifier >= 0 else ""
            stats_box.add_widget(Label(text=f"{ability}:"))
            stats_box.add_widget(Label(text=f"{score} ({sign}{modifier})"))
        stats_box.add_widget(Label(text="Bewegungsrate:"))
        stats_box.add_widget(Label(text=f"{self.character.speed}m"))
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
            # ===== KORRIGIERTE ZEILE HIER =====
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
        content_layout.add_widget(right_column)
        
        scroll_view.add_widget(content_layout)
        self.main_layout.add_widget(scroll_view)

        footer = BoxLayout(size_hint_y=None, height=50, spacing=5)
        footer.add_widget(Button(text="Info", on_press=self.show_info_popup))
        footer.add_widget(Button(text="Zauber", on_press=self.show_spells_popup))
        footer.add_widget(Button(text="Level Up", on_press=self.level_up_popup))
        footer.add_widget(Button(text="Speichern", on_press=self.save_character))
        footer.add_widget(Button(text="Hauptmenü", on_press=lambda x: setattr(self.manager, 'current', 'main')))
        self.main_layout.add_widget(footer)

    def show_popup(self, title, message):
        content = ScrollView()
        label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(width=lambda *x: label.setter('text_size')(label, (label.width, None)),
                   texture_size=lambda *x: label.setter('height')(label, label.texture_size[1]))
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
        self.show_popup("Schadenswurf", f"{weapon_info['damage']} ({roll_total}) + {ability_name[:3]}-Mod ({modifier}) = {max(1, total_damage)} Schaden")

    def show_feature_popup(self, feature, instance):
        self.show_popup(feature['name'], feature['desc'])

    def show_info_popup(self, instance):
        prof_text = ", ".join(self.character.proficiencies)
        lang_text = ", ".join(self.character.languages)
        text = (
            f"[b]Hintergrund:[/b] {self.character.background}\n\n"
            f"[b]Kompetenzen:[/b]\n{prof_text}\n\n"
            f"[b]Sprachen:[/b]\n{lang_text}\n\n"
            f"[b]Persönliche Merkmale:[/b]\n{self.character.personality_traits}\n\n"
            f"[b]Ideale:[/b]\n{self.character.ideals}\n\n"
            f"[b]Bindungen:[/b]\n{self.character.bonds}\n\n"
            f"[b]Makel:[/b]\n{self.character.flaws}"
        )
        self.show_popup("Charakter-Informationen", text)

    def show_spells_popup(self, instance):
        content = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=10)
        grid.bind(minimum_height=grid.setter('height'))

        if not self.character.spells:
            grid.add_widget(Label(text="Dieser Charakter kann nicht zaubern.", size_hint_y=None, height=40))
        else:
            for spell_level, spell_list in self.character.spells.items():
                level_name = "Zaubertricks" if spell_level == 'cantrips' else f"Level {spell_level[-1]} Zauber"
                grid.add_widget(Label(text=level_name, font_size='18sp', size_hint_y=None, height=40))
                for spell_name in spell_list:
                    btn = Button(text=spell_name, size_hint_y=None, height=40)
                    btn.bind(on_press=partial(self.show_spell_details_popup, spell_name))
                    grid.add_widget(btn)
        content.add_widget(grid)
        Popup(title="Zauberbuch", content=content, size_hint=(0.8, 0.9)).open()

    def show_spell_details_popup(self, spell_name, instance):
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )
        self.show_popup(spell_name, text)

    def level_up_popup(self, instance):
        new_level = self.character.level + 1
        features = CLASS_DATA.get(self.character.char_class, {}).get("features", {}).get(new_level, [{"name": "-", "desc": "-"}])
        feature_names = ", ".join([f['name'] for f in features])
        content = BoxLayout(orientation='vertical')
        content.add_widget(Label(text=f"Aufstieg auf Level {new_level}"))
        content.add_widget(Label(text="Neue Features: " + feature_names))
        btn = Button(text="Bestätigen")
        content.add_widget(btn)
        popup = Popup(title="Level Up", content=content, size_hint=(0.6, 0.5))
        def perform_levelup(instance):
            self.character.level_up()
            self.update_sheet()
            popup.dismiss()
        btn.bind(on_press=perform_levelup)
        popup.open()
        
    def save_character(self, instance):
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter als '{filename}' gespeichert.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Speichern: {e}")

class DnDApp(App):
    """Haupt-App-Klasse."""
    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        sm = ScreenManager()
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterSheet(name='sheet'))
        return sm

if __name__ == '__main__':
    DnDApp().run()