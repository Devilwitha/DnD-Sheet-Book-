# DnD(Sheet&Book)

Ein digitaler Charakterbogen und ein Zauberbuch für Dungeons & Dragons 5e.

## Ausführen auf einem Raspberry Pi

### Voraussetzungen

- Ein Raspberry Pi (Modell 4 oder neuer empfohlen).
- Raspberry Pi OS mit Desktop. **Hinweis:** Eine grafische Desktop-Umgebung ist erforderlich, um diese Anwendung auszuführen. Sie funktioniert nicht in einer monitorlosen oder reinen SSH-Umgebung ohne X11-Weiterleitung.
- Eine stabile Internetverbindung.

### Installation

1.  **System aktualisieren:**
    Öffnen Sie ein Terminal auf Ihrem Raspberry Pi und führen Sie die folgenden Befehle aus, um sicherzustellen, dass Ihr System auf dem neuesten Stand ist:
    ```bash
    sudo apt-get update
    sudo apt-get upgrade -y
    ```

2.  **Systemabhängigkeiten installieren:**
    Kivy benötigt mehrere Systembibliotheken, um korrekt zu funktionieren. Installieren Sie diese mit dem folgenden Befehl:
    ```bash
    sudo apt-get install -y git python3-pip
    sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
       pkg-config libgl1-mesa-dev libgles2-mesa-dev \
       python3-setuptools libgstreamer1.0-dev git-core gstreamer1.0-plugins-base \
       gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
       gstreamer1.0-libav python3-dev
    ```

3.  **Einrichtung der virtuellen Tastatur (für Touchscreens):**
    Wenn Sie einen Touchscreen verwenden, benötigen Sie eine virtuelle Tastatur für die Texteingabe. Installieren Sie sie mit:
    ```bash
    sudo apt-get update && sudo apt-get install -y matchbox-keyboard
    ```

4.  **Anwendung klonen:**
    Laden Sie die Anwendung von GitHub herunter:
    ```bash
    cd ~
    git clone https://github.com/Devilwitha/DnD-Sheet-Book-.git DnD-Sheet-Book
    cd ~/DnD-Sheet-Book
    ```

5.  **Python-Pakete installieren:**
    Neuere Versionen von Raspberry Pi OS schützen Systempakete. Die empfohlene Methode zur Installation von Python-Paketen ist die Verwendung einer virtuellen Umgebung.

    **Methode 1: Virtuelle Umgebung (Empfohlen)**
    
    Erstellen und aktivieren Sie eine virtuelle Umgebung:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
    Installieren Sie nun Kivy und andere Abhängigkeiten. Ihre Terminal-Eingabeaufforderung sollte `(.venv)` anzeigen.
    ```bash
    pip install -r requirements.txt
    ```
    Um die App später auszuführen, müssen Sie die virtuelle Umgebung erneut mit `source .venv/bin/activate` aktivieren.

    **Methode 2: Systemweite Installation (Fallback)**

    Wenn Sie Probleme beim Erstellen einer virtuellen Umgebung haben, können Sie die Pakete systemweit installieren. Dies wird nicht empfohlen, da es andere Anwendungen stören kann.
    ```bash
    pip3 install --break-system-packages kivy

    or

    pip install -r --break-system-packages requirements.txt

    ```

### Manueller Start

Nach der Installation können Sie die Anwendung manuell starten.

**Wenn Sie eine virtuelle Umgebung verwendet haben:**
```bash
cd ~/DnD-Sheet-Book
source .venv/bin/activate
python3 main.py
```

**Wenn Sie systemweit installiert haben:**
```bash
cd ~/DnD-Sheet-Book
python3 main.py
```

### Automatischer Start beim Hochfahren

So stellen Sie sicher, dass die Anwendung automatisch mit der grafischen Benutzeroberfläche startet:

1.  **Start-Skript erstellen:**
    Dieses Skript aktiviert die virtuelle Umgebung (falls verwendet) und startet die Anwendung.
    ```bash
    nano start_dnd.sh
    ```
    Fügen Sie den folgenden Inhalt hinzu. **Wichtig:** Wenn Sie keine virtuelle Umgebung verwendet haben, lassen Sie die `source`-Zeile weg.
    ```bash
    #!/bin/bash
    cd /home/pi/DnD-Sheet-Book
    python3 main.py
    ```
    Speichern und schließen Sie die Datei (Strg+X, dann Y, dann Enter).

    Machen Sie das Skript ausführbar:
    ```bash
    chmod +x start_dnd.sh
    ```

2.  **Autostart-Eintrag erstellen:**
    Erstellen Sie eine `.desktop`-Datei im Autostart-Verzeichnis.
    ```bash
    mkdir -p ~/.config/autostart
    nano ~/.config/autostart/dnd_app.desktop
    ```
    Fügen Sie den folgenden Inhalt hinzu. **Wichtig:** Stellen Sie sicher, dass der `Exec`-Pfad mit dem Speicherort Ihres Skripts übereinstimmt (z. B. `/home/devil/DnD-Sheet-Book/start_dnd.sh`, wenn Ihr Benutzer `devil` ist).
    ```ini
    [Desktop Entry]
    Type=Application
    Name=DnD Character Sheet
    Exec=/home/pi/DnD-Sheet-Book/start_dnd.sh
    StartupNotify=false
    Terminal=false
    ```
    Speichern und schließen Sie die Datei.

Die Anwendung sollte jetzt nach einem Neustart automatisch starten.

## Splashscreen Installation
Schritt-für-Schritt-Anleitung
Hier ist die Vorgehensweise, um deinen eigenen Splash-Screen einzurichten:

1. Bild vorbereiten
Dateiname: Dein Bild muss splash.png heissen.

Format: Es muss im PNG-Format vorliegen.

Auflösung: Idealerweise sollte die Auflösung deines Bildes der deines Displays entsprechen, um Verzerrungen zu vermeiden.

2. Ins richtige Verzeichnis kopieren
Dein vorbereitetes Bild muss in das Verzeichnis /usr/share/plymouth/themes/pix/ kopiert werden.

Öffne ein Terminal auf deinem Raspberry Pi.

Sichere das Originalbild (optional, aber empfohlen), damit du es später wiederherstellen kannst:

Bash
```
sudo mv /usr/share/plymouth/themes/pix/splash.png /usr/share/plymouth/themes/pix/splash.png.bak
```
Kopiere dein eigenes Bild in das Verzeichnis. Angenommen, dein Bild befindet sich im Home-Verzeichnis (/home/pi/dein-bild.png), dann lautet der Befehl:

Bash
```
sudo cp ~/DnD-Sheet-Book/osbackground/splash.png /usr/share/plymouth/themes/pix/splash.png
```
Ersetze /home/pi/dein-bild.png mit dem tatsächlichen Pfad zu deiner Datei.

3. System aktualisieren
Damit dein neues Bild beim Systemstart geladen wird, musst du die "initial ramdisk" (initramfs) aktualisieren. Dies ist ein entscheidender Schritt unter Bookworm.

Führe den folgenden Befehl im Terminal aus:

Bash
```
sudo update-initramfs -u
```
4. Neustart
Nachdem der vorherige Befehl abgeschlossen ist, starte deinen Raspberry Pi neu, um das Ergebnis zu sehen:

Bash
```
sudo reboot
```
Dein Raspberry Pi sollte nun mit deinem benutzerdefinierten Splash-Screen starten.
