# dnd_data.py

# =============================================================================================
# REGEL-KONSTANTEN
# =============================================================================================

# Übungsbonus basierend auf dem Gesamtlevel des Charakters
PROFICIENCY_BONUS = {
    1: 2, 2: 2, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 3,
    9: 4, 10: 4, 11: 4, 12: 4, 13: 5, 14: 5, 15: 5, 16: 5,
    17: 6, 18: 6, 19: 6, 20: 6
}

# Alle 18 Fertigkeiten und das zugehörige Attribut
SKILLS = {
    "Akrobatik": "Geschicklichkeit", "Tierhandhabung": "Weisheit", "Arkanes Wissen": "Intelligenz",
    "Athletik": "Stärke", "Täuschung": "Charisma", "Geschichte": "Intelligenz",
    "Menschenkenntnis": "Weisheit", "Einschüchtern": "Charisma", "Nachforschungen": "Intelligenz",
    "Medizin": "Weisheit", "Natur": "Intelligenz", "Wahrnehmung": "Weisheit",
    "Auftreten": "Charisma", "Überzeugen": "Charisma", "Religion": "Intelligenz",
    "Fingerfertigkeit": "Geschicklichkeit", "Heimlichkeit": "Geschicklichkeit", "Überlebenskunst": "Weisheit"
}

# =============================================================================================
# ZAUBER-DATEN
# =============================================================================================
SPELL_DATA = {
    # Cantrips (Level 0)
    "Säurespritzer": {"level": 0, "school": "Beschwörung", "desc": "Du schleuderst eine Säureblase. Wähle eine oder zwei Kreaturen im Umkreis von 1,5m. Ein Ziel muss einen Geschicklichkeitsrettungswurf ablegen. Bei einem Fehlschlag erleidet es 1W6 Säureschaden."},
    "Feuerpfeil": {"level": 0, "school": "Hervorrufung", "desc": "Du schleuderst einen Funken auf eine Kreatur oder einen Gegenstand. Führe einen Fernkampf-Zauberangriff durch. Bei einem Treffer erleidet das Ziel 1W10 Feuerschaden."},
    "Magierhand": {"level": 0, "school": "Beschwörung", "desc": "Eine schwebende Geisterhand erscheint an einem Punkt deiner Wahl. Du kannst die Hand benutzen, um mit einem Objekt zu interagieren, eine Tür zu öffnen oder einen Gegenstand zu tragen (max. 5 kg)."},
    "Schutz vor Klingen": {"level": 0, "school": "Bannmagie", "desc": "Du weitest deine Hand aus und zeichnest ein Schutzzeichen in die Luft. Bis zum Ende deines nächsten Zuges hast du Resistenz gegen Hieb-, Stich- und Wuchtschaden von Waffenangriffen."},
    "Licht": {"level": 0, "school": "Hervorrufung", "desc": "Du berührst ein Objekt, das nicht größer als 3m ist. Bis der Zauber endet, strahlt das Objekt helles Licht in einem Radius von 6m und gedämpftes Licht für weitere 6m aus."},
    "Heilige Flamme": {"level": 0, "school": "Hervorrufung", "desc": "Flammenartige Ausstrahlung senkt sich auf eine Kreatur herab. Das Ziel muss einen Geschicklichkeitsrettungswurf schaffen oder 1W8 gleißenden Schaden erleiden."},
    "Shillelagh": {"level": 0, "school": "Verwandlung", "desc": "Der Holzknüppel oder der Viertelstab, den du in der Hand hältst, wird mit der Macht der Natur erfüllt. Für die Wirkungsdauer verwendest du dein Zauberattribut anstelle von Stärke für die Angriffs- und Schadenswürfe dieses magischen Knüppels, und der Schadenswürfel der Waffe wird zu einem W8."},
    "Druidenhandwerk": {"level": 0, "school": "Verwandlung", "desc": "Du erschaffst einen winzigen, harmlosen sensorischen Effekt, der die Anwesenheit von Natur vorhersagt."},
    "Schauriger Strahl": {"level": 0, "school": "Hervorrufung", "desc": "Ein Strahl knisternder Energie schießt auf eine Kreatur in Reichweite. Führe einen Fernkampf-Zauberangriff gegen das Ziel aus. Bei einem Treffer erleidet das Ziel 1W10 Energieschaden."},
    
    # Level 1 Spells
    "Donnerwelle": {"level": 1, "school": "Hervorrufung", "desc": "Eine Welle donnernder Kraft fegt von dir aus. Jede Kreatur in einem 4,5-Meter-Würfel, der von dir ausgeht, muss einen Konstitutions-Rettungswurf ablegen. Bei einem misslungenen Rettungswurf erleidet eine Kreatur 2W8 Donnerschaden und wird 3 Meter von dir weggestoßen."},
    "Segnen": {"level": 1, "school": "Verzauberung", "desc": "Du segnest bis zu drei Kreaturen deiner Wahl in Reichweite. Immer wenn ein Ziel einen Angriffs- oder Rettungswurf macht, bevor der Zauber endet, kann das Ziel einen W4 addieren."},
    "Brennende Hände": {"level": 1, "school": "Hervorrufung", "desc": "Aus deinen ausgestreckten Händen schießt ein 4,5m langer Feuerkegel. Jede Kreatur im Kegel muss einen Geschicklichkeitsrettungswurf machen. Bei einem Fehlschlag erleidet sie 3W6 Feuerschaden, bei Erfolg die Hälfte."},
    "Person bezaubern": {"level": 1, "school": "Verzauberung", "desc": "Du versuchst, einen Humanoiden zu bezaubern. Er muss einen Weisheitsrettungswurf ablegen, und bei einem Fehlschlag ist er von dir bezaubert, bis der Zauber endet."},
    "Heilendes Wort": {"level": 1, "school": "Hervorrufung", "desc": "Eine Kreatur deiner Wahl, die du sehen kannst, erhält 1W4 + deinen Zaubermodifikator an Trefferpunkten zurück."},
    "Höllischer Tadel": {"level": 1, "school": "Hervorrufung", "desc": "Als Reaktion darauf, dass du von einer Kreatur in Sichtweite Schaden nimmst, umgibst du die Kreatur augenblicklich mit Flammen. Die Kreatur muss einen Geschicklichkeitsrettungswurf machen. Sie erleidet bei einem misslungenen Rettungswurf 2W10 Feuerschaden oder die Hälfte des Schadens bei einem erfolgreichen."},
    "Schutz vor Gut und Böse": {"level": 1, "school": "Bannmagie", "desc": "Bis der Zauber endet, ist eine willige Kreatur, die du berührst, vor bestimmten Arten von Kreaturen geschützt: Aberrationen, Himmlische, Elementare, Feen, Unholde und Untote."},
    "Magisches Geschoss": {"level": 1, "school": "Hervorrufung", "desc": "Du erschaffst drei magische Energiegeschosse. Jedes Geschoss trifft automatisch eine Kreatur deiner Wahl und verursacht 1W4 + 1 Energieschaden."},
    "Schild": {"level": 1, "school": "Bannmagie", "desc": "Als Reaktion, wenn du von einem Angriff getroffen wirst, hast du bis zum Beginn deines nächsten Zuges einen Bonus von +5 auf deine Rüstungsklasse."},
    "Schlaf": {"level": 1, "school": "Verzauberung", "desc": "Du versetzt Kreaturen in einen magischen Schlummer. Würfle 5W8; das Ergebnis ist die Gesamtzahl an Trefferpunkten von Kreaturen, die dieser Zauber betreffen kann."},
}

# =============================================================================================
# WAFFEN-DATEN
# =============================================================================================
WEAPON_DATA = {
    "Unbewaffneter Schlag": {"damage": "1d4", "ability": "Stärke"}, "Dolch": {"damage": "1d4", "ability": "Geschicklichkeit"},
    "Streitkolben": {"damage": "1d6", "ability": "Stärke"}, "Handaxt": {"damage": "1d6", "ability": "Stärke"},
    "Leichter Hammer": {"damage": "1d4", "ability": "Stärke"}, "Speer": {"damage": "1d6", "ability": "Stärke"},
    "Viertelstab": {"damage": "1d6", "ability": "Stärke"}, "Leichte Armbrust": {"damage": "1d8", "ability": "Geschicklichkeit"},
    "Kurzbogen": {"damage": "1d6", "ability": "Geschicklichkeit"}, "Schleuder": {"damage": "1d4", "ability": "Geschicklichkeit"},
    "Kurzschwert": {"damage": "1d6", "ability": "Geschicklichkeit"}, "Langschwert": {"damage": "1d8", "ability": "Stärke"},
    "Morgenstern": {"damage": "1d8", "ability": "Stärke"}, "Rapier": {"damage": "1d8", "ability": "Geschicklichkeit"},
    "Kriegshammer": {"damage": "1d8", "ability": "Stärke"}, "Zweihänder": {"damage": "2d6", "ability": "Stärke"},
    "Handarmbrust": {"damage": "1d6", "ability": "Geschicklichkeit"}, "Schwere Armbrust": {"damage": "1d10", "ability": "Geschicklichkeit"},
    "Langbogen": {"damage": "1d8", "ability": "Geschicklichkeit"},
}

# =============================================================================================
# RASSEN-DATEN
# =============================================================================================
RACE_DATA = {
    "Drachenblütiger": {"ability_score_increase": {"Stärke": 2, "Charisma": 1}, "speed": 9, "languages": ["Gemeinsprache", "Drakonisch"], "proficiencies": [], "traits": [{"name": "Drachenblut", "desc": "Du wählst eine Art von Drachen als Vorfahren."}, {"name": "Odemwaffe", "desc": "Du kannst deine Odemwaffe als Aktion einsetzen."}, {"name": "Schadensresistenz", "desc": "Du hast eine Resistenz gegen den Schadenstyp, der mit deinen Vorfahren verbunden ist."}]},
    "Elf (Hochelf)": {"ability_score_increase": {"Geschicklichkeit": 2, "Intelligenz": 1}, "speed": 9, "languages": ["Gemeinsprache", "Elfisch"], "proficiencies": ["Wahrnehmung"], "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in Dunkelheit sehen."}, {"name": "Feenblut", "desc": "Vorteil bei Rettungswürfen gegen Bezauberung."}, {"name": "Trance", "desc": "Benötigt nur 4 Stunden Meditation statt 8 Stunden Schlaf."}, {"name": "Zusätzlicher Zaubertrick", "desc": "Du kennst einen zusätzlichen Zaubertrick von der Magierliste."}]},
    "Halb-Elf": {"ability_score_increase": {"Charisma": 2, "Geschicklichkeit": 1, "Konstitution": 1}, "speed": 9, "languages": ["Gemeinsprache", "Elfisch", "Eine zusätzliche Sprache"], "proficiencies": [], "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in Dunkelheit sehen."}, {"name": "Feenblut", "desc": "Vorteil bei Rettungswürfen gegen Bezauberung."}, {"name": "Facettenreiche Begabung", "desc": "Übung in zwei Fertigkeiten deiner Wahl."}]},
    "Halbling (Leichtfuß)": {"ability_score_increase": {"Geschicklichkeit": 2, "Charisma": 1}, "speed": 7.5, "languages": ["Gemeinsprache", "Halblingisch"], "proficiencies": [], "traits": [{"name": "Glückspilz", "desc": "Wenn du eine 1 würfelst, kannst du den Wurf wiederholen."}, {"name": "Tapfer", "desc": "Vorteil bei Rettungswürfen gegen Furcht."}, {"name": "Behende", "desc": "Kann sich durch den Bereich größerer Kreaturen bewegen."}, {"name": "Von Natur aus heimlich", "desc": "Kann sich hinter Kreaturen verstecken, die größer sind."}]},
    "Halb-Ork": {"ability_score_increase": {"Stärke": 2, "Konstitution": 1}, "speed": 9, "languages": ["Gemeinsprache", "Orkisch"], "proficiencies": ["Einschüchtern"], "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in Dunkelheit sehen."}, {"name": "Unbarmherzige Ausdauer", "desc": "Wenn du auf 0 TP fällst, fällst du stattdessen auf 1 TP (1x pro langer Rast)."}, {"name": "Wilde Angriffe", "desc": "Bei kritischen Treffern würfelst du einen zusätzlichen Schadenswürfel."}]},
    "Mensch": {"ability_score_increase": {"Stärke": 1, "Geschicklichkeit": 1, "Konstitution": 1, "Intelligenz": 1, "Weisheit": 1, "Charisma": 1}, "speed": 9, "languages": ["Gemeinsprache", "Eine zusätzliche Sprache"], "proficiencies": []},
    "Tiefling": {"ability_score_increase": {"Charisma": 2, "Intelligenz": 1}, "speed": 9, "languages": ["Gemeinsprache", "Infernalisch"], "proficiencies": [], "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in Dunkelheit sehen."}, {"name": "Höllische Resistenz", "desc": "Resistenz gegen Feuerschaden."}, {"name": "Infernalisches Vermächtnis", "desc": "Du kennst Zaubertricks und Zauber."}]},
    "Zwerg (Hügelzwerg)": {"ability_score_increase": {"Konstitution": 2, "Weisheit": 1}, "speed": 7.5, "languages": ["Gemeinsprache", "Zwergisch"], "proficiencies": ["Schmiedewerkzeug"], "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in Dunkelheit sehen."}, {"name": "Zwergische Abhärtung", "desc": "Vorteil bei Rettungswürfen gegen Gift."}, {"name": "Zwergische Zähigkeit", "desc": "Maximale TP erhöhen sich um 1 pro Stufe."}]},
}

# =============================================================================================
# KLASSEN-FEATURES
# =============================================================================================
FIGHTER_FEATURES = {
    1: [{"name": "Kampfstil", "desc": "Du eignest dir einen bestimmten Kampfstil als deine Spezialität an."}, {"name": "Zweite Luft", "desc": "Einmal pro Rast kannst du als Bonusaktion 1W10 + deine Kämpferstufe an Trefferpunkten zurückgewinnen."}],
    2: [{"name": "Tatendrang", "desc": "Einmal pro Rast kannst du in deinem Zug eine zusätzliche Aktion ausführen."}],
    3: [{"name": "Archetyp des Kämpfers: Champion", "desc": "Dein kritischer Trefferbereich erweitert sich. Du erzielst jetzt einen kritischen Treffer bei einer 19 oder 20."}],
    4: [{"name": "Attributswerterhöhung", "desc": "Du kannst einen Attributswert um 2 oder zwei um 1 erhöhen."}],
    5: [{"name": "Zusätzlicher Angriff", "desc": "Du kannst zweimal anstatt einmal angreifen, wenn du die Angriffsaktion ergreifst."}],
    6: [{"name": "Attributswerterhöhung", "desc": "Du kannst einen Attributswert um 2 oder zwei um 1 erhöhen."}],
    7: [{"name": "Champion: Bemerkenswerter Athlet", "desc": "Du kannst die Hälfte deines Übungsbonus zu jedem Stärke-, Geschicklichkeits- oder Konstitutionswurf addieren, bei dem du noch nicht geübt bist."}],
    8: [{"name": "Attributswerterhöhung", "desc": "Du kannst einen Attributswert um 2 oder zwei um 1 erhöhen."}],
    9: [{"name": "Unbeugsam (eine Nutzung)", "desc": "Du kannst einen fehlgeschlagenen Rettungswurf wiederholen."}],
    10: [{"name": "Champion: Zusätzlicher Kampfstil", "desc": "Du kannst einen weiteren Kampfstil wählen."}],
    11: [{"name": "Zusätzlicher Angriff (2)", "desc": "Du kannst nun dreimal angreifen."}],
    12: [{"name": "Attributswerterhöhung", "desc": "Du kannst einen Attributswert um 2 oder zwei um 1 erhöhen."}],
    13: [{"name": "Unbeugsam (zwei Nutzungen)", "desc": "Du kannst einen fehlgeschlagenen Rettungswurf wiederholen."}],
    14: [{"name": "Attributswerterhöhung", "desc": "Du kannst einen Attributswert um 2 oder zwei um 1 erhöhen."}],
    15: [{"name": "Champion: Überlegener Kritischer Treffer", "desc": "Du erzielst jetzt einen kritischen Treffer bei einer 18-20."}],
    16: [{"name": "Attributswerterhöhung", "desc": "Du kannst einen Attributswert um 2 oder zwei um 1 erhöhen."}],
    17: [{"name": "Tatendrang (zwei Nutzungen)", "desc": "Du kannst Tatendrang nun zweimal pro Rast nutzen."}],
    18: [{"name": "Champion: Überlebender", "desc": "Zu Beginn jedes deiner Züge erhältst du 5 Trefferpunkte zurück, wenn du weniger als die Hälfte deiner TP hast."}],
    19: [{"name": "Attributswerterhöhung", "desc": "Du kannst einen Attributswert um 2 oder zwei um 1 erhöhen."}],
    20: [{"name": "Zusätzlicher Angriff (3)", "desc": "Du kannst nun viermal angreifen."}]
}

# =============================================================================================
# KLASSEN-DATEN (Vollständig mit den neuen Feldern)
# =============================================================================================
CLASS_DATA = {
    "Barbar": {"hit_die": 12, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Einfache Waffen", "Kriegswaffen"], "saving_throws": ["Stärke", "Konstitution"], "skill_proficiencies": ["Tierhandhabung", "Athletik", "Einschüchtern", "Natur", "Wahrnehmung", "Überlebenskunst"], "features": {1: [{"name": "Kampfrausch", "desc": "Vorteile bei Stärke-Würfen, +Schadensbonus und Resistenzen."}], 4: [{"name": "Attributswerterhöhung", "desc": "Erhöhe einen Wert um 2 oder zwei um 1."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "spells": {}},
    "Barde": {"hit_die": 8, "proficiencies": ["Leichte Rüstung", "Einfache Waffen", "Handarmbrüste", "Langschwerter", "Rapiere", "Kurzschwerter"], "saving_throws": ["Geschicklichkeit", "Charisma"], "skill_proficiencies": list(SKILLS.keys()), "features": {1: [{"name": "Barden-Inspiration (W6)", "desc": "Gib Verbündeten einen Bonuswürfel."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "cantrips_known": {1: 2, 4: 3, 10: 4}, "spell_slots": {1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}}, "spells": {"cantrips": ["Licht", "Magierhand"], "level1": ["Person bezaubern", "Heilendes Wort"]}},
    "Druide": {"hit_die": 8, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Keulen", "Dolche", "Speere"], "saving_throws": ["Intelligenz", "Weisheit"], "skill_proficiencies": ["Arkanes Wissen", "Tierhandhabung", "Menschenkenntnis", "Medizin", "Natur", "Wahrnehmung", "Religion", "Überlebenskunst"], "features": {1: [{"name": "Druidisch", "desc": "Geheimsprache der Druiden."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "cantrips_known": {1: 2, 4: 3, 10: 4}, "spell_slots": {1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}}, "spells": {"cantrips": ["Shillelagh", "Druidenhandwerk"], "level1": ["Heilendes Wort", "Donnerwelle"]}},
    "Hexenmeister": {"hit_die": 8, "proficiencies": ["Leichte Rüstung", "Einfache Waffen"], "saving_throws": ["Weisheit", "Charisma"], "skill_proficiencies": ["Arkanes Wissen", "Täuschung", "Geschichte", "Einschüchtern", "Nachforschungen", "Natur", "Religion"], "features": {1: [{"name": "Magie des Paktes", "desc": "Zauberplätze erneuern sich bei kurzer Rast."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "cantrips_known": {1: 2, 4: 3, 10: 4}, "spell_slots": {1: {"1": 1}, 2: {"1": 2}, 3: {"2": 2}}, "spells": {"cantrips": ["Schauriger Strahl", "Magierhand"], "level1": ["Höllischer Tadel", "Schutz vor Gut und Böse"]}},
    "Kämpfer": {"hit_die": 10, "proficiencies": ["Alle Rüstungen", "Schilde", "Einfache Waffen", "Kriegswaffen"], "saving_throws": ["Stärke", "Konstitution"], "skill_proficiencies": ["Akrobatik", "Tierhandhabung", "Athletik", "Geschichte", "Menschenkenntnis", "Einschüchtern", "Wahrnehmung", "Überlebenskunst"], "features": FIGHTER_FEATURES, "spells": {}},
    "Kleriker": {"hit_die": 8, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Einfache Waffen"], "saving_throws": ["Weisheit", "Charisma"], "skill_proficiencies": ["Geschichte", "Menschenkenntnis", "Medizin", "Überzeugen", "Religion"], "features": {1: [{"name": "Göttliche Domäne", "desc": "Wähle eine Domäne, die dir Kräfte verleiht."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "cantrips_known": {1: 3, 4: 4, 10: 5}, "spell_slots": {1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}}, "spells": {"cantrips": ["Heilige Flamme", "Licht"], "level1": ["Segnen", "Heilendes Wort"]}},
    "Magier": {"hit_die": 6, "proficiencies": ["Dolche", "Wurfpfeile", "Schleudern", "Leichte Armbrüste", "Viertelstäbe"], "saving_throws": ["Intelligenz", "Weisheit"], "skill_proficiencies": ["Arkanes Wissen", "Geschichte", "Menschenkenntnis", "Nachforschungen", "Medizin", "Religion"], "features": {1: [{"name": "Arkane Erholung", "desc": "Stelle Zauberplätze bei kurzer Rast wieder her."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "cantrips_known": {1: 3, 4: 4, 10: 5}, "spell_slots": {1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}, 4: {"1": 4, "2": 3}}, "spells": {"cantrips": ["Feuerpfeil", "Magierhand", "Licht"], "level1": ["Magisches Geschoss", "Schild", "Schlaf"]}},
    "Mönch": {"hit_die": 8, "proficiencies": ["Einfache Waffen", "Kurzschwerter"], "saving_throws": ["Stärke", "Geschicklichkeit"], "skill_proficiencies": ["Akrobatik", "Athletik", "Geschichte", "Menschenkenntnis", "Religion", "Heimlichkeit"], "features": {1: [{"name": "Ungepanzerte Verteidigung", "desc": "RK ist 10 + GES-Mod + WEI-Mod."}, {"name": "Kampfkunst", "desc": "GES statt STR für Angriffe."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "spells": {}},
    "Paladin": {"hit_die": 10, "proficiencies": ["Alle Rüstungen", "Schilde", "Einfache Waffen", "Kriegswaffen"], "saving_throws": ["Weisheit", "Charisma"], "skill_proficiencies": ["Athletik", "Menschenkenntnis", "Einschüchtern", "Medizin", "Überzeugen", "Religion"], "features": {1: [{"name": "Göttliches Gespür", "desc": "Spüre Untote/Unholde."}, {"name": "Handauflegen", "desc": "Heile per Berührung."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "spell_slots": {2: {"1": 2}, 3: {"1": 3}, 4: {"1": 3}}, "spells": {}},
    "Schurke": {"hit_die": 8, "proficiencies": ["Leichte Rüstung", "Einfache Waffen", "Handarmbrüste", "Langschwerter", "Rapiere", "Kurzschwerter"], "saving_throws": ["Geschicklichkeit", "Intelligenz"], "skill_proficiencies": ["Akrobatik", "Athletik", "Täuschung", "Menschenkenntnis", "Einschüchtern", "Nachforschungen", "Wahrnehmung", "Auftreten", "Überzeugen", "Fingerfertigkeit", "Heimlichkeit"], "features": {1: [{"name": "Hinterhältiger Angriff (1W6)", "desc": "Zusätzlicher Schaden."}, {"name": "Expertise", "desc": "Verdopple den Übungsbonus für 2 Fertigkeiten."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 10: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "spells": {}},
    "Waldläufer": {"hit_die": 10, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Einfache Waffen", "Kriegswaffen"], "saving_throws": ["Stärke", "Geschicklichkeit"], "skill_proficiencies": ["Tierhandhabung", "Athletik", "Menschenkenntnis", "Nachforschungen", "Natur", "Wahrnehmung", "Heimlichkeit", "Überlebenskunst"], "features": {1: [{"name": "Erzfeind", "desc": "Vorteil gegen bestimmte Kreaturen."}, {"name": "Erfahrener Erkunder", "desc": "Vorteil in bestimmtem Gelände."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "spell_slots": {2: {"1": 2}, 3: {"1": 3}, 4: {"1": 3}}, "spells": {}},
    "Zauberer": {"hit_die": 6, "proficiencies": ["Dolche", "Wurfpfeile", "Schleudern", "Leichte Armbrüste", "Viertelstäbe"], "saving_throws": ["Konstitution", "Charisma"], "skill_proficiencies": ["Arkanes Wissen", "Täuschung", "Einschüchtern", "Nachforschungen", "Überzeugen", "Religion"], "features": {1: [{"name": "Ursprung der Zauberei", "desc": "Deine angeborene Magie verleiht dir Kräfte."}], 4: [{"name": "Attributswerterhöhung", "desc": "..."}], 8: [{"name": "Attributswerterhöhung", "desc": "..."}], 12: [{"name": "Attributswerterhöhung", "desc": "..."}], 16: [{"name": "Attributswerterhöhung", "desc": "..."}], 19: [{"name": "Attributswerterhöhung", "desc": "..."}]}, "cantrips_known": {1: 4, 4: 5, 10: 6}, "spell_slots": {1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}}, "spells": {"cantrips": ["Feuerpfeil", "Licht", "Magierhand", "Schutz vor Klingen"], "level1": ["Magisches Geschoss", "Schild"]}},
}