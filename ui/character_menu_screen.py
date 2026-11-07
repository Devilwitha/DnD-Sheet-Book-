from kivy.metrics import dp
import os
from utils.storage import CharacterRepository, safe_save_path
from utils.non_ui_helpers import roll_dice
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.utils import platform
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, ensure_character_attributes, get_user_saves_dir

class CharacterMenuScreen(Screen):
    """Screen for loading, creating, or editing a character."""
    def __init__(self, **kwargs):
        super(CharacterMenuScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.saves_dir = get_user_saves_dir("characters")

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def go_to_screen(self, screen_name):
        self.app.change_screen(screen_name)

    def go_back(self):
        self.app.go_back_screen()

    def show_load_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))

        files = [f for f in os.listdir(self.saves_dir) if f.endswith('.char')]
        for filename in files:
            char_layout = BoxLayout(size_hint_y=None, height=dp(48))

            try:
                title = CharacterRepository().load(filename).name
            except ValueError:
                title = filename + ' (altes oder ungültiges Format)'
            load_btn = Button(text=title)
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
        filepath = safe_save_path(self.saves_dir, filename)
        try:
            os.remove(filepath)
            self.confirmation_popup.dismiss()
            self.popup.dismiss()
            self.show_load_popup() # Refresh the list
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Löschen des Charakters: {e}")

    def load_character(self, filename):
        filepath = safe_save_path(self.saves_dir, filename)
        try:
            character = CharacterRepository().load(filename)
            character = ensure_character_attributes(character)
            self.manager.get_screen('sheet').load_character(character)
            self.app.change_screen('sheet')
            self.popup.dismiss()
        except Exception as e:
            from utils.storage import LEGACY_MSG
            if str(e) == LEGACY_MSG:
                self.confirm_legacy_import(filename)
            else:
                self.show_popup("Fehler", f"Fehler beim Laden des Charakters: {e}")

    def confirm_legacy_import(self, filename):
        content = BoxLayout(orientation='vertical', spacing=10)
        content.add_widget(Label(text='Alten Charakter in das neue Format übernehmen?\nDie Originaldatei bleibt erhalten.'))
        convert = Button(text='Übernehmen')
        cancel = Button(text='Abbrechen')
        content.add_widget(convert)
        content.add_widget(cancel)
        popup = create_styled_popup(title='Altes Charakterformat', content=content)
        cancel.bind(on_release=popup.dismiss)

        def apply(instance):
            try:
                from utils.legacy_character import convert_legacy_character
                new_name = convert_legacy_character(self.saves_dir, filename)
            except Exception as error:
                self.show_popup('Übernahme fehlgeschlagen', str(error))
                return
            popup.dismiss()
            self.load_character(new_name)
        convert.bind(on_release=apply)
        popup.open()

    def edit_character(self, filename):
        filepath = safe_save_path(self.saves_dir, filename)
        try:
            character = CharacterRepository().load(filename)
            character = ensure_character_attributes(character)
            editor_screen = self.manager.get_screen('editor')
            editor_screen.load_character(character)
            self.app.change_screen('editor')
            self.popup.dismiss()
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Laden des Charakters für die Bearbeitung: {e}")

    def show_popup(self, title, message):
        create_styled_popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()
