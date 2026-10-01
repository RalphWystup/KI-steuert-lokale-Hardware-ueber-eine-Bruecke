#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: eine Textdatei lesen."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug

GRENZE = 60000        # Zeichen — darüber wird abgeschnitten, nicht verweigert


def tun(e):
    d = pathlib.Path(e["pfad"])
    if not d.is_file():
        return f"FEHLER: Datei fehlt: {d}"
    t = d.read_text(encoding="utf-8", errors="replace")
    if len(t) > GRENZE:
        return t[:GRENZE] + f"\n… abgeschnitten, {len(t) - GRENZE} Zeichen folgen noch"
    return t


sys.exit(werkzeug(
    "lies_datei", "Liest eine Textdatei und gibt ihren Inhalt zurück.",
    {"pfad": {"type": "string", "description": "Pfad zur Datei"}},
    ["pfad"], {"pfad": "LIESMICH.md"}, tun))
