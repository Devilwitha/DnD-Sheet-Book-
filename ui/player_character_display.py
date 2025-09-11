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

        # Basic Info
        self.ids.name_label.text = self.character.name
        self.ids.class_label.text = f"{self.character.race} {self.character.char_class} {self.character.level}"
        self.ids.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"

        # Abilities
        abilities = self.character.abilities
        self.ids.strength_label.text = f"{abilities['Stärke']} ({(abilities['Stärke'] - 10) // 2:+})"
        self.ids.dexterity_label.text = f"{abilities['Geschicklichkeit']} ({(abilities['Geschicklichkeit'] - 10) // 2:+})"
        self.ids.constitution_label.text = f"{abilities['Konstitution']} ({(abilities['Konstitution'] - 10) // 2:+})"
        self.ids.intelligence_label.text = f"{abilities['Intelligenz']} ({(abilities['Intelligenz'] - 10) // 2:+})"
        self.ids.wisdom_label.text = f"{abilities['Weisheit']} ({(abilities['Weisheit'] - 10) // 2:+})"
        self.ids.charisma_label.text = f"{abilities['Charisma']} ({(abilities['Charisma'] - 10) // 2:+})"

        # Combat Stats
        self.ids.ac_label.text = str(self.character.armor_class)
        self.ids.initiative_label.text = f"{self.character.initiative:+}"
        self.ids.speed_label.text = f"{self.character.speed}m"
