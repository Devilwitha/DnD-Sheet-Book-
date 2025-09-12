import os
import pickle
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, ensure_character_attributes

class CharacterMenuScreen(Screen):
    """Screen for loading, creating, or editing a character."""
    def __init__(self, **kwargs):
        super(CharacterMenuScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def go_to_screen(self, screen_name):
        self.app.change_screen(screen_name, source_screen=self.name)

    def go_back(self):
        if self.app.source_screen:
            self.app.change_screen(self.app.source_screen)
        else:
            self.app.change_screen('main') # Fallback

    def show_load_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))

        saves_dir = "saves"
        os.makedirs(saves_dir, exist_ok=True)
        files = [f for f in os.listdir(saves_dir) if f.endswith('.char')]
        for filename in files:
            char_layout = BoxLayout(size_hint_y=None, height=40)

            load_btn = Button(text=filename)
            load_btn.bind(on_release=lambda btn, fn=filename: self.load_character(fn))

            edit_btn = Button(text="Bearbeiten", size_hint_x=0.3)
            edit_btn.bind(on_release=lambda btn, fn=filename: self.edit_character(fn))

            delete_btn = Button(text="Löschen", size_hint_x=0.3)
            delete_btn.bind(on_release=lambda btn, fn=filename: self.delete_character_popup(fn))

            char_layout.add_widget(load_btn)
            char_layout.add_widget(edit_btn)
            char_layout.add_widget(delete_btn)
            popup_layout.add_widget(char_layout)

        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(popup_layout)
        content.add_widget(scroll_view)

        apply_styles_to_widget(content)
        self.popup = create_styled_popup(title="Charakter laden", content=content, size_hint=(0.8, 0.8))
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
        self.confirmation_popup = create_styled_popup(title="Löschen bestätigen", content=content, size_hint=(0.6, 0.4))
        self.confirmation_popup.open()

    def delete_character(self, filename):
        filepath = os.path.join("saves", filename)
        try:
            os.remove(filepath)
            self.confirmation_popup.dismiss()
            self.popup.dismiss()
            self.show_load_popup() # Refresh the list
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Löschen des Charakters: {e}")

    def load_character(self, filename):
        filepath = os.path.join("saves", filename)
        try:
            with open(filepath, 'rb') as f:
                character = pickle.load(f)
            character = ensure_character_attributes(character)
            self.manager.get_screen('sheet').load_character(character)
            self.app.change_screen('sheet', source_screen=self.name)
            self.popup.dismiss()
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Laden des Charakters: {e}")

    def edit_character(self, filename):
        filepath = os.path.join("saves", filename)
        try:
            with open(filepath, 'rb') as f:
                character = pickle.load(f)
            character = ensure_character_attributes(character)
            editor_screen = self.manager.get_screen('editor')
            editor_screen.load_character(character)
            self.app.change_screen('editor', source_screen=self.name)
            self.popup.dismiss()
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Laden des Charakters für die Bearbeitung: {e}")

    def show_popup(self, title, message):
        create_styled_popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()
