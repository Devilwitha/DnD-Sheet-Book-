import random
from functools import partial

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.checkbox import CheckBox
from kivy.uix.screenmanager import Screen
from data_manager import (
    RACE_DATA, CLASS_DATA, ALIGNMENT_DATA, BACKGROUND_DATA,
    SKILL_LIST, FIGHTING_STYLE_DATA, SPELL_DATA
)
from core.character import Character
from utils.helpers import apply_background, apply_styles_to_widget

class CharacterCreator(Screen):
    """Creator mit +/- Buttons für Attribute."""
    def __init__(self, **kwargs):
        super(CharacterCreator, self).__init__(**kwargs)
        self.inputs = {}
        self.ability_scores_labels = {}

    def build_ui(self):
        # This check is to prevent rebuilding the UI every time the screen is entered
        if self.ids.creator_layout.children:
            return

        layout = self.ids.creator_layout

        back_button = Button(text="Zurück zum Hauptmenü",
                             on_press=lambda x: setattr(self.manager, 'current', 'main'),
                             size_hint_y=None,
                             height=44)
        layout.add_widget(back_button)
        layout.add_widget(Label(text="", size_hint_y=None, height=44))

        default_height = 44
        multiline_height = 120

        fields = [
            ("Name", "TextInput", default_height, []),
            ("Rasse", "Spinner", default_height, sorted(RACE_DATA.keys())),
            ("Klasse", "Spinner", default_height, sorted(CLASS_DATA.keys())),
            ("Gesinnung", "Spinner", default_height, sorted(ALIGNMENT_DATA.keys())),
            ("Hintergrund", "Spinner", default_height, sorted(BACKGROUND_DATA.keys())),
            ("Persönliche Merkmale", "TextInput", multiline_height, []),
            ("Ideale", "TextInput", multiline_height, []),
            ("Bindungen", "TextInput", multiline_height, []),
            ("Makel", "TextInput", multiline_height, [])
        ]

        for field_name, widget_type, height, values in fields:
            label = Label(text=f"{field_name}:", size_hint=(None, None), width=180, height=height, halign='left', valign='middle')
            label.bind(size=label.setter('text_size'))
            layout.add_widget(label)

            if widget_type == "TextInput":
                widget = TextInput(size_hint_y=None, height=height, multiline=(height > default_height))
            else:
                widget = Spinner(text=values[0] if values else "", values=values, size_hint_y=None, height=height)

            self.inputs[field_name] = widget
            layout.add_widget(widget)

        abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
        for ability in abilities:
            label = Label(text=ability, size_hint=(None, None), width=180, height=default_height, halign='left', valign='middle')
            layout.add_widget(label)

            stat_box = BoxLayout(size_hint_y=None, height=default_height)
            minus_btn = Button(text="-", on_press=partial(self.adjust_ability, ability, -1))
            score_label = Label(text="10")
            plus_btn = Button(text="+", on_press=partial(self.adjust_ability, ability, 1))

            stat_box.add_widget(minus_btn)
            stat_box.add_widget(score_label)
            stat_box.add_widget(plus_btn)

            self.ability_scores_labels[ability] = score_label
            layout.add_widget(stat_box)

        layout.add_widget(Label(size_hint_y=None, height=10))
        layout.add_widget(Label(size_hint_y=None, height=10))

        roll_button = Button(text="Attribute auswürfeln", on_press=self.roll_abilities, size_hint_y=None, height=default_height)
        create_button = Button(text="Charakter erstellen", on_press=self.create_character, size_hint_y=None, height=default_height)
        layout.add_widget(roll_button)
        layout.add_widget(create_button)

    def on_pre_enter(self, *args):
        self.build_ui()
        apply_background(self)
        apply_styles_to_widget(self)

    def adjust_ability(self, ability, amount, instance):
        current_score = int(self.ability_scores_labels[ability].text)
        new_score = max(1, min(20, current_score + amount))
        self.ability_scores_labels[ability].text = str(new_score)

    def roll_abilities(self, instance):
        for ability in self.ability_scores_labels:
            rolls = sorted([random.randint(1, 6) for _ in range(4)])
            score = sum(rolls[1:])
            self.ability_scores_labels[ability].text = str(score)

    def create_character(self, instance):
        name = self.inputs["Name"].text.strip()
        if not name:
            self.show_popup("Fehler", "Bitte gib einen Namen für den Charakter ein.")
            return

        character = Character(name, self.inputs["Rasse"].text, self.inputs["Klasse"].text)

        for ability, label in self.ability_scores_labels.items():
            character.base_abilities[ability] = int(label.text)

        character.alignment = self.inputs["Gesinnung"].text
        character.background = self.inputs["Hintergrund"].text
        character.personality_traits = self.inputs["Persönliche Merkmale"].text
        character.ideals = self.inputs["Ideale"].text
        character.bonds = self.inputs["Bindungen"].text
        character.flaws = self.inputs["Makel"].text

        class_data = CLASS_DATA.get(character.char_class, {})

        if "Kampfstil" in [f.get('name') for f in class_data.get("features", {}).get(1, [])]:
             self.show_fighting_style_popup(character)
        elif character.race == "Halbelf":
            self.show_half_elf_choices_popup(character)
        else:
            self.show_skill_selection_popup(character)

    def show_half_elf_choices_popup(self, character):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text="Wähle deine Halbelf-Boni", font_size='20sp', size_hint_y=None, height=44)
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        scroll_content.add_widget(Label(text="Erhöhe zwei Attributswerte um 1", size_hint_y=None, height=30, font_size='18sp'))
        ability_grid = GridLayout(cols=3, size_hint_y=None, spacing=5)
        ability_grid.bind(minimum_height=ability_grid.setter('height'))
        self.half_elf_ability_checkboxes = {}
        abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit"]
        for ability in abilities:
            box = BoxLayout(size_hint_y=None, height=30)
            cb = CheckBox()
            self.half_elf_ability_checkboxes[ability] = cb
            box.add_widget(Label(text=ability))
            box.add_widget(cb)
            ability_grid.add_widget(box)
        scroll_content.add_widget(ability_grid)

        scroll_content.add_widget(Label(text="Wähle zwei neue Fertigkeiten", size_hint_y=None, height=30, font_size='18sp'))
        skill_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
        skill_grid.bind(minimum_height=skill_grid.setter('height'))
        self.half_elf_skill_checkboxes = {}
        for skill in sorted(SKILL_LIST.keys()):
            if skill not in character.proficiencies:
                box = BoxLayout(size_hint_y=None, height=30)
                cb = CheckBox()
                self.half_elf_skill_checkboxes[skill] = cb
                box.add_widget(Label(text=skill))
                box.add_widget(cb)
                skill_grid.add_widget(box)
        scroll_content.add_widget(skill_grid)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        confirm_btn = Button(text="Bestätigen", size_hint_y=None, height=50)
        popup_content.add_widget(confirm_btn)

        popup = Popup(title="Halbelf-Anpassung", content=popup_content, size_hint=(0.9, 0.9), auto_dismiss=False)

        def confirm_choices(instance):
            selected_abilities = [name for name, cb in self.half_elf_ability_checkboxes.items() if cb.active]
            if len(selected_abilities) != 2:
                self.show_popup("Fehler", "Bitte wähle genau zwei Attributswerte.")
                return

            selected_skills = [name for name, cb in self.half_elf_skill_checkboxes.items() if cb.active]
            if len(selected_skills) != 2:
                self.show_popup("Fehler", "Bitte wähle genau zwei Fertigkeiten.")
                return

            for ability in selected_abilities:
                character.base_abilities[ability] += 1

            character.proficiencies.extend(selected_skills)
            character.proficiencies = sorted(list(set(character.proficiencies)))

            popup.dismiss()
            self.show_skill_selection_popup(character)

        confirm_btn.bind(on_press=confirm_choices)
        apply_styles_to_widget(popup_content)
        popup.open()

    def show_fighting_style_popup(self, character):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text="Wähle deinen Kampfstil", font_size='20sp', size_hint_y=None, height=44)
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        fighter_styles = ["Defense", "Dueling", "Great Weapon Fighting", "Protection"]

        style_checkboxes = {}
        for style_name in fighter_styles:
            if style_name in FIGHTING_STYLE_DATA:
                box = BoxLayout(size_hint_y=None, height=40)
                cb = CheckBox(group='fighting_style', size_hint_x=0.1)
                style_checkboxes[style_name] = cb

                desc = FIGHTING_STYLE_DATA[style_name]
                info_btn = Button(text=f"{style_name}: {desc}", text_size=(self.width - 150, None), halign='left')

                box.add_widget(cb)
                box.add_widget(info_btn)
                scroll_content.add_widget(box)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        confirm_btn = Button(text="Bestätigen", size_hint_y=None, height=50)
        popup_content.add_widget(confirm_btn)

        popup = Popup(title="Kampfstil auswählen", content=popup_content, size_hint=(0.9, 0.9), auto_dismiss=False)

        def confirm_choice(instance):
            selected_style = None
            for name, cb in style_checkboxes.items():
                if cb.active:
                    selected_style = name
                    break

            if not selected_style:
                self.show_popup("Fehler", "Bitte wähle einen Kampfstil.")
                return

            character.fighting_style = selected_style
            character.features.append({"name": f"Kampfstil: {selected_style}", "desc": FIGHTING_STYLE_DATA[selected_style]})

            popup.dismiss()
            self.show_skill_selection_popup(character)

        confirm_btn.bind(on_press=confirm_choice)
        apply_styles_to_widget(popup_content)
        popup.open()

    def show_initial_spell_selection_popup(self, character):
        class_data = CLASS_DATA.get(character.char_class, {})
        progression = class_data.get("progression", {})
        level_1_prog = progression.get(1, {})
        if not level_1_prog:
            self.finish_character_creation(character)
            return

        cantrips_to_learn = level_1_prog.get("cantrips_known", 0)
        spells_to_learn = level_1_prog.get("spells_known", 0)

        # Handle prepared casters like Cleric and Druid
        if character.char_class in ["Kleriker", "Druide"]:
            ability_modifier = (character.base_abilities["Weisheit"] - 10) // 2
            spells_to_learn = max(1, ability_modifier + character.level)
            popup_title_text = f"Bereite deine Startzauber für {character.char_class} vor"
            spell_label_text = f"Bereite {spells_to_learn} Zauber des 1. Grades vor"
        else:
            popup_title_text = f"Wähle deine Startzauber für {character.char_class}"
            spell_label_text = f"Wähle {spells_to_learn} Zauber des 1. Grades"

        all_available_spells = class_data.get("spell_list", {})

        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text=popup_title_text, font_size='20sp', size_hint_y=None, height=44)
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        cantrip_checkboxes = {}
        if cantrips_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {cantrips_to_learn} Zaubertrick/s", size_hint_y=None, height=30, font_size='18sp'))
            cantrip_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
            cantrip_grid.bind(minimum_height=cantrip_grid.setter('height'))
            for spell_name in sorted(all_available_spells.get(0, [])):
                box = BoxLayout(size_hint_y=None, height=30)
                cb = CheckBox(size_hint_x=0.1)
                cantrip_checkboxes[spell_name] = cb
                info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                box.add_widget(cb)
                box.add_widget(info_btn)
                cantrip_grid.add_widget(box)
            scroll_content.add_widget(cantrip_grid)

        spell_checkboxes = {}
        if spells_to_learn > 0:
            scroll_content.add_widget(Label(text=spell_label_text, size_hint_y=None, height=30, font_size='18sp'))
            spell_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
            spell_grid.bind(minimum_height=spell_grid.setter('height'))
            for spell_name in sorted(all_available_spells.get(1, [])):
                box = BoxLayout(size_hint_y=None, height=30)
                cb = CheckBox(size_hint_x=0.1)
                spell_checkboxes[spell_name] = cb
                info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                box.add_widget(cb)
                box.add_widget(info_btn)
                spell_grid.add_widget(box)
            scroll_content.add_widget(spell_grid)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        confirm_btn = Button(text="Bestätigen")
        btn_box.add_widget(confirm_btn)
        popup_content.add_widget(btn_box)

        popup = Popup(title="Startzauber auswählen", content=popup_content, size_hint=(0.9, 0.9), auto_dismiss=False)

        def confirm_choices(instance):
            selected_cantrips = [name for name, cb in cantrip_checkboxes.items() if cb.active]
            if cantrips_to_learn > 0 and len(selected_cantrips) != cantrips_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {cantrips_to_learn} Zaubertrick/s.")
                return

            selected_spells = [name for name, cb in spell_checkboxes.items() if cb.active]
            if spells_to_learn > 0 and len(selected_spells) != spells_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {spells_to_learn} Zauber des 1. Grades.")
                return

            character.spells[0] = selected_cantrips
            character.spells[1] = selected_spells

            popup.dismiss()
            self.finish_character_creation(character)

        confirm_btn.bind(on_press=confirm_choices)

        apply_styles_to_widget(popup_content)
        popup.open()

    def show_skill_selection_popup(self, character):
        class_data = CLASS_DATA.get(character.char_class, {})
        skill_choices_data = class_data.get("skill_choices")

        if not skill_choices_data:
            # If no skills to choose, proceed to the next step
            if "progression" in class_data:
                self.show_initial_spell_selection_popup(character)
            else:
                self.finish_character_creation(character)
            return

        num_to_choose = skill_choices_data["choose"]
        skill_options = skill_choices_data["from"]

        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text=f"Wähle {num_to_choose} Fertigkeiten", font_size='20sp', size_hint_y=None, height=44)
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=2, size_hint_y=None, spacing=10)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        self.skill_checkboxes = {}
        for skill_name in sorted(skill_options):
            if skill_name not in character.proficiencies:
                box = BoxLayout(size_hint_y=None, height=30)
                cb = CheckBox(size_hint_x=0.1)
                self.skill_checkboxes[skill_name] = cb
                box.add_widget(cb)
                box.add_widget(Label(text=skill_name))
                scroll_content.add_widget(box)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        confirm_btn = Button(text="Bestätigen", size_hint_y=None, height=50)
        popup_content.add_widget(confirm_btn)

        popup = Popup(title="Fertigkeiten auswählen", content=popup_content, size_hint=(0.9, 0.9), auto_dismiss=False)

        def confirm_skills(instance):
            selected_skills = [name for name, cb in self.skill_checkboxes.items() if cb.active]
            if len(selected_skills) != num_to_choose:
                self.show_popup("Fehler", f"Bitte wähle genau {num_to_choose} Fertigkeiten.")
                return

            character.proficiencies.extend(selected_skills)
            character.proficiencies = sorted(list(set(character.proficiencies)))

            popup.dismiss()

            # Proceed to the next step in character creation
            if "progression" in class_data:
                self.show_initial_spell_selection_popup(character)
            else:
                self.finish_character_creation(character)

        confirm_btn.bind(on_press=confirm_skills)
        apply_styles_to_widget(popup_content)
        popup.open()

    def finish_character_creation(self, character):
        character.initialize_character()
        self.manager.get_screen('sheet').load_character(character)
        self.manager.current = 'sheet'

    def show_spell_info_popup(self, spell_name, instance):
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )
        self.show_popup(spell_name, text)

    def show_popup(self, title, message):
        content = ScrollView()
        label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.8))
        apply_styles_to_widget(popup.content)
        popup.open()
