# main.py

import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
import random
import pickle
import os
from functools import partial

from dnd_data import CLASS_DATA, RACE_DATA, WEAPON_DATA, SPELL_DATA, PROFICIENCY_BONUS, SKILLS

class Character:
    def __init__(self, name, race, char_class):
        self.name = name; self.race = race; self.char_class = char_class
        self.level = 1
        self.base_abilities = {"Stärke": 10, "Geschicklichkeit": 10, "Konstitution": 10, "Intelligenz": 10, "Weisheit": 10, "Charisma": 10}
        self.abilities = self.base_abilities.copy()
        self.hit_points = 0; self.max_hit_points = 0; self.hit_dice = {}
        self.proficiency_bonus = 0; self.armor_class = 0; self.initiative = 0; self.speed = 0
        self.inventory = {}; self.currency = {"KP": 0, "SP": 0, "EP": 0, "GM": 0, "PP": 0}
        self.equipped_weapon = "Unbewaffneter Schlag"; self.background = ""; self.alignment = ""
        self.personality_traits = ""; self.ideals = ""; self.bonds = ""; self.flaws = ""
        self.features = []; self.proficiencies = []; self.languages = []
        self.saving_throws = {}; self.skills = {}; self.spells = {}; self.max_spell_slots = {}

    def initialize_character(self):
        self.update_race_bonuses_and_speed(); self.collect_proficiencies_and_languages()
        class_info = CLASS_DATA.get(self.char_class, {})
        for skill in SKILLS: self.skills[skill] = {"proficient": False}
        for ability in self.abilities: self.saving_throws[ability] = {"proficient": False}
        for saving_throw in class_info.get("saving_throws", []): self.saving_throws[saving_throw]["proficient"] = True
        for skill in class_info.get("skill_proficiencies", [])[:2]: self.skills[skill]["proficient"] = True
        self.calculate_all_stats()
        self.max_hit_points = CLASS_DATA.get(self.char_class, {}).get("hit_die", 8) + self.get_modifier("Konstitution")
        self.hit_points = self.max_hit_points

    def get_modifier(self, ability): return (self.abilities.get(ability, 10) - 10) // 2
    
    def calculate_all_stats(self):
        self.proficiency_bonus = PROFICIENCY_BONUS.get(self.level, 2)
        self.initiative = self.get_modifier("Geschicklichkeit")
        self.armor_class = 10 + self.get_modifier("Geschicklichkeit")
        self.hit_dice = {f"d{CLASS_DATA[self.char_class]['hit_die']}": self.level}
        for ability, data in self.saving_throws.items():
            bonus = self.get_modifier(ability)
            if data["proficient"]: bonus += self.proficiency_bonus
            data["bonus"] = bonus
        for skill, data in self.skills.items():
            ability = SKILLS[skill]; bonus = self.get_modifier(ability)
            if data["proficient"]: bonus += self.proficiency_bonus
            data["bonus"] = bonus
        self.prepare_spellbook(); self.update_features()

    def update_race_bonuses_and_speed(self):
        self.abilities = self.base_abilities.copy()
        race_info = RACE_DATA.get(self.race, {})
        for ability, bonus in race_info.get("ability_score_increase", {}).items():
            if ability in self.abilities: self.abilities[ability] += bonus
        self.speed = race_info.get("speed", 9)
    
    def collect_proficiencies_and_languages(self):
        race_info = RACE_DATA.get(self.race, {}); class_info = CLASS_DATA.get(self.char_class, {})
        self.proficiencies = sorted(list(set(race_info.get("proficiencies", [])) | set(class_info.get("proficiencies", []))))
        self.languages = sorted(list(set(race_info.get("languages", [])) | set(class_info.get("languages", []))))
    
    def update_features(self):
        self.features = []; class_features = CLASS_DATA.get(self.char_class, {}).get("features", {})
        for lvl in range(1, self.level + 1):
            if lvl in class_features: self.features.extend(class_features[lvl])
    
    def prepare_spellbook(self):
        class_info = CLASS_DATA.get(self.char_class, {})
        self.spells = class_info.get("spells", {}); self.max_spell_slots = class_info.get("spell_slots", {}).get(self.level, {})
    
    def level_up(self, asi_choices=None):
        self.level += 1
        if asi_choices:
            for ability, increase in asi_choices.items(): self.base_abilities[ability] += increase
        self.update_race_bonuses_and_speed(); self.calculate_all_stats()
        hit_die = CLASS_DATA.get(self.char_class, {}).get("hit_die", 8)
        hp_increase = random.randint(1, hit_die) + self.get_modifier("Konstitution")
        self.max_hit_points += max(1, hp_increase); self.hit_points = self.max_hit_points

class MainMenu(Screen):
    def __init__(self, **kwargs):
        super(MainMenu, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Label(text="D&D Charakterblatt", font_size='32sp'))
        new_char_button = Button(text="Neuen Charakter erstellen", on_press=self.switch_to_creator)
        layout.add_widget(new_char_button)
        load_char_button = Button(text="Charakter verwalten", on_press=self.show_load_popup)
        layout.add_widget(load_char_button)
        self.add_widget(layout)
    def switch_to_creator(self, instance): self.manager.current = 'creator'
    def show_load_popup(self, instance=None):
        content = BoxLayout(orientation='vertical', spacing=10)
        popup_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        popup_layout.bind(minimum_height=popup_layout.setter('height'))
        files = [f for f in os.listdir('.') if f.endswith('.char')]
        for filename in files:
            row = BoxLayout(size_hint_y=None, height=40)
            char_name = filename.replace(".char", "").replace("_", " ").title()
            row.add_widget(Label(text=char_name))
            load_btn = Button(text="Laden", size_hint_x=0.3, on_press=partial(self.load_character, filename))
            delete_btn = Button(text="Löschen", size_hint_x=0.3, on_press=partial(self.confirm_delete, filename))
            row.add_widget(load_btn)
            row.add_widget(delete_btn)
            popup_layout.add_widget(row)
        scroll_view = ScrollView(); scroll_view.add_widget(popup_layout)
        content.add_widget(scroll_view)
        self.popup = Popup(title="Charakter verwalten", content=content, size_hint=(0.8, 0.8))
        self.popup.open()
    def load_character(self, filename, instance):
        try:
            with open(filename, 'rb') as f: character = pickle.load(f)
            self.manager.get_screen('sheet').load_character(character); self.manager.current = 'sheet'; self.popup.dismiss()
        except Exception as e: self.show_popup("Fehler", f"Fehler beim Laden: {e}")
    def confirm_delete(self, filename, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        char_name = filename.replace(".char", "").replace("_", " ").title()
        content.add_widget(Label(text=f"'{char_name}' wirklich löschen?"))
        btn_box = BoxLayout(spacing=10); yes_btn = Button(text="Ja, löschen"); no_btn = Button(text="Nein")
        btn_box.add_widget(yes_btn); btn_box.add_widget(no_btn)
        content.add_widget(btn_box)
        del_popup = Popup(title="Löschen bestätigen", content=content, size_hint=(0.6, 0.4))
        yes_btn.bind(on_press=lambda x: (self.delete_character(filename), del_popup.dismiss(), self.popup.dismiss(), self.show_load_popup()))
        no_btn.bind(on_press=del_popup.dismiss)
        del_popup.open()
    def delete_character(self, filename):
        try: os.remove(filename)
        except Exception as e: self.show_popup("Fehler", f"Konnte Datei nicht löschen: {e}")
    def show_popup(self, title, message): Popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4)).open()

class CharacterCreator(Screen):
    def __init__(self, **kwargs):
        super(CharacterCreator, self).__init__(**kwargs)
        scroll_view = ScrollView(size_hint=(1, 1)); layout = GridLayout(cols=2, padding=10, spacing=10, size_hint_y=None); layout.bind(minimum_height=layout.setter('height'))
        self.inputs = {}; default_height = 44; multiline_height = 120
        fields = [("Name", "TextInput", default_height, []), ("Rasse", "Spinner", default_height, sorted(RACE_DATA.keys())), ("Klasse", "Spinner", default_height, sorted(CLASS_DATA.keys())), ("Gesinnung", "TextInput", default_height, []), ("Hintergrund", "TextInput", default_height, []), ("Persönliche Merkmale", "TextInput", multiline_height, []), ("Ideale", "TextInput", multiline_height, []), ("Bindungen", "TextInput", multiline_height, []), ("Makel", "TextInput", multiline_height, [])]
        for field_name, widget_type, height, values in fields:
            label = Label(text=f"{field_name}:", size_hint=(None, None), width=180, height=height, halign='left', valign='middle'); label.bind(size=label.setter('text_size')); layout.add_widget(label)
            if widget_type == "TextInput": widget = TextInput(size_hint_y=None, height=height, multiline=(height > default_height))
            else: widget = Spinner(text=values[0], values=values, size_hint_y=None, height=height)
            self.inputs[field_name] = widget; layout.add_widget(widget)
        self.ability_scores_labels = {}; abilities = ["Stärke", "Geschicklichkeit", "Konstitution", "Intelligenz", "Weisheit", "Charisma"]
        for ability in abilities:
            label = Label(text=ability, size_hint=(None, None), width=180, height=default_height, halign='left', valign='middle'); layout.add_widget(label)
            stat_box = BoxLayout(size_hint_y=None, height=default_height); minus_btn = Button(text="-", on_press=partial(self.adjust_ability, ability, -1)); score_label = Label(text="10"); plus_btn = Button(text="+", on_press=partial(self.adjust_ability, ability, 1))
            stat_box.add_widget(minus_btn); stat_box.add_widget(score_label); stat_box.add_widget(plus_btn)
            self.ability_scores_labels[ability] = score_label; layout.add_widget(stat_box)
        layout.add_widget(Label(size_hint_y=None, height=10)); layout.add_widget(Label(size_hint_y=None, height=10))
        roll_button = Button(text="Attribute auswürfeln", on_press=self.roll_abilities, size_hint_y=None, height=default_height); create_button = Button(text="Charakter erstellen", on_press=self.create_character, size_hint_y=None, height=default_height)
        layout.add_widget(roll_button); layout.add_widget(create_button)
        scroll_view.add_widget(layout); self.add_widget(scroll_view)
    def adjust_ability(self, ability, amount, instance): current_score = int(self.ability_scores_labels[ability].text); new_score = max(1, min(20, current_score + amount)); self.ability_scores_labels[ability].text = str(new_score)
    def roll_abilities(self, instance):
        for ability in self.ability_scores_labels: rolls = sorted([random.randint(1, 6) for _ in range(4)]); score = sum(rolls[1:]); self.ability_scores_labels[ability].text = str(score)
    def create_character(self, instance):
        name = self.inputs["Name"].text.strip()
        if not name: self.show_popup("Fehler", "Bitte gib einen Namen ein."); return
        character = Character(name, self.inputs["Rasse"].text, self.inputs["Klasse"].text)
        for ability, label in self.ability_scores_labels.items(): character.base_abilities[ability] = int(label.text)
        character.alignment = self.inputs["Gesinnung"].text; character.background = self.inputs["Hintergrund"].text; character.personality_traits = self.inputs["Persönliche Merkmale"].text; character.ideals = self.inputs["Ideale"].text; character.bonds = self.inputs["Bindungen"].text; character.flaws = self.inputs["Makel"].text
        character.initialize_character()
        self.manager.get_screen('sheet').load_character(character); self.manager.current = 'sheet'
    def show_popup(self, title, message): Popup(title=title, content=Label(text=message), size_hint=(0.5, 0.5)).open()

class CharacterSheet(Screen):
    def __init__(self, **kwargs): super(CharacterSheet, self).__init__(**kwargs); self.character = None; self.main_layout = BoxLayout(orientation='vertical'); self.add_widget(self.main_layout)
    def load_character(self, character): self.character = character; self.update_sheet()
    def update_sheet(self):
        self.main_layout.clear_widgets();
        if not self.character: return
        header = BoxLayout(size_hint_y=None, height=80, padding=5)
        name_level_box = BoxLayout(orientation='vertical'); name_level_box.add_widget(Label(text=self.character.name, font_size='24sp')); name_level_box.add_widget(Label(text=f"Level {self.character.level} {self.character.race} {self.character.char_class}", font_size='14sp')); header.add_widget(name_level_box)
        stats_grid = GridLayout(cols=4); stats_grid.add_widget(Label(text=f"[b]RK[/b]\n{self.character.armor_class}", markup=True)); stats_grid.add_widget(Label(text=f"[b]Initiative[/b]\n{self.character.initiative:+}d", markup=True)); stats_grid.add_widget(Label(text=f"[b]Ü-Bonus[/b]\n+{self.character.proficiency_bonus}", markup=True)); stats_grid.add_widget(Label(text=f"[b]Bewegung[/b]\n{self.character.speed}m", markup=True)); header.add_widget(stats_grid)
        self.main_layout.add_widget(header)
        body = ScrollView(); content = GridLayout(cols=3, spacing=10, padding=10, size_hint_y=None); content.bind(minimum_height=content.setter('height'))
        left_col = BoxLayout(orientation='vertical', size_hint_x=0.35, size_hint_y=None, spacing=5); left_col.bind(minimum_height=left_col.setter('height'))
        for ability, score in self.character.abilities.items():
            mod = self.character.get_modifier(ability); box = BoxLayout(size_hint_y=None, height=60, orientation='vertical'); box.add_widget(Label(text=f"{ability}", bold=True)); box.add_widget(Label(text=f"{mod:+d}", font_size='22sp')); left_col.add_widget(box)
        left_col.add_widget(Label(text="Rettungswürfe", bold=True, size_hint_y=None, height=30))
        for ability, data in self.character.saving_throws.items(): left_col.add_widget(Label(text=f"{'*' if data['proficient'] else '  '} {data['bonus']:+d}  {ability}", size_hint_y=None, height=25, halign='left'))
        left_col.add_widget(Label(text="Fertigkeiten", bold=True, size_hint_y=None, height=30))
        for skill, data in self.character.skills.items(): left_col.add_widget(Label(text=f"{'*' if data['proficient'] else '  '} {data['bonus']:+d}  {skill} ({SKILLS[skill][:3]})", size_hint_y=None, height=25, font_size='12sp', halign='left'))
        content.add_widget(left_col)
        mid_col = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10); mid_col.bind(minimum_height=mid_col.setter('height'))
        hp_box = BoxLayout(orientation='vertical', size_hint_y=None, height=100); hp_box.add_widget(Label(text="Trefferpunkte")); self.hp_label = Label(text=f"{self.character.hit_points} / {self.character.max_hit_points}", font_size='22sp'); hp_box.add_widget(self.hp_label); mid_col.add_widget(hp_box)
        hd_box = BoxLayout(orientation='vertical', size_hint_y=None, height=60); hd_box.add_widget(Label(text="Trefferwürfel")); hd_box.add_widget(Label(text=" ".join([f"{num}{die}" for die, num in self.character.hit_dice.items()]))); mid_col.add_widget(hd_box)
        mid_col.add_widget(Label(text="Fähigkeiten & Merkmale", bold=True, size_hint_y=None, height=30))
        for feature in self.character.features: btn = Button(text=feature['name'], size_hint_y=None, height=40, text_size=(self.width/4, None), halign='center'); btn.bind(on_press=partial(self.show_feature_popup, feature)); mid_col.add_widget(btn)
        content.add_widget(mid_col)
        right_col = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10); right_col.bind(minimum_height=right_col.setter('height'))
        right_col.add_widget(Label(text="Inventar", bold=True, size_hint_y=None, height=30))
        self.inventory_layout = GridLayout(cols=1, spacing=5, size_hint_y=None); self.inventory_layout.bind(minimum_height=self.inventory_layout.setter('height')); self.update_inventory_display(); right_col.add_widget(self.inventory_layout); right_col.add_widget(Button(text="+ Item", on_press=self.show_add_item_popup, size_hint_y=None, height=44))
        content.add_widget(right_col)
        body.add_widget(content); self.main_layout.add_widget(body)
        footer = BoxLayout(size_hint_y=None, height=50, spacing=5); footer.add_widget(Button(text="Info", on_press=self.show_info_popup)); footer.add_widget(Button(text="Zauber", on_press=self.show_spells_popup)); footer.add_widget(Button(text="Level Up", on_press=self.level_up_popup)); footer.add_widget(Button(text="Speichern", on_press=self.save_character)); footer.add_widget(Button(text="Hauptmenü", on_press=lambda x: setattr(self.manager, 'current', 'main'))); self.main_layout.add_widget(footer)
    def level_up_popup(self, instance):
        new_level = self.character.level + 1; is_asi_level = new_level in [4, 8, 12, 16, 19]
        content = BoxLayout(orientation='vertical', padding=10, spacing=10); content.add_widget(Label(text=f"Aufstieg auf Level {new_level}"))
        if is_asi_level: content.add_widget(Label(text="Du kannst deine Attributswerte erhöhen!")); asi_btn = Button(text="Attribute wählen"); asi_btn.bind(on_press=self.asi_popup); content.add_widget(asi_btn)
        else: confirm_btn = Button(text="Bestätigen"); confirm_btn.bind(on_press=lambda x: (self.character.level_up(), self.update_sheet(), self.popup.dismiss())); content.add_widget(confirm_btn)
        self.popup = Popup(title="Level Up", content=content, size_hint=(0.7, 0.6)); self.popup.open()
    def asi_popup(self, instance):
        self.popup.dismiss(); self.asi_choices = {}; self.asi_points = 2
        content = GridLayout(cols=2, padding=10, spacing=10); self.asi_point_label = Label(text=f"Punkte übrig: {self.asi_points}"); content.add_widget(Label()); content.add_widget(self.asi_point_label)
        self.asi_labels = {}
        for ability, score in self.character.base_abilities.items():
            content.add_widget(Label(text=f"{ability} ({score})")); btn_box = BoxLayout(); plus_btn = Button(text="+"); minus_btn = Button(text="-")
            btn_box.add_widget(minus_btn); btn_box.add_widget(plus_btn); plus_btn.bind(on_press=partial(self.adjust_asi, ability, 1)); minus_btn.bind(on_press=partial(self.adjust_asi, ability, -1))
            self.asi_labels[ability] = Label(text=""); btn_box.add_widget(self.asi_labels[ability]); content.add_widget(btn_box); self.asi_choices[ability] = 0
        confirm_btn = Button(text="Bestätigen", disabled=True); content.add_widget(confirm_btn)
        self.asi_confirm_btn = confirm_btn # Referenz speichern
        asi_popup = Popup(title="Attributswerterhöhung", content=content, size_hint=(0.8, 0.8))
        confirm_btn.bind(on_press=lambda x: (self.character.level_up(self.asi_choices), self.update_sheet(), asi_popup.dismiss())); asi_popup.open()
    def adjust_asi(self, ability, amount, instance):
        if amount > 0 and self.asi_points > 0: self.asi_choices[ability] += 1; self.asi_points -= 1
        elif amount < 0 and self.asi_choices[ability] > 0: self.asi_choices[ability] -= 1; self.asi_points += 1
        self.asi_labels[ability].text = f"+{self.asi_choices[ability]}" if self.asi_choices[ability] > 0 else ""
        self.asi_point_label.text = f"Punkte übrig: {self.asi_points}"; self.asi_confirm_btn.disabled = self.asi_points > 0
    def update_inventory_display(self):
        self.inventory_layout.clear_widgets()
        for item_name, quantity in self.character.inventory.items():
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            item_row.add_widget(Label(text=f"{item_name} ({quantity})", halign='left', valign='middle'))
            btn_box = BoxLayout(size_hint_x=0.4); btn_box.add_widget(Button(text="-", on_press=partial(self.adjust_item_quantity, item_name, -1))); btn_box.add_widget(Button(text="+", on_press=partial(self.adjust_item_quantity, item_name, 1))); item_row.add_widget(btn_box)
            self.inventory_layout.add_widget(item_row)
    def adjust_item_quantity(self, item_name, amount, instance): self.character.inventory[item_name] += amount; self.update_inventory_display()
    def show_add_item_popup(self, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10); item_input = TextInput(hint_text="Gegenstand", multiline=False); content.add_widget(item_input); add_btn = Button(text="Hinzufügen"); content.add_widget(add_btn); popup = Popup(title="Item hinzufügen", content=content, size_hint=(0.8, 0.4))
        def add_action(instance):
            item_name = item_input.text.strip()
            if item_name: self.character.inventory[item_name] = self.character.inventory.get(item_name, 0) + 1; self.update_inventory_display(); popup.dismiss()
        add_btn.bind(on_press=add_action); popup.open()
    def show_spells_popup(self, instance):
        content = ScrollView(); grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=10); grid.bind(minimum_height=grid.setter('height'))
        if not self.character.spells: grid.add_widget(Label(text="Keine Zauber.", size_hint_y=None, height=40))
        else:
            if 'cantrips' in self.character.spells:
                grid.add_widget(Label(text=f"Zaubertricks ({len(self.character.spells['cantrips'])} bekannt)", font_size='18sp', size_hint_y=None, height=40))
                for spell_name in self.character.spells['cantrips']: btn = Button(text=spell_name, size_hint_y=None, height=40); btn.bind(on_press=partial(self.show_spell_details_popup, spell_name)); grid.add_widget(btn)
            for i in range(1, 10):
                level_key = f"level{i}"; slots = self.character.max_spell_slots.get(str(i), 0)
                if slots > 0 and level_key in self.character.spells:
                    grid.add_widget(Label(text=f"Level {i} Zauber (Slots: {slots})", font_size='18sp', size_hint_y=None, height=40))
                    for spell_name in self.character.spells[level_key]: btn = Button(text=spell_name, size_hint_y=None, height=40); btn.bind(on_press=partial(self.show_spell_details_popup, spell_name)); grid.add_widget(btn)
        content.add_widget(grid); Popup(title="Zauberbuch", content=content, size_hint=(0.8, 0.9)).open()
    def show_info_popup(self, instance):
        text = (f"[b]Hintergrund:[/b] {self.character.background}\n\n[b]Kompetenzen:[/b]\n{', '.join(self.character.proficiencies)}\n\n[b]Sprachen:[/b]\n{', '.join(self.character.languages)}\n\n[b]Persönliche Merkmale:[/b]\n{self.character.personality_traits}\n\n[b]Ideale:[/b]\n{self.character.ideals}\n\n[b]Bindungen:[/b]\n{self.character.bonds}\n\n[b]Makel:[/b]\n{self.character.flaws}")
        self.show_popup("Charakter-Informationen", text)
    def save_character(self, instance):
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        try:
            with open(filename, 'wb') as f: pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter als '{filename}' gespeichert.")
        except Exception as e: self.show_popup("Fehler", f"Fehler beim Speichern: {e}")
    def show_feature_popup(self, feature, instance): self.show_popup(feature['name'], feature['desc'])
    def show_spell_details_popup(self, spell_name, instance):
        spell_info = SPELL_DATA.get(spell_name, {}); text = (f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n{spell_info.get('desc', 'Keine Beschreibung.')}")
        self.show_popup(spell_name, text)
    def show_popup(self, title, message):
        content = ScrollView(); label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10)); label.bind(width=lambda *x: label.setter('text_size')(label, (label.width, None)), texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])); content.add_widget(label)
        Popup(title=title, content=content, size_hint=(0.8, 0.8)).open()

class DnDApp(App):
    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        sm = ScreenManager()
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(CharacterCreator(name='creator'))
        sm.add_widget(CharacterSheet(name='sheet'))
        return sm

if __name__ == '__main__':
    DnDApp().run()