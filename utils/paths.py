import os
import sys
import hashlib
import stat
from pathlib import Path

ALLOWED_FOLDERS = frozenset(['characters', 'maps', 'sessions', 'enemies', 'saves', 'backgrounds', 'logs', 'temp', 'archive', 'atlases', 'map_library'])
MAX_BYTES = 32 * 1024 * 1024

def resource_path(relative: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    base = Path(__file__).resolve().parents[1]
    return str(base / relative)

def user_data_dir() -> str:
    if env_dir := os.environ.get('DND_DATA_DIR'):
        path = Path(env_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    if os.name == 'nt':
        appdata = os.environ.get('APPDATA')
        if not appdata:
            raise RuntimeError("APPDATA not set on Windows")
        path = Path(appdata) / 'BolliDnD-Local'
    elif sys.platform == 'darwin':
        path = Path.home() / 'Library' / 'Application Support' / 'BolliDnD-Local'
    else:
        if os.environ.get('ANDROID_ARGUMENT') or os.environ.get('ANDROID_PRIVATE'):
            private = os.environ.get('ANDROID_PRIVATE')
            root = Path(private) if private else Path(__file__).resolve().parents[2]
            path = root / 'dnd-local'
        else:
            xdg = os.environ.get('XDG_DATA_HOME')
            if xdg:
                path = Path(xdg) / 'bollidnd-local'
            else:
                path = Path.home() / '.local' / 'share' / 'bollidnd-local'

    # Android maps /data/user/0 to /data/data. Canonicalize the trusted
    # app-owned base before child-path checks; never canonicalize peer names.
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)

def get_user_saves_dir(folder: str = 'saves') -> str:
    if folder not in ALLOWED_FOLDERS:
        raise ValueError(f"Folder '{folder}' not in whitelist")
    base = Path(user_data_dir())
    target = base / folder
    target.mkdir(parents=True, exist_ok=True)
    return str(target)

def _is_safe_path(p: Path) -> bool:
    try:
        return all(not q.is_symlink() and not (getattr(q.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)) for q in (p, *p.parents) if q.exists())
    except OSError:
        return False

def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def migrate_legacy_saves() -> None:
    legacy_base = Path(resource_path(os.path.join('utils', 'data')))
    dest_base = Path(user_data_dir())
    
    if not legacy_base.exists() or not _is_safe_path(legacy_base) or not _is_safe_path(dest_base):
        return

    items = ['characters', 'maps', 'sessions', 'enemies', 'settings.json']
    
    for item in items:
        src = legacy_base / item
        if not src.exists() or not _is_safe_path(src):
            continue

        if src.is_file():
            dest = dest_base / src.name
            if dest.exists() and not _is_safe_path(dest):
                continue
            _safe_copy_file(src, dest)
        elif src.is_dir():
            if src.name not in ALLOWED_FOLDERS:
                continue
            dest_dir = dest_base / src.name
            if not _is_safe_path(dest_dir):
                continue
            dest_dir.mkdir(parents=True, exist_ok=True)
            for file_obj in src.iterdir():
                if file_obj.is_file() and _is_safe_path(file_obj) and file_obj.stat().st_size <= MAX_BYTES:
                    _safe_copy_file(file_obj, dest_dir / file_obj.name)

def _safe_copy_file(src: Path, dest: Path) -> None:
    if not _is_safe_path(src) or not _is_safe_path(dest) or src.stat().st_size > MAX_BYTES:
        return
    if dest.exists():
        try:
            if _file_sha256(src) == _file_sha256(dest):
                return
        except (OSError, IOError):
            pass
        
        suffix = _file_sha256(src)[:8]
        dest = dest.with_name(f"{dest.stem}_{suffix}{dest.suffix}")
        if dest.exists():
            return

    try:
        with open(src, 'rb') as fsrc:
            data = fsrc.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or not _is_safe_path(dest):
            return
        with open(dest, 'xb') as fdst:
            fdst.write(data)
            fdst.flush()
            os.fsync(fdst.fileno())
    except FileExistsError:
        pass
    except (OSError, IOError):
        pass
