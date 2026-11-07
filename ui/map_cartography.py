"""Scale dialogs and cartographic map setup shared by all detail levels."""
from copy import deepcopy
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.button import Button
from utils.helpers import create_styled_popup
from utils.map_scale import KEY, DEFAULTS, parse_scale, display_values, suggested_scale


class CartographyTools:
    def _map_details(self, title, name, scale, callback, *, choose_level=False):
        box = BoxLayout(orientation='vertical', spacing=dp(7), padding=dp(10))
        name_in = TextInput(text=name, hint_text='Kartenname', multiline=False, size_hint_y=None, height=dp(44))
        width, height, unit = display_values(scale)
        w = TextInput(text=width, multiline=False)
        h = TextInput(text=height, multiline=False)
        units = Spinner(text=unit, values=['km', 'm'], size_hint_x=None, width=dp(80), font_size='14sp')
        level = Spinner(text='Welt', values=['Welt', 'Region', 'Ort', 'Innenraum'], size_hint_y=None, height=dp(42))
        line = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(5))
        for widget in (w, Label(text='×', size_hint_x=.2), h, units):
            line.add_widget(widget)
        error = Label(text='', color=(1,.5,.4,1), size_hint_y=None, height=dp(52))
        error.bind(width=lambda obj, v: setattr(obj, 'text_size', (v, None)))
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        accept = Button(text='Atlas erstellen' if choose_level else 'Übernehmen')
        cancel = Button(text='Abbrechen')
        buttons.add_widget(cancel); buttons.add_widget(accept)
        for widget in ([name_in, level] if choose_level else [name_in]):
            box.add_widget(widget)
        box.add_widget(Label(text='Reale Breite × Höhe der Karte', size_hint_y=None, height=dp(28)))
        box.add_widget(line)
        box.add_widget(Label(text='Zeichenraster und Kampfregeln bleiben unabhängig.', font_size='12sp', size_hint_y=None, height=dp(38), text_size=(dp(290),None)))
        box.add_widget(error); box.add_widget(buttons)
        popup = create_styled_popup(title=title, content=box, size_hint=(min(.94,dp(680)/max(1,Window.width)),None), height=dp(390 if choose_level else 345), auto_dismiss=False)
        popup.ids.update(dict(name=name_in, width_field=w, height_field=h, unit=units, level=level, error=error, accept=accept, cancel=cancel))
        self._details_popup = self._input_popup = popup
        def submit(*_):
            try:
                if len(name_in.text.strip()) > 80 or (not choose_level and not name_in.text.strip()):
                    raise ValueError('Bitte einen Namen mit 1 bis 80 Zeichen eingeben.')
                value = parse_scale(w.text, h.text, units.text)
                result = callback(name_in.text.strip(), value, level.text)
                if result is not False:
                    popup.dismiss()
                else:
                    error.text = 'Vorgang nicht abgeschlossen. ' + self.status[:180]
            except (ValueError, OSError) as exc:
                error.text = str(exc)
        def defaults(_, text):
            from utils.map_document import LEVEL_LABELS
            key = next(k for k,v in LEVEL_LABELS.items() if v == text)
            ww, hh, uu = DEFAULTS[key]
            w.text, h.text, units.text = str(ww), str(hh), uu
        level.bind(text=defaults)
        accept.bind(on_release=submit)
        cancel.bind(on_release=lambda *_: popup.dismiss())
        popup.open()
        return popup

    def edit_scale(self):
        atlas, node = self.atlas, self.atlas.active_id
        current = self.atlas.current()
        value = current['map'].get(KEY) or suggested_scale({}, None, current['level'])
        def apply(name, scale, _):
            if self.atlas is not atlas or self.atlas.active_id != node:
                raise ValueError('Die Karte hat gewechselt.')
            # Rename uses its existing command; this dialog changes dimensions only.
            return self._txn(lambda: self.map_data.__setitem__(KEY, scale))
        popup = self._map_details('Maßstab der aktuellen Karte', current['name'], value, apply)
        popup.ids.name.readonly = True

    def _commit_cartography(self, candidate):
        """Atlas-level edit with full undo, including child maps and boundaries."""
        candidate.encode()
        self._undo.append(deepcopy(self.atlas))
        self._trim_history(self._undo)
        self._redo.clear()
        self.atlas = candidate
        self.dirty = True
        self._activate(reset_view=False)
        return True

    @staticmethod
    def _trim_history(stack):
        """Cap complete-atlas snapshots by tile count as well as entry count."""
        def weight(item):
            return sum(len(r['map'].get('tiles',{})) for r in item.maps.values()) if hasattr(item,'maps') else len(item.get('tiles',{}))
        del stack[:-20]
        total = sum(weight(item) for item in stack)
        while len(stack)>1 and total>100000:
            total -= weight(stack.pop(0))
