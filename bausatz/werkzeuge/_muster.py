#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gemeinsames Gerüst aller Werkzeuge — Beginn mit _ , also kein eigenes Werkzeug.

Jedes Werkzeug ist ein eigenständiges Programm mit genau zwei Betriebsarten:

    python3 <werkzeug>.py --beschreibung    gibt JSON aus: name, zweck, eingabe, probe
    python3 <werkzeug>.py '<json>'          führt aus, gibt Text auf die Ausgabe

Mehr nicht. Daraus folgt, was dieses Vorgehen so brauchbar macht:

* Ein Werkzeug lässt sich **ohne Modell und ohne Netz** prüfen — einfach aufrufen.
* Ein Fehler wird **Text**, keine Ausnahme. Das Modell kann auf Text reagieren.
* Die Werkzeugliste des Modells **ist** die Dateiliste des Ordners; sie können nicht
  auseinanderlaufen.
"""
from __future__ import annotations
import json, sys


def werkzeug(name: str, zweck: str, felder: dict, pflicht: list, probe: dict, tun):
    """Die zwei Betriebsarten abwickeln. ``tun(eingabe) -> str`` ist die eigentliche Arbeit."""
    if len(sys.argv) > 1 and sys.argv[1] == "--beschreibung":
        print(json.dumps({"name": name, "zweck": zweck,
                          "eingabe": {"type": "object", "properties": felder,
                                      "required": pflicht},
                          "probe": probe}, ensure_ascii=False))
        return 0
    try:
        eingabe = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except Exception as e:
        print(f"FEHLER: Eingabe ist kein JSON: {e}")
        return 0
    fehlt = [k for k in pflicht if k not in eingabe]
    if fehlt:
        print(f"FEHLER: es fehlt: {', '.join(fehlt)}")
        return 0
    try:
        print(tun(eingabe))
    except Exception as e:                      # nie abstürzen — das Modell braucht eine Antwort
        print(f"FEHLER: {type(e).__name__}: {e}")
    return 0
