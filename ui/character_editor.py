import pickle
import random
from functools import partial

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen

from data_manager import (
    RACE_DATA, CLASS_DATA, ALIGNMENT_DATA, BACKGROUND_DATA
)
from utils.helpers import apply_background, apply_styles_to_widget

class CharacterEditor(Screen):
    """Editor-Bildschirm zum Bearbeiten eines vorhandenen Charakters."""
    def __init__(self, **kwargs):
        super(CharacterEditor, self).__init__(**kwargs)
        self.character = None
        self.inputs = {}
        self.ability_scores_labels = {}
        self.build_ui()

    def build_ui(self):
        layout = self.ids.editor_layout
        layout.clear_widgets()

        back_button = Button(text="Zurück zum Hauptmenü",
                             on_press=lambda x: setattr(self.manager, 'current', 'main'),
                             size_hint_y=None,
                             height=44)
        layout.add_widget(back_button)
        layout.add_widget(Label(text="", size_hint_y=None, height=44))

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
                widget = Spinner(values=values, size_hint_y=None, height=height)

            self.inputs[field_name] = widget
            layout.add_widget(widget)

        abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
        for ability in abilities:
            label = Label(text=ability, size_hint=(None, None), width=180, height=default_height, halign='left', valign='middle')
            layout.add_widget(label)

            stat_box = BoxLayout(size_hint_y=None, height=default_height)
            minus_btn = Button(text="-", on_press=partial(self.adjust_ability, ability, -1))
            score_label = Label()
            plus_btn = Button(text="+", on_press=partial(self.adjust_ability, ability, 1))

            stat_box.add_widget(minus_btn)
            stat_box.add_widget(score_label)
            stat_box.add_widget(plus_btn)

            self.ability_scores_labels[ability] = score_label
            layout.add_widget(stat_box)

        layout.add_widget(Label(size_hint_y=None, height=10))
        layout.add_widget(Label(size_hint_y=None, height=10))

        save_button = Button(text="Änderungen speichern", on_press=self.save_character, size_hint_y=None, height=default_height)
        layout.add_widget(save_button)

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def load_character(self, character):
        self.character = character
        self.inputs["Name"].text = self.character.name
        self.inputs["Rasse"].text = self.character.race
        self.inputs["Klasse"].text = self.character.char_class
        self.inputs["Gesinnung"].text = self.character.alignment
        self.inputs["Hintergrund"].text = self.character.background
        self.inputs["Persönliche Merkmale"].text = self.character.personality_traits
        self.inputs["Ideale"].text = self.character.ideals
        self.inputs["Bindungen"].text = self.character.bonds
        self.inputs["Makel"].text = self.character.flaws

        for ability, label in self.ability_scores_labels.items():
            label.text = str(self.character.base_abilities.get(ability, 10))

    def adjust_ability(self, ability, amount, instance):
        current_score = int(self.ability_scores_labels[ability].text)
        new_score = max(1, min(20, current_score + amount))
        self.ability_scores_labels[ability].text = str(new_score)

    def save_character(self, instance):
        if not self.character:
            return

        self.character.name = self.inputs["Name"].text.strip()
        self.character.race = self.inputs["Rasse"].text
        self.character.char_class = self.inputs["Klasse"].text
        self.character.alignment = self.inputs["Gesinnung"].text
        self.character.background = self.inputs["Hintergrund"].text
        self.character.personality_traits = self.inputs["Persönliche Merkmale"].text
        self.character.ideals = self.inputs["Ideale"].text
        self.character.bonds = self.inputs["Bindungen"].text
        self.character.flaws = self.inputs["Makel"].text

        for ability, label in self.ability_scores_labels.items():
            self.character.base_abilities[ability] = int(label.text)

        self.character.initialize_character()

        filename = f"{self.character.name.replace(' ', '_').lower()}.char"
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter '{self.character.name}' wurde erfolgreich aktualisiert.")
            self.manager.current = 'main'
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Speichern des Charakters: {e}")

    def show_popup(self, title, message):
        Popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()
