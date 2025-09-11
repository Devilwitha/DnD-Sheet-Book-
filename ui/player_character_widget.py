from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty
from kivy.uix.label import Label
from kivy.uix.button import Button
from functools import partial
from kivy.lang import Builder

Builder.load_file('ui/playercharacterwidget.kv')

class PlayerCharacterWidget(BoxLayout):
    """An interactive display of a character for the player's main screen."""
    character = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(PlayerCharacterWidget, self).__init__(**kwargs)
        self.bind(character=self.update_display)
        self.register_event_type('on_show_spells')
        self.register_event_type('on_roll_damage')
        self.register_event_type('on_use_item')
        self.register_event_type('on_show_info')
        self.register_event_type('on_show_rest')

    def on_show_spells(self, *args):
        pass

    def on_show_info(self, *args):
        pass

    def on_show_rest(self, *args):
        pass

    def on_roll_damage(self, *args):
        pass

    def on_use_item(self, *args):
        pass

    def update_display(self, *args):
        if not self.character:
            return

        for layout_id in ['stats_box', 'inventory_layout', 'equipment_layout']:
            if layout_id in self.ids:
                self.ids[layout_id].clear_widgets()

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
        self.ids.weapon_label.text = self.character.equipped_weapon

        # Inventory
        for index, item in enumerate(self.character.inventory):
            item_row = BoxLayout(size_hint_y=None, height=40)
            item_label = Label(text=f"{item['name']} (x{item['quantity']})")
            item_row.add_widget(item_label)
            if 'healing' in item:
                use_btn = Button(text="Benutzen", size_hint_x=0.4)
                use_btn.bind(on_press=partial(self.dispatch, 'on_use_item', item))
                item_row.add_widget(use_btn)
            self.ids.inventory_layout.add_widget(item_row)

        # Equipment
        for item_name, ac_bonus in self.character.equipment.items():
            self.ids.equipment_layout.add_widget(Label(text=f"{item_name} (AC: +{ac_bonus})"))
