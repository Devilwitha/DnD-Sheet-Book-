#!/bin/bash

# ==============================================================================
# Automatisiertes Installationsskript für die DnD-Sheet-Book Anwendung
# auf Debian-basierten Linux-Systemen.
#
# Dieses Skript führt die folgenden Aktionen aus:
# 1. Prüft auf Root-Rechte.
# 2. Aktualisiert das System und installiert Systemabhängigkeiten für Kivy.
# 3. Richtet eine virtuelle Python-Umgebung ein und installiert die Pakete.
# 4. Konfiguriert den automatischen Start der Anwendung.
# 5. Richtet einen Watchdog für den automatischen Neustart bei Abstürzen ein.
#
# HINWEIS: Raspberry Pi-spezifische Funktionen wie der Splash-Screen wurden
# entfernt, um die Kompatibilität mit generischen Debian-Systemen zu gewährleisten.
#
# ANWENDUNG: Führen Sie dieses Skript mit sudo aus:
# sudo bash install.sh
# ==============================================================================

# --- Schritt 1: Überprüfungen und Initialisierung ---

# Prüfen, ob das Skript mit sudo ausgeführt wird
if [ "$EUID" -ne 0 ]; then
  echo "FEHLER: Bitte führen Sie dieses Skript mit sudo aus: sudo bash $0"
  exit 1
fi

# Den ursprünglichen Benutzer ermitteln, der sudo verwendet hat
if [ -n "$SUDO_USER" ]; then
    SUDO_USER_NAME=$SUDO_USER
else
    SUDO_USER_NAME=$(who am i | awk '{print $1}')
fi

HOME_DIR=$(getent passwd $SUDO_USER_NAME | cut -d: -f6)

# Den Pfad zum Anwendungsverzeichnis ermitteln (wo sich dieses Skript befindet)
APP_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "================================================="
echo "DnD-Sheet-Book Installer für Linux"
echo "================================================="
echo "Installationsverzeichnis: $APP_DIR"
echo "Benutzer-Home-Verzeichnis: $HOME_DIR"
echo "Wird ausgeführt als Benutzer: $SUDO_USER_NAME"
echo "Installation wird in 5 Sekunden gestartet..."
sleep 5

# --- Schritt 2: System-Update und Abhängigkeiten installieren ---

echo ""
echo ">>> [Schritt 2/5] System wird aktualisiert und Abhängigkeiten werden installiert..."
apt-get update
apt-get upgrade -y

# Notwendige Basispakete installieren
apt-get install -y python3 git python3-pip python3-venv

# Kivy-Abhängigkeiten für Debian/Ubuntu installieren
# Diese ersetzen die alten, plattformspezifischen Pakete.
apt-get install -y \
    build-essential \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgl1-mesa-dev

# Optionale virtuelle Tastatur installieren
apt-get install -y matchbox-keyboard

echo ">>> Systemabhängigkeiten erfolgreich installiert."

# --- Schritt 3: Python-Umgebung einrichten ---

echo ""
echo ">>> [Schritt 3/5] Python virtuelle Umgebung wird eingerichtet..."

# Vorhandene virtuelle Umgebung für eine saubere Installation entfernen
if [ -d "$APP_DIR/.venv" ]; then
    echo "Entferne vorhandene virtuelle Umgebung..."
    rm -rf "$APP_DIR/.venv"
fi

# Virtuelle Umgebung als der ursprüngliche Benutzer erstellen
sudo -u $SUDO_USER_NAME python3 -m venv "$APP_DIR/.venv"
echo "Virtuelle Umgebung in '$APP_DIR/.venv' erstellt."

# Python-Pakete aus requirements.txt in der venv installieren
echo "Aktualisiere pip, setuptools und wheel..."
sudo -u $SUDO_USER_NAME "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel

echo "Installiere Python-Pakete (kivy, zeroconf)..."
sudo -u $SUDO_USER_NAME "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements_linux.txt"

# Überprüfen, ob die Installation erfolgreich war
if [ $? -ne 0 ]; then
    echo "FEHLER: Die Installation der Python-Pakete ist fehlgeschlagen."
    echo "Bitte überprüfen Sie die Fehlermeldungen oben."
    exit 1
fi

echo ">>> Python-Umgebung erfolgreich eingerichtet."

# --- Schritt 4: Autostart für die Anwendung einrichten ---

echo ""
echo ">>> [Schritt 4/5] Autostart für die Anwendung wird konfiguriert..."

# Start-Skript erstellen
cat << EOF > "$HOME_DIR/start_dnd.sh"
#!/bin/bash
# Dieses Skript startet die DnD-Anwendung.

# In das Anwendungsverzeichnis wechseln, um sicherzustellen, dass die App ihre Dateien findet.
cd "$APP_DIR"

# Virtuelle Umgebung mit absolutem Pfad aktivieren und Anwendung starten.
source "$APP_DIR/.venv/bin/activate"
python3 "$APP_DIR/main.py"
EOF

chmod 755 "$HOME_DIR/start_dnd.sh"
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
echo ">>> [Schritt 5/5] Watchdog für den automatischen Neustart wird eingerichtet..."

# Watchdog-Skript erstellen
cat << EOF > "$HOME_DIR/watchdog.sh"
#!/bin/bash

APP_DIR="$APP_DIR"
APP_SCRIPT="main.py"
LOCK_FILE=".app_closed_cleanly"

# In das Anwendungsverzeichnis wechseln, um sicherzustellen, dass die App ihre Dateien findet.
cd "\$APP_DIR"

while true; do
    # Überprüfen, ob der Prozess bereits läuft, indem der absolute Pfad zum Skript gesucht wird.
    if ! pgrep -f "python3 \$APP_DIR/\$APP_SCRIPT" > /dev/null; then
        if [ -f "\$LOCK_FILE" ]; then
            # Lock-Datei entfernen, wenn die App sauber beendet wurde.
            rm "\$LOCK_FILE"
            echo "Anwendung wurde sauber beendet. Watchdog pausiert."
        else
            # App neu starten, wenn sie nicht läuft und keine Lock-Datei vorhanden ist.
            echo "Anwendung abgestürzt oder nicht gestartet. Starte neu mit absoluten Pfaden..."
            source "\$APP_DIR/.venv/bin/activate"
            python3 "\$APP_DIR/\$APP_SCRIPT" &
            deactivate
        fi
    fi
    # Alle 10 Sekunden prüfen.
    sleep 10
done
EOF

chmod 755 "$HOME_DIR/watchdog.sh"
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

# --- Abschluss ---

echo ""
echo ">>> Installation abgeschlossen!"
echo ""
echo "================================================="
echo "ZUSAMMENFASSUNG"
echo "================================================="
echo "✔ Systemabhängigkeiten sind installiert."
echo "✔ Python-Pakete wurden in einer virtuellen Umgebung installiert."
echo "✔ Die Anwendung wird beim nächsten Start automatisch gestartet."
echo "✔ Ein Watchdog überwacht die Anwendung und startet sie bei Bedarf neu."
echo ""
echo ">>> Ein Neustart wird empfohlen, um alle Änderungen zu übernehmen."
echo ""
read -p "Drücken Sie ENTER, um das System jetzt neu zu starten, oder STRG+C, um den Vorgang abzubrechen. " -r
echo
echo "Neustart wird eingeleitet..."
reboot