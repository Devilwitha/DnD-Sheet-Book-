# dnd_data.py

# =============================================================================================
# ZAUBER-DATEN
# =============================================================================================
SPELL_DATA = {
    "Feuerpfeil": {"level": 0, "school": "Hervorrufung", "desc": "Du schleuderst einen Funken auf eine Kreatur oder einen Gegenstand. Führe einen Fernkampf-Zauberangriff durch. Bei einem Treffer erleidet das Ziel 1W10 Feuerschaden."},
    "Magierhand": {"level": 0, "school": "Beschwörung", "desc": "Eine schwebende Geisterhand erscheint an einem Punkt deiner Wahl. Du kannst die Hand benutzen, um mit einem Objekt zu interagieren, eine Tür zu öffnen oder einen Gegenstand zu tragen (max. 5 kg)."},
    "Heilendes Wort": {"level": 1, "school": "Hervorrufung", "desc": "Eine Kreatur deiner Wahl, die du sehen kannst, erhält 1W4 + deinen Zaubermodifikator an Trefferpunkten zurück."},
    "Magisches Geschoss": {"level": 1, "school": "Hervorrufung", "desc": "Du erschaffst drei magische Energiegeschosse. Jedes Geschoss trifft automatisch eine Kreatur deiner Wahl und verursacht 1W4 + 1 Energieschaden."},
    "Schild": {"level": 1, "school": "Bannmagie", "desc": "Als Reaktion, wenn du von einem Angriff getroffen wirst, kannst du eine unsichtbare Barriere magischer Kraft erschaffen, die dich schützt. Bis zum Beginn deines nächsten Zuges hast du einen Bonus von +5 auf deine Rüstungsklasse."},
    # Füge hier weitere Zauber hinzu...
}

# =============================================================================================
# FÄHIGKEITEN- (FEATURES) DATEN
# =============================================================================================
# Format: {"name": "Fähigkeit", "desc": "Beschreibung..."}
FIGHTER_FEATURES = {
    1: [{"name": "Kampfstil", "desc": "Du eignest dir einen bestimmten Kampfstil als deine Spezialität an (z.B. Bogenschiessen, Zweihandkampf)."},
        {"name": "Zweite Luft", "desc": "Einmal pro Rast kannst du als Bonusaktion 1W10 + deine Kämpferstufe an Trefferpunkten zurückgewinnen."}],
    2: [{"name": "Tatendrang", "desc": "Einmal pro Rast kannst du in deinem Zug eine zusätzliche Aktion ausführen."}],
    3: [{"name": "Archetyp des Kämpfers", "desc": "Du wählst einen Archetyp, der deinen Kampfstil prägt (z.B. Meister der Schlacht)."}]
}

ROGUE_FEATURES = {
    1: [{"name": "Expertise", "desc": "Wähle zwei deiner Fertigkeiten, in denen du geübt bist. Dein Übungsbonus wird für diese Fertigkeiten verdoppelt."},
        {"name": "Hinterhältiger Angriff", "desc": "Einmal pro Zug kannst du zusätzlichen 1W6 Schaden verursachen, wenn du einen Vorteil beim Angriffswurf hast oder ein Verbündeter neben dem Ziel steht."},
        {"name": "Diebeszeichen", "desc": "Du kennst die geheime Sprache der Diebe, eine Mischung aus Jargon, Gesten und Symbolen."}],
    2: [{"name": "Listige Aktion", "desc": "Du kannst als Bonusaktion die Spurt-, Rückzugs- oder Verstecken-Aktion ausführen."}],
    3: [{"name": "Schurkenarchetyp", "desc": "Du wählst einen Archetyp, dem du folgst (z.B. Dieb, Assassine)."}]
}

WIZARD_FEATURES = {
    1: [{"name": "Arkane Erholung", "desc": "Einmal pro Tag während einer kurzen Rast kannst du verbrauchte Zauberplätze wiederherstellen."},
        {"name": "Zauber wirken", "desc": "Du kannst Zauber aus der Zauberliste des Magiers wirken."}],
    2: [{"name": "Arkane Tradition", "desc": "Du wählst eine Schule der Magie, auf die du dich spezialisierst."}],
    3: [{"name": "-", "desc": "Keine neue Fähigkeit auf dieser Stufe."}]
}

# =============================================================================================
# KLASSEN-DATEN
# =============================================================================================
CLASS_DATA = {
    "Kämpfer": {
        "hit_die": 10,
        "features": FIGHTER_FEATURES,
        "proficiencies": ["Alle Rüstungen", "Schilde", "Einfache Waffen", "Kriegswaffen"],
        "spells": {}
    },
    "Schurke": {
        "hit_die": 8,
        "features": ROGUE_FEATURES,
        "proficiencies": ["Leichte Rüstung", "Einfache Waffen", "Handarmbrüste", "Langschwerter", "Rapiere", "Kurzschwerter"],
        "spells": {}
    },
    "Magier": {
        "hit_die": 6,
        "features": WIZARD_FEATURES,
        "proficiencies": ["Dolche", "Wurfpfeile", "Schleudern", "Leichte Armbrüste", "Viertelstäbe"],
        "spells": {
            "cantrips": ["Feuerpfeil", "Magierhand"],
            "level1": ["Magisches Geschoss", "Schild"]
        }
    },
    # Füge hier die Daten für die anderen Klassen hinzu
}


# =============================================================================================
# RASSEN-DATEN
# =============================================================================================
RACE_DATA = {
    "Mensch": {
        "ability_score_increase": {"Stärke": 1, "Geschicklichkeit": 1, "Konstitution": 1, "Intelligenz": 1, "Weisheit": 1, "Charisma": 1}, 
        "speed": 9,
        "languages": ["Gemeinsprache", "Eine zusätzliche Sprache"],
        "proficiencies": []
    },
    "Elf (Hochelf)": {
        "ability_score_increase": {"Geschicklichkeit": 2, "Intelligenz": 1}, 
        "speed": 9,
        "languages": ["Gemeinsprache", "Elfisch"],
        "proficiencies": ["Wahrnehmung"]
    },
    "Zwerg (Bergzwerg)": {
        "ability_score_increase": {"Konstitution": 2, "Stärke": 2}, 
        "speed": 7.5,
        "languages": ["Gemeinsprache", "Zwergisch"],
        "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung"]
    },
    # Füge hier die Daten für die anderen Völker hinzu
}

# =============================================================================================
# WAFFEN-DATEN
# =============================================================================================
WEAPON_DATA = {
    "Unbewaffneter Schlag": {"damage": "1d4", "ability": "Stärke"},
    "Dolch": {"damage": "1d4", "ability": "Geschicklichkeit"},
    "Kurzschwert": {"damage": "1d6", "ability": "Geschicklichkeit"},
    "Rapier": {"damage": "1d8", "ability": "Geschicklichkeit"},
    "Langschwert": {"damage": "1d8", "ability": "Stärke"},
    "Zweihänder": {"damage": "2d6", "ability": "Stärke"},
    "Kurzbogen": {"damage": "1d6", "ability": "Geschicklichkeit"},
}