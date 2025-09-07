# DnD(Sheet&Book)

Ein digitales Charakter- und Zauberbuch für Dungeons & Dragons 5e.

## Betrieb auf einem Raspberry Pi

### Voraussetzungen

- Ein Raspberry Pi (Modell 3B+ oder neuer empfohlen).
- Raspberry Pi OS with Desktop (früher Raspbian).
- Eine stabile Internetverbindung.

### Installation

1.  **System aktualisieren:**
    Öffnen Sie ein Terminal und führen Sie die folgenden Befehle aus, um Ihr System auf den neuesten Stand zu bringen:
    ```bash
    sudo apt-get update
    sudo apt-get upgrade -y
    ```

2.  **Abhängigkeiten installieren:**
    Kivy benötigt einige Systembibliotheken, um zu funktionieren. Installieren Sie diese mit dem folgenden Befehl:
    ```bash
    sudo apt-get install -y git python3-pip
    sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
       pkg-config libgl1-mesa-dev libgles2-mesa-dev \
       python3-setuptools libgstreamer1.0-dev git-core gstreamer1.0-plugins-base \
       gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
       gstreamer1.0-libav python3-dev
    ```

3.  **Kivy installieren:**
    Installieren Sie Kivy mit pip:
    ```bash
    pip3 install kivy
    ```

4.  **Anwendung herunterladen:**
    Klonen Sie dieses Repository in Ihr Home-Verzeichnis (ersetzen Sie `IHRE_REPOSITORY_URL` mit der korrekten URL):
    ```bash
    cd ~
    git clone https://github.com/Devilwitha/DnD-Sheet-Book-.git DnD-Sheet-Book
    ```

### Manueller Start

Nach der Installation können Sie die Anwendung manuell starten:
```bash
cd ~/DnD-Sheet-Book
python3 main.py
```

### Automatischer Start beim Booten

Um die Anwendung automatisch beim Start der grafischen Benutzeroberfläche zu starten, gehen Sie wie folgt vor:

1.  **Start-Skript erstellen:**
    Dieses Skript wechselt in das richtige Verzeichnis und startet die Anwendung.
    ```bash
    nano ~/DnD-Sheet-Book/start_dnd.sh
    ```
    Fügen Sie den folgenden Inhalt in die Datei ein:
    ```bash
    #!/bin/bash
    cd /home/pi/DnD-Sheet-Book
    python3 main.py
    ```
    Speichern und schließen Sie die Datei (Strg+X, dann J, dann Enter).

    Machen Sie das Skript ausführbar:
    ```bash
    chmod +x ~/DnD-Sheet-Book/start_dnd.sh
    ```

2.  **Autostart-Eintrag erstellen:**
    Erstellen Sie eine `.desktop`-Datei im Autostart-Verzeichnis.
    ```bash
    mkdir -p ~/.config/autostart
    nano ~/.config/autostart/dnd_app.desktop
    ```
    Fügen Sie den folgenden Inhalt in die Datei ein:
    ```ini
    [Desktop Entry]
    Type=Application
    Name=DnD Character Sheet
    Exec=/home/pi/DnD-Sheet-Book/start_dnd.sh
    StartupNotify=false
    Terminal=false
    ```
    Speichern und schließen Sie die Datei.

Nach einem Neustart sollte die Anwendung automatisch starten.
