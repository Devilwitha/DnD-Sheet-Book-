from kivy.metrics import dp
import random
import json
import os
from utils.storage import CharacterRepository, safe_save_path
from utils.non_ui_helpers import roll_dice
from functools import partial
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.app import App
from queue import Empty

from core.character import Character
from utils.data_manager import WEAPON_DATA, SPELL_DATA
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, get_user_saves_dir

class PlayerCharacterSheet(Screen):
    """A version of the character sheet for the online player."""

    def __init__(self, **kwargs):
        super(PlayerCharacterSheet, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.character = None
        self.map_data = None

    def on_enter(self, *args):
        # The character should be set by the app's global loop or waiting screen
        self.character = self.app.character
        self.update_sheet()

    def view_map(self):
        # The map data is now managed by the global loop
        if self.manager.has_screen('player_map'):
            self.manager.current = 'player_map'

    def update_sheet(self):
        if not self.character: return
        self.ids.name_label.text = f"{self.character.name}"
        self.ids.class_label.text = f"{self.character.race} {self.character.char_class} {self.character.level}"
        self.ids.alignment_label.text = f"Gesinnung: {self.character.alignment}"
        self.ids.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"
        self.ids.weapon_label.text = f"Waffe: {self.character.equipped_weapon}"

        self.ids.stats_box.clear_widgets()
        for ability, score in self.character.abilities.items():
            modifier = (score - 10) // 2
            sign = "+" if modifier >= 0 else ""
            self.ids.stats_box.add_widget(Label(text=f"{ability}:"))
            self.ids.stats_box.add_widget(Label(text=f"{score} ({sign}{modifier})"))

        self.ids.currency_box.clear_widgets()
        for curr, amount in self.character.currency.items():
            self.ids.currency_box.add_widget(Label(text=f"{curr}:"))
            self.ids.currency_box.add_widget(Label(text=str(amount)))

        self.update_inventory_display()

    def update_inventory_display(self):
        self.ids.inventory_layout.clear_widgets()
        for index, item in enumerate(self.character.inventory):
            item_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=10)
            text = f"{item['name']} ({item['quantity']})"
            item_label = Label(text=text, halign='left', valign='middle')
            item_label.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
            item_row.add_widget(item_label)
            btn_box = BoxLayout(size_hint_x=None, width=dp(104))
            if 'healing' in item:
                btn = Button(text="Benutzen")
                btn.bind(on_press=partial(self.use_healing_item, index))
                btn_box.add_widget(btn)
            if btn_box.children:
                item_row.add_widget(btn_box)
            item_label.bind(texture_size=lambda w, v, row=item_row: setattr(row, 'height', max(dp(48), v[1] + dp(12))))
            self.ids.inventory_layout.add_widget(item_row)

    def sync_character_to_host(self):
        """Legacy entry point: client snapshots must never replace DM state."""
        self.app._popup('DM-Spielstand', 'Freie Charakteränderungen nimmt die Spielleitung vor.')

    def use_healing_item(self, item_index, instance):
        self.app.request_character_action('healing_item', index=item_index)

    def show_spells_popup(self):
        if not hasattr(self.character, 'spells') or not self.character.spells:
            create_styled_popup(title="Zauber", content=Label(text="Keine Zauber bekannt."), size_hint=(0.8, 0.8)).open()
            return
        content = BoxLayout(orientation='vertical', spacing=10)
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for spell_level in sorted(self.character.spells.keys()):
            spell_list = self.character.spells[spell_level]
            if not spell_list: continue
            level_name = f"Level {spell_level}" if spell_level > 0 else "Zaubertricks"
            grid.add_widget(Label(text=level_name, font_size='18sp', size_hint_y=None, height=dp(48)))
            for spell_name in sorted(spell_list):
                btn = Button(text=spell_name, size_hint_y=None, height=dp(48))
                btn.bind(on_press=partial(self.show_spell_confirmation_popup, spell_name))
                grid.add_widget(btn)
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(grid)
        content.add_widget(scroll)
        create_styled_popup(title="Zauber", content=content, size_hint=(0.8, 0.9)).open()

    def show_spell_confirmation_popup(self, spell_name, instance):
        spell = SPELL_DATA.get(spell_name)
        if not spell: return
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        title_label = Label(text=f"[b]{spell_name}[/b]", markup=True, font_size='18sp')
        desc_label = Label(text=spell.get('desc', 'Keine Beschreibung verfügbar.'), text_size=(self.width*0.7, None))
        button_box = BoxLayout(size_hint_y=None, height=dp(48), spacing=10)
        cast_button = Button(text="Wirken")
        cancel_button = Button(text="Abbrechen")
        button_box.add_widget(cast_button)
        button_box.add_widget(cancel_button)
        content.add_widget(title_label)
        content.add_widget(desc_label)
        content.add_widget(button_box)
        popup = create_styled_popup(title="Zauber bestätigen", content=content, size_hint=(0.8, 0.6))
        def do_cast(instance):
            self.cast_spell(spell_name, spell.get('level', 0))
            popup.dismiss()
        cast_button.bind(on_press=do_cast)
        cancel_button.bind(on_press=popup.dismiss)
        popup.open()

    def cast_spell(self, spell_name, spell_level):
        self.app.request_character_action('cast_spell', spell=spell_name)

    def send_log_to_dm(self, log_message):
        self.network_manager.send_to_dm("LOG", log_message)

    def roll_d20(self, ability_name):
        modifier = (self.character.abilities.get(ability_name, 10) - 10) // 2
        roll = random.randint(1, 20)
        total = roll + modifier
        result_text = f"Wurf: {roll} + {modifier} ({ability_name}) = {total}"
        self.send_log_to_dm(f"führt einen {ability_name}-Wurf aus: {result_text}")
        create_styled_popup(title=f"{ability_name} Wurf", content=Label(text=result_text), size_hint=(0.5, 0.3)).open()

    def roll_damage(self):
        weapon_name = self.character.equipped_weapon
        weapon_info = WEAPON_DATA.get(weapon_name)
        if not weapon_info: return
        damage_str = weapon_info.get('damage', '1d4')
        ability_mod = (self.character.abilities.get(weapon_info.get('ability', 'Stärke'), 10) - 10) // 2
        roll = roll_dice(damage_str)
        total_damage = roll + ability_mod
        result_text = f"Schaden: {roll} + {ability_mod} = {total_damage}"
        self.send_log_to_dm(f"verursacht {total_damage} Schaden mit {weapon_name}.")
        create_styled_popup(title="Schadenswurf", content=Label(text=result_text), size_hint=(0.5, 0.3)).open()

    def show_rest_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        short_rest_btn = Button(text="Kurze Rast (1 Trefferwürfel)")
        long_rest_btn = Button(text="Lange Rast (DM-Freigabe)")
        content.add_widget(short_rest_btn)
        content.add_widget(long_rest_btn)
        popup = create_styled_popup(title="Rasten", content=content, size_hint=(0.5, 0.4))
        def do_short_rest(instance):
            self.app.request_character_action('short_rest', dice=1)
            popup.dismiss()
        def do_long_rest(instance):
            self.app.request_character_action('long_rest')
            popup.dismiss()
        short_rest_btn.bind(on_press=do_short_rest)
        long_rest_btn.bind(on_press=do_long_rest)
        popup.open()

    def update_player_list(self, players):
        player_list_widget = self.ids.player_list_view
        player_list_widget.clear_widgets()
        for player_name in players:
            player_list_widget.add_widget(Label(text=player_name, size_hint_y=None, height=dp(48)))

    def update_initiative_order(self, initiative_order):
        initiative_widget = self.ids.initiative_view
        initiative_widget.clear_widgets()
        for roll, name in initiative_order:
            initiative_widget.add_widget(Label(text=f"{roll}: {name}", size_hint_y=None, height=dp(48)))

    def show_full_character_sheet(self):
        self.app.source_screen = self.name
        sheet_screen = self.manager.get_screen('sheet')
        sheet_screen.load_character(self.character)
        self.manager.current = 'sheet'

    def save_character(self):
        if not self.character: return
        saves_dir = get_user_saves_dir("characters")
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        filepath = os.path.join(saves_dir, filename)
        try:
            filepath = CharacterRepository().save(self.character)
            create_styled_popup(title="Gespeichert", content=Label(text=f"Charakter als '{filepath}' gespeichert."), size_hint=(0.7, 0.4)).open()
        except Exception as e:
            create_styled_popup(title="Fehler", content=Label(text=f"Fehler beim Speichern: {e}"), size_hint=(0.7, 0.4)).open()
