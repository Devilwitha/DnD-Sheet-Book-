# DnD Sheet & Book / DnD Lokal

Digitaler Spieltisch für Android und Windows mit Charakterverwaltung, lokalem
DM-/Spieler-Netzwerk, Sitzungsarchiv und Kartenwerkstatt. Grundlage ist der
[Beta-Zweig von DnD Sheet & Book](https://github.com/Devilwitha/DnD-Sheet-Book-/tree/beta)
von BolliSoft. Die ursprünglichen Mitwirkenden stehen in [CREDITS.txt](CREDITS.txt).

## Aus dem Quellcode starten

Python 3.12 und eine virtuelle Umgebung verwenden:

```sh
python -m venv .venv
```

Unter Windows `.venv\Scripts\activate`, unter Linux `source .venv/bin/activate`
ausführen. Danach:

```sh
python -m pip install -r requirements.txt
python main.py
```

Beim ersten Start wird die Datenbank aus `utils/data/json_data` im lokalen
Benutzerprofil erzeugt. Spielstände, Einstellungen und Logs gehören nicht zum
Quellcode. `DND_DATA_DIR` kann für ein separates Testprofil gesetzt werden.

## Bedienung

- Unter **DM Spiel** eine Kampagne vorbereiten oder eine Sitzung hosten.
- Spieler verbinden sich im selben lokalen Netz per Sitzungscode oder QR-Code;
  der DM bestätigt den Beitritt. Ein Gastnetz mit Geräteisolation kann Verbindungen
  verhindern. Windows kann eine Netzwerkfreigabe für die App verlangen.
- Die **Kartenwerkstatt** ist auch ohne geöffnete Kampagne verfügbar. Der Atlas
  verbindet Welt, Regionen, Orte und Innenräume; gespeicherte Karten lassen sich
  in Kampagnen wiederverwenden.
- Das **Sitzungsarchiv** hält Ereignisse und DM-Notizen fest und erlaubt Exporte
  zur Vorbereitung des nächsten Spielabends.

## Tests

```sh
python -m pip install -r requirements_test.txt
python -m pytest
```

Die Unit-Tests verwenden isolierte Daten und Kivy-Stubs. Zusätzlich prüfen diese
Skripte echte Kivy-Fenster und benötigen eine grafische Desktop-Sitzung:

```sh
python scripts/verify_map_editor.py
python scripts/verify_map_editor_interactions.py
python scripts/verify_region_context.py
python scripts/verify_live_play.py
```

Der letzte Test startet eine lokale TCP-Testsitzung. Alle Skripte verwenden eigene
Testprofile. Screenshots und Ergebnisse landen unter `.test-output`; mit
`DND_TEST_OUTPUT` lässt sich ein anderer Ausgabeordner wählen. Der Regionentest
erzeugt seine Karten selbst und benötigt keine privaten Spielstände.

## Windows-Paket erstellen

```sh
python -m pip install -r requirements_windows.txt
python scripts/prepare_build.py
python -m PyInstaller --noconfirm --clean DnDLocal.spec
```

Das vollständige Verzeichnis `dist/DnDLocal` weitergeben. Die EXE benötigt die
beiliegenden Ressourcen. Die generierte Datenbank und Pakete werden nicht eingecheckt.

## Android-Paket erstellen

Der native Build benötigt Linux bzw. WSL2, JDK 17, Buildozer 1.5.0 und die
[Buildozer-Systemabhängigkeiten](https://buildozer.readthedocs.io/en/latest/installation.html).
Die vollständigen Befehle stehen auch in `.github/workflows/build-android.yml`.

```sh
python scripts/prepare_build.py
buildozer -v android debug
```

`buildozer.spec` bindet den Java-QR-Scanner, ZXing, Kartenbilder und PDF-Schrift ein.
`recipes/reportlab` verwendet ReportLab 4 ohne optionale native Beschleuniger.
Dieser native Android-Buildpfad ist noch nicht durch einen vollständigen Neubau
und Gerätetest verifiziert. Die vorhandenen lokal installierten APKs wurden über
einen separaten Paketierungsweg erstellt; dessen lokale Werkzeuge und Schlüssel
sind kein Bestandteil des Projekts.
Insbesondere müssen die nativen Pakete Pillow und psutil mit der festgelegten
python-for-android-Version geprüft und gegebenenfalls ihre Baurezepte angepasst
werden. Der manuelle Android-Workflow ist daher noch kein bestätigter Release-Build.

Vor einer Android-Veröffentlichung müssen Paketkennung, Versionscode und Signierung
festgelegt werden. Ein Update einer vorhandenen Installation benötigt dieselbe
Paketkennung und denselben Signaturschlüssel sowie einen passenden Versionscode.
Die Build-Workflows werden manuell gestartet und erzeugen nur Build-Artefakte;
sie veröffentlichen keine Releases.

## Ressourcen und Lizenzen

`assets/map_assets/catalog.json` beschreibt die enthaltenen Kartenbilder samt
Prüfsummen und Qualitätsstatus. Manche Bilder benötigen noch grafische Nacharbeit.
Die Asset-Erstellungswerkstatt gehört nicht zum Laufzeitprojekt.

Vorhandene Lizenztexte für gebündelte Komponenten und Schriften liegen unter
`licenses`. Diese Texte sind keine pauschale Lizenz für den gesamten Projektcode,
die übernommenen Regeldaten oder alle Bilder. Für eine öffentliche Weitergabe
bleibt deren jeweilige Herkunft und Nutzungsfreigabe zu klären.
