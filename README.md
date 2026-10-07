# Wie eine KI lokale Hard- und Software steuert

<img src="Foto_Ralph_Wystup.jpg" align="right" width="140" alt="Prof. Dr.-Ing. Ralph Wystup">

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)

Eine KI mit Agent läuft in einem Behälter auf einem Server. Sie kann rechnen und Programme schreiben — aber sie sieht keinen Bildschirm, keinen seriellen Anschluss, keine Messgeräte. Die Arbeit findet am Arbeitsplatz statt. Dieses Blatt zeigt, wie man beides verbindet, **ohne einen einzigen offenen Port**.

**Seite öffnen:** https://ralphwystup.github.io/KI-steuert-lokale-Hardware-ueber-eine-Bruecke/ — Fassung 1.1 · 07.10.2026

Die Seite ist **eine einzige HTML-Datei** mit einer laufenden Agentenschleife zum Zusehen. Sie braucht keinen Server, keine Installation und keine Bibliothek.

## Der Gedanke

Nicht der Server greift auf den Arbeitsplatz zu — der Arbeitsplatz **holt sich** die Aufträge. Damit ist jede Verbindung von innen nach außen gerichtet: keine Portfreigabe, keine feste Adresse, kein Dienst, der auf Verbindungen wartet.

Drei Ebenen:

| Ebene | läuft wo | Aufgabe |
|:--|:--|:--|
| Sprachmodell | beim Anbieter | entscheidet, tut nichts |
| Agent + Werkzeuge | auf dem Server | führt aus, aber nur was im Werkzeugordner liegt |
| Brücke | am Arbeitsplatz | holt alle zwei Sekunden Aufträge, führt sie aus, antwortet |

## Was dabei ist

| Datei | Inhalt |
|:--|:--|
| [`Bruecke_KI_und_Arbeitsplatz_1.1.html`](Bruecke_KI_und_Arbeitsplatz_1.1.html) | die Seite: Aufbau, Schaubilder, Code, Vorschriften, eine laufende Agentenschleife |
| [`bruecke.py`](bruecke.py) | die Brücke für den Arbeitsplatz, alle Projekte in einem Programm |
| [`befehl.py`](befehl.py) | einen Auftrag absetzen und auf die Antwort warten |
| [`empfaenger.py`](empfaenger.py) | die Warteschlange auf dem Server |
| [`bausatz/agent.py`](bausatz/agent.py) | ein vollständiger Agent in etwa siebzig Zeilen |
| [`bausatz/werkzeuge/`](bausatz/werkzeuge) | acht Werkzeuge, jedes ein eigenes Programm — darunter `esp32` (ein MicroPython-Brett bedienen) und `kurve_bewerten` (welche Kurvenform haben diese Messwerte?) |
| [`kette/agent_lokal.py`](kette/agent_lokal.py) | Agentenschleife mit dem Sprachmodell auf dem Arbeitsplatzrechner: das Modell entscheidet, dieses Programm führt nur aus |
| [`kette/auftraege.json`](kette/auftraege.json) | feste Aufträge mit erwarteter Messgröße und Schranke |
| [`kette/pruefe_kette.py`](kette/pruefe_kette.py) | Prüfmittel der Strecke: Programm bis auf das Brett, jeder Schritt gemessen |
| [`PRUEFPLAN.md`](PRUEFPLAN.md) | die Kriterien, mit Schranke und Prüfmittel je Punkt |
| [`BRUECKE.md`](BRUECKE.md) | Kurzanleitung zur Brücke |

## Werkzeuge als fertige Programme

Ein Agent, der beliebigen Code ausführen darf, kann alles — das ist bequem und schwer zu überblicken. Hier darf er nur, was im Ordner `werkzeuge` liegt. Jedes Programm beschreibt sich selbst:

    python3 werkzeuge/rechne.py --beschreibung
    {"name": "rechne", "zweck": "…", "eingabe": {…}, "probe": {…}}

    python3 werkzeuge/rechne.py '{"ausdruck": "70*9.81*1.5"}'
    70*9.81*1.5 = 1030.05

Daraus folgt: Was der Agent kann, ist **abzählbar**. Jedes Werkzeug ist **ohne Modell und ohne Netz prüfbar**. Und die Werkzeugliste des Modells **ist** die Dateiliste des Ordners — sie können nicht auseinanderlaufen.

    python3 agent.py --probe      ruft jedes Werkzeug einmal auf, ohne Modell
    6 von 6 in Ordnung

## Zugangsdaten

Weder Brücke noch Agent tragen Adresse oder Token im Programmtext. Beides steht in einer Datei daneben; Beispiele mit Platzhaltern liegen bei (`bruecke_zugang.beispiel.json`, `bausatz/agent_zugang.beispiel.json`). Wer ein Werkzeug weitergibt, in dem das Geheimnis steht, gibt es mit — und merkt es nicht.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
