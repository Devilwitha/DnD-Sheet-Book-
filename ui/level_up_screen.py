import random
from functools import partial
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from utils.data_manager import CLASS_DATA, SPELL_DATA
from utils.helpers import apply_styles_to_widget, create_styled_popup

class LevelUpScreen(Screen):
    """Bildschirm für den Stufenaufstieg."""
    def __init__(self, **kwargs):
        super(LevelUpScreen, self).__init__(**kwargs)
        self.character = None
        self.spell_choices = {}
        self.ability_choices = {}

    def on_pre_enter(self, *args):
        apply_styles_to_widget(self)

    def set_character(self, character):
        self.character = character
        self.update_view()

    def update_view(self):
        level_up_layout = self.ids.level_up_layout
        level_up_layout.clear_widgets()
        if not self.character:
            return

        new_level = self.character.level + 1
        self.ids.title_label.text = f"Stufenaufstieg zu Level {new_level}"

        hit_die = CLASS_DATA.get(self.character.char_class, {}).get("hit_die", 8)
        con_modifier = (self.character.abilities["Konstitution"] - 10) // 2
        hp_increase = random.randint(1, hit_die) + con_modifier
        level_up_layout.add_widget(Label(text=f"HP-Erhöhung: +{max(1, hp_increase)}", size_hint_y=None, height=40))

        features = CLASS_DATA.get(self.character.char_class, {}).get("features", {}).get(new_level, [])
        if features:
            level_up_layout.add_widget(Label(text="Neue Fähigkeiten:", font_size='20sp', size_hint_y=None, height=40))
            for feature in features:
                feature_label = Label(text=f"[b]{feature['name']}[/b]\n{feature['desc']}", markup=True, size_hint_y=None)
                feature_label.bind(
                    width=lambda *x: feature_label.setter('text_size')(feature_label, (feature_label.width, None)),
                    texture_size=lambda *x: feature_label.setter('height')(feature_label, feature_label.texture_size[1])
                )
                level_up_layout.add_widget(feature_label)

        self.ability_scores_to_increase = {}
        self.total_points_allocated = 0
        self.ability_increase_labels = {}
        self.ability_buttons = {}

        if any("Attributswerterhöhung" in f['name'] for f in features):
            level_up_layout.add_widget(Label(text="Attributsverbesserung (verteile 2 Punkte):", font_size='20sp', size_hint_y=None, height=40))

            self.points_label = Label(text="Verbleibende Punkte: 2", size_hint_y=None, height=40)
            level_up_layout.add_widget(self.points_label)

            abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
            for ability in abilities:
                box = BoxLayout(size_hint_y=None, height=40, spacing=10)

                info_btn = Button(text="?", size_hint_x=0.1, on_press=partial(self.show_ability_info, ability))
                ability_label = Label(text=f"{ability}: {self.character.abilities[ability]}", size_hint_x=0.4)

                increase_label = Label(text="", size_hint_x=0.2)
                self.ability_increase_labels[ability] = increase_label

                plus_btn = Button(text="+", size_hint_x=0.15, on_press=partial(self.increase_ability, ability))
                minus_btn = Button(text="-", size_hint_x=0.15, on_press=partial(self.decrease_ability, ability))
                self.ability_buttons[ability] = (plus_btn, minus_btn)

                box.add_widget(info_btn)
                box.add_widget(ability_label)
                box.add_widget(increase_label)
                box.add_widget(plus_btn)
                box.add_widget(minus_btn)
                level_up_layout.add_widget(box)

        class_data = CLASS_DATA.get(self.character.char_class, {})
        if "progression" in class_data:
            progression = class_data.get("progression", {})
            if self.character.level + 1 in progression:
                manage_spells_btn = Button(text="Zauber auswählen", on_press=self.show_spell_selection_popup, size_hint_y=None, height=40)
                level_up_layout.add_widget(manage_spells_btn)

    def show_spell_selection_popup(self, instance):
        class_data = CLASS_DATA.get(self.character.char_class, {})
        if not class_data or "progression" not in class_data:
            return

        progression = class_data["progression"]
        current_level = self.character.level
        new_level = current_level + 1

        old_prog = progression.get(current_level, {})
        new_prog = progression.get(new_level, {})
        if not old_prog or not new_prog:
            return

        cantrips_to_learn = new_prog.get("cantrips_known", 0) - old_prog.get("cantrips_known", 0)
        spells_to_learn = new_prog.get("spells_known", 0) - old_prog.get("spells_known", 0)
        can_replace_spell = self.character.char_class == "Barde"

        # Handle prepared casters
        if self.character.char_class in ["Kleriker", "Druide"]:
            # For simplicity, we'll let them "learn" one new spell, as their preparable count increases by 1 each level.
            spells_to_learn = 1
        elif self.character.char_class == "Paladin":
            # Paladins gain spells at level 2, and their preparable count changes based on half their level.
            old_preparable = (self.character.abilities["Charisma"] - 10) // 2 + current_level // 2
            new_preparable = (self.character.abilities["Charisma"] - 10) // 2 + new_level // 2
            spells_to_learn = max(0, new_preparable - old_preparable)
            if new_level == 2:
                spells_to_learn = (self.character.abilities["Charisma"] - 10) // 2 + 1 # Initial spells at level 2

        max_spell_level = 0
        for level, slots in new_prog["spell_slots"].items():
            if slots > 0:
                max_spell_level = max(max_spell_level, int(level))

        known_cantrips = self.character.spells.get(0, [])
        known_spells_flat = [spell for lvl, spells in self.character.spells.items() if lvl > 0 for spell in spells]

        all_available_spells = class_data.get("spell_list", {})

        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll_content = GridLayout(cols=1, size_hint_y=None, spacing=15)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))

        new_cantrip_checkboxes = {}
        if cantrips_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {cantrips_to_learn} neue/n Zaubertrick/s", size_hint_y=None, height=30, font_size='18sp'))
            cantrip_grid = GridLayout(cols=2, size_hint_y=None, spacing=5)
            cantrip_grid.bind(minimum_height=cantrip_grid.setter('height'))
            available_cantrips = all_available_spells.get(0, [])
            for spell_name in sorted(available_cantrips):
                if spell_name not in known_cantrips:
                    box = BoxLayout(size_hint_y=None, height=30)
                    cb = CheckBox(size_hint_x=0.1)
                    new_cantrip_checkboxes[spell_name] = cb
                    info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                    box.add_widget(cb)
                    box.add_widget(info_btn)
                    cantrip_grid.add_widget(box)
            scroll_content.add_widget(cantrip_grid)

        new_spell_checkboxes = {}
        if spells_to_learn > 0:
            scroll_content.add_widget(Label(text=f"Wähle {spells_to_learn} neue/n Zauber (bis Grad {max_spell_level})", size_hint_y=None, height=30, font_size='18sp'))
            spell_grid = GridLayout(cols=1, size_hint_y=None, spacing=5)
            spell_grid.bind(minimum_height=spell_grid.setter('height'))
            for spell_level in range(1, max_spell_level + 1):
                available_spells_at_level = all_available_spells.get(spell_level, [])
                if available_spells_at_level:
                    spell_grid.add_widget(Label(text=f"Grad {spell_level}", font_size='16sp', size_hint_y=None, height=25))
                    for spell_name in sorted(available_spells_at_level):
                        if spell_name not in known_spells_flat:
                            box = BoxLayout(size_hint_y=None, height=30)
                            cb = CheckBox(size_hint_x=0.1)
                            new_spell_checkboxes[spell_name] = cb
                            info_btn = Button(text=spell_name, on_press=partial(self.show_spell_info_popup, spell_name))
                            box.add_widget(cb)
                            box.add_widget(info_btn)
                            spell_grid.add_widget(box)
            scroll_content.add_widget(spell_grid)

        spell_to_replace_spinner = None
        replacement_spell_spinner = None
        if can_replace_spell and known_spells_flat:
            scroll_content.add_widget(Label(text="Ersetze einen bekannten Zauber", size_hint_y=None, height=30, font_size='18sp'))
            replace_box = BoxLayout(size_hint_y=None, height=40, spacing=10)

            spell_to_replace_spinner = Spinner(text="Wähle Zauber...", values=["Keiner"] + sorted(known_spells_flat))

            all_possible_replacements = ["Keiner"]
            for spell_level in range(1, max_spell_level + 1):
                all_possible_replacements.extend(sorted(all_available_spells.get(spell_level, [])))

            replacement_spell_spinner = Spinner(text="Wähle Ersatz...", values=list(dict.fromkeys(all_possible_replacements)))

            info_btn1 = Button(text="?", size_hint_x=0.2, on_press=lambda x: self.show_spell_info_popup(spell_to_replace_spinner.text, x))
            info_btn2 = Button(text="?", size_hint_x=0.2, on_press=lambda x: self.show_spell_info_popup(replacement_spell_spinner.text, x))

            replace_box.add_widget(spell_to_replace_spinner)
            replace_box.add_widget(info_btn1)
            replace_box.add_widget(Label(text="durch", size_hint_x=0.3))
            replace_box.add_widget(replacement_spell_spinner)
            replace_box.add_widget(info_btn2)
            scroll_content.add_widget(replace_box)

        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        popup_content.add_widget(scroll_view)

        btn_box = BoxLayout(size_hint_y=None, height=50, spacing=10)
        confirm_btn = Button(text="Bestätigen")
        cancel_btn = Button(text="Abbrechen")
        btn_box.add_widget(confirm_btn)
        btn_box.add_widget(cancel_btn)
        popup_content.add_widget(btn_box)

        popup = create_styled_popup(title="Zauber für Stufenaufstieg auswählen", content=popup_content, size_hint=(0.9, 0.9))

        def confirm_choices(instance):
            selected_cantrips = [name for name, cb in new_cantrip_checkboxes.items() if cb.active]
            if cantrips_to_learn > 0 and len(selected_cantrips) != cantrips_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {cantrips_to_learn} Zaubertrick/s.")
                return

            selected_spells = [name for name, cb in new_spell_checkboxes.items() if cb.active]
            if spells_to_learn > 0 and len(selected_spells) != spells_to_learn:
                self.show_popup("Fehler", f"Bitte wähle genau {spells_to_learn} neue/n Zauber.")
                return

            spell_to_replace = spell_to_replace_spinner.text if spell_to_replace_spinner else "Keiner"
            replacement_spell = replacement_spell_spinner.text if replacement_spell_spinner else "Keiner"

            if spell_to_replace != "Keiner" and replacement_spell == "Keiner":
                self.show_popup("Fehler", "Bitte wähle einen Ersatzzauber aus.")
                return
            if spell_to_replace == "Keiner" and replacement_spell != "Keiner":
                self.show_popup("Fehler", "Bitte wähle einen Zauber zum Ersetzen aus.")
                return
            if replacement_spell in known_spells_flat and replacement_spell != spell_to_replace:
                 self.show_popup("Fehler", f"Du kennst '{replacement_spell}' bereits.")
                 return

            self.spell_choices['new_cantrips'] = selected_cantrips
            self.spell_choices['new_spells'] = selected_spells
            if spell_to_replace != "Keiner" and replacement_spell != "Keiner":
                self.spell_choices['replaced_spell'] = spell_to_replace
                self.spell_choices['replacement_spell'] = replacement_spell

            popup.dismiss()

        confirm_btn.bind(on_press=confirm_choices)
        cancel_btn.bind(on_press=popup.dismiss)

        apply_styles_to_widget(popup_content)
        popup.open()

    def show_spell_info_popup(self, spell_name, instance):
        if spell_name in ["Keiner", "Wähle Zauber...", "Wähle Ersatz..."]:
            return
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

    def increase_ability(self, ability, instance):
        if self.total_points_allocated >= 2:
            self.show_popup("Fehler", "Du hast bereits 2 Punkte verteilt.")
            return

        current_increase = self.ability_scores_to_increase.get(ability, 0)
        # Prevent increasing a single ability by more than 2, or by 2 if another ability is already at 1
        if current_increase >= 2 or (current_increase >= 1 and self.total_points_allocated >=1):
            self.show_popup("Fehler", "Du kannst ein Attribut um maximal 2, oder zwei Attribute um maximal 1 erhöhen.")
            return

        self.ability_scores_to_increase[ability] = current_increase + 1
        self.total_points_allocated += 1
        self.update_ability_increase_display()

    def decrease_ability(self, ability, instance):
        if self.ability_scores_to_increase.get(ability, 0) > 0:
            self.ability_scores_to_increase[ability] -= 1
            if self.ability_scores_to_increase[ability] == 0:
                del self.ability_scores_to_increase[ability]
            self.total_points_allocated -= 1
            self.update_ability_increase_display()

    def update_ability_increase_display(self):
        self.points_label.text = f"Verbleibende Punkte: {2 - self.total_points_allocated}"
        for ability, label in self.ability_increase_labels.items():
            increase = self.ability_scores_to_increase.get(ability, 0)
            label.text = f"+{increase}" if increase > 0 else ""

    def show_ability_info(self, ability_name, instance):
        descriptions = {
            "Stärke": "Misst die körperliche Kraft. Wichtig für Barbaren, Kämpfer und Paladine.",
            "Geschicklichkeit": "Misst die Beweglichkeit, Reflexe und Balance. Wichtig für Schurken, Waldläufer und Mönche.",
            "Konstitution": "Misst die Ausdauer und Lebenskraft. Wichtig für alle Klassen, da es die Trefferpunkte beeinflusst.",
            "Intelligenz": "Misst die geistige Schärfe und das Erinnerungsvermögen. Wichtig für Magier.",
            "Weisheit": "Misst die Wahrnehmungsfähigkeit und Intuition. Wichtig für Kleriker und Druiden.",
            "Charisma": "Misst die Überzeugungskraft und die Stärke der Persönlichkeit. Wichtig für Barden, Hexenmeister und Paktmagier."
        }
        self.show_popup(f"Info: {ability_name}", descriptions.get(ability_name, "Keine Beschreibung verfügbar."))

    def confirm_level_up(self):
        choices = {}

        if hasattr(self, 'total_points_allocated') and self.total_points_allocated > 0:
            if self.total_points_allocated != 2:
                self.show_popup("Fehler", "Bitte verteile genau 2 Attributspunkte.")
                return

            ability_increases = []
            for ability, increase in self.ability_scores_to_increase.items():
                for _ in range(increase):
                    ability_increases.append(ability)
            choices["ability_increase"] = ability_increases


        if self.spell_choices:
            choices.update(self.spell_choices)

        self.character.level_up(choices)
        self.manager.get_screen('sheet').load_character(self.character)
        self.manager.current = 'sheet'

    def cancel_level_up(self):
        self.manager.current = 'sheet'

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
