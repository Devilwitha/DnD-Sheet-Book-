import random
from functools import partial
import pickle
import os

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.properties import ObjectProperty
from kivy.app import App

from utils.data_manager import WEAPON_DATA, SKILL_LIST, SPELL_DATA
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, get_user_saves_dir

class CharacterSheet(Screen):
    """Finaler Charakterbogen mit allen neuen Features."""
    main_layout = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(CharacterSheet, self).__init__(**kwargs)
        self.character = None
        self.currency_labels = {}

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

        app = App.get_running_app()
        if hasattr(app, 'source_screen') and app.source_screen:
            self.ids.dm_back_button.text = f"Zurück zu {app.source_screen.replace('_', ' ').title()}"
            self.ids.dm_back_button.height = 50
            self.ids.dm_back_button.opacity = 1
            self.ids.dm_back_button.disabled = False
            self.ids.main_menu_button.height = 0
            self.ids.main_menu_button.opacity = 0
            self.ids.main_menu_button.disabled = True
        else:
            self.ids.dm_back_button.height = 0
            self.ids.dm_back_button.opacity = 0
            self.ids.dm_back_button.disabled = True
            self.ids.main_menu_button.height = 50
            self.ids.main_menu_button.opacity = 1
            self.ids.main_menu_button.disabled = False

    def load_character(self, character):
        self.character = character
        if self.character:
            if hasattr(self.character, 'normalize_spells'):
                self.character.normalize_spells()
        self.update_sheet()

    def update_sheet(self):
        if not self.character:
            return

        self.ids.name_label.text = f"{self.character.name}"
        self.ids.class_label.text = f"{self.character.race} {self.character.char_class} {self.character.level}"
        self.ids.alignment_label.text = f"Gesinnung: {self.character.alignment}"

        self.ids.stats_box.clear_widgets()
        for ability, score in self.character.abilities.items():
            modifier = (score - 10) // 2
            sign = "+" if modifier >= 0 else ""
            self.ids.stats_box.add_widget(Label(text=f"{ability}:"))
            self.ids.stats_box.add_widget(Label(text=f"{score} ({sign}{modifier})"))
        self.ids.stats_box.add_widget(Label(text="Rüstungsklasse:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.armor_class}"))
        self.ids.stats_box.add_widget(Label(text="Initiative:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.initiative:+}"))
        self.ids.stats_box.add_widget(Label(text="Bewegungsrate:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.speed}m ({int(self.character.speed / 1.5)} Felder)"))
        self.ids.stats_box.add_widget(Label(text="Trefferwürfel:"))
        self.ids.stats_box.add_widget(Label(text=f"{self.character.hit_dice}/{self.character.max_hit_dice}"))


        self.ids.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"

        self.ids.weapon_spinner.text = self.character.equipped_weapon
        self.ids.weapon_spinner.values = sorted(WEAPON_DATA.keys())

        self.ids.currency_box.clear_widgets()
        self.ids.currency_box.add_widget(Label(text="Währung", size_hint_x=None, width=100))
        self.ids.currency_box.add_widget(Label())
        self.ids.currency_box.add_widget(Label())
        for curr in ["KP", "SP", "EP", "GM", "PP"]:
            self.ids.currency_box.add_widget(Label(text=f"{curr}:"))
            self.currency_labels[curr] = Label(text=str(self.character.currency[curr]))
            self.ids.currency_box.add_widget(self.currency_labels[curr])
            btn_box = BoxLayout()

            minus_btn = Button(text="-", on_press=partial(self.change_currency, curr, -1))
            plus_btn = Button(text="+", on_press=partial(self.change_currency, curr, 1))

            apply_styles_to_widget(minus_btn)
            apply_styles_to_widget(plus_btn)

            btn_box.add_widget(minus_btn)
            btn_box.add_widget(plus_btn)
            self.ids.currency_box.add_widget(btn_box)

        self.ids.features_layout.clear_widgets()
        for feature in self.character.features:
            btn = Button(text=feature['name'], size_hint_y=None, height=40, halign='left', valign='middle', padding=(10, 0))
            btn.bind(on_press=partial(self.show_feature_popup, feature))
            apply_styles_to_widget(btn)
            self.ids.features_layout.add_widget(btn)

        self.update_inventory_display()
        self.update_equipment_display()


    def show_popup(self, title, message):
        content = ScrollView()
        label = Label(text=message, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        content.add_widget(label)
        create_styled_popup(title=title, content=content, size_hint=(0.8, 0.8)).open()

    def update_weapon(self, text):
        self.character.equipped_weapon = text
        self.sync_character()

    def change_hp(self, amount):
        self.character.hit_points += amount
        self.character.hit_points = max(0, min(self.character.hit_points, self.character.max_hit_points))
        self.ids.hp_label.text = f"HP: {self.character.hit_points} / {self.character.max_hit_points}"
        self.sync_character()

    def sync_character(self):
        """Generic sync function that decides whether to sync to client or host."""
        app = App.get_running_app()
        if app.network_manager.mode == 'dm':
            self.sync_character_to_client()
        elif app.network_manager.mode == 'client':
            self.sync_character_to_host()

    def sync_character_to_host(self):
        """Sends the entire character object to the host."""
        app = App.get_running_app()
        if not self.character or not app.network_manager or app.network_manager.mode != 'client':
            return
        app.network_manager.send_to_dm("SET_CHARACTER_DATA", self.character.to_dict())

    def sync_character_to_client(self):
        """If the DM is viewing this sheet, send the updated character to the client."""
        app = App.get_running_app()
        if hasattr(app, 'source_screen') and app.source_screen and app.network_manager.mode == 'dm':
            nm = app.network_manager
            client_addr = nm.get_client_addr_by_name(self.character.name)
            if client_addr:
                nm.send_message(client_addr, "SET_CHARACTER_DATA", self.character.to_dict())

    def change_currency(self, currency, amount, instance):
        self.character.currency[currency] += amount
        self.character.currency[currency] = max(0, self.character.currency[currency])
        self.currency_labels[currency].text = str(self.character.currency[currency])
        self.sync_character()

    def update_inventory_display(self):
        self.ids.inventory_layout.clear_widgets()
        for index, item in enumerate(self.character.inventory):
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            text = f"{item['name']} ({item['quantity']})"
            if 'healing' in item:
                text += f" (Heilung: {item['healing']['count']}d{item['healing']['dice']})"
            item_row.add_widget(Label(text=text, halign='left', valign='middle'))
            btn_box = BoxLayout(size_hint_x=0.5)
            if 'healing' in item:
                btn_box.add_widget(Button(text="Benutzen", on_press=partial(self.use_healing_item, index)))
            btn_box.add_widget(Button(text="-", on_press=partial(self.adjust_item_quantity, index, -1)))
            btn_box.add_widget(Button(text="+", on_press=partial(self.adjust_item_quantity, index, 1)))
            item_row.add_widget(btn_box)
            self.ids.inventory_layout.add_widget(item_row)

    def adjust_item_quantity(self, item_index, amount, instance):
        if 0 <= item_index < len(self.character.inventory):
            self.character.inventory[item_index]['quantity'] += amount
            if self.character.inventory[item_index]['quantity'] <= 0:
                self.character.inventory.pop(item_index)
            self.update_inventory_display()
            self.sync_character()

    def use_healing_item(self, item_index, instance):
        if 0 <= item_index < len(self.character.inventory):
            item = self.character.inventory[item_index]
            healing_info = item.get('healing')
            if healing_info:
                num_dice = healing_info['count']
                dice_type = healing_info['dice']
                total_healed = sum(random.randint(1, dice_type) for _ in range(num_dice))
                self.character.hit_points = min(self.character.max_hit_points, self.character.hit_points + total_healed)
                self.show_popup("Gegenstand benutzt", f"{total_healed} HP wiederhergestellt mit {item['name']}.")
                self.adjust_item_quantity(item_index, -1, None) # This will sync
                self.update_sheet()

    def update_equipment_display(self):
        self.ids.equipment_layout.clear_widgets()
        for item_name, ac_bonus in self.character.equipment.items():
            item_row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            item_row.add_widget(Label(text=f"{item_name} (AC: +{ac_bonus})", halign='left', valign='middle'))
            remove_btn = Button(text="-", size_hint_x=0.2)
            remove_btn.bind(on_press=partial(self.remove_equipment, item_name))
            item_row.add_widget(remove_btn)
            self.ids.equipment_layout.add_widget(item_row)

    def remove_equipment(self, item_name, instance):
        if item_name in self.character.equipment:
            del self.character.equipment[item_name]
            self.character.calculate_armor_class()
            self.update_sheet()
            self.sync_character()

    def show_add_equipment_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        name_input = TextInput(hint_text="Ausrüstungsname", multiline=False)
        ac_input = TextInput(hint_text="AC Bonus", multiline=False)
        content.add_widget(name_input)
        content.add_widget(ac_input)
        add_btn = Button(text="Hinzufügen")
        content.add_widget(add_btn)
        popup = create_styled_popup(title="Ausrüstung hinzufügen", content=content, size_hint=(0.8, 0.5))
        def add_action(instance):
            name = name_input.text.strip()
            try:
                ac_bonus = int(ac_input.text.strip())
                if name:
                    self.character.equipment[name] = ac_bonus
                    self.character.calculate_armor_class()
                    self.update_sheet()
                    self.sync_character()
                    popup.dismiss()
                else:
                    self.show_popup("Fehler", "Bitte einen Namen eingeben.")
            except ValueError:
                self.show_popup("Fehler", "AC Bonus muss eine Zahl sein.")
        add_btn.bind(on_press=add_action)
        apply_styles_to_widget(content)
        popup.open()

    def show_add_item_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        item_input = TextInput(hint_text="Gegenstandname", multiline=False)
        content.add_widget(item_input)
        healing_box = BoxLayout(size_hint_y=None, height=44)
        healing_box.add_widget(Label(text="Heilitem:"))
        is_healing_checkbox = CheckBox()
        healing_box.add_widget(is_healing_checkbox)
        content.add_widget(healing_box)
        dice_count_input = TextInput(hint_text="Anzahl Würfel (z.B. 2)", multiline=False, disabled=True)
        dice_type_input = TextInput(hint_text="Würfelart (z.B. 4 für d4)", multiline=False, disabled=True)
        def on_checkbox_active(checkbox, value):
            dice_count_input.disabled = not value
            dice_type_input.disabled = not value
        is_healing_checkbox.bind(active=on_checkbox_active)
        content.add_widget(dice_count_input)
        content.add_widget(dice_type_input)
        add_btn = Button(text="Hinzufügen")
        content.add_widget(add_btn)
        popup = create_styled_popup(title="Item hinzufügen", content=content, size_hint=(0.8, 0.7))
        def add_action(instance):
            item_name = item_input.text.strip()
            if not item_name:
                self.show_popup("Fehler", "Bitte einen Namen für den Gegenstand eingeben.")
                return
            is_healing = is_healing_checkbox.active
            healing_details = None
            if is_healing:
                try:
                    count = int(dice_count_input.text)
                    dice = int(dice_type_input.text)
                    healing_details = {"count": count, "dice": dice}
                except ValueError:
                    self.show_popup("Fehler", "Ungültige Würfel-Eingabe für Heilitem.")
                    return
            found_item = None
            for item in self.character.inventory:
                if item['name'] == item_name:
                    item_is_healing = 'healing' in item
                    if is_healing and item_is_healing and item.get('healing') and healing_details and \
                       item['healing']['count'] == healing_details['count'] and \
                       item['healing']['dice'] == healing_details['dice']:
                        found_item = item
                        break
                    elif not is_healing and not item_is_healing:
                        found_item = item
                        break
            if found_item:
                found_item['quantity'] += 1
            else:
                new_item = {"name": item_name, "quantity": 1}
                if is_healing:
                    new_item['healing'] = healing_details
                self.character.inventory.append(new_item)
            self.update_inventory_display()
            self.sync_character()
            popup.dismiss()
        add_btn.bind(on_press=add_action)
        apply_styles_to_widget(content)
        popup.open()

    def roll_damage(self):
        weapon_name = self.character.equipped_weapon
        weapon_info = WEAPON_DATA.get(weapon_name, WEAPON_DATA["Unbewaffneter Schlag"])
        ability_name = weapon_info["ability"]
        modifier = (self.character.abilities[ability_name] - 10) // 2
        parts = weapon_info["damage"].split('d')
        num_dice = int(parts[0])
        dice_type = int(parts[1])
        roll_total = sum(random.randint(1, dice_type) for _ in range(num_dice))
        total_damage = roll_total + modifier
        self.show_popup(
            "Schadenswurf",
            f"{weapon_info['damage']} ({roll_total}) + {ability_name[:3]}-Mod ({modifier}) = {max(1, total_damage)} Schaden"
        )

    def show_feature_popup(self, feature, instance):
        self.show_popup(feature['name'], feature['desc'])

    def show_info_popup(self):
        prof_text = ", ".join(self.character.proficiencies)
        lang_text = ", ".join(self.character.languages)
        features_text = ""
        if self.character.features:
            features_text = "\n\n[b]Klassenmerkmale:[/b]\n"
            for feature in self.character.features:
                features_text += f"- {feature['name']}\n"
        skills_text = "\n\n[b]Fähigkeiten:[/b]\n"
        for skill, ability in SKILL_LIST.items():
            modifier = (self.character.abilities[ability] - 10) // 2
            if skill in self.character.proficiencies:
                modifier += self.character.get_proficiency_bonus()
            sign = "+" if modifier >= 0 else ""
            skills_text += f"- {skill}: {sign}{modifier}\n"
        text = (
            f"[b]Gesinnung:[/b] {self.character.alignment}\n\n"
            f"[b]Hintergrund:[/b] {self.character.background}\n\n"
            f"[b]Kompetenzen:[/b]\n{prof_text}\n\n"
            f"[b]Sprachen:[/b]\n{lang_text}\n\n"
            f"{skills_text}"
            f"[b]Persönliche Merkmale:[/b]\n{self.character.personality_traits}\n\n"
            f"[b]Ideale:[/b]\n{self.character.ideals}\n\n"
            f"[b]Bindungen:[/b]\n{self.character.bonds}\n\n"
            f"[b]Makel:[/b]\n{self.character.flaws}"
            f"{features_text}"
        )
        self.show_popup("Charakter-Informationen", text)

    def show_spells_popup(self):
        content = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=5, padding=10)
        grid.bind(minimum_height=grid.setter('height'))
        if not self.character.spells:
            grid.add_widget(Label(text="Dieser Charakter kann nicht zaubern.", size_hint_y=None, height=40))
        else:
            for spell_level in sorted(self.character.spells.keys()):
                spell_list = self.character.spells[spell_level]
                if not spell_list: continue
                level_name = "Zaubertricks" if spell_level == 0 else f"Level {spell_level} Zauber"
                if spell_level > 0:
                    max_slots = self.character.max_spell_slots.get(str(spell_level), 0)
                    current_slots = self.character.current_spell_slots.get(str(spell_level), 0)
                    level_name += f" ({current_slots}/{max_slots})"
                grid.add_widget(Label(text=level_name, font_size='18sp', size_hint_y=None, height=40))
                for spell_name in sorted(spell_list):
                    btn = Button(text=spell_name, size_hint_y=None, height=40)
                    btn.bind(on_press=partial(self.show_spell_details_popup, spell_name))
                    grid.add_widget(btn)
        content.add_widget(grid)
        apply_styles_to_widget(content)
        create_styled_popup(title="Zauberbuch", content=content, size_hint=(0.8, 0.9)).open()

    def show_spell_details_popup(self, spell_name, instance):
        spell_info = SPELL_DATA.get(spell_name, {})
        text = (
            f"[b]Level:[/b] {spell_info.get('level', 'N/A')}\n"
            f"[b]Schule:[/b] {spell_info.get('school', 'N/A')}\n\n"
            f"{spell_info.get('desc', 'Keine Beschreibung verfügbar.')}"
        )
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll_view = ScrollView()
        label = Label(text=text, markup=True, size_hint_y=None, padding=(10, 10))
        label.bind(
            width=lambda *x: label.setter('text_size')(label, (label.width, None)),
            texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
        )
        scroll_view.add_widget(label)
        content.add_widget(scroll_view)
        popup = create_styled_popup(title=spell_name, content=content, size_hint=(0.8, 0.9))
        if spell_info.get("level", 0) > 0:
            cast_btn = Button(text="Wirken", size_hint_y=None, height=44)
            cast_btn.bind(on_press=lambda x: (self.cast_spell(spell_name, spell_info.get('level'), popup)))
            content.add_widget(cast_btn)
        apply_styles_to_widget(content)
        popup.open()

    def cast_spell(self, spell_name, spell_level, spell_details_popup):
        spell_level_str = str(spell_level)
        if self.character.current_spell_slots.get(spell_level_str, 0) > 0:
            self.character.current_spell_slots[spell_level_str] -= 1
            self.show_popup("Zauber gewirkt", f"Du hast '{spell_name}' gewirkt.")
            self.sync_character()
            spell_details_popup.dismiss()
            self.show_spells_popup()
        else:
            self.show_popup("Keine Zauberplätze", f"Keine Zauberplätze für Level {spell_level} mehr übrig.")

    def open_level_up_screen(self):
        self.manager.get_screen('level_up').set_character(self.character)
        self.manager.current = 'level_up'

    def save_character(self):
        saves_dir = get_user_saves_dir("characters")
        filename = f"{self.character.name.lower().replace(' ', '_')}.char"
        filepath = os.path.join(saves_dir, filename)
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(self.character, f)
            self.show_popup("Gespeichert", f"Charakter als '{filepath}' gespeichert.")
        except Exception as e:
            self.show_popup("Fehler", f"Fehler beim Speichern: {e}")

    def roll_d20(self):
        roll = random.randint(1, 20)
        self.show_popup("d20 Wurf", f"Du hast eine {roll} gewürfelt.")

    def roll_initiative(self):
        roll = random.randint(1, 20)
        total = roll + self.character.initiative
        self.show_popup("Initiativewurf", f"Wurf: {roll} + {self.character.initiative} = {total}")

    def show_rest_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        long_rest_btn = Button(text="Grosse Rast")
        content.add_widget(long_rest_btn)
        short_rest_btn = Button(text="Kleine Rast")
        content.add_widget(short_rest_btn)
        popup = create_styled_popup(title="Rasten", content=content, size_hint=(0.6, 0.4))
        long_rest_btn.bind(on_press=lambda x: (self.do_long_rest(), popup.dismiss()))
        short_rest_btn.bind(on_press=lambda x: (self.show_short_rest_popup(), popup.dismiss()))
        apply_styles_to_widget(content)
        popup.open()

    def do_long_rest(self):
        self.character.long_rest()
        self.update_sheet()
        self.show_popup("Grosse Rast", "Du bist vollständig ausgeruht. HP und Zauberplätze wurden wiederhergestellt.")
        self.sync_character()

    def go_back(self):
        """Navigates back to the source screen and clears the source."""
        app = App.get_running_app()
        if hasattr(app, 'source_screen') and app.source_screen:
            self.manager.current = app.source_screen
            app.source_screen = None # Clear the source after using it
        else:
            self.manager.current = 'main' # Fallback

    def show_short_rest_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        if self.character.hit_dice == 0:
            content.add_widget(Label(text="Du hast keine Trefferwürfel mehr übrig."))
        else:
            content.add_widget(Label(text=f"Verfügbare Trefferwürfel: {self.character.hit_dice}/{self.character.max_hit_dice}"))
            dice_input = TextInput(hint_text="Anzahl der zu verwendenden Würfel", input_filter='int', multiline=False)
            content.add_widget(dice_input)
            heal_btn = Button(text="Heilen")
            content.add_widget(heal_btn)
            popup = create_styled_popup(title="Kleine Rast", content=content, size_hint=(0.8, 0.5))
            def heal_action(instance, p):
                try:
                    dice_to_spend = int(dice_input.text)
                    if 0 < dice_to_spend <= self.character.hit_dice:
                        healed_amount = self.character.short_rest(dice_to_spend)
                        self.update_sheet()
                        self.show_popup("Heilung", f"Du hast {healed_amount} HP wiederhergestellt.")
                        self.sync_character()
                        p.dismiss()
                    else:
                        self.show_popup("Fehler", "Ungültige Anzahl an Würfeln.")
                except ValueError:
                    self.show_popup("Fehler", "Bitte eine gültige Zahl eingeben.")
            heal_btn.bind(on_press=lambda x: heal_action(x, popup))
            apply_styles_to_widget(content)
            popup.open()
