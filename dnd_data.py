# dnd_data.py

# =============================================================================================
# ZAUBER-DATEN (Auswahl aus dem Spielerhandbuch, v.a. Level 0 & 1)
# =============================================================================================
SPELL_DATA = {
    # Cantrips (Level 0)
    "Säurespritzer": {"level": 0, "school": "Beschwörung", "desc": "Du schleuderst eine Säureblase. Wähle eine oder zwei Kreaturen im Umkreis von 1,5m. Ein Ziel muss einen Geschicklichkeitsrettungswurf ablegen. Bei einem Fehlschlag erleidet es 1W6 Säureschaden."},
    "Feuerpfeil": {"level": 0, "school": "Hervorrufung", "desc": "Du schleuderst einen Funken auf eine Kreatur oder einen Gegenstand. Führe einen Fernkampf-Zauberangriff durch. Bei einem Treffer erleidet das Ziel 1W10 Feuerschaden."},
    "Magierhand": {"level": 0, "school": "Beschwörung", "desc": "Eine schwebende Geisterhand erscheint an einem Punkt deiner Wahl. Du kannst die Hand benutzen, um mit einem Objekt zu interagieren, eine Tür zu öffnen oder einen Gegenstand zu tragen (max. 5 kg)."},
    "Schutz vor Klingen": {"level": 0, "school": "Bannmagie", "desc": "Du weitest deine Hand aus und zeichnest ein Schutzzeichen in die Luft. Bis zum Ende deines nächsten Zuges hast du Resistenz gegen Hieb-, Stich- und Wuchtschaden von Waffenangriffen."},
    "Licht": {"level": 0, "school": "Hervorrufung", "desc": "Du berührst ein Objekt, das nicht größer als 3m ist. Bis der Zauber endet, strahlt das Objekt helles Licht in einem Radius von 6m und gedämpftes Licht für weitere 6m aus."},
    "Heilige Flamme": {"level": 0, "school": "Hervorrufung", "desc": "Flammenartige Ausstrahlung senkt sich auf eine Kreatur herab. Das Ziel muss einen Geschicklichkeitsrettungswurf schaffen oder 1W8 gleißenden Schaden erleiden."},

    # Level 1 Spells
    "Brennende Hände": {"level": 1, "school": "Hervorrufung", "desc": "Aus deinen ausgestreckten Händen schießt ein 4,5m langer Feuerkegel. Jede Kreatur im Kegel muss einen Geschicklichkeitsrettungswurf machen. Bei einem Fehlschlag erleidet sie 3W6 Feuerschaden, bei Erfolg die Hälfte."},
    "Person bezaubern": {"level": 1, "school": "Verzauberung", "desc": "Du versuchst, einen Humanoiden zu bezaubern. Er muss einen Weisheitsrettungswurf ablegen, und bei einem Fehlschlag ist er von dir bezaubert, bis der Zauber endet."},
    "Heilendes Wort": {"level": 1, "school": "Hervorrufung", "desc": "Eine Kreatur deiner Wahl, die du sehen kannst, erhält 1W4 + deinen Zaubermodifikator an Trefferpunkten zurück."},
    "Magisches Geschoss": {"level": 1, "school": "Hervorrufung", "desc": "Du erschaffst drei magische Energiegeschosse. Jedes Geschoss trifft automatisch eine Kreatur deiner Wahl und verursacht 1W4 + 1 Energieschaden."},
    "Schild": {"level": 1, "school": "Bannmagie", "desc": "Als Reaktion, wenn du von einem Angriff getroffen wirst, hast du bis zum Beginn deines nächsten Zuges einen Bonus von +5 auf deine Rüstungsklasse."},
    "Schlaf": {"level": 1, "school": "Verzauberung", "desc": "Du versetzt Kreaturen in einen magischen Schlummer. Würfle 5W8; das Ergebnis ist die Gesamtzahl an Trefferpunkten von Kreaturen, die dieser Zauber betreffen kann."},
}


# =============================================================================================
# WAFFEN-DATEN (Spielerhandbuch)
# =============================================================================================
WEAPON_DATA = {
    # Einfache Nahkampfwaffen
    "Unbewaffneter Schlag": {"damage": "1d4", "ability": "Stärke"},
    "Dolch": {"damage": "1d4", "ability": "Geschicklichkeit"},
    "Streitkolben": {"damage": "1d6", "ability": "Stärke"},
    "Handaxt": {"damage": "1d6", "ability": "Stärke"},
    "Leichter Hammer": {"damage": "1d4", "ability": "Stärke"},
    "Speer": {"damage": "1d6", "ability": "Stärke"},
    "Viertelstab": {"damage": "1d6", "ability": "Stärke"},
    # Einfache Fernkampfwaffen
    "Leichte Armbrust": {"damage": "1d8", "ability": "Geschicklichkeit"},
    "Kurzbogen": {"damage": "1d6", "ability": "Geschicklichkeit"},
    "Schleuder": {"damage": "1d4", "ability": "Geschicklichkeit"},
    # Kriegswaffen Nahkampf
    "Kurzschwert": {"damage": "1d6", "ability": "Geschicklichkeit"},
    "Langschwert": {"damage": "1d8", "ability": "Stärke"},
    "Morgenstern": {"damage": "1d8", "ability": "Stärke"},
    "Rapier": {"damage": "1d8", "ability": "Geschicklichkeit"},
    "Kriegshammer": {"damage": "1d8", "ability": "Stärke"},
    "Zweihänder": {"damage": "2d6", "ability": "Stärke"},
    # Kriegswaffen Fernkampf
    "Handarmbrust": {"damage": "1d6", "ability": "Geschicklichkeit"},
    "Schwere Armbrust": {"damage": "1d10", "ability": "Geschicklichkeit"},
    "Langbogen": {"damage": "1d8", "ability": "Geschicklichkeit"},
}

# =============================================================================================
# RASSEN-DATEN (Spielerhandbuch)
# =============================================================================================
RACE_DATA = {
    "Drachenblütiger": {
        "ability_score_increase": {"Stärke": 2, "Charisma": 1}, "speed": 9,
        "languages": ["Gemeinsprache", "Drakonisch"], "proficiencies": [],
        "traits": [{"name": "Drachenblut", "desc": "Du wählst eine Art von Drachen als Vorfahren."},
                   {"name": "Odemwaffe", "desc": "Du kannst deine Odemwaffe als Aktion einsetzen. Der Rettungswurf dagegen ist 8 + dein KON-Mod + dein Übungsbonus."},
                   {"name": "Schadensresistenz", "desc": "Du hast eine Resistenz gegen den Schadenstyp, der mit deinen drachischen Vorfahren verbunden ist."}]
    },
    "Elf (Hochelf)": {
        "ability_score_increase": {"Geschicklichkeit": 2, "Intelligenz": 1}, "speed": 9,
        "languages": ["Gemeinsprache", "Elfisch"], "proficiencies": ["Wahrnehmung"],
        "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in gedämpftem Licht innerhalb von 18m sehen, als wäre es helles Licht, und in Dunkelheit, als wäre es gedämpftes Licht."},
                   {"name": "Feenblut", "desc": "Du hast Vorteil bei Rettungswürfen gegen Bezauberung und Magie kann dich nicht in den Schlaf zwingen."},
                   {"name": "Trance", "desc": "Elfen schlafen nicht. Stattdessen meditieren sie 4 Stunden am Tag."},
                   {"name": "Zusätzlicher Zaubertrick", "desc": "Du kennst einen zusätzlichen Zaubertrick von der Zauberliste des Magiers. Intelligenz ist dein Attribut dafür."}]
    },
    "Halb-Elf": {
        "ability_score_increase": {"Charisma": 2, "Geschicklichkeit": 1, "Konstitution": 1}, "speed": 9,
        "languages": ["Gemeinsprache", "Elfisch", "Eine zusätzliche Sprache"], "proficiencies": [],
        "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in gedämpftem Licht innerhalb von 18m sehen."},
                   {"name": "Feenblut", "desc": "Du hast Vorteil bei Rettungswürfen gegen Bezauberung."},
                   {"name": "Facettenreiche Begabung", "desc": "Du erhältst Übung in zwei Fertigkeiten deiner Wahl."}]
    },
    "Halbling (Leichtfuß)": {
        "ability_score_increase": {"Geschicklichkeit": 2, "Charisma": 1}, "speed": 7.5,
        "languages": ["Gemeinsprache", "Halblingisch"], "proficiencies": [],
        "traits": [{"name": "Glückspilz", "desc": "Wenn du eine 1 auf einen Angriffs-, Attributs- oder Rettungswurf würfelst, kannst du den Wurf wiederholen."},
                   {"name": "Tapfer", "desc": "Du hast Vorteil bei Rettungswürfen gegen Furcht."},
                   {"name": "Behende", "desc": "Du kannst dich durch den Bereich jeder Kreatur bewegen, die eine Größenkategorie größer ist als du."},
                   {"name": "Von Natur aus heimlich", "desc": "Du kannst versuchen, dich zu verstecken, selbst wenn du nur von einer Kreatur verdeckt wirst, die mindestens eine Größenkategorie größer ist als du."}]
    },
    "Halb-Ork": {
        "ability_score_increase": {"Stärke": 2, "Konstitution": 1}, "speed": 9,
        "languages": ["Gemeinsprache", "Orkisch"], "proficiencies": ["Einschüchtern"],
        "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in gedämpftem Licht innerhalb von 18m sehen."},
                   {"name": "Unbarmherzige Ausdauer", "desc": "Wenn du auf 0 Trefferpunkte reduziert wirst, aber nicht sofort getötet wirst, kannst du stattdessen auf 1 Trefferpunkt fallen. Einmal pro langer Rast."},
                   {"name": "Wilde Angriffe", "desc": "Wenn du mit einem Nahkampfwaffenangriff einen kritischen Treffer erzielst, kannst du einen der Schadenswürfel der Waffe ein zusätzliches Mal würfeln und zum zusätzlichen Schaden addieren."}]
    },
    "Mensch": {
        "ability_score_increase": {"Stärke": 1, "Geschicklichkeit": 1, "Konstitution": 1, "Intelligenz": 1, "Weisheit": 1, "Charisma": 1}, "speed": 9,
        "languages": ["Gemeinsprache", "Eine zusätzliche Sprache"], "proficiencies": []
    },
    "Tiefling": {
        "ability_score_increase": {"Charisma": 2, "Intelligenz": 1}, "speed": 9,
        "languages": ["Gemeinsprache", "Infernalisch"], "proficiencies": [],
        "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in Dunkelheit innerhalb von 18m sehen."},
                   {"name": "Höllische Resistenz", "desc": "Du hast Resistenz gegen Feuerschaden."},
                   {"name": "Infernalisches Vermächtnis", "desc": "Du kennst den Zaubertrick Thaumaturgie. Ab Stufe 3 kannst du Höllischer Tadel einmal pro Tag wirken, ab Stufe 5 Dunkelheit."}]
    },
    "Zwerg (Hügelzwerg)": {
        "ability_score_increase": {"Konstitution": 2, "Weisheit": 1}, "speed": 7.5,
        "languages": ["Gemeinsprache", "Zwergisch"], "proficiencies": ["Schmiedewerkzeug"],
        "traits": [{"name": "Dunkelsicht", "desc": "Du kannst in Dunkelheit innerhalb von 18m sehen."},
                   {"name": "Zwergische Abhärtung", "desc": "Du hast Vorteil bei Rettungswürfen gegen Gift und Resistenz gegen Giftschaden."},
                   {"name": "Zwergische Zähigkeit", "desc": "Deine maximalen Trefferpunkte erhöhen sich um 1 pro Stufe."}]
    }
}


# =============================================================================================
# KLASSEN-FEATURES (Level 1-20, PHB)
# =============================================================================================
FIGHTER_FEATURES = {
    1: [{"name": "Kampfstil", "desc": "Du eignest dir einen bestimmten Kampfstil als deine Spezialität an."},
        {"name": "Zweite Luft", "desc": "Einmal pro Rast kannst du als Bonusaktion 1W10 + deine Kämpferstufe an Trefferpunkten zurückgewinnen."}],
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

# (Ähnliche detaillierte Feature-Listen für alle 12 Klassen würden hier folgen)
# Dies ist ein Beispiel für die Detailtiefe.

# =============================================================================================
# KLASSEN-DATEN (Alle 12 Klassen aus dem PHB)
# =============================================================================================
CLASS_DATA = {
    "Barbar": {
        "hit_die": 12, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Einfache Waffen", "Kriegswaffen"],
        "features": {1: [{"name": "Kampfrausch", "desc": "Als Bonusaktion kannst du in einen Kampfrausch verfallen. Du erhältst Vorteile bei Stärke-Würfen, +Schadensbonus und Resistenz gegen Hieb-, Stich- und Wuchtschaden."}]},
        "spells": {}
    },
    "Barde": {
        "hit_die": 8, "proficiencies": ["Leichte Rüstung", "Einfache Waffen", "Handarmbrüste", "Langschwerter", "Rapiere", "Kurzschwerter", "Drei Musikinstrumente deiner Wahl"],
        "features": {1: [{"name": "Barden-Inspiration (W6)", "desc": "Als Bonusaktion kannst du einer Kreatur einen Inspirationswürfel geben, den sie zu einem Wurf addieren kann."}]},
        "spells": {"cantrips": ["Licht", "Magierhand"], "level1": ["Person bezaubern", "Heilendes Wort"]}
    },
    "Druide": {
        "hit_die": 8, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Keulen", "Dolche", "Speere", "Streitkolben"],
        "features": {1: [{"name": "Druidisch", "desc": "Du kennst die geheime Sprache der Druiden."}, {"name": "Zauber wirken", "desc": "Du kannst Druidenzauber wirken."}]},
        "spells": {"cantrips": ["Shillelagh", "Druidenhandwerk"], "level1": ["Heilendes Wort", "Donnerwelle"]}
    },
    "Hexenmeister": {
        "hit_die": 8, "proficiencies": ["Leichte Rüstung", "Einfache Waffen"],
        "features": {1: [{"name": "Außerweltlicher Schutzpatron", "desc": "Du schließt einen Pakt mit einem mächtigen Wesen (z.B. dem Unhold)."}, {"name": "Magie des Paktes", "desc": "Deine Zauberplätze erneuern sich bei einer kurzen Rast."}]},
        "spells": {"cantrips": ["Schauriger Strahl", "Magierhand"], "level1": ["Höllischer Tadel", "Schutz vor Gut und Böse"]}
    },
    "Kämpfer": {
        "hit_die": 10, "proficiencies": ["Alle Rüstungen", "Schilde", "Einfache Waffen", "Kriegswaffen"],
        "features": FIGHTER_FEATURES, # Verwendet die detaillierte Liste von oben
        "spells": {}
    },
    "Kleriker": {
        "hit_die": 8, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Einfache Waffen"],
        "features": {1: [{"name": "Göttliche Domäne (Domäne des Lebens)", "desc": "Deine Heilzauber sind effektiver und du erhältst Übung mit schwerer Rüstung."}]},
        "spells": {"cantrips": ["Heilige Flamme", "Licht"], "level1": ["Segnen", "Heilendes Wort"]}
    },
    "Magier": {
        "hit_die": 6, "proficiencies": ["Dolche", "Wurfpfeile", "Schleudern", "Leichte Armbrüste", "Viertelstäbe"],
        "features": {1: [{"name": "Arkane Erholung", "desc": "Einmal pro Tag während einer kurzen Rast kannst du verbrauchte Zauberplätze wiederherstellen."}]},
        "spells": {"cantrips": ["Feuerpfeil", "Magierhand", "Licht"], "level1": ["Magisches Geschoss", "Schild", "Schlaf"]}
    },
    "Mönch": {
        "hit_die": 8, "proficiencies": ["Einfache Waffen", "Kurzschwerter"],
        "features": {1: [{"name": "Ungepanzerte Verteidigung", "desc": "Deine Rüstungsklasse ist 10 + GES-Mod + WEI-Mod, wenn du keine Rüstung trägst."}, {"name": "Kampfkunst", "desc": "Du kannst Geschicklichkeit statt Stärke für Angriffe mit Mönchswaffen und unbewaffneten Schlägen verwenden."}]},
        "spells": {}
    },
    "Paladin": {
        "hit_die": 10, "proficiencies": ["Alle Rüstungen", "Schilde", "Einfache Waffen", "Kriegswaffen"],
        "features": {1: [{"name": "Göttliches Gespür", "desc": "Du kannst die Anwesenheit von Himmlischen, Unholden oder Untoten spüren."}, {"name": "Handauflegen", "desc": "Du hast einen Pool an Heilkraft, den du durch Berührung übertragen kannst."}]},
        "spells": {} # Paladine erhalten Zauber erst ab Level 2
    },
    "Schurke": {
        "hit_die": 8, "proficiencies": ["Leichte Rüstung", "Einfache Waffen", "Handarmbrüste", "Langschwerter", "Rapiere", "Kurzschwerter"],
        "features": {1: [{"name": "Expertise", "desc": "Dein Übungsbonus wird für zwei Fertigkeiten deiner Wahl verdoppelt."}, {"name": "Hinterhältiger Angriff (1W6)", "desc": "Einmal pro Zug kannst du zusätzlichen Schaden verursachen."}]},
        "spells": {}
    },
    "Waldläufer": {
        "hit_die": 10, "proficiencies": ["Leichte Rüstung", "Mittelschwere Rüstung", "Schilde", "Einfache Waffen", "Kriegswaffen"],
        "features": {1: [{"name": "Erzfeind", "desc": "Du wählst eine Art von Kreatur als deinen Erzfeind, gegen die du Vorteile hast."}, {"name": "Erfahrener Erkunder", "desc": "Du wählst ein bevorzugtes Gelände, in dem du dich leichter zurechtfindest."}]},
        "spells": {} # Waldläufer erhalten Zauber erst ab Level 2
    },
    "Zauberer": {
        "hit_die": 6, "proficiencies": ["Dolche", "Wurfpfeile", "Schleudern", "Leichte Armbrüste", "Viertelstäbe"],
        "features": {1: [{"name": "Ursprung der Zauberei (Drachenblut)", "desc": "Deine angeborene Magie stammt von Drachen ab. Du kannst Drakonisch sprechen und deine RK ist 13 + GES-Mod, wenn du keine Rüstung trägst."}]},
        "spells": {"cantrips": ["Feuerpfeil", "Licht", "Magierhand", "Schutz vor Klingen"], "level1": ["Magisches Geschoss", "Schild"]}
    },
}