#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: ein Ergebnis am Bildschirm des entfernten Arbeitsplatzes anzeigen.

Das ist der Durchstich durch alle drei Ebenen: Das Modell entscheidet, was angezeigt werden
soll; dieses Programm baut daraus eine Seite; die Brücke bringt sie auf den anderen Rechner
und öffnet sie dort.

Bemerkenswert daran: Es braucht **keinen neuen Brückenbefehl**. Die Brücke kann Dateien
übertragen und Dateien mit ihrem Standardprogramm öffnen — mehr ist nicht nötig. Wer eine
Anzeige will, schreibt sie als Datei.

Ablauf:
  1. Seite bauen und in <Projekt>/Arbeitsstand/Laptop legen
  2. 'update' — die Brücke holt sie auf den Arbeitsplatz
  3. 'oeffnen' — der Standardbrowser dort zeigt sie an
"""
import datetime, json, pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug

HIER = pathlib.Path(__file__).resolve().parent
ZIEL_PC = r"C:\Bruecke"


def seite(titel: str, zeilen: list, fussnote: str) -> str:
    z = "\n".join(
        f'<tr><td>{p.get("was","")}</td><td class="z">{p.get("wert","")}</td>'
        f'<td>{p.get("einheit","")}</td></tr>' for p in zeilen)
    return f"""<!doctype html><html lang="de"><meta charset="utf-8">
<title>{titel}</title>
<style>
 body{{font:17px/1.6 Georgia,serif;margin:0;background:#f5f6f8;color:#1a1d23}}
 .k{{max-width:640px;margin:40px auto;background:#fff;border:1px solid #d9dde4;
     border-radius:10px;padding:26px 30px;box-shadow:0 2px 10px #0001}}
 h1{{margin:0 0 4px;font-size:23px;font-weight:normal}}
 .zeit{{color:#5b626e;font-size:13px;margin-bottom:18px}}
 table{{border-collapse:collapse;width:100%}}
 td{{border-bottom:1px solid #eceff3;padding:9px 6px}}
 td.z{{text-align:right;font-variant-numeric:tabular-nums;font-weight:bold;font-size:19px}}
 .f{{margin-top:18px;padding-top:12px;border-top:1px solid #d9dde4;
     font-size:13.5px;color:#5b626e}}
 .weg{{margin-top:14px;font-size:12.5px;color:#8a919c}}
</style>
<div class="k">
 <h1>{titel}</h1>
 <div class="zeit">erzeugt {datetime.datetime.now():%d.%m.%Y %H:%M:%S} — vom Agenten auf dem Server</div>
 <table>{z}</table>
 <div class="f">{fussnote}</div>
 <div class="weg">Modell entscheidet → Werkzeug rechnet → Brücke zeigt an.
 Diese Seite ist über die Brücke auf diesen Rechner gekommen.</div>
</div>
</html>"""


def bruecke(typ: str, argument: str, projekt: str) -> str:
    e = subprocess.run([sys.executable, str(HIER / "am_arbeitsplatz.py"),
                        json.dumps({"typ": typ, "argument": argument, "projekt": projekt})],
                       capture_output=True, text=True, timeout=150)
    return (e.stdout or e.stderr).strip()


def tun(e):
    projekt = e.get("projekt", "Layout")
    name = "anzeige.html"
    uebergabe = pathlib.Path("/workspace") / projekt / "Arbeitsstand" / "Laptop"
    if not uebergabe.is_dir():
        return f"FEHLER: Übergabeordner fehlt: {uebergabe}"

    (uebergabe / name).write_text(
        seite(e.get("titel", "Ergebnis"), e.get("zeilen", []), e.get("fussnote", "")),
        encoding="utf-8")

    a = bruecke("update", f"{name} -> {ZIEL_PC}", projekt)
    if a.startswith("FEHLER") or "übernommen" not in a:
        return f"FEHLER beim Übertragen: {a}"
    b = bruecke("oeffnen", f"{ZIEL_PC}\\{name}", projekt)
    if b.startswith("FEHLER"):
        return f"übertragen, aber nicht geöffnet: {b}"
    return f"angezeigt am Arbeitsplatz: {e.get('titel','Ergebnis')} mit {len(e.get('zeilen',[]))} Zeile(n)\n  {a}\n  {b}"


sys.exit(werkzeug(
    "zeige_an",
    "Zeigt ein Ergebnis auf dem Bildschirm des entfernten Arbeitsplatzes an. "
    "zeilen ist eine Liste aus {was, wert, einheit}.",
    {"titel":    {"type": "string"},
     "zeilen":   {"type": "array", "items": {"type": "object"}},
     "fussnote": {"type": "string"},
     "projekt":  {"type": "string", "description": "Projektkanal, Vorgabe: Layout"}},
    ["titel", "zeilen"],
    {"titel": "Probe", "zeilen": [{"was": "Werkzeugprobe", "wert": "läuft", "einheit": ""}],
     "fussnote": "Selbstprobe des Werkzeugs."},
    tun))
