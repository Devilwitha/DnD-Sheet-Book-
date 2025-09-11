from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty
from kivy.uix.label import Label

class PlayerCharacterDisplay(BoxLayout):
    """A read-only display of a character's core stats for the player's main screen."""
    character = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(PlayerCharacterDisplay, self).__init__(**kwargs)
        self.bind(character=self.update_display)

    def update_display(self, *args):
        if not self.character:
            return

        # Clear previous widgets to prevent duplicates
        self.ids.stats_box.clear_widgets()

        # Basic Info
        self.ids.name_label.text = self.character.name
        self.ids.class_label.text = f"{self.character.race} {self.character.char_class} {self.character.level}"
        self.ids.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"

        # Abilities
        for ability, score in self.character.abilities.items():
            modifier = (score - 10) // 2
            sign = "+" if modifier >= 0 else ""
            self.ids.stats_box.add_widget(Label(text=f"{ability}:"))
            self.ids.stats_box.add_widget(Label(text=f"{score} ({sign}{modifier})"))

        # Combat Stats
        self.ids.stats_box.add_widget(Label(text="Rüstungsklasse:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.armor_class}"))
        self.ids.stats_box.add_widget(Label(text="Initiative:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.initiative:+}"))
        self.ids.stats_box.add_widget(Label(text="Bewegungsrate:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.speed}m"))
