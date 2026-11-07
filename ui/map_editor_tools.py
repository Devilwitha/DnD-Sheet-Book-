"""Atlas navigation and editor controls; no network or external model services."""
import copy
import os
import re

from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView

from ui.map_canvas import EditorCanvas  # Register for KV.
from ui.map_editor_drawing import DrawingTools
from ui.map_editor_panel import EditorPanel
from ui.map_asset_tools import AssetAndRegionTools
from ui.map_cartography import CartographyTools
from utils.map_scale import KEY as SCALE_KEY, scale_title, suggested_scale, grid_for_scale
from utils.map_document import Atlas, LEVELS, LEVEL_LABELS, LAYER_NAMES, color_tuple, new_map, read_atlas
from utils.formats import decode_map, encode_map, validate_primitive
from utils.helpers import create_styled_popup, get_user_saves_dir
from utils.storage import atomic_write_json, read_json, safe_save_path
from utils.data_manager import ENEMY_DATA


class MapEditorTools(EditorPanel, AssetAndRegionTools, CartographyTools, DrawingTools):
    asset_id = StringProperty('BAU-003')
    asset_name = StringProperty('Weide')
    asset_size = NumericProperty(4)
    asset_rotation = NumericProperty(0)
    asset_remove_white = BooleanProperty(True)
    selected_is_asset = BooleanProperty(False)
    selected_is_label = BooleanProperty(False)
    asset_transform_title = StringProperty('4.0 Felder · 0°')
    asset_background_title = StringProperty('Weiß ausblenden: an')
    region_shape = StringProperty('Freihand-Grenze')
    region_feedback = StringProperty('')
    scale_title = StringProperty('Maßstab festlegen …')
    purpose = StringProperty('session')
    tool_title = StringProperty('Pinsel')
    inspector_open = BooleanProperty(False)
    tool = StringProperty('brush')
    color = StringProperty('#5f8148')
    brush_width = NumericProperty(1.5)
    layer = StringProperty('terrain')
    symbol = StringProperty('Baum')
    selected_id = StringProperty('')
    status = StringProperty('Pinsel: auf der Karte ziehen.')
    map_title = StringProperty('Neue Welt')
    level_title = StringProperty('Welt')
    layer_title = StringProperty('Gelände')
    layer_visible = BooleanProperty(True)
    layer_locked = BooleanProperty(False)
    grid_visible = BooleanProperty(False)
    dirty = BooleanProperty(False)
    can_undo = BooleanProperty(False)
    can_redo = BooleanProperty(False)

    def __init__(self, **kwargs):
        self.atlas = None
        self._undo, self._redo = [], []
        self._gesture = None
        self._region_draft = []
        self.selected_region_id = ''
        self._library_last_id = None
        self._editing = False
        self._preparation_party = {}
        super().__init__(**kwargs)
        self.asset_id, self.asset_name = 'BAU-003', 'Weide'
        self.asset_size, self.asset_rotation, self.asset_remove_white = 4, 0, True
        self.selected_is_asset = False
        self.region_shape = 'Freihand-Grenze'
        self.purpose = 'session'
        self.tool, self.color, self.brush_width = 'brush', '#5f8148', 1.5
        self.layer, self.symbol, self.selected_id = 'terrain', 'Baum', ''
        self.dirty = self.can_undo = self.can_redo = False

    def _atlas_folder(self):
        return 'map_library' if self.purpose == 'library' else 'atlases'

    def begin_edit(self, purpose, map_data=None):
        """Explicit entry context: never inherit a previously edited campaign."""
        if purpose not in ('library', 'preparation', 'session'):
            raise ValueError('Unbekannter Editor-Einstieg.')
        if self._editing and self.atlas and not self._persist():
            return False
        candidate = None
        if purpose == 'library' and self._library_last_id:
            try:
                candidate = read_atlas(safe_save_path(get_user_saves_dir('map_library'), self._library_last_id + '.json'))
            except (OSError, ValueError) as exc:
                self._error(f'Letzter Atlas konnte nicht geöffnet werden: {exc}')
                self._library_last_id = None
        self.purpose = purpose
        self.atlas = candidate
        self.preloaded_map_data = copy.deepcopy(map_data)
        self._preparation_party = {key: copy.deepcopy((map_data or {}).get(key, []))
                                   for key in ('offline_players', 'online_players')} if purpose == 'preparation' else {}
        self.app.edited_map_data = None
        self._undo.clear()
        self._redo.clear()
        self._gesture = None
        self.dirty = False
        self.status = ('Freie Kartenwerkstatt · Speichern legt Karten in deiner Bibliothek ab.'
                       if purpose == 'library' else 'Bibliothek: vorhandenen Atlas als eigene Arbeitskopie verwenden.')
        return True

    def populate_spinners(self):
        super().populate_spinners()
        if self.purpose != 'session':
            names = [p['name'] for p in self._preparation_party.get('offline_players', [])
                     if isinstance(p, dict) and isinstance(p.get('name'), str)]
            self.ids.player_spinner.values = ['None'] + sorted(set(names)) if self.purpose == 'preparation' else ['None']
        self.ids.player_spinner.text = 'None'
        self.ids.player_spinner.disabled = self.purpose == 'library'

    def map_with_characters(self):
        if self.purpose == 'session':
            return super().map_with_characters()
        data = copy.deepcopy(self.map_data)
        if self.purpose == 'preparation':
            data.update(copy.deepcopy(getattr(self, '_preparation_party', {})))
        return data

    def choose_tool_title(self, title):
        from ui.map_editor_panel import TOOLS
        key = next((key for key, label in TOOLS if label == title), None)
        if key and key != self.tool:
            if key == 'asset':
                self.open_asset_browser()
            else:
                self.set_tool(key)

    def show_settings(self):
        self.set_tool('settings')
        self.inspector_open = True

    def on_pre_enter(self, *args):
        self._editing = True
        self._build_controls()
        if self.preloaded_map_data:
            try:
                self.load_existing_map(self.preloaded_map_data)
                self.preloaded_map_data = None
            except (ValueError, OSError) as exc:
                self.preloaded_map_data = None
                self.atlas = None
                self._editing = False
                self.app.edited_map_data = None
                self._error(f'Karte konnte nicht geöffnet werden: {exc}')
                Clock.schedule_once(lambda _: self.app.go_back_screen(), 0)
                return
        if self.atlas is None:
            self.atlas = Atlas(new_map(50,50), name='Unbenannte Welt')
        self._activate()
        self.populate_spinners()

    def on_leave(self, *args):
        self._editing = False

    def _error(self, message):
        from kivy.core.window import Window
        self.status = str(message)
        box = BoxLayout(orientation='vertical',spacing=dp(10),padding=dp(10))
        scroll = ScrollView(do_scroll_x=False)
        label = Label(text=str(message),size_hint_y=None,halign='left',valign='top',font_size='14sp')
        label.bind(width=lambda w,v:setattr(w,'text_size',(v,None)),
                   texture_size=lambda w,v:setattr(w,'height',v[1]))
        scroll.add_widget(label);box.add_widget(scroll)
        close = Button(text='Schließen',size_hint_y=None,height=dp(44))
        box.add_widget(close)
        popup = create_styled_popup(title='Karteneditor',content=box,size_hint=(min(.94,dp(660)/max(1,Window.width)),None),height=dp(260))
        self._error_popup = popup
        popup.ids.update(dict(close=close))
        close.bind(on_release=lambda *_:popup.dismiss())
        popup.open()

    def _prompt(self, title, initial, callback):
        box = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(12))
        field = TextInput(text=initial, hint_text='Text eingeben', multiline=False,
                          size_hint_y=None, height=dp(48), padding=(dp(10), dp(12)))
        error = Label(text='', color=(1, .65, .5, 1), size_hint_y=None, height=dp(34), font_size='13sp')
        error.bind(size=lambda w, s: setattr(w, 'text_size', s))
        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        cancel, accept = Button(text='Abbrechen'), Button(text='Übernehmen')
        buttons.add_widget(cancel)
        buttons.add_widget(accept)
        box.add_widget(field)
        box.add_widget(error)
        box.add_widget(buttons)
        popup = create_styled_popup(title=title, content=box, size_hint=(.9, None), height=dp(250), auto_dismiss=False)
        self._input_popup = popup
        popup.ids.update({'field': field, 'accept': accept, 'cancel': cancel, 'error': error})
        cancel.bind(on_release=lambda *_: popup.dismiss())

        def submit(*_):
            try:
                if callback(field.text.strip()) is not False:
                    popup.dismiss()
            except (ValueError, OSError) as exc:
                error.text = str(exc)
        accept.bind(on_release=submit)
        field.bind(on_text_validate=submit)
        popup.open()
        Clock.schedule_once(lambda _: setattr(field, 'focus', True) if popup.parent else None, .15)
        return popup

    def _remember(self, snapshot=None):
        # A caller that already holds a pre-edit snapshot passes it to avoid a second deepcopy.
        self._undo.append(copy.deepcopy(self.map_data) if snapshot is None else snapshot)
        self._trim_history(self._undo)
        self._redo.clear()
        self.dirty = True
        self._sync_ui()

    def _sync_ui(self):
        self.can_undo, self.can_redo = bool(self._undo), bool(self._redo)
        if not self.atlas:
            return
        rec = self.atlas.current()
        self.map_title, self.level_title = rec['name'], LEVEL_LABELS[rec['level']]
        self.layer_title = LAYER_NAMES[self.layer]
        art = self.map_data['artwork']
        lay = next(l for l in art['layers'] if l['id'] == self.layer)
        self.layer_visible, self.layer_locked = lay['visible'], lay['locked']
        self.grid_visible = art['grid']
        self.sync_asset_controls()
        self.sync_level_controls()
        self.scale_title = scale_title(self.map_data)
        if hasattr(self, 'sync_region_controls'):
            self.sync_region_controls()

    def _activate(self, reset_view=True):
        from utils.map_region_context import refresh_region
        if refresh_region(self.atlas, self.atlas.active_id):
            self.dirty = True
        self.region_feedback = ''
        self._region_draft = []
        self.selected_region_id = ''
        self._gesture, self.selected_id = None, ''
        self.map_data = self.atlas.current()['map']
        self.map_data['editor_origin'] = {'atlas_id': self.atlas.id, 'node_id': self.atlas.active_id}
        self.current_map_filename = self.atlas.active_id + '.json'
        if hasattr(self.ids, 'map_canvas'):
            self.ids.map_canvas.set_map(self.map_data, self.atlas.current()['pins'], reset_view=reset_view)
        for key, value in [('rows_input', self.map_data['rows']), ('cols_input', self.map_data['cols'])]:
            if hasattr(self.ids, key):
                getattr(self.ids, key).text = str(value)
        self._sync_ui()
        if hasattr(self.ids, 'breadcrumbs'):
            bar = self.ids.breadcrumbs
            bar.clear_widgets()
            for rec in self.atlas.breadcrumbs():
                from kivy.factory import Factory
                btn = Factory.AtlasButton(text=rec['name'], size_hint_x=None, width=dp(max(86, min(190, len(rec['name']) * 8 + 24))))
                btn.fill_color = (.12, .35, .32, 1) if rec['id'] == self.atlas.active_id else (.13, .19, .21, 1)
                btn.bind(on_release=lambda _, key=rec['id']: self.rename_map() if key == self.atlas.active_id else self._navigate(key))
                bar.add_widget(btn)
            if hasattr(self.ids, 'breadcrumbs_scroll'):
                Clock.schedule_once(lambda _: setattr(self.ids.breadcrumbs_scroll, 'scroll_x', 1), 0)

    def recreate_grid_from_data(self):
        # Legacy load_existing_map calls this before atlas reconstruction.
        if hasattr(self.ids, 'map_canvas'):
            self.ids.map_canvas.set_map(self.map_data)

    def update_grid_visuals(self):
        if hasattr(self.ids, 'map_canvas'):
            self.ids.map_canvas.refresh()
        self.dirty = True
        if self.atlas and not self._gesture:
            self._sync_ui()

    def load_existing_map(self, value):
        data = decode_map(value)
        if not data:
            raise ValueError('Keine Karte enthalten.')
        origin = data.get('editor_origin', {})
        atlas = None
        if isinstance(origin, dict) and all(re.fullmatch('[a-f0-9]{32}', str(origin.get(k, ''))) for k in ('atlas_id', 'node_id')):
            if self.atlas and self.atlas.id == origin['atlas_id']:
                atlas = self.atlas
            else:
                path = safe_save_path(get_user_saves_dir(self._atlas_folder()), origin['atlas_id'] + '.json')
                if os.path.isfile(path):
                    atlas = read_atlas(path)
            if atlas and origin['node_id'] in atlas.maps:
                atlas.navigate(origin['node_id'])
                atlas.current()['map'] = Atlas(data, level=atlas.current()['level']).map
            else:
                atlas = None
        if atlas is None:
            atlas = Atlas(data, name='Importierte Karte', level='interior')
        # Preserve the established offline-character import, using the new renderer.
        if self.purpose == 'session':
            super().load_existing_map(data)
        else:
            self.map_data = data
        self.atlas = atlas
        self._undo.clear()
        self._redo.clear()
        self._activate()
        self.dirty = False

    def _save_atlas(self):
        if not self.atlas:
            return
        from utils.map_region_context import refresh_region
        for key in self.atlas.maps:
            refresh_region(self.atlas, key)
        data = self.map_with_characters()
        data['editor_title'] = self.atlas.current()['name']
        data['editor_origin'] = {'atlas_id': self.atlas.id, 'node_id': self.atlas.active_id}
        data['enemies'] = [t['object'] for t in data['tiles'].values()
                           if t.get('object') and t['object'].split('#')[0].strip() in ENEMY_DATA]
        # The canvas keeps this dictionary. Replacing it on save makes subsequent
        # edits invisible until a navigation/undo happens to reconnect the view.
        self.map_data.clear()
        self.map_data.update(data)
        self.atlas.current()['map'] = self.map_data
        atomic_write_json(safe_save_path(get_user_saves_dir(self._atlas_folder()), self.atlas.id + '.json'), self.atlas.encode())
        if self.purpose == 'library':
            self._library_last_id = self.atlas.id

    def checkpoint_atlas(self):
        """Lifecycle checkpoint, without opening popups while Android is pausing."""
        if self.atlas and self._editing and not self._empty_draft():
            self._save_atlas()

    def _empty_draft(self):
        return (self.purpose == 'library' and not self.dirty and self.atlas is not None
                and not os.path.isfile(safe_save_path(get_user_saves_dir('map_library'), self.atlas.id + '.json')))

    def _persist(self, current_map=False):
        try:
            if not current_map and self._empty_draft():
                return True
            self._save_atlas()
            if current_map and self.purpose != 'library':
                payload = encode_map(self.map_data)
                validate_primitive(payload)
                atomic_write_json(safe_save_path(get_user_saves_dir('maps'), self.current_map_filename), payload)
            self.dirty = False
            return True
        except (ValueError, OSError) as exc:
            self._error(f'Speichern fehlgeschlagen. Die Arbeit bleibt im Editor.\n{exc}')
            return False

    def save_map(self):
        if self._needs_name():
            self._name_before(self.save_map)
            return False
        if self._persist(current_map=True):
            if self.purpose != 'library':
                self.app.edited_map_data = copy.deepcopy(self.map_data)
            self.status = f'Atlas und Karte „{self.map_title}“ gespeichert.'
            return True
        return False

    def _needs_name(self):
        if not self.atlas:
            return False
        root = self.atlas.maps[self.atlas.root_id]
        return root['name'] in ('Neue Welt', 'Unbenannte Welt') and root['map'].get('editor_name_confirmed') is not True

    def _name_before(self, action):
        atlas = self.atlas
        def named(name, scale=None, _level=None):
            if self.atlas is not atlas:
                raise ValueError('Die Karte hat gewechselt.')
            if not 1 <= len(name) <= 80:
                raise ValueError('Bitte einen Namen mit 1 bis 80 Zeichen eingeben.')
            root = atlas.maps[atlas.root_id]
            previous = (root['name'], root['map'].get('editor_name_confirmed'), copy.deepcopy(root['map'].get(SCALE_KEY)))
            if scale is not None:
                root['map'][SCALE_KEY] = scale
            selected = self.selected_id
            root['name'] = name
            root['map']['editor_name_confirmed'] = True
            self.dirty = True
            self._activate(reset_view=False)
            if self._live(selected):
                self.selected_id = selected
                self._sync_ui()
            failure = None
            try:
                completed = action() is not False
            except Exception as exc:
                completed, failure = False, exc
            if not completed:
                root['name'] = previous[0]
                if previous[2] is None:
                    root['map'].pop(SCALE_KEY, None)
                else:
                    root['map'][SCALE_KEY] = previous[2]
                if previous[1] is None:
                    root['map'].pop('editor_name_confirmed', None)
                else:
                    root['map']['editor_name_confirmed'] = previous[1]
                self._activate(reset_view=False)
                if self._live(selected):
                    self.selected_id = selected
                    self._sync_ui()
                raise ValueError('Speichern fehlgeschlagen. Der Entwurf bleibt erhalten.') from failure
            return True
        root = atlas.maps[atlas.root_id]
        if SCALE_KEY not in root['map']:
            self._map_details('Welt vor dem Speichern benennen', '', suggested_scale({}, None, root['level']), named)
        else:
            self._prompt('Welt vor dem Speichern benennen', '', named)

    def save_as(self):
        """Write an independent complete atlas; never overwrite the source file."""
        atlas = self.atlas
        initial = '' if self._needs_name() else (atlas.maps[atlas.root_id]['name'][:70] + ' – Kopie')
        def save_copy(name):
            if self.atlas is not atlas:
                raise ValueError('Die Karte hat gewechselt.')
            if not 1 <= len(name) <= 80:
                raise ValueError('Bitte einen Namen mit 1 bis 80 Zeichen eingeben.')
            candidate = copy.deepcopy(atlas)
            candidate.current()['map'] = self.map_with_characters()
            candidate = candidate.duplicate(strip_party=False)
            root = candidate.maps[candidate.root_id]
            root['name'] = name
            root['map']['editor_name_confirmed'] = True
            for rec in candidate.maps.values():
                rec['map']['editor_title'] = rec['name']
            payload = candidate.encode()
            atomic_write_json(safe_save_path(get_user_saves_dir(self._atlas_folder()), candidate.id + '.json'), payload)
            if self.purpose != 'library':
                atomic_write_json(safe_save_path(get_user_saves_dir('maps'), candidate.active_id + '.json'), encode_map(candidate.map))
            self.atlas = candidate
            if self.purpose == 'library':
                self._library_last_id = candidate.id
            else:
                self.app.edited_map_data = copy.deepcopy(candidate.map)
            self._undo.clear()
            self._redo.clear()
            self._activate(reset_view=False)
            self.dirty = False
            self.status = f'Eigenen Atlas „{name}“ gespeichert. Die bisherige Datei bleibt erhalten.'
        self._prompt('Gesamten Atlas speichern unter …', initial, save_copy)

    def go_back(self):
        if self.atlas and self.dirty and self._needs_name():
            self._name_before(self.go_back)
            return False
        if self.atlas and not self._persist(current_map=self.purpose != 'library'):
            return False
        if self.purpose != 'library':
            self.app.edited_map_data = copy.deepcopy(self.map_data)
        self._editing = False
        self.app.go_back_screen()
        return True

    def _navigate(self, key):
        if not self.atlas or key == self.atlas.active_id:
            return
        if not self._persist():
            return
        self.atlas.navigate(key)
        self._undo.clear()
        self._redo.clear()
        self._activate()
        self.status = ('Weltkartenausschnitt geöffnet. Hier eigene Details ergänzen; die Grundlage bearbeitest du unter „1 Welt“.'
                       if 'region_context' in self.map_data else 'Karte geöffnet. Unterkarten: gelbe Markierung auswählen.')

    def parent_map(self):
        parent = self.atlas.current()['parent_id'] if self.atlas else None
        if parent:
            self._navigate(parent)
        else:
            self.status = 'Dies ist die oberste Karte dieses Atlas.'

    def _add_child_at(self, x, y, boundary=None):
        if self.atlas.current()['level'] == 'interior':
            self.status = 'Innenräume sind die letzte Detailstufe.'
            return
        aid, nid = self.atlas.id, self.atlas.active_id
        level = LEVELS[LEVELS.index(self.atlas.current()['level']) + 1]

        def add(name, scale, _level):
            if (self.atlas.id, self.atlas.active_id) != (aid, nid):
                return False
            candidate = copy.deepcopy(self.atlas)
            cid = candidate.add_child(name, x, y, boundary=boundary)
            r, c = grid_for_scale(scale)
            candidate.maps[cid]['map'] = new_map(r, c, level)
            candidate.maps[cid]['map'][SCALE_KEY] = scale
            candidate.navigate(nid)
            self._commit_cartography(candidate)
            self.set_tool('region' if boundary else 'pin')
            self.status = f'„{name}“ angelegt. Oben {LEVEL_LABELS[level]} wählen, um die Detailkarte zu bearbeiten.'
        self._map_details(LEVEL_LABELS[level] + ' anlegen', '',
                          suggested_scale(self.map_data, boundary, level), add)

    def pin_title(self, pin):
        rec = self.atlas.maps.get(pin['child_id']) if self.atlas else None
        return rec['name'] if rec else ''

    def rename_map(self):
        def rename(name):
            if not 1 <= len(name) <= 80:
                raise ValueError('Bitte einen Namen mit 1 bis 80 Zeichen eingeben.')
            self.atlas.current()['name'] = name
            if self.atlas.active_id == self.atlas.root_id:
                self.atlas.map['editor_name_confirmed'] = True
            self.dirty = True
            self._activate(reset_view=False)
        self._prompt('Karte benennen', self.map_title, rename)

    def _choice_popup(self, title, choices):
        scroll = ScrollView(do_scroll_x=False)
        box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6))
        box.bind(minimum_height=box.setter('height'))
        popup = create_styled_popup(title=title, content=scroll, size_hint=(.92, .85))
        self._choice_dialog = popup
        for title, action in choices:
            button = Button(text=title, size_hint_y=None, height=dp(52), halign='left', shorten=True)
            button.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(16), s[1])))
            button.bind(on_release=lambda _, fn=action: (popup.dismiss(), fn()))
            box.add_widget(button)
        scroll.add_widget(box)
        popup.open()

    def show_hierarchy(self):
        choices = []
        def walk(key, depth=0):
            rec = self.atlas.maps[key]
            choices.append(('    ' * depth + LEVEL_LABELS[rec['level']] + ': ' + rec['name'], lambda key=key: self._navigate(key)))
            for pin in rec['pins']:
                walk(pin['child_id'], depth + 1)
        walk(self.atlas.root_id)
        self._choice_popup('Karten im Atlas', choices)

    def load_map_popup(self):
        if self.atlas and not self._persist():
            return
        from ui.map_library import MapLibrary
        self.library_popup = MapLibrary(self)
        self.library_popup.open()

    def _open_atlas(self, atlas, as_copy=False):
        # A library source is never edited by a campaign. All child links get new IDs.
        self.atlas = atlas.duplicate() if as_copy else atlas
        self._undo.clear()
        self._redo.clear()
        self._activate()
        self.populate_spinners()
        self.dirty = as_copy
        self.status = ('Eigene Arbeitskopie geöffnet. Die Vorlage bleibt unverändert.' if as_copy
                       else 'Bibliothekskarte geöffnet. Änderungen werden in dieser Vorlage gespeichert.')

    def create_grid(self):
        self.new_atlas_popup()

    def new_atlas_popup(self):
        def submit(name, scale, level):
            lev = next(k for k, v in LEVEL_LABELS.items() if v == level)
            r, c = grid_for_scale(scale)
            data = new_map(r, c, lev)
            data[SCALE_KEY] = scale
            atlas = Atlas(data, name=name or 'Unbenannte Welt', level=lev)
            if name:
                atlas.map['editor_name_confirmed'] = True
            if self.atlas and not self._persist():
                return False
            self.atlas = atlas
            self._undo.clear()
            self._redo.clear()
            self._activate()
            self.dirty = True
        self._map_details('Neuer Atlas – bisheriger wird gespeichert', '',
                          suggested_scale({}, None, 'world'), submit, choose_level=True)

    def set_layer(self, name):
        self.layer = next((k for k, v in LAYER_NAMES.items() if v == name), self.layer)
        self._sync_ui()

    def choose_tile_type(self):
        for key in ('player_spinner', 'enemy_spinner', 'furniture_spinner'):
            if hasattr(self.ids, key):
                getattr(self.ids, key).text = 'None'
        if hasattr(self.ids, 'mimic_checkbox'):
            self.ids.mimic_checkbox.active = False
        self.set_tool('tile')

    def choose_placement(self, key, value):
        if value.strip().lower() in ('', 'none', 'keine', 'kein'):
            return
        for other in ('player_spinner', 'enemy_spinner', 'furniture_spinner'):
            if key != other:
                getattr(self.ids, other).text = 'None'
        self.set_tool('tile')

    def set_color(self, value):
        try:
            color_tuple(value)
            self.color = value.lower()
        except ValueError:
            self.status = 'Farbe als #RRGGBB eingeben, z. B. #5f8148.'

    def toggle_layer(self, field):
        if not self.atlas or field not in ('visible', 'locked'):
            return
        self._remember()
        layer = next(l for l in self.map_data['artwork']['layers'] if l['id'] == self.layer)
        layer[field] = not layer[field]
        self.selected_id = ''
        self.update_grid_visuals()

    def toggle_grid(self):
        self._remember()
        self.map_data['artwork']['grid'] = not self.map_data['artwork']['grid']
        self.update_grid_visuals()

    def set_background(self):
        self._remember()
        self.map_data['artwork']['background'] = self.color
        self.update_grid_visuals()

    def show_info_popup(self):
        text = ('Welt → Region → Ort → Innenraum\n\n'
                    'Beim ersten Speichern eine neue Welt benennen. Aktuellen Kartennamen antippen zum Umbenennen. '
                    'Unter „Karte …“ legt „Speichern unter“ eine unabhängige Kopie des gesamten Atlas an.\n\n'
                    'Beim Erstellen reale Breite × Höhe in km oder m angeben. Maßstab ändern ist oben jederzeit verfügbar. Die Leiste auf der Karte zeigt eine horizontale Entfernung. Kampfregeln werden dadurch nicht geändert.\n\n'
                    'Welt: Regionen wählen und direkt eine freie Grenzlinie über eine Insel ziehen. Eine vorherige Landübernahme ist nicht nötig. Anfang und Ende nahe Küste oder Regionsgrenze setzen. Die erste Linie legt zwei angrenzende Regionen an; weitere Linien teilen bestehende Regionen. Alternativ Grenzpunkte setzen wählen, Punkte anklicken und Grenze übernehmen drücken. Letzten Punkt zurück und Linie verwerfen korrigieren den Entwurf. Rückgängig stellt auch Unterkarten wieder her. '
                    'Für alte Einzelumrisse: Grenzen neu aufteilen (Kopie) erhält den alten Atlas und alle Detailkarten. In der Kopie optional Ganze Landfläche wählen und die Flächen vorhandenen Regionen zuordnen. Bereits gestaltete Detailkarten werden nicht zugeschnitten; ihren Maßstab bei Bedarf dort ändern.\n\n'
                    'Innerhalb einer Region: Orte / POI als getrennte Umrisse oder Rechtecke einzeichnen. Freiräume sind hier erlaubt. Dasselbe gilt für Gebäude / Innenräume auf der Ortskarte. Im Tab der nächsten Stufe wählst du die Detailkarten. '
                    'Region bearbeiten oder Tab 2 Regionen öffnet die tatsächliche Detailkarte. Die Welt bleibt die Übersicht zum Einzeichnen der Grenzen. Die vier Stufen und die Namen darüber führen zurück. '
                    '„Ortpunkt“ verknüpft eine Detailkarte ohne Umriss.\n\n'
                    '„Assets“ öffnet die Bildauswahl mit Kategorien und Suche. Bild wählen, dann auf die Karte tippen. '
                    'Größenkontrollen ändern das zuletzt gesetzte Bild; „Größe eingeben“ setzt die genaue Breite. Auswahl verschiebt Bilder. Weiß ausblenden lässt sich abschalten. '
                    'Die Qualitätsangabe zeigt Motive, die noch Nacharbeit benötigen.\n\n'
                    'Pinsel und Formen ziehen; Text und Symbole antippen. Auswahl zieht Elemente. '
                    'Radierer kürzt Linien; Formen/Symbole werden ganz entfernt.\n\n'
                    'Hand verschiebt die Ansicht; Mausrad oder +/− vergrößern. '
                    '„Spielfelder“ setzt Wände, Türen und Figuren. Zeichnungen allein blockieren keine Bewegung.\n\n'
                    'Ebenen lassen sich ausblenden und sperren. Ausgeblendete Zeichnungen werden weder angezeigt noch an Spieler übertragen. '
                    'Speichern und Zurück sichern den gesamten Atlas. Am Handy das Werkzeug im Dropdown wählen; Optionen öffnet die Einstellungen. '
                    'Bibliothekskarten sind unabhängig von Kampagnen. In einer Vorbereitung oder Sitzung wird eine eigene Kopie verwendet. '
                    'Die quadratischen Spielfelder bleiben auch bei ausgeblendetem Raster erhalten. Mausrad nach vorne vergrößert die Karte.')
        scroll = ScrollView(do_scroll_x=False)
        label = Label(text=text, size_hint_y=None, halign='left', valign='top', padding=(dp(12), dp(12)))
        label.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)),
                   texture_size=lambda w, v: setattr(w, 'height', v[1]))
        scroll.add_widget(label)
        create_styled_popup(title='Bedienung', content=scroll, size_hint=(.94, .85)).open()
