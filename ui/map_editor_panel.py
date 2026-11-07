"""Kontextuelles Inspector-Panel (Mixin) fuer den Kivy-Karteneditor."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

PALETTE = ('#5f8148', '#a4ae72', '#c6b78b', '#8d7050', '#819daa', '#495d71', '#e6d8b8', '#353e38')
TOOLS = (('select', 'Auswahl'), ('asset', 'Assets'), ('hand', 'Hand'), ('brush', 'Pinsel'), ('land', 'Landfläche'),
         ('line', 'Linie'), ('rect', 'Rechteck'), ('ellipse', 'Ellipse'), ('eraser', 'Radierer'),
         ('label', 'Text'), ('symbol', 'Skizzen'), ('region', 'Regionen'), ('pin', 'Ortpunkt'), ('tile', 'Spielfelder'),
         )
TOOL_TITLES = dict(TOOLS)
from utils.map_document import LAYER_NAMES, LEVELS
ROW_H = dp(44)


class EditorResponsiveBox(BoxLayout):
    """Collapsed alternative toolbars must not consume touches on other rows."""
    def on_touch_down(self, touch):
        if self.disabled or self.opacity == 0:
            return False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.disabled or self.opacity == 0:
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.disabled or self.opacity == 0:
            return False
        return super().on_touch_up(touch)


class EditorPanel:
    def _bind_if(self, name, callback):
        if self.property(name, quiet=True) is not None:
            self.bind(**{name: callback})

    def _build_controls(self):
        from kivy.utils import get_color_from_hex
        from kivy.uix.slider import Slider
        from kivy.factory import Factory
        if getattr(self, '_controls_built', False):
            return
        self._controls_built = True
        self._tool_buttons = {}
        self._shown = []

        def btn(title, action):
            b = Factory.AtlasButton(text=title, size_hint_y=None, height=ROW_H)
            b.bind(on_release=lambda *_: action())
            return b

        def head(text):
            return Factory.AtlasLabel(text=text, size_hint_y=None, height=dp(30))

        def row(*widgets):
            r = BoxLayout(size_hint_y=None, height=ROW_H, spacing=dp(4))
            for w in widgets:
                r.add_widget(w)
            return r

        def spin(text, values, callback, id_=None):
            w = Factory.AtlasSpinner(text=text, values=values, size_hint_y=None, height=ROW_H)
            if id_:
                self.ids[id_] = w
            w.bind(text=lambda _, value: callback(value))
            return w

        # Werkzeugleiste (gleich grosse Kinder; Groesse kommt aus dem KV)
        for key, title in TOOLS:
            b = Factory.AtlasButton(text=title, font_size='12sp')
            b.bind(on_release=lambda _, key=key: self.open_asset_browser() if key == 'asset' else self.set_tool(key))
            self.ids.tool_row.add_widget(b)
            self._tool_buttons[key] = b

        self._level_buttons = {}
        for level, title in zip(LEVELS, ('1 Welt', '2 Regionen', '3 Orte / POI', '4 Innenräume')):
            b = Factory.AtlasButton(text=title, font_size='12sp')
            b.bind(on_release=lambda _, level=level: self.open_level(level))
            self.ids.level_bar.add_widget(b)
            self._level_buttons[level] = b

        panel = self.ids.inspector
        panel.size_hint_y = None
        panel.spacing = dp(4)
        panel.bind(minimum_height=panel.setter('height'))
        self._tool_heading = head('')

        # Farbe
        palette = GridLayout(cols=8, size_hint_y=None, height=dp(34), spacing=dp(4))
        for c in PALETTE:
            b = Button(background_normal='', background_color=get_color_from_hex(c))
            b.bind(on_release=lambda _, c=c: self.set_color(c))
            palette.add_widget(b)
        field = TextInput(text=self.color, multiline=False, font_size='16sp')
        self.ids.hex_input = field
        field.bind(on_text_validate=lambda *_: self.set_color(field.text))
        color_row = row(field, btn('Farbe setzen', lambda: self.set_color(field.text)))
        self._bind_if('color', lambda _, c: setattr(field, 'text', c) if field.text != c else None)

        # Groesse
        size_label = Label(text='Größe %.1f' % self.brush_width, font_size='13sp', size_hint_x=.4)
        slider = Slider(min=.1, max=6, step=.1, value=self.brush_width)
        slider.bind(value=lambda _, v: setattr(self, 'brush_width', v)
                    if abs(self.brush_width - v) > 1e-6 else None)

        def on_width(_, v):
            size_label.text = 'Größe %.1f' % v
            if abs(slider.value - v) > 1e-6:
                slider.value = v
        self._bind_if('brush_width', on_width)
        size_row = row(size_label, slider)

        # Symbol
        symbol = spin('Baum', ['Baum', 'Berg', 'Haus', 'Höhle', 'Felsen', 'Tisch'],
                      lambda v: setattr(self, 'symbol', v) if getattr(self, 'symbol', None) != v else None)
        self._bind_if('symbol', lambda _, v: setattr(symbol, 'text', v) if symbol.text != v else None)

        # Auswahl
        recolor = btn('Umfärben', self.recolor_selected)
        remove = btn('Entfernen', self.delete_selected)

        def on_selected(*_):
            remove.disabled = not getattr(self, 'selected_id', None)
            selected = self._live(self.selected_id) if self.atlas and self.selected_id else None
            recolor.disabled = remove.disabled or bool(selected and selected['kind'] == 'asset')
        on_selected()
        self._bind_if('selected_id', on_selected)

        # Spielfelder
        hint = Factory.AtlasLabel(text='Wände: Typ "Wand" wählen, dann Felder antippen oder ziehen. '
                                       'Wände blockieren Bewegung.', size_hint_y=None, height=dp(48),
                                  font_size='13sp')
        hint.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
        tile_type = spin('Boden', ['Boden', 'Wand', 'Tür', 'Auslöser', 'Optionen'],
                         lambda _: self.choose_tile_type(), 'tile_type_spinner')
        tile_widgets = [hint, tile_type]
        for id_, title in (('player_spinner', 'Spieler (in einer Sitzung)'), ('enemy_spinner', 'Gegner platzieren'),
                           ('furniture_spinner', 'Möbel platzieren (blockieren)')):
            tile_widgets += [head(title), spin('None', ['None'], lambda v, k=id_: self.choose_placement(k, v), id_)]
        check = CheckBox(size_hint_x=None, width=ROW_H)
        self.ids.mimic_checkbox = check
        tile_widgets.append(row(check, Factory.AtlasLabel(text='Möbel ist ein Mimic (nur DM)')))
        tile_widgets.append(btn('Gegnerliste laden', self.load_enemy_list_popup))

        asset_picker = btn('Bild wählen: ' + self.asset_name, self.open_asset_browser)
        self._bind_if('asset_name', lambda _, v: setattr(asset_picker, 'text', 'Bild wählen: ' + v))
        transform = head(self.asset_transform_title)
        self._bind_if('asset_transform_title', lambda _, v: setattr(transform, 'text', v))
        white = btn(self.asset_background_title, lambda: self.transform_asset(toggle_white=True))
        self._bind_if('asset_background_title', lambda _, v: setattr(white, 'text', v))
        self._asset_widgets = [transform, btn('Größe eingeben …', self.set_asset_size),
            row(btn('Kleiner', lambda: self.transform_asset(scale=1/1.2)), btn('Größer', lambda: self.transform_asset(scale=1.2))),
            row(btn('Drehen -15°', lambda: self.transform_asset(degrees=-15)), btn('Drehen +15°', lambda: self.transform_asset(degrees=15))), white]
        region_hint = Factory.AtlasLabel(text='Regionen direkt mit freien Grenzlinien einzeichnen.', height=dp(100))
        region_shape = spin(self.region_shape, ['Freihand-Grenze', 'Grenzpunkte setzen', 'Ganze Landfläche'], lambda v: setattr(self, 'region_shape', v))
        self._region_selector, self._region_hint = region_shape, region_hint
        self._border_feedback = head('')
        self._border_feedback.color = (1,.65,.35,1)
        self._finish_border = btn('Grenze übernehmen', self.finish_region_line)
        self._border_draft_buttons = [self._finish_border, btn('Letzten Punkt zurück', self.undo_region_point), btn('Linie verwerfen', self.cancel_region_line)]
        self._edit_region_button = btn('Region bearbeiten', self.open_selected_region)
        self._reset_regions = btn('Grenzen neu aufteilen (Kopie) …', self.reset_region_partition)
        scale_button = btn(self.scale_title, self.edit_scale)
        self._bind_if('scale_title', lambda _, v: setattr(scale_button, 'text', 'Maßstab: ' + v))
        # Einstellungen
        rows_in = Label(text='24', font_size='16sp')
        cols_in = Label(text='32', font_size='16sp')
        self.ids.rows_input, self.ids.cols_input = rows_in, cols_in
        settings_widgets = [
            scale_button,
            btn('Karte umbenennen', self.rename_map),
            btn('Speichern unter …', self.save_as),
            btn('Hintergrund färben', self.set_background),
            head('Quadratische Felder: Zeilen × Spalten'), row(rows_in, cols_in),
            btn('Neuer Atlas …', self.new_atlas_popup),
            btn('Bedienung erklären', self.show_info_popup)]

        # Persistente Ebenen-Steuerung (alle Werkzeuge)
        names = LAYER_NAMES
        values = list(names.values())
        layers = spin(getattr(self, 'layer_title', '') or values[0], values,
                      lambda v: self.set_layer(v) if v != getattr(self, 'layer_title', None) else None)
        self._bind_if('layer_title', lambda _, v: setattr(layers, 'text', v) if layers.text != v else None)
        visible = btn('Sichtbar', lambda: self.toggle_layer('visible'))
        locked = btn('Bearbeitbar', lambda: self.toggle_layer('locked'))
        grid = btn('Raster: aus', self.toggle_grid)

        def on_visible(*_):
            visible.text = 'Sichtbar' if getattr(self, 'layer_visible', True) else 'Ausgeblendet'

        def on_locked(*_):
            locked.text = 'Gesperrt' if getattr(self, 'layer_locked', False) else 'Bearbeitbar'

        def on_grid(*_):
            grid.text = 'Raster: an' if getattr(self, 'grid_visible', False) else 'Raster: aus'
        for name, cb in (('layer_visible', on_visible), ('layer_locked', on_locked), ('grid_visible', on_grid)):
            self._bind_if(name, cb)
            cb()
        self._layer_block = [head('Zeichenebene'), layers, row(visible, locked), grid]

        # Kontextbloecke: (Werkzeuge, Widgets); jede Instanz existiert nur einmal
        self._tool_blocks = [
            (('select', 'brush', 'land', 'line', 'rect', 'ellipse', 'label', 'symbol', 'settings'),
             [head('Farbe'), palette, color_row]),
            (('brush', 'line', 'rect', 'ellipse', 'eraser', 'label', 'symbol'), [size_row]),
            (('symbol',), [head('Symbol'), symbol]),
            (('select',), [head('Ausgewähltes Element'), row(recolor, remove)]),
            (('tile',), tile_widgets),
            (('asset',), [asset_picker]),
            (('region',), [region_hint, region_shape, self._border_feedback, *self._border_draft_buttons, self._edit_region_button, self._reset_regions, btn('Karten im Atlas', self.show_hierarchy)]),
            (('settings',), settings_widgets),
        ]
        self._bind_if('selected_is_asset', self._refresh_inspector)
        self._text_widgets = [btn('Beschriftung bearbeiten …', self.edit_label),
                              row(btn('Text kleiner', lambda: self.resize_label(1/1.2)),
                                  btn('Text größer', lambda: self.resize_label(1.2)))]
        self._bind_if('selected_is_label', self._refresh_inspector)
        self._bind_if('tool', self._on_tool_changed)
        self._on_tool_changed()

    def _on_tool_changed(self, *_):
        for key, b in self._tool_buttons.items():
            b.fill_color = (.08, .48, .43, 1) if self.tool == key else (.19, .25, .29, 1)
        self.tool_title = TOOL_TITLES.get(self.tool, 'Karteneinstellungen')
        self._tool_heading.text = self.tool_title
        self._refresh_inspector()

    def _refresh_inspector(self, *_):
        panel = self.ids.inspector
        wanted = [self._tool_heading]
        for tools, widgets in self._tool_blocks:
            if self.tool in tools:
                wanted += widgets
        if self.tool == 'asset' or (self.tool == 'select' and self.selected_is_asset):
            wanted += self._asset_widgets
        if self.tool == 'select' and self.selected_is_label:
            wanted += self._text_widgets
        if self.tool != 'region':
            wanted += self._layer_block
        if self.tool == 'region' and self.atlas:
            if self.atlas.current()['level'] != 'world':
                hidden = [*self._border_draft_buttons, self._border_feedback, self._edit_region_button, self._reset_regions]
            else:
                hidden = [] if getattr(self, '_region_draft', []) else self._border_draft_buttons
                if not self.region_feedback:
                    hidden = [*hidden, self._border_feedback]
            wanted = [w for w in wanted if w not in hidden]
        if wanted == self._shown and len(panel.children) == len(wanted):
            return
        panel.clear_widgets()
        for w in wanted:
            panel.add_widget(w)
        self._shown = wanted
        self.ids.inspector_scroll.scroll_y = 1
