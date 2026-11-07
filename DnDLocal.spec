from pathlib import Path
from kivy_deps import sdl2, glew
root = Path(SPECPATH)
datas = []
for directory, suffixes in [('ui', {'.kv'}), ('utils/data/json_data', {'.json'}), ('logo', {'.png'}), ('osbackground', {'.png', '.jpg'}), ('licenses', {'.txt'}), ('assets/map_assets', {'.jpg', '.json'}), ('assets/fonts', {'.ttf'})]:
    for p in (root / directory).rglob('*'):
        if p.is_file() and p.suffix.lower() in suffixes:
            datas.append((str(p), str(p.parent.relative_to(root))))
datas += [(str(root / name), str(Path(name).parent)) for name in ['version.txt', 'CREDITS.txt', 'changelog.txt', 'utils/data/dnd.db']]
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=datas,
             hiddenimports=['ui.custom_widgets', 'kivy.uix.tabbedpanel', 'kivy.uix.spinner', 'kivy.uix.filechooser', 'kivy.uix.modalview'],
             excludes=['pytest','tkinter','matplotlib','IPython'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DnDLocal', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / 'logo/logo.png'))
coll = COLLECT(exe, a.binaries, a.datas, *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
               strip=False, upx=False, name='DnDLocal')
