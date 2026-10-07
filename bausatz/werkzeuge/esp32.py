#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: ein MicroPython-Brett bedienen — schreiben, starten, mitlesen.

Das ist das Werkzeug, mit dem ein Modell ein selbst geschriebenes Programm auf einen ESP32
bringt und nachsieht, was dort geschieht. Es gibt dem Modell **keine Reihenfolge vor**: Was
wann getan wird, entscheidet das Modell aus dem Auftrag. Hier stehen nur die Handgriffe.

    schreiben     Programmtext in eine Datei legen (im Übergabeordner)
    uebertragen   diese Datei auf das Brett, Prüfsumme kommt VOM BRETT zurück
    starten       Brett neu starten, danach läuft main.py
    mitlesen      zuhören, was das Brett über die serielle Leitung sagt
    anschluesse   welche Anschlüsse es gibt und welcher nach einem ESP32 aussieht
    liste         was auf dem Brett liegt

Der Weg führt über die Brücke auf dem Arbeitsplatzrechner; sie holt die Aufträge von sich aus
ab. Zugang steht in ``agent_zugang.json`` neben dem Agenten, nicht hier im Programm.
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug                                              # noqa: E402

ZUGANG = pathlib.Path(__file__).resolve().parent.parent / "agent_zugang.json"
ABLAGE = pathlib.Path("/workspace/Kurs_Agent/Arbeitsstand/Laptop")        # von hier holt die Brücke
PROJEKT = "Kurs_Agent"
WARTEN = 300


def zugang() -> tuple[str, str]:
    if not ZUGANG.is_file():
        raise RuntimeError(f"Zugangsdatei fehlt: {ZUGANG}")
    j = json.loads(ZUGANG.read_text(encoding="utf-8"))
    return j["empfaenger"].rstrip("/"), j["token"]


def bruecke(typ: str, arg: str) -> str:
    """Einen Auftrag in die Warteschlange legen und auf die Antwort der Brücke warten."""
    basis, token = zugang()
    f = {"token": token, "projekt": PROJEKT, "typ": typ, "url": arg}
    nr = urllib.request.urlopen(urllib.request.Request(
        basis + "/befehl?" + urllib.parse.urlencode(f), data=b"", method="POST"),
        timeout=20).read().decode().strip()
    ende = time.time() + WARTEN
    while time.time() < ende:
        time.sleep(2)
        t = urllib.request.urlopen(
            basis + "/antwort_lesen?" + urllib.parse.urlencode({"id": nr}), timeout=15
        ).read().decode(errors="replace").strip()
        if t:
            return t
    return f"FEHLER: die Brücke hat in {WARTEN} s nicht geantwortet. Läuft sie auf dem Rechner?"


def tun(e: dict) -> str:
    was = e["was"]
    port = e.get("port", "COM3")

    if was == "anschluesse":
        return bruecke("anschluesse", "")

    if was == "liste":
        return bruecke("mpy", f"liste {port}")

    if was == "starten":
        return bruecke("mpy", f"reset {port}")

    if was == "mitlesen":
        s = max(1, min(int(e.get("sekunden", 10)), 60))
        return bruecke("seriell", f"{port} {s}")

    if was == "schreiben":
        name = e.get("datei", "programm.py")
        if "/" in name or "\\" in name or not name.endswith(".py"):
            return f"FEHLER: {name} ist kein zulässiger Dateiname (nur <name>.py, ohne Pfad)"
        if "text" not in e:
            return "FEHLER: es fehlt: text (der Programmtext)"
        ABLAGE.mkdir(parents=True, exist_ok=True)
        (ABLAGE / name).write_text(e["text"], encoding="utf-8")
        import hashlib
        h = hashlib.sha256(e["text"].encode("utf-8")).hexdigest()
        return (f"{name} geschrieben: {len(e['text'].encode('utf-8'))} Byte, sha256 {h}\n"
                f"Als Nächstes kann sie mit was=uebertragen auf das Brett.")

    if was == "uebertragen":
        name = e.get("datei", "programm.py")
        ziel = e.get("ziel", "main.py")
        if not (ABLAGE / name).is_file():
            return f"FEHLER: {name} gibt es nicht. Erst mit was=schreiben anlegen."
        a = bruecke("update", name)
        if "übernommen" not in a:
            return f"FEHLER: die Datei kam nicht auf dem Rechner an.\n{a}"
        return bruecke("mpy", f"senden {name} {port} {ziel}")

    return (f"FEHLER: {was} kenne ich nicht. Möglich: schreiben, uebertragen, starten, "
            f"mitlesen, anschluesse, liste")


if __name__ == "__main__":
    sys.exit(werkzeug(
        name="esp32",
        zweck=("Ein MicroPython-Brett am Arbeitsplatz bedienen: ein Programm schreiben, es "
               "übertragen (die Prüfsumme kommt vom Brett zurück), das Brett starten und "
               "mitlesen, was es sagt. Die Reihenfolge bestimmst du."),
        felder={
            "was": {"type": "string",
                    "enum": ["schreiben", "uebertragen", "starten", "mitlesen", "anschluesse", "liste"],
                    "description": "der Handgriff"},
            "text": {"type": "string", "description": "bei was=schreiben: der vollständige Programmtext"},
            "datei": {"type": "string", "description": "Dateiname, z. B. blink.py (Standard programm.py)"},
            "ziel": {"type": "string", "description": "bei was=uebertragen: Name auf dem Brett (Standard main.py, "
                                                      "das führt MicroPython nach dem Start aus)"},
            "port": {"type": "string", "description": "Anschluss, Standard COM3"},
            "sekunden": {"type": "integer", "description": "bei was=mitlesen: wie lange zugehört wird (Standard 10)"},
        },
        pflicht=["was"],
        probe={"was": "anschluesse"},
        tun=tun))
