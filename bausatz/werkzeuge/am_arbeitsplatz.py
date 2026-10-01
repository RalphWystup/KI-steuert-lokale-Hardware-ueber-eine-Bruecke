#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: einen Befehl am entfernten Arbeitsplatz ausführen — über die Brücke.

Das ist das einzige Werkzeug, das aus dem Behälter hinausreicht. Für das Modell sieht es
aus wie jedes andere: Name, Zweck, Eingaben, Textantwort. Dass die Arbeit auf einem anderen
Rechner geschieht, merkt es nur daran, dass die Antwort ein paar Sekunden braucht.

Der Weg: Auftrag in die Warteschlange des Empfängers legen, dann warten, bis die Brücke
geantwortet hat. Die Brücke holt den Auftrag von sich aus ab — niemand verbindet sich zu ihr.

Zugang steht in ``agent_zugang.json`` neben dem Agenten, nicht hier im Programm.
"""
import json, pathlib, sys, time, urllib.parse, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug

ZUGANG = pathlib.Path(__file__).resolve().parent.parent / "agent_zugang.json"
WARTEN = 110          # Sekunden, bis aufgegeben wird


def zugang():
    if not ZUGANG.is_file():
        raise RuntimeError(
            f"Zugangsdatei fehlt: {ZUGANG}\n"
            '  { "empfaenger": "http://127.0.0.1:8085", "token": "<Token>" }')
    j = json.loads(ZUGANG.read_text(encoding="utf-8"))
    for k in ("empfaenger", "token"):
        if not j.get(k):
            raise RuntimeError(f"In {ZUGANG} fehlt: {k}")
    return j["empfaenger"].rstrip("/"), j["token"]


def tun(e):
    basis, token = zugang()
    f = {"token": token, "projekt": e.get("projekt", "Standard"),
         "typ": e["typ"], "url": e.get("argument", "")}
    nr = urllib.request.urlopen(urllib.request.Request(
        basis + "/befehl?" + urllib.parse.urlencode(f), data=b"", method="POST"),
        timeout=20).read().decode()

    ende = time.time() + WARTEN
    while time.time() < ende:
        a = urllib.request.urlopen(
            f"{basis}/antwort_lesen?id={nr}", timeout=15).read().decode()
        if a:
            return a
        time.sleep(1)
    return (f"FEHLER: keine Antwort innerhalb {WARTEN} s. "
            f"Läuft die Brücke am Arbeitsplatz? Der Auftrag {nr} wartet weiter.")


sys.exit(werkzeug(
    "am_arbeitsplatz",
    "Führt einen Befehl am entfernten Arbeitsplatz aus, über die Brücke. "
    "typ: dateiliste | hochladen | update | oeffnen | bildschirm | info. "
    "Die Brücke weist zurück, was nicht erlaubt ist.",
    {"typ":      {"type": "string", "description": "Art des Befehls"},
     "argument": {"type": "string", "description": "Pfad oder Dateiname, je nach Typ"},
     "projekt":  {"type": "string", "description": "Projektkanal, Vorgabe: Standard"}},
    ["typ"], {"typ": "info"}, tun))
