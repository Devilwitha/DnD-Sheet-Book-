"""Local rotating technical logs, excluding game text and received payloads."""
import logging
import logging.handlers
import platform
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from utils.paths import get_user_saves_dir, resource_path

logger = logging.getLogger('dnd.local')


def configure():
    if logger.handlers:
        return
    handler = logging.handlers.RotatingFileHandler(
        Path(get_user_saves_dir('logs')) / 'diagnostic.log',
        maxBytes=512 * 1024, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    version = Path(resource_path('version.txt')).read_text(encoding='utf-8').strip()
    logger.info('startup version=%s python=%s platform=%s',
                version[:80], platform.python_version(), sys.platform)
    previous = sys.excepthook

    def uncaught(kind, value, tb):
        record_error('uncaught', value)
        previous(kind, value, tb)
    sys.excepthook = uncaught


def record_error(event, error):
    """Keep locations and exception class, never exception text or local variables."""
    frames = traceback.extract_tb(error.__traceback__)
    location = ','.join(f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in frames[-6:])
    logger.error('%s class=%s frames=%s', event, type(error).__name__, location)


def export_diagnostics():
    folder = Path(get_user_saves_dir('logs'))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    target = folder / f'DnD-Diagnose-{stamp}.zip'
    for handler in logger.handlers:
        handler.flush()
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as out:
        for name in ('diagnostic.log', 'diagnostic.log.1', 'diagnostic.log.2', 'diagnostic.log.3'):
            source = folder / name
            if source.is_file() and not source.is_symlink():
                out.write(source, name)
    return str(target)
