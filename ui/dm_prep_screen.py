import json
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from core.enemy import Enemy
from utils.helpers import apply_background, apply_styles_to_widget

class DMPrepScreen(Screen):
    """Screen for the DM to prepare the game."""
    def __init__(self, **kwargs):
        super(DMPrepScreen, self).__init__(**kwargs)
        self.enemy_list = []

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def update_enemy_list_ui(self):
        enemy_list_widget = self.ids.enemy_list_view
        enemy_list_widget.clear_widgets()
        for enemy in self.enemy_list:
            enemy_label = Label(text=f"{enemy.name} (HP: {enemy.hp}, AC: {enemy.ac})")
            enemy_list_widget.add_widget(enemy_label)

    def add_enemy_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        name_input = TextInput(hint_text="Name")
        hp_input = TextInput(hint_text="HP", input_filter='int')
        ac_input = TextInput(hint_text="AC", input_filter='int')
        initiative_input = TextInput(hint_text="Initiative Bonus", input_filter='int')
        attacks_input = TextInput(hint_text="Angriffe (z.B. Biss:1d6+2)")
        notes_input = TextInput(hint_text="Notizen")

        content.add_widget(name_input)
        content.add_widget(hp_input)
        content.add_widget(ac_input)
        content.add_widget(initiative_input)
        content.add_widget(attacks_input)
        content.add_widget(notes_input)

        save_button = Button(text="Speichern")
        content.add_widget(save_button)

        popup = Popup(title="Gegner hinzufügen", content=content, size_hint=(0.8, 0.8))

        def save_action(instance):
            # Basic validation
            if not name_input.text or not hp_input.text or not ac_input.text:
                return

            # For simplicity, attacks are just a string for now.
            # A more robust implementation would parse this.
            new_enemy = Enemy(
                name=name_input.text,
                hp=int(hp_input.text),
                ac=int(ac_input.text),
                initiative=int(initiative_input.text or 0),
                attacks=[attacks_input.text],
                notes=notes_input.text
            )
            self.enemy_list.append(new_enemy)
            self.update_enemy_list_ui()
            popup.dismiss()

        save_button.bind(on_press=save_action)
        popup.open()

    def save_enemy_list(self):
        # For now, hardcoded filename. Later, a file chooser.
        filename = "my_enemies.enemies"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                list_to_save = [enemy.to_dict() for enemy in self.enemy_list]
                json.dump(list_to_save, f, indent=4)
            print(f"[*] Enemy list saved to {filename}")
        except Exception as e:
            print(f"[!] Error saving enemy list: {e}")

    def load_enemy_list(self):
        filename = "my_enemies.enemies"
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                list_from_file = json.load(f)
                self.enemy_list = [Enemy.from_dict(data) for data in list_from_file]
            self.update_enemy_list_ui()
            print(f"[*] Enemy list loaded from {filename}")
        except Exception as e:
            print(f"[!] Error loading enemy list: {e}")

    def open_map_editor(self):
        self.manager.current = 'map_editor'
