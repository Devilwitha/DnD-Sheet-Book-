"""Explicit, on-device camera scan; no photos, storage access or external scanner app."""
_callback = None
REQUEST_CODE = 29451


def start_scan(callback):
    global _callback
    from kivy.utils import platform
    if platform != 'android':
        callback(None, 'Der Kamerascan ist in der Android-App verfügbar. Am PC bitte Adresse und Code verwenden.')
        return
    if _callback is not None:
        return
    from android import activity
    from kivy.clock import Clock
    from jnius import autoclass
    def on_result(request, result, intent):
        global _callback
        if request != REQUEST_CODE:
            return
        activity.unbind(on_activity_result=on_result)
        _callback = None
        text = str(intent.getStringExtra('dnd_qr')) if result == -1 and intent is not None else None
        error = intent.getStringExtra('dnd_error') if intent is not None else None
        Clock.schedule_once(lambda dt: callback(text, str(error) if error else None))
    try:
        host = autoclass('org.kivy.android.PythonActivity').mActivity
        intent = autoclass('android.content.Intent')()
        intent.setClassName(host.getPackageName(), 'ch.bollisoft.dndlocal.scan.QrScanActivity')
        _callback = on_result  # retain callback until ActivityResult, including permission dialogs
        activity.bind(on_activity_result=on_result)
        host.startActivityForResult(intent, REQUEST_CODE)
    except Exception:
        activity.unbind(on_activity_result=on_result)
        _callback = None
        callback(None, 'Der Kamerascanner konnte nicht gestartet werden. Bitte Adresse und Code manuell eingeben.')
