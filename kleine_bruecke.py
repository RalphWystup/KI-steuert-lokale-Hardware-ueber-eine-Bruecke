#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kleine Brücke: holt und bringt Dateien, sonst nichts.

    python3 kleine_bruecke.py                      läuft los, Kanal "Unterwegs"
    python3 kleine_bruecke.py --kanal Unterwegs --ordner C:\\Arbeit
    python3 kleine_bruecke.py --einmal             einen Durchlauf, dann Schluss

Wofür
-----
Die große Brücke (``bruecke.py``) kann ein CAD-Programm bedienen, ein Steckbrett flashen, ein
Sprachmodell starten. Das will man nicht auf jedem Rechner. Diese hier kann **drei Dinge**:
auflisten, eine Datei holen, eine Datei bringen. Mehr gibt es nicht — kein Programmstart, kein
Löschen, kein Zugriff außerhalb ihres Ordners.

Damit lässt sich ein zweiter Rechner an denselben Arbeitsbereich hängen, ohne dass dort etwas
installiert wird außer Python selbst.

**Jede Brücke braucht ihren eigenen Kanal.** Zwei Brücken am selben Kanal holen abwechselnd
Aufträge aus derselben Warteschlange; welcher Rechner welchen bekommt, ist dann Zufall, und man
sucht den Fehler an der falschen Stelle. Darum steht der Kanal oben und ist nicht der der großen
Brücke.

Zugang
------
Neben dieser Datei liegt ``kleine_bruecke_zugang.json``:

    { "empfaenger": "https://…", "token": "<Token>" }

Das Token steht nicht im Programm. Wer die Datei weitergibt, gibt keinen Zugang weiter.
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

HIER = pathlib.Path(__file__).resolve().parent
ZUGANG = HIER / "kleine_bruecke_zugang.json"
TAKT = 3                      # Sekunden zwischen zwei Blicken in die Warteschlange
MAX_DATEI = 64 * 1024 * 1024  # eine Datei bis 64 MB


def zugang() -> tuple[str, str]:
    if not ZUGANG.is_file():
        raise SystemExit(f"Zugangsdatei fehlt: {ZUGANG}\n"
                         '  {{ "empfaenger": "https://…", "token": "<Token>" }}')
    j = json.loads(ZUGANG.read_text(encoding="utf-8"))
    for k in ("empfaenger", "token"):
        if not j.get(k):
            raise SystemExit(f"In {ZUGANG} fehlt: {k}")
    return j["empfaenger"].rstrip("/"), j["token"]


def sicher(ordner: pathlib.Path, name: str) -> pathlib.Path:
    """Einen Pfad im eigenen Ordner bilden — und nur dort.

    Ein Name, der aus dem Ordner herausführt (``..``, ein Laufwerksbuchstabe, ein führender
    Schrägstrich), wird abgewiesen. Das ist die einzige Stelle, an der diese Brücke gefährlich
    werden könnte, deshalb steht die Prüfung hier und nicht verteilt.
    """
    p = (ordner / name).resolve()
    if not str(p).startswith(str(ordner.resolve())):
        raise ValueError(f"{name} führt aus {ordner} heraus")
    return p


def auflisten(ordner: pathlib.Path, rest: str) -> str:
    ziel = sicher(ordner, rest.strip()) if rest.strip() else ordner
    if not ziel.is_dir():
        return f"FEHLER: {ziel} ist kein Ordner"
    zeilen = []
    for d in sorted(ziel.iterdir()):
        zeilen.append(f"  {'<DIR> ' if d.is_dir() else f'{d.stat().st_size:>8}'}  {d.name}")
    return f"{ziel} ({len(zeilen)} Einträge):\n" + "\n".join(zeilen[:300])


def bringen(basis: str, token: str, kanal: str, ordner: pathlib.Path, rest: str) -> str:
    """Dateien aus dem Arbeitsbereich holen und hier ablegen (wie 'update' der großen Brücke)."""
    namen, _, unterordner = rest.partition(" -> ")
    ziel = sicher(ordner, unterordner.strip()) if unterordner.strip() else ordner
    ziel.mkdir(parents=True, exist_ok=True)
    aus = []
    for name in [n.strip() for n in namen.split(",") if n.strip()]:
        f = {"token": token, "projekt": kanal, "name": name}
        try:
            with urllib.request.urlopen(f"{basis}/datei?" + urllib.parse.urlencode(f), timeout=120) as r:
                inhalt = r.read(MAX_DATEI)
        except Exception as e:
            aus.append(f"{name}: FEHLER {e}")
            continue
        (ziel / pathlib.Path(name).name).write_bytes(inhalt)
        aus.append(f"{name}: {len(inhalt)} Byte übernommen")
    return f"nach {ziel}: " + "; ".join(aus)


def holen(basis: str, token: str, kanal: str, ordner: pathlib.Path, rest: str) -> str:
    """Eine Datei von hier in den Arbeitsbereich schicken (wie 'hochladen')."""
    p = sicher(ordner, rest.strip())
    if not p.is_file():
        return f"FEHLER: {p} gibt es nicht"
    daten = p.read_bytes()[:MAX_DATEI]
    f = {"token": token, "projekt": kanal, "name": p.name}
    req = urllib.request.Request(f"{basis}/upload?" + urllib.parse.urlencode(f), data=daten,
                                 method="POST", headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return f"{p.name}: {len(daten)} Byte hochgeladen — " + r.read().decode(errors="replace").strip()[:200]


def ausfuehren(ordner: pathlib.Path, rest: str) -> str:
    """Ein Python-Programm aus DIESEM Ordner laufen lassen und seine Ausgabe zurückgeben.

    Die kleine Brücke konnte zunächst nur Dateien. Das war zu eng: Eine Prüfung, die auf dem
    zweiten Rechner laufen soll, muss von dort auch gestartet werden können — sonst muss ein
    Mensch sie abtippen, und man prüft nicht den Rechner, sondern seine Geduld (Auftraggeber,
    08.10.2026: „warum brauchst du das, du hast doch die kleine und die große Brücke").

    Der Rahmen ist derselbe wie bei der großen Brücke:

      * Nur eine Datei, die in diesem Ordner liegt, und nur mit der Endung .py.
      * Der Name darf nur Buchstaben, Ziffern, Punkt, Strich, Unterstrich enthalten — kein Pfad.
      * Argumente sind erlaubt, aber nur aus demselben engen Zeichenvorrat; nichts wird an eine
        Kommandozeile durchgereicht, der Aufruf wird hier gebaut.
      * Genommen wird das Python des Kurspakets, falls vorhanden, sonst das laufende.
      * Höchstens 15 Minuten, höchstens 60 kB Ausgabe.
    """
    teile = (rest or "").split()
    if not teile:
        return "FEHLER: Aufruf python <datei.py> [kurze Argumente]"
    name = teile[0]
    import re
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.py", name):
        return f"FEHLER: {name} ist kein zulässiger Dateiname (nur <name>.py, ohne Pfad)"
    datei = sicher(ordner, name)
    if not datei.is_file():
        return f"FEHLER: {name} liegt nicht in {ordner}"
    argumente = teile[1:]
    for a in argumente:
        if not re.fullmatch(r"[A-Za-z0-9._=/\\:-]{1,120}", a):
            return f"FEHLER: Argument {a!r} enthält Zeichen, die hier nicht durchgehen"
    kurspython = ordner / "ablage" / "python" / "python.exe"
    py = str(kurspython) if kurspython.is_file() else sys.executable
    import subprocess
    try:
        r = subprocess.run([py, str(datei)] + argumente, capture_output=True, text=True,
                           timeout=900, cwd=str(ordner))
    except subprocess.TimeoutExpired:
        return f"FEHLER: {name} lief länger als 15 Minuten und wurde beendet"
    aus = ((r.stdout or "") + (r.stderr or ""))[:60000]
    return f"{name} mit {pathlib.Path(py).name}, Rückgabe {r.returncode}:\n{aus}"


def einmal(basis: str, token: str, kanal: str, ordner: pathlib.Path) -> int:
    """Einen Blick in die Warteschlange; gibt die Zahl der bearbeiteten Aufträge zurück."""
    f = urllib.parse.urlencode({"token": token, "projekt": kanal})
    try:
        with urllib.request.urlopen(f"{basis}/befehle?{f}", timeout=20) as r:
            auftraege = json.loads(r.read() or "[]")
    except Exception as e:
        print(f"  Warteschlange nicht erreichbar: {e}")
        return 0
    for a in auftraege:
        typ, arg = a.get("typ", ""), a.get("url", "")
        print(f"  {typ} {arg[:70]}")
        try:
            if typ == "dateiliste":
                text = auflisten(ordner, arg)
            elif typ == "update":
                text = bringen(basis, token, kanal, ordner, arg)
            elif typ == "hochladen":
                text = holen(basis, token, kanal, ordner, arg)
            elif typ == "python":
                text = ausfuehren(ordner, arg)
            elif typ == "info":
                text = (f"Kleine Brücke 1.0 auf {os.environ.get('COMPUTERNAME') or os.uname().nodename}, "
                        f"Kanal {kanal}, Ordner {ordner}. Kann: dateiliste, update, hochladen, python, info.")
            else:
                text = (f"FEHLER: {typ} kennt die kleine Brücke nicht. Sie kann dateiliste, "
                        f"update, hochladen, python, info — mehr absichtlich nicht.")
        except Exception as e:
            text = f"FEHLER: {type(e).__name__}: {e}"
        g = urllib.parse.urlencode({"token": token, "id": a.get("id", "")})
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"{basis}/antwort?{g}", data=text.encode("utf-8"), method="POST"), timeout=30).read()
        except Exception as e:
            print(f"    Antwort kam nicht durch: {e}")
    return len(auftraege)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--kanal", default="Unterwegs", help="eigener Kanal, NICHT der der großen Brücke")
    p.add_argument("--ordner", default=str(HIER), help="in diesem Ordner wird gearbeitet, nur hier")
    p.add_argument("--einmal", action="store_true", help="einen Durchlauf, dann Schluss")
    a = p.parse_args()
    basis, token = zugang()
    ordner = pathlib.Path(a.ordner).resolve()
    ordner.mkdir(parents=True, exist_ok=True)
    print(f"Kleine Brücke 1.0 — Kanal {a.kanal}, Ordner {ordner}")
    print(f"  Warteschlange: {basis}")
    print("  Kann: auflisten, holen, bringen, python <datei.py> aus diesem Ordner.\n")
    if a.einmal:
        return 0 if einmal(basis, token, a.kanal, ordner) >= 0 else 1
    letzte = time.time()
    while True:
        n = einmal(basis, token, a.kanal, ordner)
        if n == 0 and time.time() - letzte > 60:
            letzte = time.time()
            print(f"  {time.strftime('%H:%M:%S')} — wartet")
        time.sleep(TAKT)


if __name__ == "__main__":
    sys.exit(main())
