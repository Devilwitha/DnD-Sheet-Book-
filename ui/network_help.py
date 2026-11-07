"""A connection checklist and explicit Windows setup, usable during a running game."""
import threading
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from utils.helpers import create_styled_popup, apply_styles_to_widget
from utils.network_setup import local_interfaces
from utils import windows_network


def show_network_help(network_manager, initial_report=None, on_continue=None):
    content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
    scroll = ScrollView(do_scroll_x=False)
    text = Label(text='Lokale Verbindung wird geprüft …', size_hint_y=None, halign='left')
    text.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)),
              texture_size=lambda w, v: setattr(w, 'height', v[1] + dp(12)))
    scroll.add_widget(text)
    content.add_widget(scroll)
    setup = Button(text='Windows-Freigabe einrichten', size_hint_y=None, height=dp(52), disabled=True)
    if windows_network.supported():
        content.add_widget(setup)
    retry = Button(text='Erneut prüfen', size_hint_y=None, height=dp(48))
    close = Button(text='Weiter zur Sitzung' if on_continue else 'Zurück', size_hint_y=None, height=dp(48))
    content.add_widget(retry)
    content.add_widget(close)
    popup = create_styled_popup(title='Verbindungshilfe', content=content, size_hint=(.94, .9), auto_dismiss=on_continue is None)
    active = True
    busy = False

    def display(report, rows, result=None):
        nonlocal busy
        busy = False
        if not active:
            return
        if result == 'cancelled':
            status = 'Windows-Einrichtung abgebrochen. Du kannst es später erneut versuchen.'
        elif report.get('policy_blocks'):
            status = 'Eine Windows-Richtlinie sperrt lokale Freigaben. Diese kann die App nicht aufheben.'
        elif report.get('configured'):
            status = 'Die lokale Windows-Freigabe ist eingerichtet. Jetzt den aktuellen QR-Code am Smartphone scannen.'
        elif report.get('unknown'):
            status = 'Die Windows-Freigabe konnte nicht sicher geprüft werden. Die Einrichtung ist über den Button möglich.'
        elif report.get('supported'):
            status = 'Die Windows-Freigabe für diese App ist noch nicht vollständig eingerichtet.'
        else:
            status = 'Die Windows-Einrichtung steht im installierten Windows-DM-Programm zur Verfügung.'
        if result in ('failed', 'busy'):
            status = 'Windows-Einrichtung nicht abgeschlossen. Bitte erneut prüfen. ' + status
        addresses = '\n'.join(f"• {r['address']} ({r['adapter']})" for r in rows) or 'Keine lokale IPv4-Adresse gefunden.'
        host = 'DM-Sitzung läuft.' if network_manager.mode == 'dm' and network_manager.running else 'Zuerst eine DM-Sitzung starten.'
        text.text = (f'{host}\n\n{status}\n\nAdressen dieses Geräts:\n{addresses}\n\n'
                     'Die Windows-Einrichtung erlaubt ausschließlich DnD Lokal Verbindungen aus dem lokalen Netzwerk. '
                     'Vorhandene lokale Sperren für diese App werden ersetzt. Windows fragt gegebenenfalls einmalig nach Administratorbestätigung. '
                     'Die Änderung gilt auch, wenn Windows dieses WLAN als öffentlich einstuft.\n\n'
                     'Beide Geräte ins normale WLAN verbinden. Gast-WLAN, VPNs und manche Hotspots können direkte Geräteverbindungen verhindern. '
                     'Ein anderer gemeinsamer Router oder ein Hotspot mit erlaubter Gerätekommunikation ist dann eine Alternative.\n\n'
                     'Der aktuelle QR-Code enthält mehrere Adressen, die das Smartphone automatisch versucht. '
                     'Nach einem Netzwerkwechsel die Einladung neu öffnen.\n\n'
                     'Diese Prüfung bestätigt die lokale Einrichtung; die Erreichbarkeit vom Smartphone kann nur ein Beitritt bestätigen.')
        setup.disabled = bool(report.get('configured')) or bool(report.get('policy_blocks'))
        retry.disabled = False
        close.disabled = False
        if result == 'success' and report.get('configured') and on_continue:
            popup.dismiss()
            on_continue()

    def work(configure=False):
        try:
            result = windows_network.request_firewall_setup() if configure else None
            report = windows_network.firewall_status()
            # The elevated helper verifies effective rules before returning success.
            # Some Windows accounts cannot read firewall policies without elevation.
            if result == 'success' and report.get('unknown'):
                report = {'supported': True, 'configured': True}
            rows = local_interfaces()
        except Exception:
            result, report, rows = 'failed', {'supported': windows_network.supported(), 'unknown': True}, []
        Clock.schedule_once(lambda dt: display(report, rows, result))

    def run(configure=False):
        nonlocal busy
        if busy:
            return
        busy = True
        setup.disabled = retry.disabled = True
        close.disabled = bool(on_continue)
        text.text = 'Bitte die Windows-Bestätigung beachten …' if configure else 'Lokale Verbindung wird geprüft …'
        threading.Thread(target=work, args=(configure,), daemon=True).start()

    def dismissed(*args):
        nonlocal active
        active = False

    setup.bind(on_release=lambda *_: run(True))
    retry.bind(on_release=lambda *_: run())
    def continue_or_close(*args):
        popup.dismiss()
        if on_continue:
            on_continue()
    close.bind(on_release=continue_or_close)
    popup.bind(on_dismiss=dismissed)
    apply_styles_to_widget(content)
    popup.open()
    if initial_report is None:
        run()
    else:
        display(initial_report, local_interfaces())
    return popup


def prepare_host(screen, start):
    """Check before listening, so setup can avoid the initial Windows block dialog."""
    if not windows_network.supported() or getattr(screen.app, '_network_setup_checked', False):
        start()
        return
    manager = screen.network_manager
    generation = screen._enter_gen
    def checked(report):
        if generation != screen._enter_gen or not screen.manager or screen.manager.current != 'dm_lobby':
            return
        screen.app._network_setup_checked = True
        if report.get('configured'):
            start()
        else:
            show_network_help(manager, initial_report=report, on_continue=start)
    def worker():
        report = windows_network.firewall_status()
        Clock.schedule_once(lambda dt: checked(report))
    threading.Thread(target=worker, daemon=True).start()
