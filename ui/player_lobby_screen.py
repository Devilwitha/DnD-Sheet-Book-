import os
import pickle
import json
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.clock import Clock
from zeroconf import ServiceBrowser, Zeroconf
from kivy.app import App
from kivy.uix.screenmanager import Screen
from utils.helpers import apply_background, apply_styles_to_widget, ensure_character_attributes, create_styled_popup
from core.character import Character
import socket

class DMListener:
    def __init__(self, screen):
        self.screen = screen

    def remove_service(self, zeroconf, type, name):
        Clock.schedule_once(lambda dt: self.screen.remove_dm_service(name))

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            Clock.schedule_once(lambda dt: self.screen.add_dm_service(info))

    def update_service(self, zeroconf, type, name):
        self.add_service(self, zeroconf, type, name)


class PlayerLobbyScreen(Screen):
    """Screen for the player lobby."""
    def __init__(self, **kwargs):
        super(PlayerLobbyScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.zeroconf = None
        self.browser = None
        self.available_dms = {}
        self.selected_dm_info = None
        self.selected_char_file = None
        self.char_popup = None

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)
        self.ids.selected_char_label.text = "Kein Charakter ausgewählt"
        self.selected_char_file = None
        self.selected_dm_info = None

    def on_enter(self, *args):
        self.start_discovery()

    def start_discovery(self):
        self.ids.dm_list.clear_widgets()
        self.available_dms.clear()
        try:
            self.zeroconf = Zeroconf()
            listener = DMListener(self)
            self.browser = ServiceBrowser(self.zeroconf, "_dndgame._tcp.local.", listener)
            print("[*] Started Zeroconf discovery.")
        except Exception as e:
            print(f"[!] Zeroconf failed to start: {e}")
            self.show_error_popup("Netzwerkfehler", "Konnte keine Spiele im lokalen Netzwerk suchen.")

    def add_dm_service(self, info):
        if info.name in self.available_dms:
            return
        self.available_dms[info.name] = info
        dm_button = Button(
            text=f"{info.properties.get(b'name', b'Unknown DM').decode()} at {socket.inet_ntoa(info.addresses[0])}",
            size_hint_y=None, height=60
        )
        dm_button.bind(on_press=lambda x, i=info: self.select_dm(i))
        self.ids.dm_list.add_widget(dm_button)

    def remove_dm_service(self, name):
        if name in self.available_dms:
            del self.available_dms[name]
            self.ids.dm_list.clear_widgets()
            for info in self.available_dms.values():
                self.add_dm_service(info)

    def select_dm(self, info):
        self.selected_dm_info = info
        # Optionally highlight the selected DM in the UI

    def show_char_selection_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))
        saves_dir = "saves"
        os.makedirs(saves_dir, exist_ok=True)
        files = [f for f in os.listdir(saves_dir) if f.endswith('.char')]
        for filename in files:
            btn = Button(text=filename, size_hint_y=None, height=44)
            btn.bind(on_release=lambda b, fn=filename: self.select_character(fn))
            popup_layout.add_widget(btn)
        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(popup_layout)
        content.add_widget(scroll_view)
        self.char_popup = create_styled_popup(title="Charakter auswählen", content=content, size_hint=(0.8, 0.8))
        self.char_popup.open()

    def select_character(self, filename):
        self.selected_char_file = filename
        self.ids.selected_char_label.text = f"Ausgewählt: {filename}"
        if self.char_popup:
            self.char_popup.dismiss()

    def connect_to_dm(self):
        if not self.selected_char_file:
            self.show_error_popup("Fehler", "Bitte wähle zuerst einen Charakter aus.")
            return
        if not self.selected_dm_info:
            self.show_error_popup("Fehler", "Bitte wähle zuerst einen DM aus der Liste aus.")
            return

        try:
            filepath = os.path.join("saves", self.selected_char_file)
            with open(filepath, 'rb') as f:
                character = pickle.load(f)
            character = ensure_character_attributes(character)
            self.app.character = character # Store character on the app for other screens
        except Exception as e:
            self.show_error_popup("Ladefehler", f"Konnte Charakter nicht laden: {e}")
            return

        ip_address = socket.inet_ntoa(self.selected_dm_info.addresses[0])
        port = self.selected_dm_info.port

        success, message = self.network_manager.connect_to_server(ip_address, port, character)

        if success:
            self.manager.current = 'player_waiting'
        else:
            self.show_error_popup("Verbindungsfehler", f"Konnte keine Verbindung zum DM herstellen: {message}")

    def on_leave(self, *args):
        self.stop_discovery()

    def stop_discovery(self):
        if self.zeroconf:
            self.zeroconf.close()
            self.zeroconf = None
            self.browser = None

    def show_error_popup(self, title, message):
        create_styled_popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()
