"""User-selected document export through Android SAF, without storage permission."""
from pathlib import Path

_pending = None
REQUEST = 5403


def save_document(path, completed):
    global _pending
    if _pending is not None:
        completed('Es ist bereits ein Export geöffnet.')
        return
    from android import activity
    from jnius import autoclass
    from kivy.clock import Clock
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    current = PythonActivity.mActivity

    def result(request, code, data):
        global _pending
        if request != REQUEST:
            return
        activity.unbind(on_activity_result=result)
        _pending = None
        message = 'Export abgebrochen.'
        if code == -1 and data is not None:
            stream = None
            try:
                stream = current.getContentResolver().openOutputStream(data.getData(), 'w')
                with open(path, 'rb') as source:
                    while chunk := source.read(64 * 1024):
                        stream.write(bytearray(chunk))
                stream.flush()
                message = 'Diagnose-ZIP gespeichert.'
            except Exception as error:
                from utils.diagnostics import record_error
                record_error('android_export', error)
                message = 'Die gewählte Datei konnte nicht geschrieben werden.'
            finally:
                if stream is not None:
                    stream.close()
        Clock.schedule_once(lambda dt: completed(message))

    intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType('application/zip')
    intent.putExtra(Intent.EXTRA_TITLE, Path(path).name)
    activity.bind(on_activity_result=result)
    _pending = result
    try:
        current.startActivityForResult(intent, REQUEST)
    except Exception:
        _pending = None
        activity.unbind(on_activity_result=result)
        raise
