"""Local map catalogue. Campaigns always receive independent atlas copies."""
import os
import re

from kivy.factory import Factory
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from utils.formats import decode_map
from utils.helpers import create_styled_popup, get_user_saves_dir
from utils.map_document import Atlas, LEVEL_LABELS, read_atlas
from utils.storage import read_json, safe_save_path


class MapLibrary:
    def __init__(self, editor):
        self.editor = editor
        self.entries = []
        box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
        standalone = editor.purpose == 'library'
        hint = Factory.AtlasLabel(
            text=('Vorlagen bearbeiten oder als Kopie öffnen. In Kampagnen bleibt das Original erhalten.'
                  if standalone else 'Atlas auswählen: Es wird eine eigene Arbeitskopie für diese Vorbereitung / Sitzung erstellt.'),
            height=dp(56))
        box.add_widget(hint)
        self.search = TextInput(hint_text='Kartenname suchen …', multiline=False,
                                size_hint_y=None, height=dp(44), font_size='16sp')
        box.add_widget(self.search)
        self.list = BoxLayout(orientation='vertical', spacing=dp(8), size_hint_y=None)
        self.list.bind(minimum_height=self.list.setter('height'))
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.list)
        box.add_widget(scroll)
        footer = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        new = Factory.AtlasButton(text='Neuer Atlas')
        close = Factory.AtlasButton(text='Schließen')
        footer.add_widget(new)
        footer.add_widget(close)
        box.add_widget(footer)
        self.popup = create_styled_popup(title='Kartenbibliothek', content=box, size_hint=(.96, .92))
        new.bind(on_release=lambda *_: (self.popup.dismiss(), editor.new_atlas_popup()))
        close.bind(on_release=lambda *_: self.popup.dismiss())
        self.search.bind(text=lambda *_: self.render())
        for folder in ('map_library', 'atlases', 'maps'):
            for filename in sorted(os.listdir(get_user_saves_dir(folder))):
                if not filename.endswith('.json'):
                    continue
                # UUID map exports are already represented by their parent atlas.
                if folder == 'maps' and re.fullmatch(r'[a-f0-9]{32}\.json', filename):
                    continue
                path = safe_save_path(get_user_saves_dir(folder), filename)
                try:
                    atlas = self.read(folder, path)
                    title = atlas.maps[atlas.root_id]['name']
                    detail = f"{LEVEL_LABELS[atlas.maps[atlas.root_id]['level']]} · {len(atlas.maps)} Karte(n)"
                    detail += ' · Vorlage' if folder == 'map_library' else ' · Bisherige Karte'
                    self.entries.append((title, detail, folder, path, None))
                except (OSError, ValueError) as exc:
                    self.entries.append((filename, 'Nicht lesbar', folder, path, str(exc)))
        self.render()

    @staticmethod
    def read(folder, path):
        if folder != 'maps':
            return read_atlas(path)
        data = decode_map(read_json(path))
        return Atlas(data, name=str(data.get('editor_title') or os.path.basename(path))[:80], level='interior')

    def render(self):
        self.list.clear_widgets()
        query = self.search.text.casefold().strip()
        for entry in self.entries:
            title, detail, folder, path, error = entry
            if query and query not in (title + ' ' + detail).casefold():
                continue
            row = BoxLayout(size_hint_y=None, height=dp(76), spacing=dp(6))
            button = Factory.AtlasButton(text=title + '\n' + detail, height=dp(76), halign='left')
            button.bind(on_release=lambda _, entry=entry: self.choose(entry))
            row.add_widget(button)
            if self.editor.purpose == 'library' and folder == 'map_library' and not error:
                duplicate = Factory.AtlasButton(text='Kopie', size_hint_x=None, width=dp(64), height=dp(76))
                duplicate.bind(on_release=lambda _, entry=entry: self.choose(entry, force_copy=True))
                row.add_widget(duplicate)
            self.list.add_widget(row)
        if not self.list.children:
            self.list.add_widget(Factory.AtlasLabel(text='Keine passenden Karten. Mit „Neuer Atlas“ beginnen.', height=dp(70)))

    def choose(self, entry, force_copy=False):
        title, detail, folder, path, error = entry
        try:
            if error:
                raise ValueError(error)
            atlas = self.read(folder, path)
            copy = force_copy or self.editor.purpose != 'library' or folder != 'map_library'
            self.editor._open_atlas(atlas, as_copy=copy)
            if copy and self.editor.purpose == 'library':
                atlas = self.editor.atlas
                atlas.maps[atlas.root_id]['name'] = (title[:72] + ' – Kopie')[:80]
                self.editor._activate()
            self.popup.dismiss()
        except (OSError, ValueError) as exc:
            self.editor._error(f'Karte konnte nicht geöffnet werden: {exc}')

    def open(self):
        self.popup.open()
