import random
from functools import partial
import pickle
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.properties import ObjectProperty

from data_manager import WEAPON_DATA, SKILL_LIST, SPELL_DATA
from utils.helpers import apply_background, apply_styles_to_widget

class CharacterSheet(Screen):
    """Finaler Charakterbogen mit allen neuen Features."""
    main_layout = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(CharacterSheet, self).__init__(**kwargs)
        self.character = None
        self.currency_labels = {}

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def load_character(self, character):
        self.character = character
        if self.character:
            if hasattr(self.character, 'normalize_spells'):
                self.character.normalize_spells()
        self.update_sheet()

    def update_sheet(self):
        if not self.character:
            return

        self.ids.name_label.text = f"{self.character.name}"
        self.ids.class_label.text = f"{self.character.race} {self.character.char_class} {self.character.level}"
        self.ids.alignment_label.text = f"Gesinnung: {self.character.alignment}"

        self.ids.stats_box.clear_widgets()
        for ability, score in self.character.abilities.items():
            modifier = (score - 10) // 2
            sign = "+" if modifier >= 0 else ""
            self.ids.stats_box.add_widget(Label(text=f"{ability}:"))
            self.ids.stats_box.add_widget(Label(text=f"{score} ({sign}{modifier})"))
        self.ids.stats_box.add_widget(Label(text="Rüstungsklasse:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.armor_class}"))
        self.ids.stats_box.add_widget(Label(text="Initiative:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.initiative:+}"))
        self.ids.stats_box.add_widget(Label(text="Bewegungsrate:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.speed}m ({int(self.character.speed / 1.5)} Felder)"))

        self.ids.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"

        self.ids.weapon_spinner.text = self.character.equipped_weapon
        self.ids.weapon_spinner.values = sorted(WEAPON_DATA.keys())

        self.ids.currency_box.clear_widgets()
        self.ids.currency_box.add_widget(Label(text="Währung", size_hint_x=None, width=100))
        self.ids.currency_box.add_widget(Label())
        self.ids.currency_box.add_widget(Label())
        for curr in ["KP", "SP", "EP", "GM", "PP"]:
            self.ids.currency_box.add_widget(Label(text=f"{curr}:"))
            self.currency_labels[curr] = Label(text=str(self.character.currency[curr]))
            self.ids.currency_box.add_widget(self.currency_labels[curr])
            btn_box = BoxLayout()
            btn_box.add_widget(Button(text="-", on_press=partial(self.change_currency, curr, -1)))
            btn_box.add_widget(Button(text="+", on_press=partial(self.change_currency, curr, 1)))
            self.ids.currency_box.add_widget(btn_box)

        self.ids.features_layout.clear_widgets()
        for feature in self.character.features:
            btn = Button(text=feature['name'], size_hint_y=None, height=40, halign='left', valign='middle', padding=(10, 0))
            btn.bind(on_press=partial(self.show_feature_popup, feature))
            self.ids.features_layout.add_widget(btn)

        self.update_inventory_display()
        self.update_equipment_display()


    def show_popup(self, title, message):
        content = ScrollView()
        label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        Popup(title=title, content=content, size_hint=(0.8, 0.8)).open()

    def update_weapon(self, text):
        self.character.equipped_weapon = text

    def change_hp(self, amount):
        self.character.hit_points += amount
        self.character.hit_points = max(0, min(self.character.hit_points, self.character.max_hit_points))
        self.ids.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"

    def change_currency(self, currency, amount, instance):
        self.character.currency[currency] += amount
        self.character.currency[currency] = max(0, self.character.currency[currency])
        self.currency_labels[currency].text = str(self.character.currency[currency])

    def update_inventory_display(self):
        self.ids.inventory_layout.clear_widgets()
        for item_name, quantity in self.character.inventory.items():
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            item_row.add_widget(Label(text=f"{item_name} ({quantity})", halign='left', valign='middle'))

            btn_box = BoxLayout(size_hint_x=0.4)
            btn_box.add_widget(Button(text="-", on_press=partial(self.adjust_item_quantity, item_name, -1)))
            btn_box.add_widget(Button(text="+", on_press=partial(self.adjust_item_quantity, item_name, 1)))

            item_row.add_widget(btn_box)
            self.ids.inventory_layout.add_widget(item_row)

    def adjust_item_quantity(self, item_name, amount, instance):
        self.character.inventory[item_name] += amount
        if self.character.inventory[item_name] <= 0:
            del self.character.inventory[item_name]
        self.update_inventory_display()

    def update_equipment_display(self):
        self.ids.equipment_layout.clear_widgets()
        for item_name, ac_bonus in self.character.equipment.items():
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            item_row.add_widget(Label(text=f"{item_name} (AC: +{ac_bonus})", halign='left', valign='middle'))

            remove_btn = Button(text="-", size_hint_x=0.2)
            remove_btn.bind(on_press=partial(self.remove_equipment, item_name))

            item_row.add_widget(remove_btn)
            self.ids.equipment_layout.add_widget(item_row)

    def remove_equipment(self, item_name, instance):
        if item_name in self.character.equipment:
            del self.character.equipment[item_name]
            self.character.calculate_armor_class()
            self.update_sheet()

    def show_add_equipment_popup(self):
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
        apply_styles_to_widget(content)
        popup.open()

    def show_add_item_popup(self):
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
        apply_styles_to_widget(content)
        popup.open()

    def roll_damage(self):
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

    def show_info_popup(self):
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

    def show_spells_popup(self):
        content = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=10)
        grid.bind(minimum_height=grid.setter('height'))

        if not self.character.spells:
            grid.add_widget(Label(text="Dieser Charakter kann nicht zaubern.", size_hint_y=None, height=40))
        else:
            for spell_level in sorted(self.character.spells.keys()):
                spell_list = self.character.spells[spell_level]
                if not spell_list: continue

                level_name = "Zaubertricks" if spell_level == 0 else f"Level {spell_level} Zauber"
                grid.add_widget(Label(text=level_name, font_size='18sp', size_hint_y=None, height=40))
                for spell_name in sorted(spell_list):
                    btn = Button(text=spell_name, size_hint_y=None, height=40)
                    btn.bind(on_press=partial(self.show_spell_details_popup, spell_name))
                    grid.add_widget(btn)

        content.add_widget(grid)
        apply_styles_to_widget(content)
        Popup(title="Zauberbuch", content=content, size_hint=(0.8, 0.9)).open()

    def show_spell_details_popup(self, spell_name, instance):
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )
        self.show_popup(spell_name, text)

    def open_level_up_screen(self):
        self.manager.get_screen('level_up').set_character(self.character)
        self.manager.current = 'level_up'

    def save_character(self):
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        try:
            with open(filename, 'wb') as f:
                pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter als '{filename}' gespeichert.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Speichern: {e}")
