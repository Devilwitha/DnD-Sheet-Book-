import random
import json
import os
import pickle
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
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup

class PlayerCharacterSheet(Screen):
    """A version of the character sheet for the online player."""

    def __init__(self, **kwargs):
        super(PlayerCharacterSheet, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.character = None
        self.update_event = None
        self.map_data = None

    def on_enter(self, *args):
        self.character = self.app.character
        self.update_sheet()
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.5)

    def on_leave(self, *args):
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

    def check_for_updates(self, dt):
        if not self.network_manager.running and self.network_manager.mode == 'idle':
            self.handle_disconnect("Verbindung zum DM verloren.")
            return

        try:
            while True:
                source, message = self.network_manager.incoming_messages.get_nowait()
                msg_type = message.get('type')
                payload = message.get('payload')

                if msg_type == 'KICK':
                    self.handle_disconnect("Du wurdest vom DM gekickt.")
                    return
                elif msg_type == 'GAME_STATE_UPDATE':
                    self.update_player_list(payload.get('players', []))
                    self.update_initiative_order(payload.get('initiative', []))
                elif msg_type == 'SET_CHARACTER_DATA':
                    self.character = Character.from_dict(payload)
                    self.app.character = self.character
                    self.update_sheet()
                    create_styled_popup(title="Update", content=Label(text="Dein Charakter wurde vom DM aktualisiert."), size_hint=(0.6, 0.4)).open()
                elif msg_type == 'SAVE_YOUR_CHARACTER':
                    self.save_character()
                elif msg_type == 'MAP_DATA':
                    self.map_data = payload
                    self.ids.view_map_button.disabled = False
                    # Optionally, switch to the map screen automatically
                    # self.view_map()
        except Empty:
            pass

    def view_map(self):
        if self.map_data:
            map_screen = self.manager.get_screen('player_map')
            map_screen.set_map_data(self.map_data)
            self.manager.current = 'player_map'

    def handle_disconnect(self, message):
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None
            create_styled_popup(title="Verbindung getrennt", content=Label(text=message), size_hint=(0.7, 0.4)).open()
            self.manager.current = 'main'

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
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            text = f"{item['name']} ({item['quantity']})"
            item_row.add_widget(Label(text=text, halign='left', valign='middle'))
            btn_box = BoxLayout(size_hint_x=0.5)
            if 'healing' in item:
                btn = Button(text="Benutzen")
                btn.bind(on_press=partial(self.use_healing_item, index))
                btn_box.add_widget(btn)
            item_row.add_widget(btn_box)
            self.ids.inventory_layout.add_widget(item_row)

    def sync_character_to_host(self):
        """Sends the entire character object to the host."""
        if not self.character: return
        self.network_manager.send_to_dm("SET_CHARACTER_DATA", self.character.to_dict())

    def use_healing_item(self, item_index, instance):
        if 0 <= item_index < len(self.character.inventory):
            item = self.character.inventory[item_index]
            if 'healing' in item:
                total_healed = sum(random.randint(1, item['healing']['dice']) for _ in range(item['healing']['count']))
                self.character.hit_points = min(self.character.max_hit_points, self.character.hit_points + total_healed)
                log_msg = f"{self.character.name} benutzt {item['name']} und heilt {total_healed} HP."
                self.send_log_to_dm(log_msg)
                item['quantity'] -= 1
                if item['quantity'] <= 0:
                    self.character.inventory.pop(item_index)
                self.update_sheet()
                self.sync_character_to_host()

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
            grid.add_widget(Label(text=level_name, font_size='18sp', size_hint_y=None, height=40))
            for spell_name in sorted(spell_list):
                btn = Button(text=spell_name, size_hint_y=None, height=40)
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
        button_box = BoxLayout(size_hint_y=None, height=44, spacing=10)
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
        spell_level_str = str(spell_level)
        if spell_level > 0:
            if self.character.current_spell_slots.get(spell_level_str, 0) > 0:
                self.character.current_spell_slots[spell_level_str] -= 1
            else:
                create_styled_popup(title="Fehler", content=Label(text="Keine Zauberplätze auf diesem Grad verfügbar.")).open()
                return
        log_msg = f"{self.character.name} wirkt {spell_name}."
        self.send_log_to_dm(log_msg)
        self.update_sheet()
        self.sync_character_to_host()

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
        num_dice, dice_type = map(int, damage_str.split('d'))
        ability_mod = (self.character.abilities.get(weapon_info.get('ability', 'Stärke'), 10) - 10) // 2
        roll = sum(random.randint(1, dice_type) for _ in range(num_dice))
        total_damage = roll + ability_mod
        result_text = f"Schaden: {roll} + {ability_mod} = {total_damage}"
        self.send_log_to_dm(f"verursacht {total_damage} Schaden mit {weapon_name}.")
        create_styled_popup(title="Schadenswurf", content=Label(text=result_text), size_hint=(0.5, 0.3)).open()

    def show_rest_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        short_rest_btn = Button(text="Kurze Rast")
        long_rest_btn = Button(text="Lange Rast")
        content.add_widget(short_rest_btn)
        content.add_widget(long_rest_btn)
        popup = create_styled_popup(title="Rasten", content=content, size_hint=(0.5, 0.4))
        def do_short_rest(instance):
            regain_amount = max(1, self.character.level // 2)
            self.character.hit_dice = min(self.character.max_hit_dice, self.character.hit_dice + regain_amount)
            self.send_log_to_dm(f"macht eine kurze Rast.")
            self.update_sheet()
            self.sync_character_to_host()
            popup.dismiss()
        def do_long_rest(instance):
            self.character.hit_points = self.character.max_hit_points
            self.character.hit_dice = self.character.max_hit_dice
            if hasattr(self.character, 'current_spell_slots'):
                self.character.current_spell_slots = {k: v for k, v in self.character.max_spell_slots.items()}
            self.send_log_to_dm(f"macht eine lange Rast.")
            self.update_sheet()
            self.sync_character_to_host()
            popup.dismiss()
        short_rest_btn.bind(on_press=do_short_rest)
        long_rest_btn.bind(on_press=do_long_rest)
        popup.open()

    def update_player_list(self, players):
        player_list_widget = self.ids.player_list_view
        player_list_widget.clear_widgets()
        for player_name in players:
            player_list_widget.add_widget(Label(text=player_name, size_hint_y=None, height=30))

    def update_initiative_order(self, initiative_order):
        initiative_widget = self.ids.initiative_view
        initiative_widget.clear_widgets()
        for roll, name in initiative_order:
            initiative_widget.add_widget(Label(text=f"{roll}: {name}", size_hint_y=None, height=30))

    def show_full_character_sheet(self):
        sheet_screen = self.manager.get_screen('sheet')
        sheet_screen.load_character(self.character)
        self.manager.current = 'sheet'

    def save_character(self):
        if not self.character: return
        saves_dir = "saves"
        os.makedirs(saves_dir, exist_ok=True)
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        filepath = os.path.join(saves_dir, filename)
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(self.character, f)
            create_styled_popup(title="Gespeichert", content=Label(text=f"Charakter als '{filepath}' gespeichert."), size_hint=(0.7, 0.4)).open()
        except Exception as e:
            create_styled_popup(title="Fehler", content=Label(text=f"Fehler beim Speichern: {e}"), size_hint=(0.7, 0.4)).open()
