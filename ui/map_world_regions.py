"""Political regions: adopt a whole landmass, then split it along shared borders."""
from copy import deepcopy
import math
from utils.map_document import new_map
from utils.map_regions import (validate_boundary, simplify_gesture, boundary_contains,
                               boundary_center, _segments_touch)
from utils.map_scale import KEY, suggested_scale, grid_for_scale


class WorldRegionTools:
    def sync_region_controls(self):
        if not hasattr(self, '_region_selector'):
            return
        world = self.atlas.current()['level'] == 'world'
        level = self.atlas.current()['level']
        if getattr(self, '_region_level', None) != level:
            self._region_level = level
            self.region_shape = 'Freihand-Grenze' if world else 'Umriss'
        self._region_selector.values = ['Freihand-Grenze', 'Grenzpunkte setzen', 'Ganze Landfläche'] if world else ['Umriss', 'Rechteck']
        self._region_selector.text = self.region_shape
        self._region_hint.text = ('Grenze direkt über eine Insel ziehen. Anfang und Ende nahe Küste oder Regionsrand. Alternativ Grenzpunkte setzen und übernehmen.' if world else
                                 'Orte / Innenräume als einzelne Umrisse oder Rechtecke zeichnen. Zwischenräume sind erlaubt.')
        self._reset_regions.disabled = not world or not self.atlas.current()['pins']
        from kivy.metrics import dp
        self._border_feedback.text = self.region_feedback
        self._border_feedback.height = dp(110) if self.region_feedback else 0
        draft = getattr(self, '_region_draft', [])
        for button in self._border_draft_buttons:
            button.disabled = not world or not draft
        self._finish_border.disabled = not world or len(draft)<2
        selected = self.atlas.maps.get(getattr(self, 'selected_region_id', ''))
        self._edit_region_button.disabled = not world or not self.atlas.current()['pins']
        self._edit_region_button.text = 'Region bearbeiten' + (': ' + selected['name'] if selected and selected['parent_id'] == self.atlas.active_id else '')
        self._refresh_inspector()

    def open_selected_region(self):
        key = getattr(self, 'selected_region_id', '')
        if key in self.atlas.maps and self.atlas.maps[key]['parent_id'] == self.atlas.active_id:
            self._navigate(key)
        else:
            self.open_level('region')

    def cancel_region_line(self):
        self.region_feedback = ''
        self._region_draft = []
        self._sync_ui()
        self.ids.map_canvas.refresh()
        self.status = 'Grenzlinie verworfen. Bestehende Regionen bleiben erhalten.'

    def undo_region_point(self):
        self.region_feedback = ''
        if getattr(self, '_region_draft', []):
            self._region_draft.pop()
        self._sync_ui()
        self.ids.map_canvas.refresh()

    def add_region_point(self, x, y):
        draft = getattr(self, '_region_draft', [])
        if len(draft)>=256:
            self.status = 'Maximal 256 Grenzpunkte. Linie übernehmen oder Punkte zurücknehmen.'
            return
        from kivy.metrics import dp
        threshold = max(.02,min(.8,dp(3)/max(1,self.ids.map_canvas._geometry()[2])))
        if not draft or math.dist(draft[-1],(x,y))>threshold:
            self._region_draft = draft + [[x,y]]
        self.region_feedback = ''
        self.inspector_open = True
        self.status = f'{len(self._region_draft)} Grenzpunkte. Weitere Punkte antippen, dann „Grenze übernehmen“.'
        self._sync_ui()
        self.ids.map_canvas.refresh()

    def finish_region_line(self):
        self._split_world({'area': getattr(self, '_region_draft', [])})

    def _land_at(self, x, y):
        visible = {l['id'] for l in self._art()['layers'] if l['visible']}
        for el in reversed(self._els()):
            if el['layer'] != 'terrain' or el['layer'] not in visible:
                continue
            pts = el['points']
            if el['kind'] == 'polygon':
                # Freehand terrain has up to 1024 samples; reduce only the initial
                # coast once. All subsequent partitions preserve this shared ring.
                pts = simplify_gesture(pts, .03)
            elif el['kind'] == 'rect':
                (a,b),(c,d) = pts
                pts = [[a,b],[c,b],[c,d],[a,d]]
            elif el['kind'] == 'ellipse':
                (a,b),(c,d) = pts
                pts = [[(a+c)/2 + abs(a-c)/2*math.cos(i*math.tau/64),
                        (b+d)/2 + abs(b-d)/2*math.sin(i*math.tau/64)] for i in range(64)]
            else:
                continue
            if boundary_contains(pts, x, y):
                return validate_boundary(pts, self.map_data['cols'], self.map_data['rows'])
        return None

    def _adopt_land(self, x, y):
        try:
            area = self._land_at(x,y)
            if not area:
                raise ValueError('Zuerst mit Landfläche eine Insel / einen Kontinent zeichnen, dann dessen Fläche antippen.')
            # Existing regions must not be silently overwritten, even if old
            # outlines are only partially inside the chosen continent.
            for pin in self.atlas.current()['pins']:
                other = pin.get('boundary')
                if other and (any(boundary_contains(area,*p) for p in other)
                              or any(boundary_contains(other,*p) for p in area)
                              or any(_segments_touch(a,b,c,d) for a,b in zip(area,area[1:]+area[:1])
                                     for c,d in zip(other,other[1:]+other[:1]))):
                    raise ValueError('Hier bestehen bereits Regionsgrenzen. „Freihand-Grenze“ benutzen oder „Grenzen neu aufteilen (Kopie)“ wählen.')
            self._assign_region(area)
        except ValueError as exc:
            self._error(str(exc))
        return True

    def _split_world(self, gesture):
        from utils.map_region_workflow import resolve_cut
        line = simplify_gesture(gesture['area'], .03)
        self._region_draft = [list(p) for p in line]
        unit = self.ids.map_canvas._geometry()[2]
        from kivy.metrics import dp
        snap = max(.15,min(2.5,dp(16)/max(1.,unit)))
        try:
            child, (a,b), _ = resolve_cut(self.atlas.current(),line,snap)
        except ValueError as exc:
            self.region_feedback = str(exc).split(' Die Linie bleibt sichtbar:')[0][:220]
            self.status = 'Grenze noch nicht übernommen. Hinweis und Korrekturen rechts unter Regionen.'
            self.region_shape = 'Grenzpunkte setzen'
            self.inspector_open = True
            self._sync_ui()
            self.ids.map_canvas.refresh()
            return False
        self.region_feedback = ''
        self._sync_ui()
        self.ids.map_canvas.refresh()
        if child is None:
            self._first_regions_dialog(a,b)
        else:
            pin = next(p for p in self.atlas.current()['pins'] if p['child_id']==child)
            if boundary_contains(b,pin['x'],pin['y']):
                a,b = b,a
            self._assign_region(b,split=(child,a))
        return True

    def _first_regions_dialog(self, a, b):
        from kivy.core.window import Window
        from kivy.metrics import dp
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.textinput import TextInput
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from utils.helpers import create_styled_popup
        atlas,node = self.atlas,self.atlas.active_id
        names = {r['name'] for r in atlas.maps.values()}
        index = 1
        while f'Region {index}' in names or f'Region {index+1}' in names:
            index+=1
        box = BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8))
        fields = [TextInput(text=f'Region {index+i}',multiline=False,size_hint_y=None,height=dp(44)) for i in range(2)]
        info = Label(text='Die Linie teilt die Insel in zwei angrenzende Regionen.\nGrößen werden aus der Weltkarte übernommen.',size_hint_y=None,height=dp(58),font_size='13sp')
        info.bind(width=lambda w,v:setattr(w,'text_size',(v,None)))
        error = Label(text='',color=(1,.5,.4,1),size_hint_y=None,height=dp(50))
        error.bind(width=lambda w,v:setattr(w,'text_size',(v,None)))
        buttons = BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(8))
        accept,cancel = Button(text='Regionen anlegen'),Button(text='Abbrechen')
        buttons.add_widget(cancel);buttons.add_widget(accept)
        for w in [info,*fields,error,buttons]: box.add_widget(w)
        popup = create_styled_popup(title='Freie Grenze · zwei Regionen',content=box,size_hint=(min(.94,dp(600)/max(1,Window.width)),None),height=dp(360),auto_dismiss=False)
        popup.ids.update(dict(first=fields[0],second=fields[1],error=error,accept=accept,cancel=cancel))
        self._partition_popup = popup
        def apply(*_):
            try:
                if self.atlas is not atlas or self.atlas.active_id != node:
                    raise ValueError('Die Karte hat gewechselt.')
                new_names = [f.text.strip() for f in fields]
                if any(not 1<=len(n)<=80 for n in new_names):
                    raise ValueError('Bitte für beide Regionen 1 bis 80 Zeichen eingeben.')
                if new_names[0].casefold()==new_names[1].casefold():
                    raise ValueError('Bitte zwei unterscheidbare Regionsnamen eingeben.')
                candidate = deepcopy(atlas)
                for name,boundary in zip(new_names,(a,b)):
                    candidate.navigate(node)
                    x,y=boundary_center(boundary)
                    scale=suggested_scale(candidate.map,boundary,'region')
                    key=candidate.add_child(name,x,y,boundary=boundary)
                    rows,cols=grid_for_scale(scale)
                    candidate.maps[key]['map']=new_map(rows,cols,'region')
                    candidate.maps[key]['map'][KEY]=scale
                candidate.navigate(node)
                self._commit_cartography(candidate)
                self.selected_region_id = key
                self.region_shape = 'Freihand-Grenze'
                self._sync_ui()
                self.status = 'Zwei Regionen angelegt. Weitere Grenzen hier zeichnen; „Region bearbeiten“ oder Tab „2 Regionen“ öffnet die Detailkarte.'
                popup.dismiss()
            except (ValueError,OSError) as exc:
                error.text=str(exc)
        accept.bind(on_release=apply); cancel.bind(on_release=lambda *_:popup.dismiss())
        popup.open()

    def _assign_region(self, boundary, split=None):
        atlas, node = self.atlas, self.atlas.active_id
        scale = suggested_scale(self.map_data, boundary, 'region')
        def assign(name=None, physical=None, child_id=None):
            if self.atlas is not atlas or self.atlas.active_id != node:
                raise ValueError('Die Karte hat gewechselt.')
            candidate = deepcopy(atlas)
            parent = candidate.current()
            if split:
                old = next(p for p in parent['pins'] if p['child_id'] == split[0])
                old['boundary'] = deepcopy(split[1])
                old['x'], old['y'] = boundary_center(split[1])
            x,y = boundary_center(boundary)
            if child_id:
                target = next(p for p in parent['pins'] if p['child_id'] == child_id)
                if target.get('boundary'):
                    raise ValueError('Diese Region hat bereits eine Fläche.')
                target.update(x=x,y=y,boundary=deepcopy(boundary))
                name = candidate.maps[child_id]['name']
            else:
                child_id = candidate.add_child(name,x,y,boundary=boundary)
                r,c = grid_for_scale(physical)
                candidate.maps[child_id]['map'] = new_map(r,c,'region')
                candidate.maps[child_id]['map'][KEY] = physical
                candidate.navigate(node)
            self._commit_cartography(candidate)
            self.selected_region_id = child_id
            self.region_shape = 'Freihand-Grenze'
            self._sync_ui()
            self.status = f'„{name}“ zugeordnet. Weitere Grenze von Rand zu Rand ziehen; Rückgängig setzt die Aufteilung zurück.'
            if split:
                self.status = f'„{name}“ abgeteilt. Bestehende Detailkarte bleibt unverändert; ihren Maßstab bei Bedarf dort anpassen.'
        def existing(key):
            try:
                assign(child_id=key)
            except (ValueError, OSError, StopIteration) as exc:
                self._error(str(exc) or 'Die gewählte Region ist nicht mehr verfügbar.')
        def new():
            self._map_details('Neue Region · Name und Kartengröße', '', scale,
                              lambda name, physical, _: assign(name,physical))
        unassigned = [p for p in atlas.current()['pins'] if not p.get('boundary')]
        if unassigned:
            choices = [('Vorhandene Region: ' + atlas.maps[p['child_id']]['name'],
                        lambda key=p['child_id']: existing(key)) for p in unassigned]
            choices.append(('Neue Region erstellen …', new))
            self._choice_popup('Fläche einer Region zuordnen', choices)
        else:
            new()

    def reset_region_partition(self):
        """Explicit independent copy; old boundaries and detail maps stay saved."""
        if self.atlas.current()['level'] != 'world':
            return
        atlas = self.atlas
        def create(name):
            if self.atlas is not atlas:
                raise ValueError('Die Karte hat gewechselt.')
            if not 1 <= len(name) <= 80:
                raise ValueError('Bitte einen Namen mit 1 bis 80 Zeichen eingeben.')
            if not self._persist():
                return False
            candidate = atlas.duplicate(strip_party=False)
            candidate.maps[candidate.root_id]['name'] = name
            candidate.maps[candidate.root_id]['map']['editor_name_confirmed'] = True
            for pin in candidate.current()['pins']:
                pin.pop('boundary', None)
            self.atlas = candidate
            self._undo.clear(); self._redo.clear()
            self._activate(reset_view=False)
            self.dirty = True
            self.region_shape = 'Freihand-Grenze'
            self.set_tool('region')
            self.status = 'Kopie erstellt. Ganze Landfläche zuordnen oder direkt Grenzen zeichnen. Vorhandene Detailkarten bleiben erhalten.'
        self._prompt('Neue Aufteilung als Kopie – Name', (atlas.maps[atlas.root_id]['name'] + ' – neue Grenzen')[:80], create)
