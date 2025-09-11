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
from kivy.uix.checkbox import CheckBox
from kivy.properties import ObjectProperty
from kivy.app import App

from data_manager import WEAPON_DATA, SKILL_LIST, SPELL_DATA
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup

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

        app = App.get_running_app()
        if hasattr(app, 'source_screen') and app.source_screen == 'dm_main':
            self.ids.dm_back_button.height = 50
            self.ids.dm_back_button.opacity = 1
            self.ids.dm_back_button.disabled = False
            self.ids.main_menu_button.height = 0
            self.ids.main_menu_button.opacity = 0
            self.ids.main_menu_button.disabled = True
            del app.source_screen
        else:
            self.ids.dm_back_button.height = 0
            self.ids.dm_back_button.opacity = 0
            self.ids.dm_back_button.disabled = True
            self.ids.main_menu_button.height = 50
            self.ids.main_menu_button.opacity = 1
            self.ids.main_menu_button.disabled = False

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
        self.ids.stats_box.add_widget(Label(text="Trefferwürfel:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.hit_dice}/{self.character.max_hit_dice}"))


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

            minus_btn = Button(text="-", on_press=partial(self.change_currency, curr, -1))
            plus_btn = Button(text="+", on_press=partial(self.change_currency, curr, 1))

            apply_styles_to_widget(minus_btn)
            apply_styles_to_widget(plus_btn)

            btn_box.add_widget(minus_btn)
            btn_box.add_widget(plus_btn)
            self.ids.currency_box.add_widget(btn_box)

        self.ids.features_layout.clear_widgets()
        for feature in self.character.features:
            btn = Button(text=feature['name'], size_hint_y=None, height=40, halign='left', valign='middle', padding=(10, 0))
            btn.bind(on_press=partial(self.show_feature_popup, feature))
            apply_styles_to_widget(btn)
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
        create_styled_popup(title=title, content=content, size_hint=(0.8, 0.8)).open()

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
        for index, item in enumerate(self.character.inventory):
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            text = f"{item['name']} ({item['quantity']})"
            if 'healing' in item:
                text += f" (Heilung: {item['healing']['count']}d{item['healing']['dice']})"
            item_row.add_widget(Label(text=text, halign='left', valign='middle'))
            btn_box = BoxLayout(size_hint_x=0.5)
            if 'healing' in item:
                btn_box.add_widget(Button(text="Benutzen", on_press=partial(self.use_healing_item, index)))
            btn_box.add_widget(Button(text="-", on_press=partial(self.adjust_item_quantity, index, -1)))
            btn_box.add_widget(Button(text="+", on_press=partial(self.adjust_item_quantity, index, 1)))
            item_row.add_widget(btn_box)
            self.ids.inventory_layout.add_widget(item_row)

    def adjust_item_quantity(self, item_index, amount, instance):
        if 0 <= item_index < len(self.character.inventory):
            self.character.inventory[item_index]['quantity'] += amount
            if self.character.inventory[item_index]['quantity'] <= 0:
                self.character.inventory.pop(item_index)
            self.update_inventory_display()

    def use_healing_item(self, item_index, instance):
        if 0 <= item_index < len(self.character.inventory):
            item = self.character.inventory[item_index]
            healing_info = item.get('healing')
            if healing_info:
                num_dice = healing_info['count']
                dice_type = healing_info['dice']
                total_healed = sum(random.randint(1, dice_type) for _ in range(num_dice))
                self.character.hit_points = min(self.character.max_hit_points, self.character.hit_points + total_healed)
                self.show_popup("Gegenstand benutzt", f"{total_healed} HP wiederhergestellt mit {item['name']}.")
                self.adjust_item_quantity(item_index, -1, None)
                self.update_sheet()

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
        pass # Implementation omitted for brevity

    def show_add_item_popup(self):
        pass # Implementation omitted for brevity

    def roll_damage(self):
        pass # Implementation omitted for brevity

    def show_feature_popup(self, feature, instance):
        self.show_popup(feature['name'], feature['desc'])

    def show_info_popup(self):
        pass # Implementation omitted for brevity

    def show_spells_popup(self):
        pass # Implementation omitted for brevity

    def cast_spell(self, spell_name, spell_level, spell_details_popup):
        pass # Implementation omitted for brevity

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

    def roll_d20(self):
        roll = random.randint(1, 20)
        self.show_popup("d20 Wurf", f"Du hast eine {roll} gewürfelt.")

    def roll_initiative(self):
        roll = random.randint(1, 20)
        total = roll + self.character.initiative
        self.show_popup("Initiativewurf", f"Wurf: {roll} + {self.character.initiative} = {total}")

    def show_rest_popup(self):
        pass # Implementation omitted for brevity

    def do_long_rest(self):
        self.character.long_rest()
        self.update_sheet()
        self.show_popup("Grosse Rast", "Du bist vollständig ausgeruht. HP und Zauberplätze wurden wiederhergestellt.")

    def show_short_rest_popup(self):
        pass # Implementation omitted for brevity
