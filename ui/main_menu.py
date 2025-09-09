import os
import pickle
import sys

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen

from utils.helpers import apply_background, apply_styles_to_widget

class MainMenu(Screen):
    """Hauptmenü-Bildschirm zum Erstellen oder Laden eines Charakters."""
    def __init__(self, **kwargs):
        super(MainMenu, self).__init__(**kwargs)

        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Image(source='logo/logo.png'))

        self.new_char_button = Button(text="Neuen Charakter erstellen", on_press=self.switch_to_creator)
        layout.add_widget(self.new_char_button)

        self.load_char_button = Button(text="Charakter laden", on_press=self.show_load_popup)
        layout.add_widget(self.load_char_button)

        self.options_button = Button(text="Optionen", on_press=self.switch_to_options)
        layout.add_widget(self.options_button)

        self.add_widget(layout)

    def on_pre_enter(self, *args):
        """Wird ausgeführt, bevor der Bildschirm angezeigt wird."""
        apply_background(self)
        apply_styles_to_widget(self)

    def switch_to_options(self, instance):
        self.manager.current = 'options'

    def restart_app(self, dt):
        os.execv(sys.executable, ['python'] + sys.argv)

    def switch_to_creator(self, instance):
        self.manager.current = 'creator'

    def show_load_popup(self, instance):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))

        files = [f for f in os.listdir('.') if f.endswith('.char')]
        for filename in files:
            char_layout = BoxLayout(size_hint_y=None, height=40)

            load_btn = Button(text=filename)
            load_btn.bind(on_release=lambda btn, fn=filename: self.load_character(fn))

            delete_btn = Button(text="Löschen", size_hint_x=0.3)
            delete_btn.bind(on_release=lambda btn, fn=filename: self.delete_character_popup(fn))

            char_layout.add_widget(load_btn)
            char_layout.add_widget(delete_btn)
            popup_layout.add_widget(char_layout)

        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(popup_layout)
        content.add_widget(scroll_view)

        apply_styles_to_widget(content)
        self.popup = Popup(title="Charakter laden", content=content, size_hint=(0.8, 0.8))
        self.popup.open()

    def delete_character_popup(self, filename):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=f"Möchtest du {filename} wirklich löschen?"))

        btn_layout = BoxLayout(spacing=10)
        yes_btn = Button(text="Ja", on_press=lambda x: self.delete_character(filename))
        no_btn = Button(text="Nein", on_press=lambda x: self.confirmation_popup.dismiss())
        btn_layout.add_widget(yes_btn)
        btn_layout.add_widget(no_btn)

        content.add_widget(btn_layout)

        apply_styles_to_widget(content)
        self.confirmation_popup = Popup(title="Löschen bestätigen", content=content, size_hint=(0.6, 0.4))
        self.confirmation_popup.open()

    def delete_character(self, filename):
        try:
            os.remove(filename)
            self.confirmation_popup.dismiss()
            self.popup.dismiss()
            self.show_load_popup(None) # Refresh the list
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Löschen des Charakters: {e}")

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
