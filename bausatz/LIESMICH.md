# Bausatz: Agent mit Werkzeugen als fertige Programme

Ein vollständiger, lauffähiger Agent in etwa siebzig Zeilen — und eine Werkzeugsammlung,
in der jedes Werkzeug ein eigenes kleines Programm ist.

## Der Gedanke

Ein Agent, der beliebigen Code ausführen darf, kann alles. Das ist bequem und schwer zu
überblicken. Hier darf er nur, was im Ordner `werkzeuge` liegt:

    werkzeuge/dateiliste.py        Dateien eines Verzeichnisses nennen
    werkzeuge/lies_datei.py        eine Textdatei lesen
    werkzeuge/rechne.py            einen Rechenausdruck auswerten
    werkzeuge/am_arbeitsplatz.py   einen Befehl über die Brücke ausführen

Was der Agent kann, ist damit abzählbar. Ein neues Werkzeug ist eine neue Datei; am Agenten
ändert sich nichts.

## Die Schnittstelle eines Werkzeugs

Jedes Programm kann genau zweierlei:

    python3 werkzeuge/rechne.py --beschreibung
    {"name": "rechne", "zweck": "…", "eingabe": {…}, "probe": {…}}

    python3 werkzeuge/rechne.py '{"ausdruck": "70*9.81*1.5"}'
    70*9.81*1.5 = 1030.05

Mehr nicht. Daraus folgt:

* Ein Werkzeug ist **ohne Modell und ohne Netz prüfbar** — einfach aufrufen.
* Ein Fehler wird **Text**, nie eine Ausnahme. Das Modell kann auf Text reagieren.
* Die Werkzeugliste des Modells **ist** die Dateiliste des Ordners.

## Aufrufe

    python3 agent.py --werkzeuge      die Sammlung zeigen
    python3 agent.py --probe          jedes Werkzeug einmal aufrufen, ohne Modell
    python3 agent.py "Was steht in LIESMICH.md?"

Für den letzten Aufruf braucht es einen Schlüssel in `ANTHROPIC_API_KEY`. Die ersten beiden
laufen ohne alles — damit lässt sich die Sammlung prüfen, bevor ein Modell im Spiel ist.

## Zugang zur Brücke

`am_arbeitsplatz.py` braucht `agent_zugang.json` neben dem Agenten:

    { "empfaenger": "http://127.0.0.1:8085", "token": "<Token des Empfaengers>" }

Das Token steht beim Empfänger in `.empfaenger_token`. **Es gehört nicht in den Programmtext**
— wer das Werkzeug weitergibt, gäbe es sonst mit.

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)
