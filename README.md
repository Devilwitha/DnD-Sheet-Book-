# DnD(Sheet&Book)

A digital character sheet and spellbook for Dungeons & Dragons 5e.

## Running on a Raspberry Pi

### Prerequisites

- A Raspberry Pi (Model 3B+ or newer recommended).
- Raspberry Pi OS with Desktop. **Note:** A graphical desktop environment is required to run this application. It will not work in a headless or SSH-only environment without X11 forwarding.
- A stable internet connection.

### Installation

1.  **Update Your System:**
    Open a terminal on your Raspberry Pi and run the following commands to ensure your system is up-to-date:
    ```bash
    sudo apt-get update
    sudo apt-get upgrade -y
    ```

2.  **Install System Dependencies:**
    Kivy requires several system libraries to function correctly. Install them with the following command:
    ```bash
    sudo apt-get install -y git python3-pip
    sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
       pkg-config libgl1-mesa-dev libgles2-mesa-dev \
       python3-setuptools libgstreamer1.0-dev git-core gstreamer1.0-plugins-base \
       gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
       gstreamer1.0-libav python3-dev
    ```

3.  **Virtual Keyboard Setup (for Touchscreens):**
    If you are using a touchscreen, you will need a virtual keyboard for text input. Install it with:
    ```bash
    sudo apt-get update && sudo apt-get install -y matchbox-keyboard
    ```

4.  **Clone the Application:**
    Download the application from GitHub:
    ```bash
    cd ~
    git clone https://github.com/Devilwitha/DnD-Sheet-Book-.git DnD-Sheet-Book
    cd ~/DnD-Sheet-Book
    ```

5.  **Install Python Packages:**
    Recent versions of Raspberry Pi OS protect system packages. The recommended way to install Python packages is within a virtual environment.

    **Method 1: Virtual Environment (Recommended)**
    
    Create and activate a virtual environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
    Now, install Kivy and other dependencies. Your terminal prompt should show `(.venv)`.
    ```bash
    pip install kivy
    ```
    To run the app later, you will need to activate the virtual environment again with `source .venv/bin/activate`.

    **Method 2: System-wide Install (Fallback)**

    If you have issues with creating a virtual environment, you can install the packages system-wide. This is not recommended as it can interfere with other applications.
    ```bash
    pip3 install --break-system-packages kivy
    ```

### Manual Start

After installation, you can start the application manually.

**If you used a virtual environment:**
```bash
cd ~/DnD-Sheet-Book
source .venv/bin/activate
python3 main.py
```

**If you installed system-wide:**
```bash
cd ~/DnD-Sheet-Book
python3 main.py
```

### Automatic Start on Boot

To make the application start automatically with the graphical user interface:

1.  **Create a Start Script:**
    This script will activate the virtual environment (if used) and start the application.
    ```bash
    nano start_dnd.sh
    ```
    Add the following content. **Important:** If you did not use a virtual environment, omit the `source` line.
    ```bash
    #!/bin/bash
    cd /home/pi/DnD-Sheet-Book
    python3 main.py
    ```
    Save and close the file (Ctrl+X, then Y, then Enter).

    Make the script executable:
    ```bash
    chmod +x start_dnd.sh
    ```

2.  **Create Autostart Entry:**
    Create a `.desktop` file in the autostart directory.
    ```bash
    mkdir -p ~/.config/autostart
    nano ~/.config/autostart/dnd_app.desktop
    ```
    Add the following content. **Important:** Make sure the `Exec` path matches the location of your script (e.g., `/home/devil/DnD-Sheet-Book/start_dnd.sh` if your user is `devil`).
    ```ini
    [Desktop Entry]
    Type=Application
    Name=DnD Character Sheet
    Exec=/home/pi/DnD-Sheet-Book/start_dnd.sh
    StartupNotify=false
    Terminal=false
    ```
    Save and close the file.

The application should now start automatically after a reboot.



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
