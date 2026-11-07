"""Editor controls for raster stamps and the four linked map levels."""
from utils.asset_catalog import asset_info, asset_path
from utils.map_document import add_element, LEVELS, LEVEL_LABELS
from utils.map_regions import boundary_contains, boundary_center, validate_boundary, simplify_gesture


from ui.map_world_regions import WorldRegionTools


class AssetAndRegionTools(WorldRegionTools):
    def open_asset_browser(self):
        from ui.map_asset_browser import AssetBrowser
        try:
            if getattr(self, 'asset_browser', None) is None:
                self.asset_browser = AssetBrowser(self)
            self.asset_browser.open()
        except (OSError, ValueError) as exc:
            self._error(f'Assets konnten nicht geöffnet werden: {exc}')

    def select_asset(self, key):
        from pathlib import Path
        info = asset_info(key)
        if info is None or not Path(asset_path(key)).is_file():
            self._error('Dieses Asset ist nicht installiert.')
            return False
        self.asset_id, self.asset_name = key, info['name']
        self.selected_id = ''
        self.set_tool('asset')
        self.inspector_open = True
        return True

    def _place_asset(self, x, y):
        if self._blocked(self.layer):
            return True
        if not self.asset_id:
            self.open_asset_browser()
            return True
        def place():
            self.selected_id = add_element(self._art(), 'asset', [[x, y]], '#ffffff',
                self.asset_size, self.layer, asset_id=self.asset_id,
                rotation=self.asset_rotation, remove_white=self.asset_remove_white)
        if self._txn(place):
            self.inspector_open = True
            self.status = 'Bild gesetzt und ausgewählt. Größe und Drehung ändern dieses Bild; Auswahl verschiebt es.'
        return True

    def transform_asset(self, scale=1, degrees=0, toggle_white=False, width=None):
        element = self._live(self.selected_id) if self.tool in ('select', 'asset') else None
        if element and element['kind'] != 'asset':
            element = None
        if element or self.tool == 'select':
            if not element or element['kind'] != 'asset' or self._blocked(element['layer']):
                return False
            def edit():
                element['width'] = max(.5, min(20, width if width is not None else element['width'] * scale))
                element['rotation'] = (element['rotation'] + degrees) % 360
                if toggle_white:
                    element['remove_white'] = not element['remove_white']
            if self._txn(edit):
                self.asset_size, self.asset_rotation, self.asset_remove_white = element['width'], element['rotation'], element['remove_white']
            else:
                return False
        else:
            self.asset_size = max(.5, min(20, width if width is not None else self.asset_size * scale))
            self.asset_rotation = (self.asset_rotation + degrees) % 360
            if toggle_white:
                self.asset_remove_white = not self.asset_remove_white
            self._sync_ui()
        if hasattr(self.ids, 'map_canvas'):
            self.ids.map_canvas.refresh()
        return True

    def sync_asset_controls(self):
        element = self._live(self.selected_id) if self.atlas and self.selected_id else None
        self.selected_is_asset = bool(element and element['kind'] == 'asset')
        self.selected_is_label = bool(element and element['kind'] == 'label')
        chosen = self.tool in ('asset', 'select') and self.selected_is_asset
        if chosen:
            size, rotation, white = element['width'], element['rotation'], element['remove_white']
        else:
            size, rotation, white = self.asset_size, self.asset_rotation, self.asset_remove_white
        self.asset_transform_title = ('Auswahl: ' if chosen else 'Nächstes Bild: ') + f'{size:.1f} Felder · {rotation:.0f}°'
        self.asset_background_title = 'Weiß ausblenden: ' + ('an' if white else 'aus')

    def set_asset_size(self):
        element = self._live(self.selected_id) if self.selected_id else None
        chosen_id = element['id'] if element and element['kind'] == 'asset' else None
        initial = element['width'] if chosen_id else self.asset_size
        atlas, node = self.atlas, self.atlas.active_id
        def resize(text):
            import math
            try:
                value = float(text.replace(',', '.'))
            except ValueError:
                raise ValueError('Größe als Zahl eingeben, z. B. 3,5.') from None
            if not math.isfinite(value) or not .5 <= value <= 20:
                raise ValueError('Bitte 0,5 bis 20 Felder eingeben.')
            if self.atlas is not atlas or self.atlas.active_id != node or self.selected_id != (chosen_id or ''):
                raise ValueError('Die Auswahl hat gewechselt.')
            if not self.transform_asset(width=value):
                raise ValueError('Größe konnte nicht geändert werden. Ist die Objektebene gesperrt?')
        self._prompt('Bildbreite in Feldern', f'{initial:g}', resize)

    def region_at(self, x, y):
        return next((p for p in reversed(self.atlas.current()['pins'])
                     if p.get('boundary') and boundary_contains(p['boundary'], x, y)), None)

    def _region_down(self, x, y):
        if self.atlas.current()['level'] == 'world' and self.region_shape in ('Landfläche übernehmen', 'Ganze Landfläche'):
            return self._adopt_land(x, y)
        if self.atlas.current()['level'] == 'interior':
            self.status = 'Innenraum ist die vierte und letzte Kartenstufe.'
            return True
        if self.atlas.current()['level'] == 'world' and self.region_shape in ('Freihand-Grenze', 'Grenze teilen'):
            self._region_draft = []
        pin = self.region_at(x, y)
        self._start('region', x, y, area=[[x, y]], child=pin['child_id'] if pin else None,
                    shape=self.region_shape)
        return True

    def _finish_region(self, g):
        self._gesture = None
        self.ids.map_canvas.refresh()
        if self.atlas.current()['level'] == 'world' and g['shape'] == 'Grenzpunkte setzen':
            self.add_region_point(*g['last'])
            return
        if not g['moved']:
            if g.get('child'):
                self._navigate(g['child'])
            else:
                self.status = ('Freie Grenzlinie über eine Insel ziehen oder Grenzpunkte setzen.' if self.atlas.current()['level'] == 'world' else 'Ort als Umriss oder Rechteck ziehen, dann benennen.')
            return
        if self.atlas.current()['level'] == 'world' and g['shape'] in ('Grenze teilen', 'Freihand-Grenze'):
            self._split_world(g)
            return
        try:
            points = validate_boundary(simplify_gesture(g['area']), self.map_data['cols'], self.map_data['rows'])
            x, y = boundary_center(points)
            self._add_child_at(x, y, boundary=points)
        except ValueError as exc:
            self._error(str(exc))

    def open_level(self, level):
        if not self.atlas:
            return
        root = self.atlas.maps[self.atlas.root_id]
        if root['level'] == level:
            self._navigate(root['id'])
            return
        index = LEVELS.index(level)
        if index <= LEVELS.index(root['level']):
            return
        parents = [r for r in self.atlas.maps.values() if r['level'] == LEVELS[index - 1]]
        if not parents:
            self.status = 'Zuerst eine Karte der vorherigen Stufe anlegen.'
            return
        records = [r for r in self.atlas.maps.values() if r['level'] == level]
        if not records:
            self.status = 'Noch keine Region vorhanden. Auf der Weltkarte „Regionen“ wählen und eine Grenze zeichnen.' if level == 'region' else 'Zuerst einen Ort / Innenraum auf der vorherigen Karte einzeichnen.'
            return
        if len(records) == 1:
            self._navigate(records[0]['id'])
            return
        choices = []
        for rec in records:
            parent_name = self.atlas.maps[rec['parent_id']]['name']
            choices.append((rec['name'] + ' · ' + parent_name, lambda key=rec['id']: self._navigate(key)))
        self._choice_popup(LEVEL_LABELS[level] + ' bearbeiten', choices)

    def define_on_parent(self, key):
        self._navigate(key)
        if self.atlas.active_id == key:
            self.start_region()

    def start_region(self):
        self.set_tool('region')
        self.inspector_open = True

    def sync_level_controls(self):
        if not self.atlas or not hasattr(self, '_level_buttons'):
            return
        current = LEVELS.index(self.atlas.current()['level'])
        available = {rec['level'] for rec in self.atlas.maps.values()}
        for index, (level, button) in enumerate(self._level_buttons.items()):
            button.disabled = level not in available
            button.fill_color = (.12, .45, .38, 1) if index == current else (.16, .22, .25, 1)
