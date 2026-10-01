# Die Brücke

Verbindet den PC mit dem Workspace. **Eine für alle Projekte.**

## Auf dem PC

Ordner `C:\Bruecke`, darin `bruecke.py`. Starten mit `Bruecke_starten.bat` — die Datei
schreibt sich beim ersten Lauf selbst. Das Fenster heißt „Bruecke – alle Projekte" und
muss offen bleiben; es startet sich nach einem Absturz selbst neu.

## Im Workspace

`befehl.py` schickt einen Befehl und wartet auf die Antwort:

    python3 befehl.py info
    python3 befehl.py -p Layout dateiliste "C:\Layout"
    python3 befehl.py -p Projekt_B hochladen "C:\Projekt_B\Datei.odt"

Ohne `-p` geht der Befehl an das Projekt Projekt_A.

## Wie es arbeitet

Die Brücke **holt** Befehle ab, sie empfängt keine. Deshalb muss am PC kein Port offen
sein, keine Freigabe in der Firewall, keine feste Adresse. In jedem Durchlauf fragt sie
alle Projekte aus `PROJEKTE` der Reihe nach ab und antwortet jeweils demselben Projekt.

Dateien gehen immer in den Ordner **des Projekts, aus dem der Befehl kam**:

| Richtung | Ort im Workspace |
|:--|:--|
| `hochladen` (PC → Workspace) | `<Projekt>/Bilder/` |
| `update` (Workspace → PC) | aus `<Projekt>/Arbeitsstand/Laptop/` |

**Ein neues Projekt braucht zweierlei:** eine Zeile in `PROJEKTE` und im Workspace die
Ordner `<Projekt>/Arbeitsstand/Laptop` und `<Projekt>/Bilder`. Fehlt `Arbeitsstand`,
erkennt der Empfänger das Projekt nicht und legt alles im Standardprojekt ab — das kostete
am 01.10.2026 eine halbe Stunde Fehlersuche.

## Was sie nicht tut

Keine Programme starten (außer FEMM), nichts Ausführbares öffnen, nur Datenendungen.
Verschieben und Löschen nur in ausdrücklich erlaubten Zweigen und nur für namentlich
genannte Dateien. Von jeder überschriebenen Datei bleiben drei Fassungen im
Sicherungsordner.

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)
