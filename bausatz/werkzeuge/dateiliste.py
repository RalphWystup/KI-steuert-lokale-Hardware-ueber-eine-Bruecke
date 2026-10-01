#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: die Dateien eines Verzeichnisses nennen."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug

GRENZE = 200          # mehr als das liest kein Modell sinnvoll


def tun(e):
    o = pathlib.Path(e.get("ordner", "."))
    if not o.is_dir():
        return f"FEHLER: kein Verzeichnis: {o}"
    d = sorted(p for p in o.iterdir() if not p.name.startswith("."))
    z = [f"  {'<DIR> ' if p.is_dir() else f'{p.stat().st_size:6d}'}  {p.name}" for p in d[:GRENZE]]
    mehr = f"\n  … und {len(d) - GRENZE} weitere" if len(d) > GRENZE else ""
    return f"{o} ({len(d)} Einträge):\n" + "\n".join(z) + mehr


sys.exit(werkzeug(
    "dateiliste", "Nennt die Dateien und Unterverzeichnisse eines Verzeichnisses.",
    {"ordner": {"type": "string", "description": "Pfad, Vorgabe: aktuelles Verzeichnis"}},
    [], {"ordner": "."}, tun))
