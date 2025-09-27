# DnD(Sheet&Book) - Digitaler Spieltisch

## 1. Allgemeinbeschreibung

**DnD(Sheet&Book)** ist ein umfassendes digitales Werkzeug für Dungeons & Dragons 5e, konzipiert für den Einsatz auf einem Raspberry Pi. Es dient als vollwertiger digitaler Spieltisch und bietet eine breite Palette an Funktionen für Spieler und Spielleiter (DMs).

Die Anwendung umfasst:
-   **Charakterverwaltung:** Erstellen, bearbeiten, speichern und leveln Sie Ihre Charaktere mit einem detaillierten, interaktiven Charakterbogen.
-   **Multiplayer-Modus:** Verbinden Sie mehrere Geräte in einem lokalen Netzwerk. Spieler können einem vom DM gehosteten Spiel beitreten.
-   **Spielleiter-Werkzeuge:** Ein dedizierter DM-Bildschirm ermöglicht die Verwaltung von Spielern, Gegnern, die Steuerung des Kampfes über eine interaktive Karte und das Führen eines Spielprotokolls.
-   **Karten-Editor:** Ein leistungsstarker Editor zum Erstellen und Bearbeiten von eigenen Dungeon-Karten.
-   **System-Integration:** Bietet Funktionen wie einen automatisierten Installer, App-Updates, System-Neustart und WLAN-Management direkt aus der Anwendung heraus.

## 2. Installation 

### Raspberry Pi

Die Installation auf einem Raspberry Pi wurde vollständig automatisiert, um den Prozess so einfach wie möglich zu gestalten.

**Voraussetzungen:**
-   Ein Raspberry Pi (Modell 4 oder neuer empfohlen).
-   Raspberry Pi OS mit Desktop-Umgebung.
-   Eine Internetverbindung für die Installation.

**Anleitung:**

1.  Öffnen Sie ein Terminal auf Ihrem Raspberry Pi.
2.  Laden Sie das Projekt von GitHub herunter (falls noch nicht geschehen):
    ```bash
    git clone https://github.com/Devilwitha/DnD-Sheet-Book-.git
    ```
3.  Wechseln Sie in das Projektverzeichnis:
    ```bash
    cd DnD-Sheet-Book-
    ```
4.  Führen Sie das automatisierte Installationsskript aus:
    ```bash
    sudo bash install_on_pi.sh
    ```

Das Skript kümmert sich um alles Weitere:
-   Aktualisierung Ihres Systems.
-   Installation aller notwendigen System- und Python-Abhängigkeiten.
-   Einrichtung der Anwendung für den **automatischen Start** nach einem Neustart.
-   Konfiguration eines **Watchdogs**, der die App bei einem Absturz automatisch neu startet.
-   Installation eines benutzerdefinierten **Splash-Screens** für den Systemstart.

Am Ende der Installation werden Sie gefragt, ob Sie das System neu starten möchten. Bestätigen Sie mit **Enter**, um alle Änderungen zu übernehmen.

### Android
- Downloade die APK von: https://github.com/Devilwitha/DnD-Sheet-Book-/releases herunter
- installiere es direkt auf dem android (eine meldung erscheint auf nicht installieren klicken und direkt erneut installieren dan wird die app installiert)
- - oder Clone das Github Projekt und führe Install_and_log.py aus um ess zu installieren (Debug Optionen müssen in den Einstellungen aktiviert sein)

**Mann muss die app deinstallieren und erneut installieren um zu updaten. Es gibt noch probleme mit der signiereung der apk mit github**

### Windows
- Downloade die EXE von: https://github.com/Devilwitha/DnD-Sheet-Book-/releases herunter
- Entpacke das verzeichniss und starte die Exe
- Falls eine Meldung erscheint das "Der Computer wurde durch Windows geschützt" kommt dan auf, Weiter Informationen klicken und dann auf den Button Trozdem ausführen klicken
- - warum erscheint diese Meldung? Das erscheint da die EXE mit Github automatisch generiert wird und somit keine gültige Signatur enthält

---

## 3. Die Bildschirme der Anwendung

Hier finden Sie eine detaillierte Beschreibung aller Bildschirme und ihrer Funktionen.

### Hauptmenü & Navigation

#### Ladebildschirm (Splash Screen)
-   **Zweck:** Der erste Bildschirm, der beim Start der App angezeigt wird.
-   **Bedienung:** Tippen Sie auf den Bildschirm, um ins Hauptmenü zu gelangen.

#### Hauptmenü (Main Menu)
-   **Zweck:** Die zentrale Navigations-Drehscheibe der Anwendung.
-   **Bedienung:**
    -   **Charakter:** Führt zur Charakterverwaltung (erstellen, laden, bearbeiten).
    -   **DM Spiel:** Führt zum Multiplayer-Menü, um ein Spiel zu hosten oder ihm beizutreten.
    -   **Optionen:** Öffnet die Anwendungsoptionen.

### Optionen & Einstellungen

#### Optionen (Options)
-   **Zweck:** Bietet Zugriff auf verschiedene Einstellungs- und Informationsbildschirme.
-   **Bedienung:**
    -   **Gui Einstellungen:** Führt zu den visuellen Anpassungsoptionen.
    -   **SaveData übertragen:** Öffnet den Bildschirm zur Datenübertragung zwischen Geräten.
    -   **System Einstellungen:** Führt zu systemnahen Funktionen wie Updates und Neustarts.
    -   **Info:** Zeigt technische Details zur App und zum System an.
    -   **Zurück:** Kehrt zum Hauptmenü zurück.

#### GUI Einstellungen (Settings)
-   **Zweck:** Ein Untermenü für visuelle Anpassungen.
-   **Bedienung:**
    -   **Hintergründe:** Öffnet die Verwaltung der Hintergrundbilder.
    -   **Customization:** Öffnet erweiterte Einstellungen für Farben und Stile.

#### Hintergrund Einstellungen (Background Settings)
-   **Zweck:** Ermöglicht die Verwaltung der Hintergrundbilder für verschiedene App-Bereiche.
-   **Bedienung:**
    -   **Hintergrund anzeigen (Schalter):** Aktiviert oder deaktiviert alle Hintergrundbilder.
    -   **Buttons zum Ändern:** Öffnen einen Dateimanager, um spezifische Hintergrundbilder für den allgemeinen Hintergrund, die Charaktererstellung und den Charakterbogen festzulegen.

#### Customization Einstellungen
-   **Zweck:** Detaillierte Kontrolle über das Erscheinungsbild der Benutzeroberfläche.
-   **Bedienung:** Bietet Schieberegler, Schalter und Farbwähler zur Anpassung von:
    -   Button-Transparenz
    -   Allgemeiner Schriftfarbe
    -   Popup-Hintergrundfarbe
    -   Button-Schrift- und Hintergrundfarbe

#### System Einstellungen (System Settings)
-   **Zweck:** Zugriff auf systemnahe Funktionen, Updates und Hardware-Einstellungen.
-   **Bedienung:** (Viele Funktionen sind nur auf dem Raspberry Pi verfügbar)
    -   **Nach Updates suchen:** Sucht nach App-Updates auf GitHub (Main, Beta, Alpha Branches).
    -   **WLAN:** Zeigt den WLAN-Status an, scannt nach Netzwerken und ermöglicht die Verbindung.
    -   **On-Screen Keyboard (Schalter):** Aktiviert/deaktiviert die Bildschirmtastatur.
    -   **Changelog:** Zeigt die `changelog.txt`-Datei an.
    -   **Anwendung/System neustarten/herunterfahren:** Führt die entsprechenden Systembefehle aus.

#### Info
-   **Zweck:** Zeigt technische Informationen an.
-   **Bedienung:** Ein reiner Lese-Bildschirm mit Details zu App-Version, System, Auflösung etc.

#### Changelog
-   **Zweck:** Zeigt die Änderungshistorie der Anwendung an.
-   **Bedienung:** Zeigt den Inhalt der `changelog.txt` in einem scrollbaren Fenster.

#### Datenübertragung (Transfer)
-   **Zweck:** Ermöglicht den Austausch von Speicherdaten (Charaktere, Karten etc.) zwischen zwei Geräten im selben Netzwerk, ohne eine Spielsitzung zu starten.
-   **Bedienung:**
    -   **Senden:** Ein Gerät wählt "Senden", dann den Datentyp und die zu sendenden Dateien aus. Es wird sichtbar im Netzwerk.
    -   **Empfangen:** Das andere Gerät wählt "Empfangen", sucht nach dem Sender, wählt ihn aus der Liste aus und startet den Download.

### Charakterverwaltung

#### Charakter Menü
-   **Zweck:** Das Hauptmenü für alle Aktionen rund um den Charakter.
-   **Bedienung:**
    -   **Neuen Charakter erstellen:** Startet den Charakter-Erstellungsprozess.
    -   **Charakter laden:** Öffnet ein Popup mit allen gespeicherten Charakteren. Jeder Eintrag bietet Optionen zum **Laden** (öffnet den Charakterbogen), **Bearbeiten** (öffnet den Editor) oder **Löschen** des Charakters.

#### Charaktererstellung (Character Creator)
-   **Zweck:** Ein detaillierter, schrittweiser Prozess zur Erstellung eines neuen D&D-Charakters.
-   **Bedienung:**
    1.  Füllen Sie die Basisdaten aus (Name, Rasse, Klasse etc.).
    2.  Verteilen Sie Attributspunkte manuell (+/-) oder würfeln Sie sie zufällig aus.
    3.  Ein Klick auf "Charakter erstellen" startet eine Reihe von Popups für klassen- und rassenspezifische Wahlen (z.B. Kampfstil, Fertigkeiten, Zauber).
    4.  Nach Abschluss aller Schritte wird der fertige Charakter im Charakterbogen angezeigt.

#### Charaktereditor (Character Editor)
-   **Zweck:** Bearbeitung der grundlegenden Daten eines bestehenden Charakters.
-   **Bedienung:** Lädt einen Charakter in die bekannte Erstellungsmaske. Hier können Name, Gesinnung, Attributswerte etc. geändert werden. Eine Neuauswahl von klassenspezifischen Merkmalen wie Zaubern ist hier nicht möglich.

#### Charakterbogen (Character Sheet)
-   **Zweck:** Das Herzstück für den Spieler. Eine interaktive Anzeige aller Charakterdaten für den Einzelspieler-Modus.
-   **Bedienung:** Der Bogen ist in mehrere Bereiche aufgeteilt:
    -   **Anzeigen:** Zeigt alle Werte, HP, AC, Initiative, Fähigkeiten, Inventar, Ausrüstung und Währung an.
    -   **Interaktionen:** Bietet Buttons und Regler zur direkten Manipulation von HP und Währung.
    -   **Aktionsleiste (unten):** Eine Reihe von Buttons für alle wichtigen Aktionen im Spiel:
        -   **Info:** Zeigt detaillierte Infos zu Fertigkeiten, Sprachen etc.
        -   **Zauber:** Öffnet das Zauberbuch zum Wirken von Zaubern.
        -   **Rast:** Ermöglicht eine kurze oder lange Rast.
        -   **d20 Wurf / Initiative:** Für schnelle Würfelwürfe.
        -   **Level Up:** Startet den Stufenaufstiegsprozess.
        -   **Speichern:** Speichert den Charakter manuell.

#### Stufenaufstieg (Level Up)
-   **Zweck:** Führt den Spieler durch den Stufenaufstieg.
-   **Bedienung:** Zeigt automatisch die HP-Erhöhung und neue Fähigkeiten an. Bietet, falls auf dem neuen Level verfügbar, Popups zur Erhöhung von Attributswerten oder zur Auswahl neuer Zauber.

### Multiplayer & Spielleitung

#### DM Spiel (Multiplayer Menu)
-   **Zweck:** Der Einstiegspunkt für den Multiplayer-Modus für Spieler und DMs.
-   **Bedienung:**
    -   **DM Hosten:** Startet eine neue, leere Sitzung und führt zur DM Lobby.
    -   **Spieler beitreten:** Führt zur Spieler Lobby, um nach Spielen zu suchen.
    -   **DM Vorbereiten:** Ermöglicht die Vorbereitung einer Sitzung (Gegner, Karte, Notizen), bevor sie gehostet wird.
    -   **Sitzung laden:** Lädt eine gespeicherte Sitzung und führt dann zur DM Lobby.

#### DM Vorbereitung (DM Prep)
-   **Zweck:** Ein Werkzeug für den DM, um eine Spielsitzung vorzubereiten.
-   **Bedienung:** Der DM kann hier eine Gegnerliste erstellen und speichern, Notizen für die Sitzung verfassen und über den "Map Editor"-Button eine Karte erstellen oder bearbeiten. Mit "Sitzung Hosten" werden alle vorbereiteten Daten gebündelt und in die DM Lobby übernommen.

#### DM Lobby
-   **Zweck:** Der Warteraum für den DM.
-   **Bedienung:** Startet automatisch den Server und zeigt eine Liste der Spieler an, die dem Spiel beitreten. Der DM kann hier auf alle Spieler warten und dann mit "Spiel starten" die Sitzung für alle beginnen.

#### Spieler Lobby (Player Lobby)
-   **Zweck:** Der Bildschirm für Spieler, um einem Spiel beizutreten.
-   **Bedienung:** Sucht automatisch nach verfügbaren DMs im Netzwerk. Der Spieler muss einen Charakter auswählen, einen DM aus der Liste auswählen und auf "Verbinden" klicken.

#### Spieler Wartebildschirm (Player Waiting Screen)
-   **Zweck:** Ein Wartebildschirm für den Spieler nach erfolgreicher Verbindung.
-   **Bedienung:** Zeigt Statusmeldungen vom DM an. Wenn der DM das Spiel startet, wird der Spieler automatisch zu seinem Charakterbogen weitergeleitet.

#### DM Hauptbildschirm (DM Main Screen)
-   **Zweck:** Die Kommandozentrale für den DM während des Spiels.
-   **Bedienung:** Ein dreispaltiges Layout:
    -   **Links:** Listen der Spieler, Gegner und Objekte.
    -   **Mitte:** Die interaktive Karte. Der DM kann mit Linksklick Charaktere/Gegner auswählen und bewegen und mit Rechtsklick Angriffe für Gegner initiieren.
    -   **Rechts:** Die Initiative-Leiste, eine Vielzahl von Steuerungs-Buttons (Runde beenden, Initiative würfeln, Gegner hinzufügen, Sitzung speichern, Karte laden/bearbeiten) und das Spielprotokoll.

#### Spieler Charakterbogen (Multiplayer)
-   **Zweck:** Eine vereinfachte Version des Charakterbogens für den Multiplayer-Modus.
-   **Bedienung:** Zeigt die wichtigsten Charakterdaten an. Die Aktionsleiste am unteren Rand erlaubt es dem Spieler, Aktionen auszuführen (z.B. einen Attributswurf machen, einen Zauber wirken). Diese Aktionen werden automatisch an den DM gesendet und im Spielprotokoll vermerkt.

#### Map Editor
-   **Zweck:** Ein Editor zum Erstellen und Bearbeiten von 2D-Karten.
-   **Bedienung:** Bietet Werkzeuge zum Zeichnen von Kacheln (Boden, Wand, Tür), zum Platzieren von Spielern und Gegnern sowie zum Hinzufügen von Möbelstücken (die als Mimic getarnt werden können). Karten können gespeichert und geladen werden.

#### Spieler-Karte (Player Map)
-   **Zweck:** Zeigt dem Spieler die Karte an, die der DM teilt.
-   **Bedienung:** Der Spieler kann auf seinen Charakter klicken, um ihn auszuwählen, und auf ein gültiges Feld klicken, um eine Bewegungsanfrage an den DM zu senden. Angriffe auf Gegner können ebenfalls per Klick initiiert werden. Alle Aktionen sind nur möglich, wenn der Spieler am Zug ist.

---

## 4. Funktionsweise im Überblick

### Typischer Ablauf für Spieler
1.  **Charakter erstellen:** Gehen Sie zu `Charakter -> Neuen Charakter erstellen` und folgen Sie den Schritten.
2.  **Spiel beitreten:** Gehen Sie zu `DM Spiel -> Spieler beitreten`.
3.  **Charakter & DM auswählen:** Wählen Sie Ihren Charakter aus und klicken Sie auf den Namen des DMs in der Liste der verfügbaren Spiele.
4.  **Verbinden:** Klicken Sie auf "Verbinden" und warten Sie im Wartebildschirm, bis der DM das Spiel startet.
5.  **Spielen:** Sie werden automatisch zu Ihrem Spieler-Charakterbogen weitergeleitet. Von hier aus können Sie würfeln, zaubern oder zur Karte wechseln, um sich zu bewegen.

### Typischer Ablauf für Spielleiter
1.  **(Optional) Vorbereiten:** Gehen Sie zu `DM Spiel -> DM Vorbereiten`, um Gegner, eine Karte und Notizen für die Sitzung zu erstellen. Klicken Sie dann auf "Sitzung Hosten".
2.  **Direkt Hosten:** Gehen Sie zu `DM Spiel -> DM Hosten`, um eine leere Sitzung zu starten.
3.  **Warten:** In der DM Lobby sehen Sie, wie die Spieler beitreten.
4.  **Spiel starten:** Wenn alle bereit sind, klicken Sie auf "Spiel starten".
5.  **Leiten:** Vom DM Hauptbildschirm aus verwalten Sie das Spiel: Bewegen Sie Gegner, verfolgen Sie die Initiative und reagieren Sie auf die Aktionen der Spieler, die im Log erscheinen.

<!-- prepare_build helper removed per request -->
