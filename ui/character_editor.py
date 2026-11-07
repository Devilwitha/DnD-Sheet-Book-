
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

from utils.data_manager import (
    RACE_DATA, CLASS_DATA, ALIGNMENT_DATA, BACKGROUND_DATA
)
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from core.character import Character
from utils.storage import CharacterRepository

class CharacterEditor(Screen):
    """Editor-Bildschirm zum Bearbeiten eines vorhandenen Charakters."""
    def __init__(self, **kwargs):
        super(CharacterEditor, self).__init__(**kwargs)
        self.character = None
        self.inputs = {}
        self.ability_scores_labels = {}
        self.build_ui()

    def build_ui(self):
        from kivy.metrics import dp

        layout = self.ids.editor_layout
        layout.clear_widgets()
        # Header and back button live in the KV file above the ScrollView.

        default_height = dp(48)
        multiline_height = dp(120)

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
            label = Label(text=f"{field_name}:", size_hint=(1, None), height=default_height,
                          halign='left', valign='middle', font_size='16sp', padding=(dp(4), 0))
            label.bind(size=label.setter('text_size'))
            layout.add_widget(label)

            if widget_type == "TextInput":
                widget = TextInput(size_hint=(1, None), height=height,
                                   multiline=(height > default_height), font_size='16sp')
            else:
                widget = Spinner(values=values, size_hint=(1, None), height=height, font_size='16sp')

            self.inputs[field_name] = widget
            layout.add_widget(widget)

        abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
        for ability in abilities:
            label = Label(text=ability, size_hint=(1, None), height=default_height,
                          halign='left', valign='middle', font_size='16sp', padding=(dp(4), 0))
            label.bind(size=label.setter('text_size'))
            layout.add_widget(label)

            stat_box = BoxLayout(size_hint=(1, None), height=default_height, spacing=dp(6))
            minus_btn = Button(text="-", size_hint=(1, 1), font_size='22sp',
                               on_press=partial(self.adjust_ability, ability, -1))
            score_label = Label(size_hint=(1, 1), font_size='18sp')
            plus_btn = Button(text="+", size_hint=(1, 1), font_size='22sp',
                              on_press=partial(self.adjust_ability, ability, 1))

            stat_box.add_widget(minus_btn)
            stat_box.add_widget(score_label)
            stat_box.add_widget(plus_btn)

            self.ability_scores_labels[ability] = score_label
            layout.add_widget(stat_box)

        layout.add_widget(Label(size_hint=(1, None), height=dp(10)))
        layout.add_widget(Label(size_hint=(1, None), height=dp(10)))

        save_button = Button(text="Änderungen speichern", on_press=self.save_character,
                             size_hint=(1, None), height=dp(52), font_size='16sp')
        layout.add_widget(save_button)
        layout.add_widget(Label(size_hint=(1, None), height=dp(52)))

        # Bottom spacing so the footer stays reachable when scrolled
        layout.add_widget(Label(size_hint=(1, None), height=dp(24)))
        layout.add_widget(Label(size_hint=(1, None), height=dp(24)))

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def load_character(self, character):
        # Work on a copy; the original is only updated after a successful save
        self.original_character = character
        self.character = Character.from_dict(character.to_dict())
        self.inputs['Name'].text = self.character.name
        self.inputs['Rasse'].text = self.character.race
        self.inputs['Klasse'].text = self.character.char_class
        self.inputs['Rasse'].disabled = True
        self.inputs['Klasse'].disabled = True
        self.inputs['Gesinnung'].text = self.character.alignment
        self.inputs['Hintergrund'].text = self.character.background
        self.inputs['Persönliche Merkmale'].text = self.character.personality_traits
        self.inputs['Ideale'].text = self.character.ideals
        self.inputs['Bindungen'].text = self.character.bonds
        self.inputs['Makel'].text = self.character.flaws

        for ability, label in self.ability_scores_labels.items():
            label.text = str(self.character.base_abilities.get(ability, 10))

    def adjust_ability(self, ability, amount, instance):
        current_score = int(self.ability_scores_labels[ability].text)
        new_score = max(1, min(20, current_score + amount))
        self.ability_scores_labels[ability].text = str(new_score)

    def save_character(self, instance):
        if not self.character:
            return

        name = self.inputs['Name'].text.strip()
        if not name:
            self.show_popup('Fehler', 'Bitte gib einen Namen ein.')
            return

        if (self.inputs['Rasse'].text != self.character.race
                or self.inputs['Klasse'].text != self.character.char_class):
            self.inputs['Rasse'].text = self.character.race
            self.inputs['Klasse'].text = self.character.char_class
            self.show_popup('Nicht möglich',
                            'Rasse und Klasse können nach der Erstellung nicht geändert werden. '
                            'Dafür wird ein neuer Charakter benötigt; ein bestehender Charakter '
                            'kann nicht zurückgesetzt oder neu ausgewürfelt werden.')
            return

        candidate = Character.from_dict(self.character.to_dict())
        if hasattr(self.original_character, "_local_save_name"):
            candidate._local_save_name = self.original_character._local_save_name
        candidate.name = name
        candidate.alignment = self.inputs['Gesinnung'].text
        candidate.background = self.inputs['Hintergrund'].text
        candidate.personality_traits = self.inputs['Persönliche Merkmale'].text
        candidate.ideals = self.inputs['Ideale'].text
        candidate.bonds = self.inputs['Bindungen'].text
        candidate.flaws = self.inputs['Makel'].text
        for ability, label in self.ability_scores_labels.items():
            candidate.base_abilities[ability] = int(label.text)

        candidate.recalculate_derived()  # keeps HP, resources, choices, inventory

        try:
            CharacterRepository().save(candidate)
        except Exception as e:
            self.show_popup('Fehler', f'Fehler beim Speichern des Charakters: {e}')
            return

        self.character = candidate
        original = getattr(self, 'original_character', None)
        if original is not None and original is not candidate:
            original.__dict__.update(Character.from_dict(candidate.to_dict()).__dict__)
        self.show_popup('Gespeichert', f"Charakter '{candidate.name}' wurde erfolgreich aktualisiert.")
        self.manager.current = 'main'

    def show_popup(self, title, message):
        create_styled_popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()
