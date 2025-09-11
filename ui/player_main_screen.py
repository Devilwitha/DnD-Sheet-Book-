import socket
import threading
import json
import random
from functools import partial
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup
from data_manager import WEAPON_DATA, SPELL_DATA, SKILL_LIST

class PlayerMainScreen(Screen):
    """The main screen for the player during a game session."""
    def __init__(self, **kwargs):
        super(PlayerMainScreen, self).__init__(**kwargs)
        self.character = None
        self.client_socket = None
        self.listener_thread = None
        self.summary = ""

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def set_player_data(self, character, client_socket, summary=""):
        self.character = character
        self.client_socket = client_socket
        self.summary = summary
        print(f"[*] Player screen initialized for {self.character.name}.")
        self.update_ui()
        self.start_listening()

    def update_ui(self):
        self.update_character_sheet()
        self.update_log("Verbunden mit DM.")
        if self.summary:
            self.ids.summary_label.text = f"[b]Letzte Zusammenfassung:[/b]\n{self.summary}"
        else:
            self.ids.summary_label.text = ""

    def update_character_sheet(self):
        if self.character:
            self.ids.character_display.character = self.character

    def start_listening(self):
        if self.client_socket:
            self.listener_thread = threading.Thread(target=self.listen_for_dm_messages)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            print("[*] Player listener thread started.")

    def listen_for_dm_messages(self):
        while self.client_socket:
            try:
                header = self.client_socket.recv(10)
                if not header:
                    print("[*] DM disconnected (header empty).")
                    Clock.schedule_once(lambda dt: self.handle_disconnect())
                    break

                msg_len = int(header.strip())
                data = b''
                while len(data) < msg_len:
                    chunk = self.client_socket.recv(msg_len - len(data))
                    if not chunk: break
                    data += chunk

                response = json.loads(data.decode('utf-8'))
                msg_type = response.get('type')
                payload = response.get('payload')

                if msg_type == 'LOG':
                    Clock.schedule_once(lambda dt, m=payload: self.update_log(m))
                elif msg_type == 'KICK':
                    print("[*] Kicked by DM.")
                    Clock.schedule_once(lambda dt: self.handle_disconnect())
                    break
                elif msg_type == 'UPDATE_CHAR':
                    attr = payload.get('attribute')
                    value = payload.get('value')
                    if hasattr(self.character, attr):
                        current_value = getattr(self.character, attr)
                        setattr(self.character, attr, current_value + value)
                        self.update_character_sheet()
                else:
                    print(f"[*] Received unhandled message type: {msg_type}")

            except (socket.error, OSError) as e:
                print(f"[!] Player listener thread error: {e}")
                Clock.schedule_once(lambda dt: self.handle_disconnect())
                break
        print("[*] Player listener thread finished.")

    def update_log(self, message):
        self.ids.log_output.text += f"\n{message}"

    def handle_disconnect(self):
        self.update_log("DM hat die Verbindung getrennt. Kehre zum Hauptmenü zurück.")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        Clock.schedule_once(lambda dt: self.go_to_main_menu(), 3)

    def go_to_main_menu(self):
        self.manager.current = 'main'

    def on_leave(self, *args):
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

    def send_message_to_dm(self, msg_type, payload):
        if not self.client_socket: return
        try:
            data = json.dumps({'type': msg_type, 'payload': payload})
            message = f"{len(data):<10}{data}"
            self.client_socket.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"[!] Failed to send message to DM: {e}")

    def roll_d20(self):
        roll = random.randint(1, 20)
        popup = create_styled_popup(title='d20 Wurf',
                                    content=Label(text=f'Du hast eine {roll} gewürfelt.'),
                                    size_hint=(0.6, 0.4))
        popup.open()
        self.send_message_to_dm("LOG", f"{self.character.name} hat eine {roll} gewürfelt.")

    def roll_damage(self):
        if not self.character: return
        weapon_name = self.character.equipped_weapon
        weapon_info = WEAPON_DATA.get(weapon_name, WEAPON_DATA["Unbewaffneter Schlag"])
        ability_name = weapon_info["ability"]
        modifier = (self.character.abilities[ability_name] - 10) // 2
        parts = weapon_info["damage"].split('d')
        num_dice = int(parts[0])
        dice_type = int(parts[1])
        roll_total = sum(random.randint(1, dice_type) for _ in range(num_dice))
        total_damage = roll_total + modifier

        log_msg = f"{self.character.name} greift mit {weapon_name} an: {max(1, total_damage)} Schaden!"
        popup_msg = f"{weapon_info['damage']} ({roll_total}) + {ability_name[:3]}-Mod ({modifier}) = {max(1, total_damage)} Schaden"
        popup = create_styled_popup(title="Schadenswurf", content=Label(text=popup_msg), size_hint=(0.8, 0.4))
        popup.open()
        self.send_message_to_dm("LOG", log_msg)

    def show_spells_popup(self):
        # This method now only opens the list of spells.
        # The confirmation and casting logic is handled by show_spell_confirmation_popup.
        content = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=10)
        grid.bind(minimum_height=grid.setter('height'))

        if not self.character.spells:
            grid.add_widget(Label(text="Dieser Charakter kann nicht zaubern.", size_hint_y=None, height=40))
        else:
            for spell_level in sorted(self.character.spells.keys()):
                spell_list = self.character.spells[spell_level]
                if not spell_list: continue
                level_name = "Zaubertricks" if spell_level == 0 else f"Level {spell_level}"
                if spell_level > 0:
                    max_slots = self.character.max_spell_slots.get(str(spell_level), 0)
                    current_slots = self.character.current_spell_slots.get(str(spell_level), 0)
                    level_name += f" ({current_slots}/{max_slots})"
                grid.add_widget(Label(text=level_name, font_size='18sp', size_hint_y=None, height=40))
                for spell_name in sorted(spell_list):
                    btn = Button(text=spell_name, size_hint_y=None, height=40)
                    btn.bind(on_press=partial(self.show_spell_confirmation_popup, spell_name))
                    grid.add_widget(btn)

        content.add_widget(grid)
        apply_styles_to_widget(content)
        self.spells_popup = create_styled_popup(title="Zauberbuch", content=content, size_hint=(0.8, 0.9))
        self.spells_popup.open()

    def show_spell_confirmation_popup(self, spell_name, instance):
        """Shows spell details and asks for confirmation to cast."""
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        label = Label(text=text, markup=True, size_hint_y=None)
        label.bind(width=lambda *x: label.setter('text_size')(label, (label.width, None)),
                   texture_size=lambda *x: label.setter('height')(label, label.texture_size[1]))
        scroll.add_widget(label)
        content.add_widget(scroll)

        button_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        cast_button = Button(text="Wirken")
        cancel_button = Button(text="Abbrechen")
        button_layout.add_widget(cast_button)
        button_layout.add_widget(cancel_button)
        content.add_widget(button_layout)

        popup = create_styled_popup(title=spell_name, content=content, size_hint=(0.8, 0.8))

        cast_button.bind(on_press=lambda x: (self.cast_spell(spell_name), popup.dismiss(), self.spells_popup.dismiss()))
        cancel_button.bind(on_press=popup.dismiss)

        popup.open()

    def cast_spell(self, spell_name):
        spell_info = SPELL_DATA.get(spell_name, {})
        spell_level = spell_info.get("level", 0)
        spell_level_str = str(spell_level)

        if spell_level == 0 or self.character.current_spell_slots.get(spell_level_str, 0) > 0:
            if spell_level > 0:
                self.character.current_spell_slots[spell_level_str] -= 1

            log_msg = f"{self.character.name} wirkt '{spell_name}'."
            self.send_message_to_dm("LOG", log_msg)
            self.update_log(log_msg)
            self.update_character_sheet()

            popup = create_styled_popup(title="Zauber gewirkt", content=Label(text=f"Du hast '{spell_name}' gewirkt."), size_hint=(0.7, 0.4))
            popup.open()
        else:
            popup = create_styled_popup(title="Keine Zauberplätze", content=Label(text=f"Keine Zauberplätze für Level {spell_level} mehr übrig."), size_hint=(0.7, 0.4))
            popup.open()

    def use_item(self, item, instance):
        if 'healing' in item:
            healing_info = item.get('healing')
            num_dice = healing_info['count']
            dice_type = healing_info['dice']
            total_healed = sum(random.randint(1, dice_type) for _ in range(num_dice))

            self.character.hit_points = min(self.character.max_hit_points, self.character.hit_points + total_healed)

            log_msg = f"{self.character.name} benutzt {item['name']} und heilt {total_healed} HP."
            self.send_message_to_dm("LOG", log_msg)
            self.update_log(log_msg)

            item['quantity'] -= 1
            if item['quantity'] <= 0:
                self.character.inventory.remove(item)

            self.update_character_sheet()

    def show_info_popup(self):
        if not self.character: return
        prof_text = ", ".join(self.character.proficiencies)
        lang_text = ", ".join(self.character.languages)
        text = (
            f"[b]Gesinnung:[/b] {self.character.alignment}\n\n"
            f"[b]Hintergrund:[/b] {self.character.background}\n\n"
            f"[b]Kompetenzen:[/b]\n{prof_text}\n\n"
            f"[b]Sprachen:[/b]\n{lang_text}"
        )
        content = ScrollView()
        label = Label(text=text, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        create_styled_popup(title="Charakter-Informationen", content=content, size_hint=(0.8, 0.8)).open()

    def show_rest_popup(self):
        if not self.character: return
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        long_rest_btn = Button(text="Grosse Rast")
        content.add_widget(long_rest_btn)
        popup = create_styled_popup(title="Rasten", content=content, size_hint=(0.6, 0.4))
        long_rest_btn.bind(on_press=lambda x: (self.do_long_rest(), popup.dismiss()))
        apply_styles_to_widget(content)
        popup.open()

    def do_long_rest(self):
        self.character.long_rest()
        self.update_character_sheet()
        log_msg = f"{self.character.name} hat eine grosse Rast gemacht."
        self.send_message_to_dm("LOG", log_msg)
        self.update_log(log_msg)
