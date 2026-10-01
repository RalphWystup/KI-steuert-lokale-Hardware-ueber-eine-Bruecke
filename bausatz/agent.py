#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ein Agent in siebzig Zeilen — mit Werkzeugen als fertige Programme.

Der Unterschied zu einem Agenten, der beliebigen Code ausführen darf: Hier gibt es eine
**Sammlung fertiger Programme** im Ordner ``werkzeuge``. Mehr kann der Agent nicht. Jedes
Programm beschreibt sich selbst; der Agent liest die Beschreibungen und gibt sie dem Modell
als Werkzeugliste.

Was das bringt:

* Was der Agent tun kann, steht im Ordner — nachlesbar, prüfbar, abzählbar.
* Ein neues Werkzeug ist eine neue Datei. Am Agenten ändert sich nichts.
* Jedes Werkzeug ist für sich prüfbar, ohne Modell und ohne Netz.
* Was nicht im Ordner liegt, geschieht nicht. Auch nicht aus Versehen.

Aufruf:   python3 agent.py "Was steht in messung.csv?"
          python3 agent.py --werkzeuge          nur die Sammlung zeigen
          python3 agent.py --probe              jedes Werkzeug einmal aufrufen, ohne Modell

Der Schlüssel für das Modell steht in der Umgebungsvariablen ANTHROPIC_API_KEY.

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)
"""
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys

MODELL = "claude-sonnet-5"
H = pathlib.Path(__file__).resolve().parent
ORDNER = H / "werkzeuge"
ZEITGRENZE = 120          # Sekunden je Werkzeug — eines darf die Schleife nicht aufhalten


# --------------------------------------------------------------------- Die Sammlung lesen
def sammlung() -> list[dict]:
    """Jedes Programm im Ordner beschreibt sich selbst über ``--beschreibung``.

    Der Agent kennt die Werkzeuge nicht; er findet sie. Damit ist die Liste, die das Modell
    sieht, immer dieselbe wie die Liste der Dateien — sie kann nicht auseinanderlaufen.
    """
    aus = []
    for d in sorted(ORDNER.glob("*.py")):
        if d.name.startswith("_"):
            continue
        e = subprocess.run([sys.executable, str(d), "--beschreibung"],
                           capture_output=True, text=True, timeout=20)
        if e.returncode:
            print(f"  übergangen: {d.name} beschreibt sich nicht ({e.stderr.strip()[:60]})")
            continue
        b = json.loads(e.stdout)
        b["datei"] = d.name
        aus.append(b)
    return aus


def ausfuehren(name: str, eingabe: dict, werkzeuge: list[dict]) -> str:
    """Ein Werkzeug aufrufen. Alles, was schiefgeht, wird Text — nie eine Ausnahme."""
    pass_ = next((w for w in werkzeuge if w["name"] == name), None)
    if not pass_:
        return f"FEHLER: Werkzeug {name} gibt es nicht. Vorhanden: " + \
               ", ".join(w["name"] for w in werkzeuge)
    try:
        e = subprocess.run([sys.executable, str(ORDNER / pass_["datei"]), json.dumps(eingabe)],
                           capture_output=True, text=True, timeout=ZEITGRENZE)
    except subprocess.TimeoutExpired:
        return f"FEHLER: {name} hat {ZEITGRENZE} s überschritten"
    return (e.stdout or e.stderr or "(keine Ausgabe)").strip()


# --------------------------------------------------------------------- Die Schleife
def schleife(auftrag: str, werkzeuge: list[dict], laut: bool = True) -> str:
    import anthropic
    client = anthropic.Anthropic()
    fuer_modell = [{"name": w["name"], "description": w["zweck"],
                    "input_schema": w["eingabe"]} for w in werkzeuge]
    verlauf = [{"role": "user", "content": auftrag}]

    for runde in range(1, 26):                      # Obergrenze: kein endloses Hin und Her
        antwort = client.messages.create(model=MODELL, max_tokens=4000,
                                         messages=verlauf, tools=fuer_modell)
        verlauf.append({"role": "assistant", "content": antwort.content})
        aufrufe = [b for b in antwort.content if b.type == "tool_use"]

        if not aufrufe:
            return "".join(b.text for b in antwort.content if b.type == "text")

        ergebnisse = []
        for a in aufrufe:                           # zu JEDEM Aufruf ein Ergebnis
            if laut:
                print(f"  [{runde}] {a.name} {json.dumps(a.input, ensure_ascii=False)}")
            text = ausfuehren(a.name, a.input, werkzeuge)
            if laut:
                print(f"       -> {text[:100]}")
            ergebnisse.append({"type": "tool_result", "tool_use_id": a.id, "content": text})
        verlauf.append({"role": "user", "content": ergebnisse})

    return "Abbruch: 25 Runden ohne Ergebnis."


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("auftrag", nargs="?", help="was der Agent tun soll")
    p.add_argument("--werkzeuge", action="store_true", help="nur die Sammlung zeigen")
    p.add_argument("--probe", action="store_true", help="jedes Werkzeug einmal aufrufen")
    a = p.parse_args()

    w = sammlung()
    if a.werkzeuge or not a.auftrag and not a.probe:
        print(f"{len(w)} Werkzeuge in {ORDNER}\n")
        for x in w:
            felder = ", ".join(x["eingabe"].get("properties", {}))
            print(f"  {x['name']:18s} {x['zweck']}")
            print(f"  {'':18s} Eingabe: {felder or '—'}   [{x['datei']}]")
        return 0

    if a.probe:
        print(f"Probe ohne Modell — jedes Werkzeug einmal:\n")
        fehler = 0
        for x in w:
            text = ausfuehren(x["name"], x.get("probe", {}), w)
            gut = not text.startswith("FEHLER")
            fehler += 0 if gut else 1
            print(f"  {x['name']:18s} {'ok  ' if gut else 'FEHLER'} {text[:70]}")
        print(f"\n{len(w) - fehler} von {len(w)} in Ordnung")
        return 1 if fehler else 0

    print(f"{len(w)} Werkzeuge · Modell {MODELL}\n")
    print(schleife(a.auftrag, w))
    return 0


if __name__ == "__main__":
    sys.exit(main())
