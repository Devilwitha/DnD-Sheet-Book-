"""Host invitation shared by lobby and running session."""
from kivy.metrics import dp
from kivy.graphics.texture import Texture
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from utils.helpers import create_styled_popup
from utils.join_qr import make_join_payload
from utils.wire import get_local_ipv4s


def qr_texture(payload):
    import segno
    matrix = list(segno.make_qr(payload, error='m').matrix_iter(scale=4, border=4))
    size = len(matrix)
    pixels = bytes(0 if value else 255 for row in reversed(matrix) for value in row for _ in range(3))
    texture = Texture.create(size=(size, size), colorfmt='rgb')
    texture.blit_buffer(pixels, colorfmt='rgb', bufferfmt='ubyte')
    texture.mag_filter = 'nearest'
    texture.min_filter = 'nearest'
    return texture


def show_join_dialog(network_manager):
    content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
    code = network_manager.join_code
    port = network_manager.port
    addresses = get_local_ipv4s()
    selector = Spinner(text=addresses[0] if addresses else 'Keine LAN-Adresse', values=addresses,
                       size_hint_y=None, height=dp(48))
    content.add_widget(selector)
    info = Label(text='QR-Code scannen. Die App probiert die verfügbaren LAN-/WLAN-Adressen automatisch.',
                 size_hint_y=None, height=dp(52), halign='center')
    info.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
    content.add_widget(info)
    qr = Image(fit_mode='contain')
    content.add_widget(qr)
    label = Label(size_hint_y=None, height=dp(64), font_size='18sp', halign='center')
    label.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)))
    content.add_widget(label)
    def refresh(*args):
        label.text = f'{selector.text}:{port}\nBeitrittscode: {code or "–"}'
        try:
            qr.texture = qr_texture(make_join_payload(selector.text, port, code, addresses=addresses))
        except ValueError:
            qr.texture = None
            info.text = 'Keine passende lokale Adresse. Netzwerkverbindung prüfen oder Adresse manuell eingeben.'
    selector.bind(text=refresh)
    refresh()
    help_button = Button(text='Verbindungshilfe', size_hint_y=None, height=dp(48))
    def help_connection(*args):
        from ui.network_help import show_network_help
        show_network_help(network_manager)
    help_button.bind(on_release=help_connection)
    content.add_widget(help_button)
    close = Button(text='Zurück zur Sitzung', size_hint_y=None, height=dp(48))
    content.add_widget(close)
    popup = create_styled_popup(title='Spieler einladen', content=content, size_hint=(0.92, 0.92))
    close.bind(on_release=popup.dismiss)
    popup.open()
    return popup
