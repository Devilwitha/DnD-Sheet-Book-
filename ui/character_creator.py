from kivy.metrics import dp
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
from utils.data_manager import (
    RACE_DATA, CLASS_DATA, ALIGNMENT_DATA, BACKGROUND_DATA,
    SKILL_LIST, FIGHTING_STYLE_DATA, SPELL_DATA
)
from core.character import Character
from utils.storage import CharacterRepository
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup

class CharacterCreator(Screen):
    """Creator mit +/- Buttons für Attribute."""
    def __init__(self, **kwargs):
        super(CharacterCreator, self).__init__(**kwargs)
        self.inputs = {}
        self.ability_scores_labels = {}

    def build_ui(self):
        if getattr(self, '_creator_panels', None):
            return
        self._creator_step = 0
        self._creator_panels = []
        for _ in range(3):
            panel = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
            panel.bind(minimum_height=panel.setter('height'))
            self._creator_panels.append(panel)

        def help_text(panel, message):
            label = Label(text=message, size_hint_y=None, height=dp(74), halign='left', valign='middle')
            label.bind(size=lambda w, size: setattr(w, 'text_size', (size[0]-dp(8), size[1])))
            panel.add_widget(label)

        help_text(self._creator_panels[0], 'Beginne mit Name, Volk und Klasse. Die Klasse bestimmt deine Fähigkeiten. Der Hintergrund beschreibt dein Leben vor dem Abenteuer.')
        help_text(self._creator_panels[1], 'Attribute beeinflussen deine Würfelboni. Du kannst würfeln oder die mit dem DM vereinbarten Werte eintragen. Volksboni ergänzt die App anschließend.')
        help_text(self._creator_panels[2], 'Diese Angaben sind optional und helfen beim Rollenspiel. Danach führt dich die App durch die nötigen Fähigkeiten und Zauber deiner Klasse.')
        fields = [
            ('Name', [], 0), ('Rasse', sorted(RACE_DATA), 0),
            ('Klasse', sorted(CLASS_DATA), 0), ('Hintergrund', sorted(BACKGROUND_DATA), 0),
            ('Gesinnung', sorted(ALIGNMENT_DATA), 2), ('Persönliche Merkmale', [], 2),
            ('Ideale', [], 2), ('Bindungen', [], 2), ('Makel', [], 2)]
        for name, values, step in fields:
            panel = self._creator_panels[step]
            panel.add_widget(Label(text=name + ':', size_hint_y=None, height=dp(32), halign='left'))
            if values:
                widget = Spinner(text=values[0], values=values, size_hint_y=None, height=dp(50))
            else:
                widget = TextInput(multiline=step == 2, hint_text='Optional' if step == 2 else 'Dein Charaktername',
                                   size_hint_y=None, height=dp(100 if step == 2 else 50))
            self.inputs[name] = widget
            panel.add_widget(widget)
        panel = self._creator_panels[1]
        explanations = {'Stärke': 'Körperkraft', 'Geschicklichkeit': 'Beweglichkeit', 'Konstitution': 'Widerstandskraft',
                        'Intelligenz': 'Wissen', 'Weisheit': 'Wahrnehmung', 'Charisma': 'Auftreten'}
        for ability, meaning in explanations.items():
            panel.add_widget(Label(text=f'{ability} – {meaning}', size_hint_y=None, height=dp(36)))
            row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
            value = Label(text='10')
            self.ability_scores_labels[ability] = value
            row.add_widget(Button(text='−', on_release=partial(self.adjust_ability, ability, -1)))
            row.add_widget(value)
            row.add_widget(Button(text='+', on_release=partial(self.adjust_ability, ability, 1)))
            panel.add_widget(row)
        panel.add_widget(Button(text='Attribute auswürfeln', size_hint_y=None, height=dp(52), on_release=self.roll_abilities))
        self.show_creator_step(0)

    def show_creator_step(self, step):
        self._creator_step = max(0, min(2, step))
        self.ids.creator_layout.clear_widgets()
        self.ids.creator_layout.add_widget(self._creator_panels[self._creator_step])
        self.ids.creator_step_label.text = ['1 / 3 · Grundidee', '2 / 3 · Attribute', '3 / 3 · Persönlichkeit'][self._creator_step]
        self.ids.creator_previous.disabled = self._creator_step == 0
        self.ids.creator_next.text = 'Weiter' if self._creator_step < 2 else 'Charakter erstellen'
        self.ids.creator_scroll.scroll_y = 1

    def creator_next(self):
        if self._creator_step == 0 and not self.inputs['Name'].text.strip():
            self.show_popup('Charaktername', 'Bitte gib deinem Charakter einen Namen.')
            return
        if self._creator_step == 2:
            self.create_character(None)
        else:
            self.show_creator_step(self._creator_step + 1)

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
        name = self.inputs['Name'].text.strip()
        if not name:
            self.show_popup('Fehler', 'Bitte gib einen Namen für den Charakter ein.')
            return

        character = Character(name, self.inputs['Rasse'].text, self.inputs['Klasse'].text)

        for ability, label in self.ability_scores_labels.items():
            character.base_abilities[ability] = int(label.text)

        character.alignment = self.inputs['Gesinnung'].text
        character.background = self.inputs['Hintergrund'].text
        character.personality_traits = self.inputs['Persönliche Merkmale'].text
        character.ideals = self.inputs['Ideale'].text
        character.bonds = self.inputs['Bindungen'].text
        character.flaws = self.inputs['Makel'].text

        class_data = CLASS_DATA.get(character.char_class, {})

        # Chain: fighting style -> half-elf -> skills -> spells -> finish
        if 'Kampfstil' in [f.get('name') for f in class_data.get('features', {}).get(1, [])]:
            self.show_fighting_style_popup(character)
        else:
            self.show_skill_selection_popup(character)

    def show_half_elf_choices_popup(self, character):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_content.add_widget(Label(text='Wähle deine Halbelf-Boni', font_size='20sp', size_hint_y=None, height=dp(48)))

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        scroll_content.add_widget(Label(text='Erhöhe zwei Attributswerte um 1', size_hint_y=None, height=dp(48), font_size='18sp'))
        ability_grid = GridLayout(cols=3, size_hint_y=None, spacing=5)
        ability_grid.bind(minimum_height=ability_grid.setter('height'))
        ability_cbs = {}
        for ability in ['Stärke', 'Geschicklichkeit', 'Konstitution', 'Intelligenz', 'Weisheit']:
            box = BoxLayout(size_hint_y=None, height=dp(48))
            cb = CheckBox()
            ability_cbs[ability] = cb
            box.add_widget(Label(text=ability))
            box.add_widget(cb)
            ability_grid.add_widget(box)
        scroll_content.add_widget(ability_grid)

        scroll_content.add_widget(Label(text='Wähle zwei neue Fertigkeiten', size_hint_y=None, height=dp(48), font_size='18sp'))
        skill_grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
        skill_grid.bind(minimum_height=skill_grid.setter('height'))
        known = self._known_proficiencies(character)
        skill_cbs = {}
        for skill in sorted(SKILL_LIST.keys()):
            if skill not in known:
                box = BoxLayout(size_hint_y=None, height=dp(48))
                cb = CheckBox()
                skill_cbs[skill] = cb
                box.add_widget(Label(text=skill))
                box.add_widget(cb)
                skill_grid.add_widget(box)
        scroll_content.add_widget(skill_grid)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        confirm_btn = Button(text='Bestätigen', size_hint_y=None, height=dp(50))
        popup_content.add_widget(confirm_btn)

        popup = create_styled_popup(title='Halbelf-Anpassung', content=popup_content, size_hint=(0.9, 0.9))
        popup.auto_dismiss = False

        def confirm_choices(instance):
            selected_abilities = [n for n, cb in ability_cbs.items() if cb.active]
            if len(selected_abilities) != 2:
                self.show_popup('Fehler', 'Bitte wähle genau zwei Attributswerte.')
                return
            selected_skills = [n for n, cb in skill_cbs.items() if cb.active]
            if len(selected_skills) != 2:
                self.show_popup('Fehler', 'Bitte wähle genau zwei Fertigkeiten.')
                return
            # Stored only as bonuses; applied by Character (no double counting in base_abilities)
            character.half_elf_bonuses = {'abilities': selected_abilities, 'skills': selected_skills}
            popup.dismiss()
            self.show_skill_selection_popup(character)

        confirm_btn.bind(on_press=confirm_choices)
        apply_styles_to_widget(popup_content)
        popup.open()

    def show_fighting_style_popup(self, character):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        title = Label(text="Wähle deinen Kampfstil", font_size='20sp', size_hint_y=None, height=dp(48))
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        fighter_styles = ["Defense", "Dueling", "Great Weapon Fighting", "Protection"]

        style_checkboxes = {}
        for style_name in fighter_styles:
            if style_name in FIGHTING_STYLE_DATA:
                box = BoxLayout(size_hint_y=None, height=dp(48))
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

        confirm_btn = Button(text="Bestätigen", size_hint_y=None, height=dp(50))
        popup_content.add_widget(confirm_btn)

        popup = create_styled_popup(title="Kampfstil auswählen", content=popup_content, size_hint=(0.9, 0.9))
        popup.auto_dismiss = False

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
            character.update_features()  # style feature is derived from fighting_style

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
        title = Label(text=popup_title_text, font_size='20sp', size_hint_y=None, height=dp(48))
        popup_content.add_widget(title)

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        cantrip_checkboxes = {}
        if cantrips_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {cantrips_to_learn} Zaubertrick/s", size_hint_y=None, height=dp(48), font_size='18sp'))
            cantrip_grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
            cantrip_grid.bind(minimum_height=cantrip_grid.setter('height'))
            for spell_name in sorted(all_available_spells.get(0, [])):
                box = BoxLayout(size_hint_y=None, height=dp(48))
                cb = CheckBox(size_hint_x=None, width=dp(48))
                cantrip_checkboxes[spell_name] = cb
                info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                box.add_widget(cb)
                box.add_widget(info_btn)
                cantrip_grid.add_widget(box)
            scroll_content.add_widget(cantrip_grid)

        spell_checkboxes = {}
        if spells_to_learn > 0:
            scroll_content.add_widget(Label(text=spell_label_text, size_hint_y=None, height=dp(48), font_size='18sp'))
            spell_grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
            spell_grid.bind(minimum_height=spell_grid.setter('height'))
            for spell_name in sorted(all_available_spells.get(1, [])):
                box = BoxLayout(size_hint_y=None, height=dp(48))
                cb = CheckBox(size_hint_x=None, width=dp(48))
                spell_checkboxes[spell_name] = cb
                info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                box.add_widget(cb)
                box.add_widget(info_btn)
                spell_grid.add_widget(box)
            scroll_content.add_widget(spell_grid)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        btn_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=10)
        confirm_btn = Button(text="Bestätigen")
        btn_box.add_widget(confirm_btn)
        popup_content.add_widget(btn_box)

        popup = create_styled_popup(title="Startzauber auswählen", content=popup_content, size_hint=(0.9, 0.9))
        popup.auto_dismiss = False

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
        """Chain step after the fighting style: half-elf choices (if needed), then skills."""
        if character.race == 'Halbelf' and not character.half_elf_bonuses:
            self.show_half_elf_choices_popup(character)
            return
        self.show_skill_choice_popup(character)

    def finish_character_creation(self, character):
        character.initialize_character()
        try:
            CharacterRepository().save(character)  # autosave only for the final character
        except Exception as e:
            self.show_popup('Fehler', f'Charakter konnte nicht gespeichert werden: {e}')
            return
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
        popup = create_styled_popup(title=title, content=content, size_hint=(0.8, 0.8))
        popup.open()
    def _known_proficiencies(self, character):
        known = set(RACE_DATA.get(character.race, {}).get('proficiencies', []))
        known.update(CLASS_DATA.get(character.char_class, {}).get('proficiencies', []))
        known.update((character.half_elf_bonuses or {}).get('skills', []))
        known.update(character.selected_skills or [])
        return known
    def show_skill_choice_popup(self, character):
        class_data = CLASS_DATA.get(character.char_class, {})
        skill_choices_data = class_data.get('skill_choices')

        def next_step():
            if 'progression' in class_data:
                self.show_initial_spell_selection_popup(character)
            else:
                self.finish_character_creation(character)

        if not skill_choices_data:
            next_step()
            return

        num_to_choose = skill_choices_data['choose']
        skill_options = skill_choices_data['from']

        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_content.add_widget(Label(text=f'Wähle {num_to_choose} Fertigkeiten', font_size='20sp', size_hint_y=None, height=dp(48)))

        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=10)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        known = self._known_proficiencies(character)
        skill_cbs = {}
        for skill_name in sorted(skill_options):
            if skill_name not in known:
                box = BoxLayout(size_hint_y=None, height=dp(48))
                cb = CheckBox(size_hint_x=None, width=dp(48))
                skill_cbs[skill_name] = cb
                box.add_widget(cb)
                box.add_widget(Label(text=skill_name))
                scroll_content.add_widget(box)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        confirm_btn = Button(text='Bestätigen', size_hint_y=None, height=dp(50))
        popup_content.add_widget(confirm_btn)

        popup = create_styled_popup(title='Fertigkeiten auswählen', content=popup_content, size_hint=(0.9, 0.9))
        popup.auto_dismiss = False

        def confirm_skills(instance):
            selected = [n for n, cb in skill_cbs.items() if cb.active]
            if len(selected) != num_to_choose:
                self.show_popup('Fehler', f'Bitte wähle genau {num_to_choose} Fertigkeiten.')
                return
            character.selected_skills = sorted(set(character.selected_skills) | set(selected))
            popup.dismiss()
            next_step()

        confirm_btn.bind(on_press=confirm_skills)
        apply_styles_to_widget(popup_content)
        popup.open()
