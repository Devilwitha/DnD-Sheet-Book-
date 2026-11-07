# Offline map asset picker popup (Kivy 2.3.1). Uses only catalog ids and cached textures.
from math import ceil

from kivy.factory import Factory
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from ui.asset_render import preview_texture
from utils.asset_catalog import catalog
from utils.helpers import create_styled_popup

ALL = 'Alle Kategorien'
PAGE_SIZE = 6


def _text(entry, key, limit=80):
    return str(entry.get(key) or '')[:limit]


def _label(text, size, height, **kw):
    lbl = Label(text=text, markup=False, font_size=size, size_hint_y=None, height=height,
                halign='center', valign='middle', shorten=True, shorten_from='right', **kw)
    lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    return lbl


class AssetCard(ButtonBehavior, BoxLayout):
    # The whole card is the touch target; children never consume touches.
    def __init__(self, entry, selected, **kw):
        super().__init__(orientation='vertical', size_hint_y=None, height=dp(160),
                         padding=dp(4), spacing=dp(2), **kw)
        self.asset_id = str(entry['id'])
        with self.canvas.before:
            Color(0.09, 0.10, 0.12, 1)
            self._bg = Rectangle()
            Color(*((0.30, 0.85, 0.45, 1) if selected else (0.28, 0.30, 0.34, 1)))
            self._ln = Line(width=dp(2.5) if selected else dp(1))
        self.bind(pos=self._redraw, size=self._redraw)
        try:
            tex = preview_texture(self.asset_id, remove_white=True)  # shared cached GPU texture
        except Exception:
            tex = None
        if tex is not None:
            self.add_widget(Image(texture=tex, fit_mode='contain'))
        else:
            self.add_widget(Label(text='Keine Vorschau', font_size=sp(11), markup=False))
        self.add_widget(_label(_text(entry, 'name'), sp(12), dp(34), max_lines=2))
        self.add_widget(_label(_text(entry, 'qa', 40), sp(10), dp(16), color=(0.7, 0.75, 0.8, 1)))

    def _redraw(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size
        self._ln.rectangle = (self.x, self.y, self.width, self.height)


class AssetBrowser:
    def __init__(self, editor):
        self.editor = editor
        self.entries = tuple(catalog())
        self.filtered = ()
        self.page = 0
        self.query = ''
        self.category = ALL
        self._build()

    def _build(self):
        cats = sorted({_text(e, 'category', 60) for e in self.entries if e.get('category')})
        root = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.search = TextInput(hint_text='Suchen', multiline=False, write_tab=False,
                                padding=(dp(8), dp(11)), font_size=sp(14))
        self.spinner = Factory.AtlasSpinner(text=ALL, values=[ALL] + cats, size_hint_x=0.45)
        top.add_widget(self.search)
        top.add_widget(self.spinner)
        self.scroll = ScrollView(do_scroll_x=False, do_scroll_y=True, bar_width=dp(4))
        self.grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(6), padding=dp(2))
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        self.empty = Label(text='Keine Assets gefunden.', markup=False, size_hint_y=None, height=dp(60))
        pager = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.prev_btn = Factory.AtlasButton(text='<', size_hint_x=None, width=dp(44))
        self.next_btn = Factory.AtlasButton(text='>', size_hint_x=None, width=dp(44))
        self.page_lbl = Label(text='', markup=False, font_size=sp(13))
        for w in (self.prev_btn, self.page_lbl, self.next_btn):
            pager.add_widget(w)
        close = Factory.AtlasButton(text='Schließen', size_hint_y=None, height=dp(44))
        for w in (top, self.scroll, pager, close):
            root.add_widget(w)
        self.popup = create_styled_popup('Asset wählen', root)
        self.popup.size_hint = (0.96, 0.94)
        self.popup.size_hint_max_x = dp(900)
        self.popup.auto_dismiss = True
        # Bind once; the popup and its content are reused for every open().
        self.search.bind(text=self._on_query)
        self.spinner.bind(text=self._on_category)
        self.prev_btn.bind(on_release=lambda *_: self._go(-1))
        self.next_btn.bind(on_release=lambda *_: self._go(1))
        close.bind(on_release=lambda *_: self.dismiss())
        self.popup.bind(width=self._update_cols)
        self._update_cols()

    def _update_cols(self, *_):
        self.grid.cols = 3 if self.popup.width >= dp(700) else 2

    def _on_query(self, _w, value):
        self.query = (value or '').strip().casefold()
        self.page = 0
        self._refresh()

    def _on_category(self, _w, value):
        self.category = value or ALL
        self.page = 0
        self._refresh()

    def _go(self, delta):
        self.page += delta
        self._refresh()

    def _matches(self, e):
        if self.category != ALL and str(e.get('category') or '') != self.category:
            return False
        if not self.query:
            return True
        hay = ' '.join(str(e.get(k) or '') for k in ('name', 'category', 'id')).casefold()
        return self.query in hay

    def _refresh(self):
        self.filtered = tuple(e for e in self.entries if self._matches(e))
        pages = max(1, ceil(len(self.filtered) / PAGE_SIZE))
        self.page = min(max(self.page, 0), pages - 1)
        start = self.page * PAGE_SIZE
        current = str(getattr(self.editor, 'asset_id', '') or '')
        self.grid.clear_widgets()
        for e in self.filtered[start:start + PAGE_SIZE]:
            card = AssetCard(e, str(e['id']) == current)
            card.bind(on_release=lambda w: self._select(w.asset_id))
            self.grid.add_widget(card)
        if not self.filtered:
            self.grid.add_widget(self.empty)
        self.grid.parent.scroll_y = 1
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= pages - 1
        self.page_lbl.text = 'Seite %d/%d  (%d Treffer)' % (self.page + 1, pages, len(self.filtered))
        name = next((_text(e, 'name', 40) for e in self.entries if str(e['id']) == current), '')
        self.popup.title = 'Asset wählen' + (' - aktuell: ' + name if name else '')

    def _select(self, asset_id):
        try:
            result = self.editor.select_asset(asset_id)
        except Exception:
            result = False
        ok = result is not False and str(getattr(self.editor, 'asset_id', asset_id)) == asset_id
        if ok:
            self.dismiss()  # close only after a successful selection
        else:
            self.page_lbl.text = 'Auswahl fehlgeschlagen'

    def open(self):
        self._refresh()
        if not getattr(self.popup, '_window', None):
            self.popup.open()

    def dismiss(self):
        self.popup.dismiss()
