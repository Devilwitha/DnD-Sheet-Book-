#!/bin/bash

# ==============================================================================
# Automatisiertes Installationsskript für die DnD-Sheet-Book Anwendung
# auf einem Raspberry Pi.
#
# Dieses Skript führt die folgenden Aktionen aus:
# 1. Prüft auf Root-Rechte.
# 2. Aktualisiert das System und installiert Systemabhängigkeiten.
# 3. Richtet eine virtuelle Python-Umgebung ein und installiert Pakete.
# 4. Konfiguriert den automatischen Start der Anwendung.
# 5. Richtet einen Watchdog für den automatischen Neustart bei Abstürzen ein.
# 6. Installiert einen benutzerdefinierten Splash-Screen.
#
# ANWENDUNG: Führen Sie dieses Skript mit sudo aus:
# sudo bash install_on_pi.sh
# ==============================================================================

# --- Schritt 1: Überprüfungen und Initialisierung ---

# Prüfen, ob das Skript mit sudo ausgeführt wird
if [ "$EUID" -ne 0 ]; then
  echo "FEHLER: Bitte führen Sie dieses Skript mit sudo aus: sudo bash $0"
  exit 1
fi

# Den ursprünglichen Benutzer ermitteln, der sudo verwendet hat
SUDO_USER_NAME=${SUDO_USER:-$(who am i | awk '{print $1}')}
HOME_DIR=$(getent passwd $SUDO_USER_NAME | cut -d: -f6)

# Den Pfad zum Anwendungsverzeichnis ermitteln (wo sich dieses Skript befindet)
APP_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "================================================="
echo "DnD-Sheet-Book Installer für Raspberry Pi"
echo "================================================="
echo "Installationsverzeichnis: $APP_DIR"
echo "Benutzer-Home-Verzeichnis: $HOME_DIR"
echo "Wird ausgeführt als Benutzer: $SUDO_USER_NAME"
echo "Installation wird in 5 Sekunden gestartet..."
sleep 5

# --- Schritt 2: System-Update und Abhängigkeiten installieren ---

echo ""
echo ">>> [Schritt 2/7] System wird aktualisiert und Abhängigkeiten werden installiert..."
apt-get update
apt-get upgrade -y

# Notwendige Pakete für Kivy und die Anwendung installieren
apt-get install -y python3 git python3-pip python3-venv

# Kivy source installation dependencies from official documentation
# https://kivy.org/doc/stable/installation/installation-rpi.html
apt-get install -y build-essential git make autoconf automake libtool \
      pkg-config cmake ninja-build libasound2-dev libpulse-dev libaudio-dev \
      libjack-dev libsndio-dev libsamplerate0-dev libx11-dev libxext-dev \
      libxrandr-dev libxcursor-dev libxfixes-dev libxi-dev libxss-dev libwayland-dev \
      libxkbcommon-dev libdrm-dev libgbm-dev libgl1-mesa-dev libgles2-mesa-dev \
      libegl1-mesa-dev libdbus-1-dev libibus-1.0-dev libudev-dev fcitx-libs-dev

apt-get install -y xorg wget libxrender-dev lsb-release libraspberrypi-dev raspberrypi-kernel-headers

# Optionale virtuelle Tastatur installieren
apt-get install -y matchbox-keyboard

echo ">>> Systemabhängigkeiten erfolgreich installiert."

# --- Schritt 3: Python-Umgebung einrichten ---

echo ""
echo ">>> [Schritt 3/7] Python virtuelle Umgebung wird eingerichtet..."

# Virtuelle Umgebung als der ursprüngliche Benutzer erstellen
sudo -u $SUDO_USER_NAME python3 -m venv "$APP_DIR/.venv"
echo "Virtuelle Umgebung in '$APP_DIR/.venv' erstellt."

# Python-Pakete aus requirements.txt in der venv installieren
echo "Aktualisiere pip, setuptools und wheel..."
sudo -u $SUDO_USER_NAME "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel

echo "Installiere Python-Pakete (kivy, zeroconf)..."
sudo -u $SUDO_USER_NAME "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements_linux.txt"

echo ">>> Python-Umgebung erfolgreich eingerichtet."

# --- Schritt 4: Autostart für die Anwendung einrichten ---

echo ""
echo ">>> [Schritt 4/7] Autostart für die Anwendung wird konfiguriert..."

# Start-Skript erstellen
cat << EOF > "$HOME_DIR/start_dnd.sh"
#!/bin/bash
# Dieses Skript startet die DnD-Anwendung.

# In das Anwendungsverzeichnis wechseln
cd "$APP_DIR"

# Virtuelle Umgebung aktivieren und Anwendung starten
source .venv/bin/activate
python3 main.py
EOF

chmod +x "$HOME_DIR/start_dnd.sh"
chown $SUDO_USER_NAME:$SUDO_USER_NAME "$HOME_DIR/start_dnd.sh"
echo "Start-Skript 'start_dnd.sh' in '$HOME_DIR' erstellt."

# .desktop-Datei für den Autostart erstellen
AUTOSTART_DIR="$HOME_DIR/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
chown $SUDO_USER_NAME:$SUDO_USER_NAME "$AUTOSTART_DIR"

cat << EOF > "$AUTOSTART_DIR/dnd_app.desktop"
[Desktop Entry]
Type=Application
Name=DnD Character Sheet
Exec=$HOME_DIR/start_dnd.sh
StartupNotify=false
Terminal=false
EOF

chown $SUDO_USER_NAME:$SUDO_USER_NAME "$AUTOSTART_DIR/dnd_app.desktop"
echo ".desktop-Datei für den App-Autostart in '$AUTOSTART_DIR' erstellt."

echo ">>> Anwendungs-Autostart erfolgreich konfiguriert."

# --- Schritt 5: Watchdog für den automatischen Neustart einrichten ---

echo ""
echo ">>> [Schritt 5/7] Watchdog für den automatischen Neustart wird eingerichtet..."

# Watchdog-Skript erstellen
cat << EOF > "$HOME_DIR/watchdog.sh"
#!/bin/bash

APP_DIR="$APP_DIR"
APP_SCRIPT="main.py"
LOCK_FILE=".app_closed_cleanly"

cd "\$APP_DIR"

while true; do
    if ! pgrep -f "python3 \$APP_SCRIPT" > /dev/null; then
        if [ -f "\$LOCK_FILE" ]; then
            rm "\$LOCK_FILE"
            echo "Anwendung wurde sauber beendet. Watchdog pausiert."
        else
            echo "Anwendung abgestürzt oder nicht gestartet. Starte neu..."
            source .venv/bin/activate
            python3 "\$APP_SCRIPT" &
            deactivate
        fi
    fi
    sleep 10
done
EOF

chmod +x "$HOME_DIR/watchdog.sh"
chown $SUDO_USER_NAME:$SUDO_USER_NAME "$HOME_DIR/watchdog.sh"
echo "Watchdog-Skript 'watchdog.sh' in '$HOME_DIR' erstellt."

# .desktop-Datei für den Watchdog-Autostart erstellen
cat << EOF > "$AUTOSTART_DIR/dnd_watchdog.desktop"
[Desktop Entry]
Type=Application
Name=DnD App Watchdog
Exec=$HOME_DIR/watchdog.sh
StartupNotify=false
Terminal=false
EOF

chown $SUDO_USER_NAME:$SUDO_USER_NAME "$AUTOSTART_DIR/dnd_watchdog.desktop"
echo ".desktop-Datei für den Watchdog-Autostart in '$AUTOSTART_DIR' erstellt."

echo ">>> Watchdog erfolgreich eingerichtet."

# --- Schritt 6: Splash-Screen installieren ---

echo ""
echo ">>> [Schritt 6/7] Benutzerdefinierter Splash-Screen wird installiert..."

SPLASH_PATH="/usr/share/plymouth/themes/pix"
if [ -f "$SPLASH_PATH/splash.png" ]; then
    echo "Sichere das originale splash.png nach splash.png.bak"
    mv "$SPLASH_PATH/splash.png" "$SPLASH_PATH/splash.png.bak"
else
    echo "Kein originales splash.png gefunden, fahre fort."
fi

echo "Kopiere neuen Splash-Screen..."
cp "$APP_DIR/osbackground/splash.png" "$SPLASH_PATH/splash.png"

echo "Aktualisiere initramfs (dies kann einen Moment dauern)..."
update-initramfs -u

echo ">>> Splash-Screen erfolgreich installiert."

# --- Schritt 7: Abschluss ---

echo ""
echo ">>> [Schritt 7/7] Installation abgeschlossen!"
echo ""
echo "================================================="
echo "ZUSAMMENFASSUNG"
echo "================================================="
echo "✔ Systemabhängigkeiten sind installiert."
echo "✔ Python-Pakete wurden in einer virtuellen Umgebung installiert."
echo "✔ Die Anwendung wird beim nächsten Start automatisch gestartet."
echo "✔ Ein Watchdog überwacht die Anwendung und startet sie bei Bedarf neu."
echo "✔ Der benutzerdefinierte Splash-Screen ist installiert."
echo ""
echo ">>> Ein Neustart wird empfohlen, um alle Änderungen zu übernehmen."
echo ""
read -p "Drücken Sie ENTER, um das System jetzt neu zu starten, oder STRG+C, um den Vorgang abzubrechen. " -r
echo
echo "Neustart wird eingeleitet..."
reboot
