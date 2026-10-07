#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agentenschleife mit dem Sprachmodell, das auf dem Arbeitsplatzrechner liegt.

    python3 agent_lokal.py "<Auftrag>"  [--modell coder|3b|7b] [--runden 12]
    python3 agent_lokal.py --auftrag atmen-sinus

Der Unterschied zu allem, was hier vorher stand: **Die Reihenfolge der Schritte entscheidet das
Modell.** Dieses Programm fragt nur, führt aus, was das Modell verlangt, und gibt die Antwort
zurück. Es enthält keine Kette. Wenn das Modell das Brett nie anspricht oder in der falschen
Reihenfolge arbeitet, kommt genau das heraus — und ist damit gemessen.

Das Modell läuft auf dem Arbeitsplatzrechner (llama-server aus dem Kurspaket, 127.0.0.1:8099)
und wird über die Brücke beauftragt. Es ist damit von diesem Programm unabhängig: Niemand hier
schreibt die Programme, die auf dem Brett landen.

Die Werkzeuge kommen aus dem Bausatz (``Bruecke/bausatz/werkzeuge``) — dieselben, die
``agent.py --probe`` einzeln prüft. Sie werden nicht hier beschrieben, sondern dort gefunden.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys
import time

HIER = pathlib.Path(__file__).resolve().parent
BAUSATZ = HIER.parent / "bausatz"
BEFEHL = HIER.parent / "befehl.py"
AUFTRAEGE = HIER / "auftraege.json"
ABLAGE = pathlib.Path("/workspace/Kurs_Agent/Arbeitsstand/Laptop")
PROJEKT = "Kurs_Agent"


def bausatz_agent():
    """Den Bausatz-Agenten laden, um seine Werkzeugsammlung zu benutzen — nicht abzuschreiben."""
    spec = importlib.util.spec_from_file_location("bausatz_agent", BAUSATZ / "agent.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bruecke(typ: str, arg: str, zeit: int = 960) -> str:
    r = subprocess.run([sys.executable, str(BEFEHL), "-p", PROJEKT, typ, arg],
                       capture_output=True, text=True, timeout=zeit)
    return (r.stdout or "") + (r.stderr or "")


def modell_fragen(verlauf: list, werkzeuge: list[dict]) -> dict:
    """Eine Runde beim Modell auf dem Arbeitsplatzrechner. Gibt die Nachricht des Modells zurück."""
    anfrage = {
        "messages": verlauf,
        # Ein Programmtext in einem Werkzeugaufruf braucht Platz. Mit 1200 brach die Antwort
        # mitten im JSON ab, und ein abgeschnittener Aufruf sieht aus wie gar keiner.
        "max_tokens": 3000,
        "temperature": 0.2,
        "tools": [{"type": "function",
                   "function": {"name": w["name"], "description": w["zweck"],
                                "parameters": w["eingabe"]}} for w in werkzeuge],
    }
    # Über eine Datei, nicht über die Befehlszeile: Ein Gespräch mit Werkzeugliste und
    # Zwischenergebnissen wird schnell länger, als eine Befehlszeile trägt — der erste Versuch
    # brach genau daran in Runde 5 ab.
    ABLAGE.mkdir(parents=True, exist_ok=True)
    (ABLAGE / "anfrage.json").write_text(json.dumps(anfrage, ensure_ascii=False), encoding="utf-8")
    hin = bruecke("update", "anfrage.json")
    if "übernommen" not in hin:
        raise RuntimeError("Die Anfrage kam nicht auf dem Rechner an: " + hin.strip()[:200])
    roh = bruecke("modell", "frage_datei anfrage.json")
    if "{" not in roh:
        raise RuntimeError("Das Modell hat nicht geantwortet: " + roh.strip()[:300])
    antwort = json.loads(roh[roh.index("{"):])
    if "choices" not in antwort:
        raise RuntimeError("Unerwartete Antwort des Modells: " + roh[:300])
    wahl = antwort["choices"][0]
    nachricht = wahl["message"]
    nachricht["_ende"] = wahl.get("finish_reason", "")
    return nachricht


def aus_text(inhalt: str, werkzeuge: list[dict]) -> list[dict]:
    """Werkzeugaufrufe erkennen, die das Modell als Text schreibt statt über die Schnittstelle.

    Kleine Modelle beherrschen das vorgesehene Feld ``tool_calls`` oft nicht und geben statt
    dessen JSON im Fließtext aus, meist in einem Codeblock. Das hier anzunehmen ist Nachsicht im
    **Format**, nicht in der Sache: Was das Werkzeug dann tut und was dabei herauskommt, wird
    genauso gemessen. Erkannt wird nur, was einen bekannten Werkzeugnamen trägt.
    """
    namen = {w["name"] for w in werkzeuge}
    gefunden = []
    for stueck in inhalt.replace("```json", "```").split("```"):
        s = stueck.strip()
        if not s.startswith("{"):
            continue
        try:
            d = json.loads(s)
        except ValueError:
            continue
        name = d.get("name") or d.get("werkzeug") or d.get("tool")
        if name not in namen:
            continue
        arg = d.get("arguments", d.get("parameters", d.get("eingabe", {})))
        if isinstance(arg, str):
            try:
                arg = json.loads(arg)
            except ValueError:
                arg = {}
        gefunden.append({"id": name, "function": {"name": name,
                                                  "arguments": json.dumps(arg, ensure_ascii=False)}})
    return gefunden


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("auftragstext", nargs="?", help="der Auftrag in Worten")
    p.add_argument("--auftrag", help="statt dessen eine Kennung aus auftraege.json")
    p.add_argument("--modell", default="coder", choices=["coder", "3b", "7b"])
    p.add_argument("--runden", type=int, default=12)
    a = p.parse_args()

    if a.auftrag:
        auftraege = {x["kennung"]: x for x in json.loads(AUFTRAEGE.read_text(encoding="utf-8"))}
        if a.auftrag not in auftraege:
            print(f"FEHLER: {a.auftrag} steht nicht in auftraege.json")
            return 2
        text = auftraege[a.auftrag]["text"]
    elif a.auftragstext:
        text = a.auftragstext
    else:
        print("FEHLER: entweder einen Auftragstext oder --auftrag angeben")
        return 2

    print("Modell auf dem Arbeitsplatzrechner starten …")
    print("  " + bruecke("modell", f"start {a.modell}").strip()[:140])

    m = bausatz_agent()
    werkzeuge = m.sammlung()
    print(f"  {len(werkzeuge)} Werkzeuge: " + ", ".join(w["name"] for w in werkzeuge))
    print(f"\nAuftrag an das Modell:\n  {text[:300]}{'…' if len(text) > 300 else ''}\n")

    verlauf = [{"role": "system",
                "content": ("Du bedienst einen Arbeitsplatz über Werkzeuge. Rufe Werkzeuge auf, "
                            "um den Auftrag wirklich auszuführen; behaupte nichts, was du nicht "
                            "mit einem Werkzeug geprüft hast. Antworte erst dann in Worten, wenn "
                            "der Auftrag erledigt ist.")},
               {"role": "user", "content": text}]

    t0 = time.time()
    letzte: list[str] = []
    for runde in range(1, a.runden + 1):
        try:
            nachricht = modell_fragen(verlauf, werkzeuge)
        except Exception as e:
            print(f"ABBRUCH in Runde {runde}: {e}")
            return 1
        inhalt = nachricht.get("content") or ""
        rufe = nachricht.get("tool_calls") or aus_text(inhalt, werkzeuge)
        if inhalt:
            print(f"  Modell: {inhalt.strip()[:400]}")
        verlauf.append({k: v for k, v in nachricht.items() if k in ("role", "content", "tool_calls")})

        # Eine abgeschnittene Antwort ist kein erledigter Auftrag. Das wird dem Modell gesagt,
        # statt es als Erfolg zu verbuchen -- der erste Lauf endete genau so fälschlich mit
        # „erledigt", obwohl das Programm mitten im Satz abbrach.
        if not rufe and nachricht.get("_ende") == "length":
            print("    (Antwort war abgeschnitten — das Modell wird darauf hingewiesen)")
            verlauf.append({"role": "user",
                            "content": "Deine Antwort war abgeschnitten. Fasse dich kürzer und rufe "
                                       "genau ein Werkzeug auf."})
            continue
        if not rufe and '"name"' in inhalt and "{" in inhalt:
            print("    (sah nach einem Werkzeugaufruf aus, war aber nicht lesbar — Hinweis an das Modell)")
            verlauf.append({"role": "user",
                            "content": "Dein Werkzeugaufruf war nicht lesbar. Gib genau ein JSON-Objekt "
                                       "der Form {\"name\": …, \"arguments\": {…}} aus, sonst nichts."})
            continue

        if not rufe:
            print(f"\nDas Modell hält den Auftrag für erledigt (Runde {runde}, "
                  f"{time.time()-t0:.0f} s).")
            return 0

        # Im Kreis laufen ist kein Fortschritt: Wiederholt das Modell denselben Aufruf, wird es
        # darauf hingewiesen statt immer weiter bedient. Gemessen am 07.10.2026: Das 3B-Modell
        # rief elfmal hintereinander „mitlesen", weil sein Programm nichts ausgab.
        marke = json.dumps([r["function"] for r in rufe], ensure_ascii=False)
        if letzte.count(marke) >= 2:
            print("    (dritter gleicher Aufruf — Hinweis an das Modell)")
            verlauf.append({"role": "user",
                            "content": "Du rufst dasselbe Werkzeug mit denselben Werten immer wieder auf "
                                       "und bekommst dasselbe Ergebnis. Ändere etwas: Prüfe, ob dein "
                                       "Programm überhaupt etwas mit print ausgibt."})
            letzte.clear()
            continue
        letzte.append(marke)

        for ruf in rufe:
            name = ruf["function"]["name"]
            try:
                eingabe = json.loads(ruf["function"]["arguments"] or "{}")
            except ValueError:
                eingabe = {}
            kurz = json.dumps(eingabe, ensure_ascii=False)
            print(f"  → {name} {kurz[:160]}{'…' if len(kurz) > 160 else ''}")
            ergebnis = m.ausfuehren(name, eingabe, werkzeuge)
            print(f"    {ergebnis.strip()[:300]}")
            verlauf.append({"role": "tool", "tool_call_id": ruf.get("id", name), "content": ergebnis[:4000]})

    print(f"\nNach {a.runden} Runden nicht fertig geworden ({time.time()-t0:.0f} s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
