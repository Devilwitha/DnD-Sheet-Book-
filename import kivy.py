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
import random
import pickle
import os

# In einer vollständigen Anwendung würden diese Daten aus externen Dateien (z. B. JSON) geladen.
# =============================================================================================
# ERWEITERTE KLASSEN-DATEN
# =============================================================================================
CLASS_DATA = {
    "Barbar": {
        "hit_die": 12,
        "features": {1: ["Ungepanzerte Verteidigung", "Kampfrausch"], 2: ["Gefahrensinn", "Tollkühner Angriff"], 3: ["Pfad des Barbaren"]}
    },
    "Barde": {
        "hit_die": 8,
        "features": {1: ["Barden-Inspiration", "Zauber wirken"], 2: ["Hansdampf in allen Gassen", "Lied der Rast"], 3: ["Barden-Kollegium", "Expertise"]}
    },
    "Druide": {
        "hit_die": 8,
        "features": {1: ["Druidisch", "Zauber wirken"], 2: ["Druidenzirkel", "Tiergestalt"], 3: ["-"]}
    },
    "Hexenmeister": {
        "hit_die": 8,
        "features": {1: ["Außerweltlicher Schutzpatron", "Magie des Paktes"], 2: ["Schaurige Anrufungen"], 3: ["Gabe des Paktes"]}
    },
    "Kämpfer": {
        "hit_die": 10,
        "features": {1: ["Kampfstil", "Zweite Luft"], 2: ["Tatendrang"], 3: ["Archetyp des Kämpfers"]}
    },
    "Kleriker": {
        "hit_die": 8,
        "features": {1: ["Göttliche Domäne", "Zauber wirken"], 2: ["Göttliche Macht fokussieren"], 3: ["-"]}
    },
    "Magier": {
        "hit_die": 6,
        "features": {1: ["Arkane Erholung", "Zauber wirken"], 2: ["Arkane Tradition"], 3: ["-"]}
    },
    "Mönch": {
        "hit_die": 8,
        "features": {1: ["Ungepanzerte Verteidigung", "Kampfkunst"], 2: ["Ki", "Ungepanzerte Bewegung"], 3: ["Mönchstradition", "Gegnerschlag ablenken"]}
    },
    "Paladin": {
        "hit_die": 10,
        "features": {1: ["Göttliches Gespür", "Handauflegen"], 2: ["Kampfstil", "Zauber wirken", "Göttliches Niederstrecken"], 3: ["Heiliger Eid", "Göttliche Gesundheit"]}
    },
    "Schurke": {
        "hit_die": 8,
        "features": {1: ["Expertise", "Hinterhältiger Angriff", "Diebeszeichen"], 2: ["Listige Aktion"], 3: ["Schurkenarchetyp"]}
    },
    "Waldläufer": {
        "hit_die": 10,
        "features": {1: ["Erzfeind", "Erfahrener Erkunder"], 2: ["Kampfstil", "Zauber wirken"], 3: ["Archetyp des Waldläufers", "Scharfes Bewusstsein"]}
    },
    "Zauberer": {
        "hit_die": 6,
        "features": {1: ["Ursprung der Zauberei", "Zauber wirken"], 2: ["Quelle der Magie"], 3: ["Metamagie"]}
    }
}

# =============================================================================================
# ERWEITERTE RASSEN-DATEN
# =============================================================================================
RACE_DATA = {
    "Drachenblütiger": {"ability_score_increase": {"Stärke": 2, "Charisma": 1}},
    "Elf (Hochelf)": {"ability_score_increase": {"Geschicklichkeit": 2, "Intelligenz": 1}},
    "Elf (Waldelf)": {"ability_score_increase": {"Geschicklichkeit": 2, "Weisheit": 1}},
    "Elf (Drow)": {"ability_score_increase": {"Geschicklichkeit": 2, "Charisma": 1}},
    "Gnom (Felsengnom)": {"ability_score_increase": {"Intelligenz": 2, "Konstitution": 1}},
    "Gnom (Waldgnom)": {"ability_score_increase": {"Intelligenz": 2, "Geschicklichkeit": 1}},
    "Halb-Elf": {"ability_score_increase": {"Charisma": 2, "Geschicklichkeit": 1, "Konstitution": 1}}, # +2 CHA, +1 auf zwei andere
    "Halbling (Leichtfuß)": {"ability_score_increase": {"Geschicklichkeit": 2, "Charisma": 1}},
    "Halbling (Stämmiger)": {"ability_score_increase": {"Geschicklichkeit": 2, "Konstitution": 1}},
    "Halb-Ork": {"ability_score_increase": {"Stärke": 2, "Konstitution": 1}},
    "Mensch": {"ability_score_increase": {"Stärke": 1, "Geschicklichkeit": 1, "Konstitution": 1, "Intelligenz": 1, "Weisheit": 1, "Charisma": 1}},
    "Tiefling": {"ability_score_increase": {"Charisma": 2, "Intelligenz": 1}},
    "Zwerg (Hügelzwerg)": {"ability_score_increase": {"Konstitution": 2, "Weisheit": 1}},
    "Zwerg (Bergzwerg)": {"ability_score_increase": {"Konstitution": 2, "Stärke": 2}}
}

class Character:
    """Klasse zur Speicherung aller Charakterdaten."""
    def __init__(self, name, race, char_class):
        self.name = name
        self.race = race
        self.char_class = char_class
        self.level = 1
        self.experience_points = 0
        # Basiswerte vor Rassenboni
        self.base_abilities = {
            "Stärke": 10, "Geschicklichkeit": 10, "Konstitution": 10,
            "Intelligenz": 10, "Weisheit": 10, "Charisma": 10
        }
        self.abilities = self.base_abilities.copy()
        self.hit_points = 0
        self.max_hit_points = 0
        self.features = []
        self.inventory = []
        self.update_race_bonuses()
        self.calculate_initial_hp()
        self.update_features()

    def update_race_bonuses(self):
        """Aktualisiert die Attributswerte basierend auf der Rasse."""
        self.abilities = self.base_abilities.copy() # Setzt auf Basiswerte zurück
        bonuses = RACE_DATA.get(self.race, {}).get("ability_score_increase", {})
        for ability, bonus in bonuses.items():
            if ability in self.abilities:
                self.abilities[ability] += bonus

    def calculate_initial_hp(self):
        """Berechnet die anfänglichen Trefferpunkte."""
        hit_die = CLASS_DATA.get(self.char_class, {}).get("hit_die", 8)
        con_modifier = (self.abilities["Konstitution"] - 10) // 2
        self.max_hit_points = hit_die + con_modifier
        self.hit_points = self.max_hit_points

    def update_features(self):
        """Sammelt alle Features bis zum aktuellen Level."""
        self.features = []
        class_features = CLASS_DATA.get(self.char_class, {}).get("features", {})
        for lvl in range(1, self.level + 1):
            if lvl in class_features:
                self.features.extend(class_features[lvl])

    def level_up(self):
        """Führt einen Stufenaufstieg durch."""
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
        """Wechselt zum Charaktererstellungsbildschirm."""
        self.manager.current = 'creator'

    def show_load_popup(self, instance):
        """Zeigt ein Popup zum Laden von Charakterdateien an."""
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
        """Lädt einen Charakter aus einer Datei."""
        try:
            with open(filename, 'rb') as f:
                character = pickle.load(f)
            self.manager.get_screen('sheet').load_character(character)
            self.manager.current = 'sheet'
            self.popup.dismiss()
        except Exception as e:
            print(f"Fehler beim Laden des Charakters: {e}")

class CharacterCreator(Screen):
    """Bildschirm zur Erstellung eines neuen Charakters."""
    def __init__(self, **kwargs):
        super(CharacterCreator, self).__init__(**kwargs)
        layout = GridLayout(cols=2, padding=10, spacing=10)

        layout.add_widget(Label(text="Name:"))
        self.name_input = TextInput(multiline=False)
        layout.add_widget(self.name_input)

        layout.add_widget(Label(text="Rasse:"))
        self.race_input = Spinner(text='Mensch', values=sorted(list(RACE_DATA.keys())))
        layout.add_widget(self.race_input)

        layout.add_widget(Label(text="Klasse:"))
        self.class_input = Spinner(text='Kämpfer', values=sorted(list(CLASS_DATA.keys())))
        layout.add_widget(self.class_input)

        self.ability_scores_labels = {}
        for ability in ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]:
            layout.add_widget(Label(text=ability))
            self.ability_scores_labels[ability] = Label(text="10")
            layout.add_widget(self.ability_scores_labels[ability])
        
        roll_button = Button(text="Attribute auswürfeln (4d6, niedrigsten verwerfen)", on_press=self.roll_abilities)
        layout.add_widget(roll_button)
        
        create_button = Button(text="Charakter erstellen", on_press=self.create_character)
        layout.add_widget(create_button)

        self.add_widget(layout)

    def roll_abilities(self, instance):
        """Würfelt die Attributswerte."""
        for ability in self.ability_scores_labels:
            rolls = sorted([random.randint(1, 6) for _ in range(4)])
            score = sum(rolls[1:])
            self.ability_scores_labels[ability].text = str(score)

    def create_character(self, instance):
        """Erstellt einen neuen Charakter und wechselt zum Charakterblatt."""
        name = self.name_input.text.strip()
        race = self.race_input.text
        char_class = self.class_input.text

        if name:
            character = Character(name, race, char_class)
            for ability, label in self.ability_scores_labels.items():
                character.base_abilities[ability] = int(label.text)
            
            character.update_race_bonuses()
            character.calculate_initial_hp()
            
            self.manager.get_screen('sheet').load_character(character)
            self.manager.current = 'sheet'

class CharacterSheet(Screen):
    """Bildschirm zur Anzeige und Verwaltung des Charakterblatts."""
    def __init__(self, **kwargs):
        super(CharacterSheet, self).__init__(**kwargs)
        self.character = None
        self.main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        self.add_widget(self.main_layout)

    def load_character(self, character):
        """Lädt die Daten eines Charakters und aktualisiert die Anzeige."""
        self.character = character
        self.update_sheet()

    def update_sheet(self):
        """Aktualisiert die Benutzeroberfläche mit den aktuellen Charakterdaten."""
        self.main_layout.clear_widgets()
        if not self.character:
            return

        # Header
        header = BoxLayout(size_hint_y=None, height=40)
        header.add_widget(Label(text=f"Name: {self.character.name}"))
        header.add_widget(Label(text=f"Rasse: {self.character.race}"))
        header.add_widget(Label(text=f"Klasse: {self.character.char_class}"))
        header.add_widget(Label(text=f"Level: {self.character.level}"))
        self.main_layout.add_widget(header)
        
        # Hauptbereich mit ScrollView
        body_layout = GridLayout(cols=2, spacing=10)
        
        # Linke Spalte: Attribute und Aktionen
        left_column = BoxLayout(orientation='vertical', spacing=10, size_hint_x=0.5)
        
        # Attribute
        ability_layout = GridLayout(cols=2, size_hint_y=None, height=200)
        for ability, score in self.character.abilities.items():
            modifier = (score - 10) // 2
            sign = "+" if modifier >= 0 else ""
            ability_layout.add_widget(Label(text=f"{ability}:"))
            ability_layout.add_widget(Label(text=f"{score} ({sign}{modifier})"))
        left_column.add_widget(ability_layout)

        # Trefferpunkte
        hp_layout = BoxLayout(orientation='vertical', size_hint_y=None, height=80)
        hp_layout.add_widget(Label(text="Trefferpunkte", font_size='20sp'))
        self.hp_label = Label(text=f"{self.character.hit_points} / {self.character.max_hit_points}", font_size='18sp')
        hp_layout.add_widget(self.hp_label)
        left_column.add_widget(hp_layout)

        # Aktionen
        actions_layout = GridLayout(cols=2, size_hint_y=None, height=100)
        attack_button = Button(text="Angriff\n(Stärke)", on_press=self.roll_attack)
        actions_layout.add_widget(attack_button)
        damage_button = Button(text="Schaden\n(1d8+STR)", on_press=self.roll_damage)
        actions_layout.add_widget(damage_button)
        str_save_button = Button(text="STR-Rettungswurf", on_press=lambda x: self.roll_check("Stärke"))
        actions_layout.add_widget(str_save_button)
        dex_save_button = Button(text="DEX-Rettungswurf", on_press=lambda x: self.roll_check("Geschicklichkeit"))
        actions_layout.add_widget(dex_save_button)
        left_column.add_widget(actions_layout)
        
        body_layout.add_widget(left_column)

        # Rechte Spalte: Features
        right_column = BoxLayout(orientation='vertical', spacing=5)
        right_column.add_widget(Label(text="Features & Fähigkeiten", font_size='20sp', size_hint_y=None, height=30))
        
        features_text = "\n".join(f"- {feature}" for feature in self.character.features)
        features_label = Label(text=features_text, size_hint_y=None, valign='top', halign='left')
        features_label.bind(texture_size=features_label.setter('size'))
        
        scroll_view = ScrollView()
        scroll_view.add_widget(features_label)
        right_column.add_widget(scroll_view)
        body_layout.add_widget(right_column)

        self.main_layout.add_widget(body_layout)
        
        # Footer: Steuerung
        control_layout = BoxLayout(size_hint_y=None, height=50)
        levelup_button = Button(text="Level Up", on_press=self.level_up_popup)
        control_layout.add_widget(levelup_button)
        save_button = Button(text="Charakter speichern", on_press=self.save_character)
        control_layout.add_widget(save_button)
        main_menu_button = Button(text="Hauptmenü", on_press=self.go_to_main_menu)
        control_layout.add_widget(main_menu_button)
        self.main_layout.add_widget(control_layout)

    def roll_check(self, ability):
        modifier = (self.character.abilities[ability] - 10) // 2
        roll = random.randint(1, 20)
        result = roll + modifier
        self.show_popup(f"{ability}-Wurf", f"Wurf: 1d20 ({roll}) + Mod ({modifier}) = {result}")

    def roll_attack(self, instance):
        modifier = (self.character.abilities["Stärke"] - 10) // 2
        roll = random.randint(1, 20)
        result = roll + modifier
        self.show_popup("Angriffswurf", f"Angriff: 1d20 ({roll}) + STR ({modifier}) = {result}")

    def roll_damage(self, instance):
        modifier = (self.character.abilities["Stärke"] - 10) // 2
        roll = random.randint(1, 8)
        result = roll + modifier
        self.show_popup("Schadenswurf", f"Schaden: 1d8 ({roll}) + STR ({modifier}) = {max(1, result)}")

    def level_up_popup(self, instance):
        new_level = self.character.level + 1
        features = CLASS_DATA.get(self.character.char_class, {}).get("features", {}).get(new_level, ["Keine neuen Features auf diesem Level."])
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Möchtest du auf Level {new_level} aufsteigen?"))
        content.add_widget(Label(text="Neue Features:"))
        for feature in features:
            content.add_widget(Label(text=f"- {feature}", font_size='12sp'))
            
        confirm_button = Button(text="Bestätigen", size_hint_y=None, height=44)
        popup = Popup(title="Level Up!", content=content, size_hint=(0.7, 0.7))
        confirm_button.bind(on_release=lambda btn: self.perform_level_up(popup))
        content.add_widget(confirm_button)
        popup.open()

    def perform_level_up(self, popup):
        self.character.level_up()
        popup.dismiss()
        self.update_sheet()
        self.show_popup("Level Up!", f"Du bist jetzt Level {self.character.level}!")

    def save_character(self, instance):
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter '{self.character.name}' wurde als '{filename}' gespeichert.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Speichern: {e}")
            
    def go_to_main_menu(self, instance):
        self.manager.current = 'main'

    def show_popup(self, title, message):
        popup = Popup(title=title, content=Label(text=message), size_hint=(0.5, 0.5))
        popup.open()

class DnDApp(App):
    """Haupt-App-Klasse."""
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterSheet(name='sheet'))
        return sm

if __name__ == '__main__':
    DnDApp().run()