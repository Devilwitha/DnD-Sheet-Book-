from kivy.metrics import dp
import json
import random
import os
import sqlite3
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from queue import Empty

from core.character import Character
import copy
from core.enemy import Enemy
from utils.formats import decode_map, encode_map, decode_session, encode_session
from utils.storage import read_json, atomic_write_json, safe_save_path
from core.game_manager import GameManager
from utils.helpers import apply_background, apply_styles_to_widget, create_styled_popup, get_user_saves_dir
from utils.non_ui_helpers import roll_dice
from utils.map_actions import reachable_tiles, action_reason, attack_result_text
from functools import partial
from utils.data_manager import ENEMY_DATA
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from ui.archive_controller import ArchiveController
from ui.character_authority import CharacterAuthority
from ui.character_approval import ask_dm, character_summary

class DMMainScreen(CharacterAuthority, ArchiveController, Screen):
    def add_offline_player_popup(self):
        # Popup für neuen Offline-Spieler mit AC, Angriffsbonus, Übungsbonus, Schaden
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        name_input = TextInput(hint_text="Name", multiline=False)
        ac_input = TextInput(hint_text="Rüstungsklasse (AC)", multiline=False, input_filter='int')
        attack_bonus_input = TextInput(hint_text="Angriffsbonus", multiline=False, input_filter='int')
        proficiency_input = TextInput(hint_text="Übungsbonus", multiline=False, input_filter='int')
        damage_input = TextInput(hint_text="Schaden (z.B. 2d4)", multiline=False)
        add_btn = Button(text="Hinzufügen")
        cancel_btn = Button(text="Abbrechen")
        btn_box = BoxLayout(orientation='horizontal', spacing=10)
        btn_box.add_widget(add_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(Label(text="Neuen Offline-Spieler anlegen:"))
        content.add_widget(name_input)
        content.add_widget(ac_input)
        content.add_widget(attack_bonus_input)
        content.add_widget(proficiency_input)
        content.add_widget(damage_input)
        content.add_widget(btn_box)
        popup = create_styled_popup(title="Offline-Spieler hinzufügen", content=content, size_hint=(0.5, 0.7))

        def on_add(instance):
            name = name_input.text.strip()
            try:
                ac = int(ac_input.text.strip())
            except Exception:
                ac = 10
            try:
                attack_bonus = int(attack_bonus_input.text.strip())
            except Exception:
                attack_bonus = 0
            try:
                proficiency = int(proficiency_input.text.strip())
            except Exception:
                proficiency = 2
            damage = damage_input.text.strip() or "1d8"
            if not name or self.game_manager.get_character_or_enemy_by_name(name):
                self.log_message("Name darf nicht leer sein!")
                return
            from utils.formats import validate_attacks
            try:
                attacks = validate_attacks([{'name': 'Angriff', 'damage': damage}])
                if not 0 <= ac <= 100 or not -100 <= attack_bonus <= 100 or not 0 <= proficiency <= 20:
                    raise ValueError('Werte außerhalb der erlaubten Grenzen')
            except ValueError:
                self.log_message('Ungültige Kampfwerte oder Würfelangabe.')
                return
            char = Character(name, race='', char_class='')
            char.hit_points = char.max_hit_points = 10
            char.armor_class = ac
            char.attack_bonus = attack_bonus
            char.proficiency = proficiency
            char.attacks = attacks
            if not hasattr(self.game_manager, 'offline_players'):
                self.game_manager.offline_players = []
            self.game_manager.offline_players.append(char)
            self.update_offline_players_list()
            popup.dismiss()

        add_btn.bind(on_press=on_add)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()
    def update_offline_players_list(self):
        offline_players_widget = self.ids.offline_players_list
        offline_players_widget.clear_widgets()
        for char in self.game_manager.offline_players:
            box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48))
            label = Label(text=char.name, size_hint_x=0.7)
            remove_btn = Button(text="Entfernen", size_hint_x=0.3, size_hint_y=None, height=dp(48))
            def make_remove_callback(c):
                return lambda instance: self.remove_offline_player(c)
            remove_btn.bind(on_press=make_remove_callback(char))
            box.add_widget(label)
            box.add_widget(remove_btn)
            offline_players_widget.add_widget(box)

    def remove_offline_player(self, char):
        if char in self.game_manager.offline_players:
            self.game_manager.offline_players.remove(char)
            self.update_offline_players_list()
    """The main screen for the Dungeon Master to manage the game."""
    def __init__(self, **kwargs):
        super(DMMainScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.network_manager = self.app.network_manager
        self.game_manager = GameManager(logger_func=self.log_message)
        self.update_event = None
        self.selected_object = None
        self.highlighted_tiles = []
        self._map_widget_bound = False
        self.dm_selected_attacker = None  # Stores attacker name (player or enemy)
        self.session_roster = {}
        self.session_metadata = {}
        self._log_times = {}
        self.action_mode = 'inspect'
        self._map_feedback = ''
        self._selector_updating = False
        self.init_archive()

    def on_pre_enter(self, *args):
        apply_background(self)
        apply_styles_to_widget(self)

    def on_enter(self, *args):
        already_active = bool(getattr(self.app, 'dm_session_active', False))
        self.app.dm_session_active = True
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None
        if getattr(self, '_resume_from_sheet', False) or (already_active and not self.app.edited_map_data
                and not self.app.loaded_session_data and not getattr(self.app, 'prepared_session_data', None)):
            # Returning from the shared CharacterSheet: resume only. No GAME_START, no state/map reload.
            self._resume_from_sheet = False
            self.app.source_screen = None
            self.sync_online_players()
            self.update_ui()
            self.broadcast_game_state()
            self.update_event = Clock.schedule_interval(self.check_for_updates, 0.2)
            return

        self.sync_online_players()
        if not self._map_widget_bound:
            self.ids.dm_map_grid.bind(on_tile_click=self.handle_tile_click)
            self._map_widget_bound = True

        if self.app.edited_map_data:
            try:
                self.ensure_journal()
            except (OSError, ValueError, sqlite3.Error) as exc:
                self.archive_failed(exc)
            try:
                self.game_manager.map_data = GameManager.normalize_map(self.app.edited_map_data)
                self.register_map_figures()
            except Exception as e:
                self.log_message(f'Karte konnte nicht geladen werden: {e}')
            self.app.edited_map_data = None
            self.log_message('Zuletzt bearbeitete Karte geladen.')
            self.update_map_widget()
            self.broadcast_map_data()
        else:
            with self.network_manager.lock:
                ready = [addr for addr, c in self.network_manager.clients.items() if c.get('approved', True)]
            for addr in ready:
                self.network_manager.send_message(addr, 'GAME_START', 'Das Spiel beginnt!')
            self.load_state_from_manager()

        self.update_ui()
        self.broadcast_map_data()
        self.broadcast_game_state()
        self.update_event = Clock.schedule_interval(self.check_for_updates, 0.2)
        self.checkpoint_archive()

    def on_leave(self, *args):
        if getattr(self.app, 'dm_session_active', False) and self.network_manager.mode == 'dm':
            return
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None

    def load_state_from_manager(self):
        session = None
        if self.app.loaded_session_data:
            session = self.app.loaded_session_data
            self.app.loaded_session_data = None
        elif hasattr(self.app, 'prepared_session_data') and self.app.prepared_session_data:
            session = self.app.prepared_session_data
            self.app.prepared_session_data = None

        if not session:
            try:
                self.ensure_journal()
            except (OSError, ValueError, sqlite3.Error) as exc:
                self.archive_failed(exc)
            return
        try:
            session = decode_session(session)
            if self.archive_id and session.get('archive_id') != self.archive_id:
                self.checkpoint_archive('Vor Sitzungswechsel', strict=True)
                self.detach_journal()
            self.ensure_journal(session)
            self.game_manager.apply_session(session)
            self.session_roster = {p['character_id']: p for p in session.get('online_players', [])}
            self.session_metadata = {k: session[k] for k in ('notes', 'summary') if k in session}
            self.sync_online_players()
        except Exception as e:
            create_styled_popup(title='Ladefehler', content=Label(text=f'Sitzung ungueltig:\n{e}'), size_hint=(0.7, 0.5)).open()
            self.ids.log_output.text = 'Neue Sitzung gestartet.\n'
            return

        md = self.game_manager.map_data
        self.register_map_figures()
        if session.get('type') == 'prepared' and not self.game_manager.enemies and md and isinstance(md.get('enemies'), list):
            for n in md['enemies']:
                st = ENEMY_DATA.get(str(n).split('#')[0].strip())
                if st:
                    self.game_manager.enemies.append(Enemy(name=str(n), hp=st['hp'], armor_class=st.get('ac', 10), attacks=st['attacks']))

        log = session.get('log')
        if not isinstance(log, str) or not log:
            logs = session.get('logs')
            log = '\n'.join(str(x) for x in logs) if isinstance(logs, list) else ''
        if not log:
            log = 'Neue Sitzung gestartet.\n'
        if not log.endswith('\n'):
            log += '\n'
        if session.get('type') == 'prepared':
            log += f"Notizen: {session.get('notes', '')}\n"
        self.ids.log_output.text = log

    def check_for_updates(self, dt):
        for _ in range(64):
            try:
                item = self.network_manager.incoming_messages.get_nowait()
            except Empty:
                break
            try:
                self._handle_network_item(item)
            except Exception as e:
                from utils.diagnostics import record_error
                record_error('dm_message', e)
                self.log_message('Eine ungültige Netzwerknachricht wurde verworfen.')

    def get_character_or_enemy_by_name(self, name):
        return self.game_manager.get_character_or_enemy_by_name(name)

    def handle_character_death(self, character_name):
        # This method is now fully handled by the game manager
        # The UI update and broadcast calls will happen in the calling method
        outcome = self.game_manager.handle_character_death(character_name)
        if outcome == "VICTORY":
             self.network_manager.broadcast_message("VICTORY", "Alle Feinde wurden besiegt!")
        self.update_ui()
        self.broadcast_map_data()
        self.broadcast_game_state()

    def handle_player_attack(self, player_name, payload):
        # This is now handled in check_for_updates
        pass

    def handle_interaction(self, player_name, pos, *, dm_override=False):
        md = self.game_manager.map_data
        if not dm_override and self.game_manager.get_current_turn_info()['name'] != player_name:
            return False, 'Diese Figur ist gerade nicht am Zug.'
        if not md or pos not in md.get('tiles', {}):
            return False, 'Ungültiges Zielfeld.'
        actor_pos = self.game_manager.find_object_pos(player_name)
        if actor_pos is None:
            return False, 'Die ausgewählte Figur ist nicht auf dieser Karte platziert.'
        if not dm_override and max(abs(actor_pos[0] - pos[0]), abs(actor_pos[1] - pos[1])) > 1:
            return False, 'Der Gegenstand ist zu weit entfernt.'
        tile = md['tiles'][pos]
        furniture = tile.get('furniture')
        if not furniture:
            return False, 'Auf diesem Feld liegt kein Gegenstand.'
        furn_type = furniture['type']
        if furniture.get('is_mimic'):
            self.log_message(f'MIMIC! Die {furn_type} bei {pos} entpuppt sich als Mimic, als {player_name} interagiert!')
            tile['furniture'] = None
            mimic_data = ENEMY_DATA.get('Mimic', {'hp': 30, 'ac': 12, 'attacks': [{'name': 'Biss', 'damage': '1d8+3'}]})
            count = 1
            for enemy in self.game_manager.enemies:
                if enemy.name.startswith('Mimic'):
                    try:
                        num = int(enemy.name.split('#')[-1])
                        if num >= count:
                            count = num + 1
                    except (ValueError, IndexError):
                        continue
            new_enemy = Enemy(name=f'Mimic #{count}', hp=mimic_data['hp'], armor_class=mimic_data['ac'], attacks=mimic_data['attacks'])
            self.game_manager.enemies.append(new_enemy)
            self.game_manager.add_to_running_initiative(new_enemy)
            tile['object'] = new_enemy.name
            self.update_ui()
            self.broadcast_map_data()
        else:
            self.log_message(f'{player_name} interagiert mit {furn_type} bei {pos}.')
        return True, f'{player_name} interagiert mit {furn_type}.'

    def update_ui(self):
        self.update_map_view()
        self.update_online_players_list()
        self.update_offline_players_list()
        self.update_enemies_list_ui()
        self.update_initiative_ui()
        if self.game_manager.map_data:
            self.update_objects_list_ui()

    def update_map_view(self):
        # Selection changes must not rebuild unrelated lists and their pressed buttons.
        self.update_map_controls()
        self.update_map_widget()

    def update_map_widget(self):
        if 'dm_map_grid' in self.ids:
            current_turn_info = self.game_manager.get_current_turn_info()
            map_widget = self.ids.dm_map_grid
            map_widget.set_data(
                map_data=self.game_manager.map_data,
                highlighted_tiles=self.highlighted_tiles,
                current_turn_pos=current_turn_info['pos'],
                selected_pos=self.game_manager.find_object_pos(self.dm_selected_attacker)
            )

    def log_message(self, message, actor=None):
        self.journal_message(message, actor)
        # A check to prevent errors during __init__
        if hasattr(self, 'ids') and self.ids.get('log_output'):
            from datetime import datetime
            self.ids.log_output.text = (self.ids.log_output.text + f"[{datetime.now():%H:%M:%S}] {message}\n")[-64000:]
        else:
            print(f"LOG: {message}")

    def roll_initiative_for_all(self):
        self.sync_online_players()
        players = (list(self.game_manager.online_players.values()) + list(self.game_manager.disconnected_players.values())
                   + list(self.game_manager.offline_players))
        order = self.game_manager.roll_initiative_for_all(players=players)
        self.log_message('Initiativereihenfolge:\n' + '\n'.join(f'{roll}: {name}' for roll, name in order))
        self.update_ui()
        self.broadcast_game_state()

    def end_turn(self):
        self.game_manager.end_turn()
        self.selected_object = None
        self.dm_selected_attacker = None
        self.action_mode = 'inspect'
        self._map_feedback = ''
        self.update_ui()
        self.broadcast_game_state()

    def start_next_turn(self):
        # This is now handled internally by game_manager on roll_initiative and end_turn
        pass

    def broadcast_game_state(self):
        current_turn_info = self.game_manager.get_current_turn_info()
        state = {
            'players': list(self.game_manager.online_players.keys()),
            'initiative': self.game_manager.initiative_order,
            'current_turn': current_turn_info['name'],
            'current_turn_pos': current_turn_info['pos'],
            'turn_action_state': dict(current_turn_info['state'])
        }
        self.network_manager.broadcast_message("GAME_STATE_UPDATE", state)
        with self.network_manager.lock:
            clients = list(self.network_manager.clients.items())
        for addr, info in clients:
            if not info.get('approved', True):
                continue
            char = self.game_manager.get_character_or_enemy_by_name(info['character'].name)
            if isinstance(char, Character) and char.character_id == info['character'].character_id:
                self.network_manager.send_message(addr, 'SYNC_CHARACTER', char.to_dict())

    def update_initiative_ui(self):
        initiative_list_widget = self.ids.initiative_list
        initiative_list_widget.clear_widgets()
        current_turn_name = self.game_manager.get_current_turn_info()['name']

        for i, (roll, name) in enumerate(self.game_manager.initiative_order):
            text = f"{roll}: {name}"
            label = Label(text=text, size_hint_y=None, height=dp(48))
            if name == current_turn_name:
                label.color = (0.2, 1, 0.2, 1)
                label.bold = True
            initiative_list_widget.add_widget(label)
        self.ids.current_turn_label.text = f"Am Zug: {current_turn_name or 'Niemand'}"

    def create_enemy_instance(self, name, data, instance):
        count = 1
        for enemy in self.game_manager.enemies:
            if enemy.name.startswith(name):
                try:
                    num = int(enemy.name.split('#')[-1])
                    if num >= count: count = num + 1
                except (ValueError, IndexError): continue
        unique_name = f"{name} #{count}"
        while self.game_manager.get_character_or_enemy_by_name(unique_name):
            count += 1
            unique_name = f"{name} #{count}"

        new_enemy = Enemy(name=unique_name, hp=data['hp'], armor_class=data['ac'], attacks=data['attacks'])
        self.game_manager.enemies.append(new_enemy)
        self.game_manager.add_to_running_initiative(new_enemy)
        self.update_enemies_list_ui()
        self.broadcast_game_state()
        self.log_message(f"Gegner '{unique_name}' hinzugefügt.")
        if hasattr(self, 'enemy_popup'): self.enemy_popup.dismiss()

    def show_enemy_stats(self, enemy, instance):
        content = BoxLayout(orientation='vertical', spacing=5, padding=10)
        content.add_widget(Label(text=f"Name: {enemy.name}"))
        content.add_widget(Label(text=f"HP: {enemy.hp}"))
        content.add_widget(Label(text=f"AC: {enemy.armor_class}"))
        attacks_str = ", ".join([f"{a['name']} ({a['damage']})" for a in enemy.attacks])
        content.add_widget(Label(text=f"Angriffe: {attacks_str}"))
        create_styled_popup(title="Gegner-Statistiken", content=content, size_hint=(0.6, 0.5)).open()

    def do_load_map(self, filename, instance):
        try:
            path = safe_save_path(get_user_saves_dir('maps'), filename)
            loaded = decode_map(read_json(path))
            enemies = None
            names = loaded.get('enemies')
            if isinstance(names, list):
                enemies = []
                for n in names:
                    if isinstance(n, dict):
                        enemies.append(Enemy.from_dict(n))
                        continue
                    st = ENEMY_DATA.get(str(n).split('#')[0].strip())
                    if st:
                        enemies.append(Enemy(name=str(n), hp=st['hp'], armor_class=st.get('ac', 10), attacks=st['attacks']))
            offline = None
            if 'offline_players' in loaded:
                offline = [Character.from_dict(p) for p in loaded['offline_players'] if isinstance(p, dict)]
        except Exception as e:
            create_styled_popup(title='Load Error', content=Label(text=f'Error loading map:\n{e}'), size_hint=(0.7, 0.5)).open()
            return
        self.game_manager.map_data = loaded
        if enemies is not None:
            self.game_manager.enemies = enemies
        self.register_map_figures()
        self.log_message(f"Map '{filename}' geladen.")
        self.update_ui()
        self.broadcast_map_data()
        self.broadcast_game_state()
        if hasattr(self, 'load_map_popup_widget'):
            self.load_map_popup_widget.dismiss()

    def broadcast_map_data(self):
        md = self.game_manager.map_data
        if not md:
            return
        player_map = {
            'rows': md.get('rows'),
            'cols': md.get('cols'),
            'enemies': md.get('enemies', []),
            'tiles': copy.deepcopy(md.get('tiles', {})),
        }
        if md.get('artwork'):
            from utils.map_document import public_artwork
            player_map['artwork'] = public_artwork(md['artwork'])
        if md.get('region_context'):
            from utils.map_region_context import public_context
            player_map['region_context'] = public_context(md['region_context'], md['rows'], md['cols'])
        if md.get('cartography_scale'):
            player_map['cartography_scale'] = copy.deepcopy(md['cartography_scale'])
        for tile in player_map['tiles'].values():
            furn = tile.get('furniture')
            if isinstance(furn, dict):
                furn.pop('is_mimic', None)
            if tile.get('type') == 'Trigger':
                tile['type'] = 'Floor'
                tile.pop('trigger_message', None)
        self.network_manager.broadcast_message('MAP_DATA', encode_map(player_map))

    def register_map_figures(self):
        gm = self.game_manager
        md = gm.map_data or {}
        # Map-editor returns and loaded maps must use the same character data as the session.
        for raw in md.get('offline_players', []):
            char = raw if isinstance(raw, Character) else Character.from_dict(raw)
            if not gm.get_character_or_enemy_by_name(char.name):
                gm.offline_players.append(char)
        for raw in md.get('online_players', []):
            char = raw if isinstance(raw, Character) else Character.from_dict(raw)
            if not gm.get_character_or_enemy_by_name(char.name):
                gm.disconnected_players[char.name] = char
        definitions = {e['name']: e for e in md.get('enemies', []) if isinstance(e, dict)}
        for tile in md.get('tiles', {}).values():
            name = tile.get('object')
            if not name or gm.get_character_or_enemy_by_name(name):
                continue
            data = definitions.get(name) or ENEMY_DATA.get(name.split('#')[0].strip())
            if data:
                enemy = Enemy.from_dict(dict(data, name=name))
                gm.enemies.append(enemy)
                gm.add_to_running_initiative(enemy)

    def update_map_controls(self):
        if 'actor_selector' not in self.ids:
            return
        gm = self.game_manager
        names = list(dict.fromkeys(
            [p.name for p in gm.online_players.values()] + list(gm.disconnected_players)
            + [p.name for p in gm.offline_players] + [e.name for e in gm.enemies]
            + [t['object'] for t in (gm.map_data or {}).get('tiles', {}).values() if t.get('object')]))
        current = gm.get_current_turn_info()['name']
        if self.dm_selected_attacker not in names:
            placed = [n for n in names if gm.find_object_pos(n) is not None]
            self.dm_selected_attacker = current if current in placed else (placed[0] if placed else (names[0] if names else None))
        name = self.dm_selected_attacker
        self._selector_updating = True
        self.ids.actor_selector.values = names
        self.ids.actor_selector.text = name or 'Figur wählen'
        self._selector_updating = False
        position = gm.find_object_pos(name) if name else None
        active = bool(name and position is not None)
        self.ids.dm_move_button.disabled = not active
        self.ids.dm_attack_button.disabled = not active or gm.get_character_or_enemy_by_name(name) is None
        self.ids.dm_interact_button.disabled = not active
        self.ids.dm_place_button.disabled = not name or not gm.map_data
        self.ids.dm_end_turn_button.disabled = not current
        self.ids.dm_map_status.text = f"Ausgewählt: {name or 'keine Figur'} (blau)\n" + (
            f"Spielerzug: {current} · DM darf jederzeit handeln" if current else 'Freies Spiel · DM darf jederzeit handeln')
        hint = {'inspect': 'Figur antippen, dann bewegen. Blau: Auswahl. Grün: Spielerzug.',
                'move': 'DM-Bewegung: freies gelbes Zielfeld antippen. Andere Figur = neue Auswahl.',
                'attack': 'DM-Angriff: Zielfigur antippen. Spieleraktionen werden nicht verbraucht.',
                'place': 'Ein freies Feld antippen. Die ausgewählte Figur wird dort platziert.',
                'interact': 'DM-Interaktion: Gegenstand antippen; Entfernung spielt keine Rolle.'}[self.action_mode]
        if name and position is None and self.action_mode != 'place':
            hint = f'{name} fehlt auf der Karte. Mit Platzieren ein freies Feld wählen.'
        elif name and gm.get_character_or_enemy_by_name(name) is None:
            hint = f'{name}: Nur Kartenfigur, keine Kampfwerte. Bewegen und Interagieren sind möglich.'
        self.ids.dm_map_hint.text = self._map_feedback or hint
        for ident, mode in (('dm_move_button', 'move'), ('dm_attack_button', 'attack'), ('dm_place_button', 'place'), ('dm_interact_button', 'interact')):
            self.ids[ident].background_color = (0.25, 0.65, 1, 1) if mode == self.action_mode else (1, 1, 1, 1)
        self.highlighted_tiles = [pos for pos, tile in (gm.map_data or {}).get('tiles', {}).items()
                                  if tile.get('type') != 'Wall' and not tile.get('object') and not tile.get('furniture')
                                  ] if self.action_mode in ('move', 'place') and name else []

    def select_map_actor(self, name):
        if getattr(self, '_selector_updating', True):
            return
        if not self.game_manager.get_character_or_enemy_by_name(name) and self.game_manager.find_object_pos(name) is None:
            return
        self.dm_selected_attacker = name
        self.action_mode = 'move' if self.game_manager.find_object_pos(name) is not None else 'place'
        self._map_feedback = ''
        self.update_map_view()

    def select_map_action(self, mode):
        self.action_mode = mode
        self._map_feedback = ''
        self.update_map_view()

    def map_feedback(self, message):
        self._map_feedback = action_reason(message)
        self.log_message(self._map_feedback)
        self.update_map_view()

    def handle_tile_click(self, instance, touch, row, col):
        if getattr(touch, 'is_mouse_scrolling', False):
            return
        if getattr(touch, 'button', 'left') == 'right':
            self.handle_right_click(row, col)
        else:
            self.handle_left_click(row, col)

    def handle_left_click(self, row, col):
        tile = (self.game_manager.map_data or {}).get('tiles', {}).get((row, col))
        if not tile:
            return
        name = self.dm_selected_attacker
        if tile.get('object') and self.action_mode in ('inspect', 'move', 'place'):
            self.select_map_actor(tile['object'])
        elif self.action_mode == 'place' and name:
            success, message = self.game_manager.place_object(name, (row, col))
            self.map_feedback(message)
            if success:
                self.action_mode = 'inspect'
                self.broadcast_map_data()
                self.broadcast_game_state()
                self.update_ui()
        elif self.action_mode == 'move' and name:
            self.move_object(name, (row, col))
        elif self.action_mode == 'attack' and name:
            self.handle_right_click(row, col)
        elif self.action_mode == 'interact' and name:
            success, message = self.handle_interaction(name, (row, col), dm_override=True)
            self.map_feedback(message)
            self.broadcast_game_state()
        elif tile.get('object'):
            self.select_map_actor(tile['object'])
        else:
            self.map_feedback('Zuerst eine Figur und eine Aktion wählen.')

    def handle_right_click(self, row, col):
        target = (self.game_manager.map_data or {}).get('tiles', {}).get((row, col), {}).get('object')
        if not self.dm_selected_attacker or not target:
            self.map_feedback('Zuerst eine Figur wählen, dann eine Zielfigur antippen.')
            return
        self.dm_attack(self.dm_selected_attacker, target)

    def dm_attack(self, attacker_name, target_name):
        attacker = self.game_manager.get_character_or_enemy_by_name(attacker_name)
        if isinstance(attacker, Enemy) and len(attacker.attacks) > 1:
            content = BoxLayout(orientation='vertical', spacing=dp(8))
            popup = create_styled_popup(title='Angriff wählen', content=content, size_hint=(0.85, 0.7))
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
            grid.bind(minimum_height=grid.setter('height'))
            for attack in attacker.attacks:
                button = Button(text=f"{attack['name']} ({attack.get('damage', '')})", size_hint_y=None, height=dp(48))
                def choose(instance, attack=attack):
                    popup.dismiss()
                    self._execute_dm_attack(attacker, target_name, attack)
                button.bind(on_release=choose)
                grid.add_widget(button)
            scroll.add_widget(grid)
            content.add_widget(scroll)
            popup.open()
        elif attacker:
            self._execute_dm_attack(attacker, target_name, None)
        else:
            self.map_feedback('Angreifer nicht vorhanden.')

    def _execute_dm_attack(self, attacker, target_name, attack):
        result = self.game_manager.handle_attack(attacker.name, target_name, attack_name=(attack or {}).get('name'), dm_override=True)
        self.log_message(f'DM-Angriff: {attacker.name} → {target_name}.')
        self.map_feedback(attack_result_text(attacker.name, target_name, result))
        if result.get('success'):
            self.update_ui()
            self.broadcast_map_data()
            self.broadcast_game_state()

    def highlight_movement_range(self, obj_name, r_start, c_start):
        self.highlighted_tiles = list(reachable_tiles(self.game_manager.map_data, (r_start, c_start),
                                                       self.game_manager.turn_action_state.get('movement_left', 0)))

    def move_object(self, obj_name, to_pos):
        success, reason = self.game_manager.move_object(obj_name, to_pos, dm_override=True)
        self.map_feedback(f'{obj_name} wurde bewegt.' if success else reason)
        if success:
            self.broadcast_map_data()
            self.check_for_trigger(obj_name, to_pos)
            self.broadcast_game_state()

    def show_join_qr(self):
        from ui.join_dialog import show_join_dialog
        show_join_dialog(self.network_manager)

    def confirm_end_session(self):
        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        label = Label(text='Die Verbindung zu allen Spielern wird getrennt.\nJournal und aktueller Spielstand werden vorher archiviert.', text_size=(dp(330), None), halign='center')
        content.add_widget(label)
        popup = create_styled_popup(title='Ganze Sitzung beenden?', content=content, size_hint=(0.9, 0.55))
        cancel = Button(text='Zurück zur Sitzung', size_hint_y=None, height=dp(48))
        cancel.bind(on_release=popup.dismiss)
        content.add_widget(cancel)
        finish = Button(text='Sitzung beenden und trennen', size_hint_y=None, height=dp(48))
        def end(*args):
            finished_sid = self.archive_id
            try:
                self.close_journal()
            except (OSError, ValueError, sqlite3.Error):
                label.text = 'Archivieren fehlgeschlagen. Die Sitzung bleibt geöffnet.\nBitte Speicherplatz prüfen und erneut versuchen.'
                return  # Keep the session open if archiving fails.
            popup.dismiss()
            self.app.dm_session_active = False
            self.network_manager.stop_server()
            self.game_manager = GameManager(logger_func=self.log_message)
            self.session_roster = {}
            self.session_metadata = {}
            self.dm_selected_attacker = None
            self.action_mode = 'inspect'
            self.app.change_screen('dm_spiel')
            if finished_sid:
                from ui.session_archive_dialog import ArchiveBrowser
                browser = ArchiveBrowser(self.app)
                browser.detail(finished_sid)
                browser.open()
        finish.bind(on_release=end)
        content.add_widget(finish)
        popup.open()

    def update_online_players_list(self):
        online_players_widget = self.ids.online_players_list
        online_players_widget.clear_widgets()
        def get_name(p):
            return p.name if hasattr(p, 'name') else str(p)
        for char in sorted(list(self.game_manager.online_players.values()) + list(self.game_manager.disconnected_players.values()), key=get_name):
            if hasattr(char, 'name'):
                text = f"{char.name}  {char.hit_points}/{char.max_hit_points} HP"
                if char.name in self.game_manager.disconnected_players:
                    text += ' · getrennt (DM steuerbar)'
                btn = Button(text=text, size_hint_y=None, height=dp(48))
                btn.bind(on_press=partial(self.open_character_sheet, char.name))
                apply_styles_to_widget(btn)
                online_players_widget.add_widget(btn)
            else:
                online_players_widget.add_widget(Label(text=get_name(char), size_hint_y=None, height=dp(48)))

    def update_offline_players_list(self):
        offline_players_widget = self.ids.offline_players_list
        offline_players_widget.clear_widgets()
        def get_name(p):
            return p.name if hasattr(p, 'name') else str(p)
        for player in sorted(self.game_manager.offline_players, key=get_name):
            name = get_name(player)
            player_entry = BoxLayout(size_hint_y=None, height=dp(48), spacing=5)
            label = Label(text=name)
            remove_button = Button(text="Entfernen", size_hint_x=0.4)
            remove_button.bind(on_press=partial(self.remove_offline_player, player))
            player_entry.add_widget(label)
            player_entry.add_widget(remove_button)
            offline_players_widget.add_widget(player_entry)

    def remove_offline_player(self, player, instance=None):
        if player in self.game_manager.offline_players:
            self.game_manager.offline_players.remove(player)
            self.update_offline_players_list()
            name = player.name if hasattr(player, 'name') else str(player)
            self.log_message(f"Offline-Spieler '{name}' entfernt.")

    def add_offline_player(self):
        self.add_offline_player_popup()

    def add_enemy(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        for name, data in sorted(ENEMY_DATA.items()):
            btn = Button(text=name, size_hint_y=None, height=dp(48))
            btn.bind(on_press=partial(self.create_enemy_instance, name, data))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.enemy_popup = create_styled_popup(title="Gegner hinzufügen", content=content, size_hint=(0.8, 0.8))
        self.enemy_popup.open()

    def save_session(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        text_input = TextInput(hint_text='Name dieser Spielstand-Version', multiline=False)
        content.add_widget(text_input)
        save_button = Button(text='Speichern')
        popup = create_styled_popup(title='Sitzung speichern', content=content, size_hint=(0.7, 0.4))

        def show_err(msg):
            create_styled_popup(title='Speicherfehler', content=Label(text=msg), size_hint=(0.7, 0.5)).open()

        def do_save(instance):
            name = text_input.text.strip()
            if name.lower().endswith('.json'):
                name = name[:-5]
            bad = set('/:*?<>|') | {chr(92), chr(34)}
            if not name or len(name) > 80 or name in ('.', '..') or any(ch in bad for ch in name):
                show_err('Ungueltiger Sitzungsname.')
                return
            filename = f'{name}.json'
            try:
                self.save_named_snapshot(name)
            except Exception as e:
                show_err(f'Fehler:\n{e}')
                return
            popup.dismiss()

        save_button.bind(on_press=do_save)
        content.add_widget(save_button)
        popup.open()

    def load_map_popup(self):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        maps_dir = get_user_saves_dir("maps")
        map_files = [f for f in os.listdir(maps_dir) if f.endswith('.json')]
        if not map_files:
            create_styled_popup(title="Keine Karten", content=Label(text="Keine Karten zum Laden gefunden."), size_hint=(0.6, 0.4)).open()
            return
        for filename in sorted(map_files):
            btn = Button(text=self.map_display_name(filename), size_hint_y=None, height=dp(48))
            btn.bind(on_press=partial(self.do_load_map, filename))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.load_map_popup_widget = create_styled_popup(title="Karte laden", content=content, size_hint=(0.8, 0.8))
        self.load_map_popup_widget.open()

    def update_enemies_list_ui(self):
        enemy_list_widget = self.ids.enemies_list
        enemy_list_widget.clear_widgets()
        for enemy in self.game_manager.enemies:
            enemy_entry = BoxLayout(size_hint_y=None, height=dp(48))
            name_button = Button(text=enemy.name)
            name_button.bind(on_press=partial(self.show_enemy_stats, enemy))
            remove_button = Button(text="Entfernen", size_hint_x=0.3, on_press=partial(self.remove_enemy, enemy))
            enemy_entry.add_widget(name_button)
            enemy_entry.add_widget(remove_button)
            enemy_list_widget.add_widget(enemy_entry)

    def remove_enemy(self, enemy, instance):
        if enemy in self.game_manager.enemies:
            self.game_manager.handle_character_death(enemy.name)
            self.update_ui()
            self.broadcast_map_data()
            self.broadcast_game_state()
            self.log_message(f"Gegner '{enemy.name}' entfernt.")

    def update_objects_list_ui(self):
        objects_list_widget = self.ids.objects_list
        objects_list_widget.clear_widgets()
        if not self.game_manager.map_data or not self.game_manager.map_data.get('tiles'):
            return
        for pos, tile_data in self.game_manager.map_data['tiles'].items():
            if tile_data.get('furniture'):
                furn = tile_data['furniture']
                furn_type = furn['type']
                is_mimic = furn.get('is_mimic', False)
                text = f"{furn_type} at {pos}"
                if is_mimic:
                    text += " (Mimic!)"
                label = Label(text=text, size_hint_y=None, height=dp(48))
                if is_mimic:
                    label.color = (1, 0.5, 1, 1)
                objects_list_widget.add_widget(label)

    def check_for_trigger(self, obj_name, pos):
        if not self.game_manager.map_data: return
        tile = self.game_manager.map_data['tiles'].get(pos)
        if not tile or tile.get('type') != 'Trigger':
            return
        message = tile.get('trigger_message')
        if not message:
            return

        player_char = self.game_manager.get_character_or_enemy_by_name(obj_name)
        if player_char and isinstance(player_char, Character):
            player_addr = self.network_manager.get_client_addr_by_name(obj_name)
            if player_addr:
                self.log_message(f"Trigger ausgelöst bei {pos} von {obj_name}. Sende Nachricht.")
                self.network_manager.send_message(player_addr, "TRIGGER_MESSAGE", {'message': message})

    def _editor_callback(self, instance, map_data=None):
        gm = getattr(self.app, 'game_manager', None)
        if gm is not None:
            gm.offline_players = list(getattr(self.game_manager, 'offline_players', []))
            gm.online_players = dict(getattr(self.game_manager, 'online_players', {}))
            gm.disconnected_players = dict(self.game_manager.disconnected_players)
        editor_screen = self.manager.get_screen('map_editor')
        data = map_data if isinstance(map_data, dict) else self.game_manager.map_data
        if editor_screen.begin_edit('session', data):
            self.app.change_screen('map_editor')

    def create_new_map(self):
        self._editor_callback(None, map_data=None)

    def edit_existing_map(self):
        self.select_map_to_edit_popup(self._editor_callback)

    def select_map_to_edit_popup(self, callback):
        content = BoxLayout(orientation='vertical', spacing=10)
        scroll_content = GridLayout(cols=1, spacing=10, size_hint_y=None)
        scroll_content.bind(minimum_height=scroll_content.setter('height'))
        saves_dir = get_user_saves_dir("maps")
        map_files = [f for f in os.listdir(saves_dir) if f.endswith('.json')]
        if not map_files:
            create_styled_popup(title="No Maps", content=Label(text="No saved maps found to edit."), size_hint=(0.6, 0.4)).open()
            return
        for filename in map_files:
            btn = Button(text=self.map_display_name(filename), size_hint_y=None, height=dp(48))
            btn.bind(on_press=lambda x, f=filename: self.load_and_pass_map_to_editor(f, callback))
            scroll_content.add_widget(btn)
        scroll_view = ScrollView()
        scroll_view.add_widget(scroll_content)
        content.add_widget(scroll_view)
        self.edit_map_popup = create_styled_popup(title="Select Map to Edit", content=content, size_hint=(0.8, 0.8))
        self.edit_map_popup.open()

    @staticmethod
    def map_display_name(filename):
        try:
            data = read_json(safe_save_path(get_user_saves_dir('maps'), filename))
            name = data.get('editor_title') if isinstance(data, dict) else None
            return name if isinstance(name, str) and 0 < len(name) <= 80 else filename
        except (ValueError, OSError):
            return filename

    def load_and_pass_map_to_editor(self, filename, callback):
        try:
            path = safe_save_path(get_user_saves_dir('maps'), filename)
            loaded_data = decode_map(read_json(path))
        except Exception as e:
            create_styled_popup(title='Load Error', content=Label(text=f'Error loading map for editing:\n{e}'), size_hint=(0.7, 0.5)).open()
            return
        if hasattr(self, 'edit_map_popup'):
            self.edit_map_popup.dismiss()
        callback(None, map_data=loaded_data)
    def sync_online_players(self):
        try:
            with self.network_manager.lock:
                players = {}
                for c in self.network_manager.clients.values():
                    ch = c.get('character')
                    if ch is not None and c.get('approved', True):
                        players[ch.name] = ch
        except Exception:
            return
        gm = self.game_manager
        retained = {**gm.disconnected_players, **gm.online_players}
        connected_ids = {p.character_id for p in players.values()}
        for char in list(gm.offline_players):
            if char.character_id in connected_ids:
                retained[char.name] = char
                gm.offline_players.remove(char)
        for p in retained.values():
            self.session_roster[p.character_id] = p.to_dict()
        blocked = self._reserved_names()
        with self.network_manager.lock:
            clients = list(self.network_manager.clients.items())
        for addr, info in clients:
            if not info.get('approved', True):
                continue
            connected = info['character']
            saved = next((p for p in retained.values() if p.character_id == connected.character_id), None)
            same_name = retained.get(connected.name)
            if connected.name.casefold() in blocked or (same_name and same_name.character_id != connected.character_id):
                self.network_manager.kick_player(addr)
                players.pop(connected.name, None)
            elif saved:
                # Loading a saved session while clients are already connected must retain saved HP/items.
                players.pop(connected.name, None)
                players[saved.name] = saved
                with self.network_manager.lock:
                    if addr in self.network_manager.clients:
                        self.network_manager.clients[addr]['character'] = saved
        self.game_manager.online_players = players
        self.game_manager.disconnected_players = {name: p for name, p in retained.items()
                                                   if name not in players and name.casefold() not in blocked}
    def _reserved_names(self):
        return {p.name.casefold() for p in self.game_manager.offline_players + self.game_manager.enemies}

    def capture_state_snapshot(self):
        return self.game_manager.capture_snapshot()
    @staticmethod
    def _parse_pos(value):
        try:
            if isinstance(value, (str, bytes, dict)) or len(value) != 2:
                return None
            r, c = value
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (r, c)):
                return None
            return (r, c)
        except TypeError:
            return None
    def _handle_network_item(self, item):
        old_actor = getattr(self, '_journal_actor', None)
        try:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], tuple):
                with self.network_manager.lock:
                    client = self.network_manager.clients.get(item[0])
                    char = client.get('character') if client else None
                self._journal_actor = getattr(char, 'name', None)
            return self._process_network_item(item)
        finally:
            self._journal_actor = old_actor

    def _process_network_item(self, item):
        if not isinstance(item, tuple) or len(item) != 2:
            return
        source, message = item
        if source == 'PLAYER_JOINED':
            addr = message['addr']
            with self.network_manager.lock:
                client = self.network_manager.clients.get(addr)
                if client is None:
                    return
                char = client['character']
            if isinstance(char, dict):
                char = Character.from_dict(char)
            existing = self.game_manager.disconnected_players.get(char.name)
            if char.name.casefold() in self._reserved_names() or (existing and existing.character_id != char.character_id):
                self.network_manager.kick_player(message['addr'])
                return
            retained = next((p for p in self.game_manager.disconnected_players.values()
                             if p.character_id == char.character_id), None)
            saved = retained.to_dict() if retained else self.session_roster.get(char.character_id)
            if client.get('resumed') and client.get('approved'):
                active = next((p for p in self.game_manager.online_players.values()
                               if p.character_id == char.character_id), char)
                saved = (retained or active).to_dict()
            if saved:
                char = Character.from_dict(saved)
                with self.network_manager.lock:
                    if addr not in self.network_manager.clients:
                        return
                    self.network_manager.clients[addr]['character'] = char
                    self.network_manager.clients[addr]['approved'] = True
            elif not client.get('approved', True):
                if client.get('approval_shown'):
                    return
                client['approval_shown'] = True
                def accept():
                    with self.network_manager.lock:
                        if self.network_manager.clients.get(addr) is not client:
                            return
                        client['approved'] = True
                    self._process_network_item(('PLAYER_JOINED', {'addr': addr}))
                ask_dm('Neuen Charakter aufnehmen', character_summary(char), accept,
                       lambda: self.network_manager.kick_player(addr), 'Charakter übernehmen')
                return
            self.game_manager.online_players[char.name] = char
            self.session_roster[char.character_id] = copy.deepcopy(char.to_dict())
            self.game_manager.disconnected_players.pop(char.name, None)
            self.game_manager.add_to_running_initiative(char)
            self.network_manager.send_message(addr, 'CHAR_DATA', char.to_dict())
            self.network_manager.send_message(addr, 'GAME_START', 'Du trittst der laufenden Sitzung bei.')
            self.update_ui()
            self.broadcast_map_data()
            self.broadcast_game_state()
            self.log_message(f'{char.name} ist der laufenden Sitzung beigetreten.')
            return
        if source == 'PLAYER_LEFT':
            self.sync_online_players()
            self.update_ui()
            self.broadcast_game_state()
            return
        if not isinstance(message, dict):
            return

        with self.network_manager.lock:
            client = self.network_manager.clients.get(source)
            player_char = client.get('character') if client else None
        if player_char is None or not client.get('approved', True):
            return
        actor = player_char.name  # actor is always bound to the connection
        if actor.casefold() in self._reserved_names():
            self.network_manager.kick_player(source)
            return
        msg_type = message.get('type')
        payload = message.get('payload')
        if msg_type == 'LOG' and isinstance(payload, str):
            import time
            now = time.monotonic()
            if now - self._log_times.get(actor, 0) < 0.2:
                return
            self._log_times[actor] = now
            self.log_message(actor + ': ' + payload[:2000])
            return
        if not isinstance(payload, dict):
            payload = {}
        send = self.network_manager.send_message

        if msg_type in ('MOVE_OBJECT', 'PLAYER_ATTACK', 'END_TURN', 'INTERACT_WITH_OBJECT', 'INTERACT'):
            from collections import OrderedDict
            import re
            request_id = payload.get('request_id')
            if request_id is not None:
                if not isinstance(request_id, str) or re.fullmatch('[0-9a-f]{32}', request_id) is None:
                    send(source, 'ERROR', 'Ungültige Aktionskennung.')
                    return
                cache = client.setdefault('action_results', OrderedDict())
                if request_id in cache:
                    kind, reply = cache[request_id]
                    send(source, kind, reply)
                    return
                raw_send = send
                def send(address, kind, result):
                    if address == source and kind in ('ACTION_RESULT', 'ERROR'):
                        result = dict(result) if isinstance(result, dict) else {'message': str(result)}
                        result['request_id'] = request_id
                        cache[request_id] = (kind, result)
                        while len(cache) > 128:
                            cache.popitem(last=False)
                    return raw_send(address, kind, result)

        if msg_type == 'MOVE_OBJECT':
            name = payload.get('name')
            if name is not None and name != actor:
                send(source, 'ERROR', 'Du kannst nur deinen eigenen Charakter bewegen.')
                return
            pos = self._parse_pos(payload.get('to_pos'))
            if pos is None:
                send(source, 'ERROR', 'Ungueltige Zielposition.')
                return
            success, reason = self.game_manager.move_object(actor, pos)
            if success:
                self.update_ui()
                self.broadcast_map_data()
                self.check_for_trigger(actor, pos)
                self.broadcast_game_state()
                send(source, 'ACTION_RESULT', {'message': 'Bewegung ausgeführt.'})
            else:
                send(source, 'ERROR', action_reason(reason))

        elif msg_type == 'PLAYER_ATTACK':
            kwargs = {}
            if payload.get('type') == 'dice':
                die = payload.get('d20')
                if type(die) is not int or not 1 <= die <= 20:
                    send(source, 'ERROR', 'Bitte nur den W20-Wert von 1 bis 20 eingeben.')
                    return
                kwargs['natural_roll'] = die
                kwargs['damage_roll'] = payload.get('damage')
            if payload.get('type') == 'manual':
                kwargs['attack_roll'] = payload.get('attack_roll')
                kwargs['damage_roll'] = payload.get('damage')
            result = self.game_manager.handle_attack(
                attacker_name=actor,
                target_name=payload.get('enemy_name'),
                attack_name=payload.get('attack_name'),
                **kwargs
            )
            if result.get('success'):
                self.update_ui()
                self.broadcast_map_data()
                self.broadcast_game_state()
                send(source, 'ACTION_RESULT', {'message': attack_result_text(actor, payload.get('enemy_name'), result)})
                if result.get('combat_result') == 'VICTORY':
                    self.network_manager.broadcast_message('VICTORY', 'Alle Gegner wurden besiegt. Die Sitzung läuft weiter.')
            else:
                send(source, 'ERROR', action_reason(result.get('reason')))

        elif msg_type == 'END_TURN':
            if self.game_manager.get_current_turn_info()['name'] == actor:
                self.end_turn()
                send(source, 'ACTION_RESULT', {'message': 'Zug beendet. Die nächste Figur ist am Zug.'})
            else:
                send(source, 'ERROR', 'Du bist gerade nicht am Zug.')

        elif msg_type in ('INTERACT_WITH_OBJECT', 'INTERACT'):
            pos = self._parse_pos(payload.get('pos'))
            if pos is None:
                send(source, 'ERROR', 'Ungueltige Position.')
                return
            success, reason = self.handle_interaction(actor, pos)
            send(source, 'ACTION_RESULT' if success else 'ERROR', {'message': reason} if success else reason)
            self.broadcast_game_state()

        elif msg_type == 'CHARACTER_ACTION':
            self.handle_character_action(source, client, payload)
        elif msg_type == 'SET_CHARACTER_DATA':
            current = self.game_manager.online_players.get(actor)
            if current is not None:
                send(source, 'SYNC_CHARACTER', current.to_dict())
            send(source, 'ERROR', 'Es gilt der DM-Spielstand. Freie Charakteränderungen und Stufenaufstiege nimmt der DM vor. Bitte beide Geräte auf die aktuelle Version aktualisieren.')
    def open_character_sheet(self, name, instance=None):
        """Opens the shared CharacterSheet for an online player, using the authoritative network character."""
        nm = self.network_manager
        char = None
        with nm.lock:
            for c in nm.clients.values():
                ch = c.get('character')
                if ch is not None and ch.name == name:
                    char = ch
                    break
        if char is None:
            char = self.game_manager.get_character_or_enemy_by_name(name)
        if char is None:
            self.log_message('Spieler nicht mehr verbunden.')
            return
        self.app.source_screen = 'dm_main'
        self.manager.get_screen('sheet').load_character(char)
        self._resume_from_sheet = True
        self.manager.current = 'sheet'
