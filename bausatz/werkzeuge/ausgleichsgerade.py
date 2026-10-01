#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: Ausgleichsgerade nach der Methode der kleinsten Quadrate.

Zeigt, wofür Werkzeuge eigentlich da sind. Ein Sprachmodell kann eine Regression nicht
rechnen — es kann sie beschreiben. Die Zahl muss aus einem Programm kommen, sonst ist sie
geraten.

Die Rechnung ist mit Papier nachvollziehbar, Formel für Formel:

    m = (n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)          Steigung
    b = (Σy − m·Σx) / n                             Achsenabschnitt
    R² = 1 − Σ(y − ŷ)² / Σ(y − ȳ)²                  Bestimmtheitsmaß
    s  = sqrt( Σ(y − ŷ)² / (n − 2) )                Reststreuung

Kein eingebauter Löser, keine Bibliothek: Wer das Ergebnis anzweifelt, kann es nachrechnen.
"""
import json, math, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug


def zahl(t):
    """Deutsche und englische Schreibweise annehmen — Messdaten kommen in beiden."""
    return float(str(t).strip().replace(",", "."))


def tun(e):
    x = [zahl(v) for v in e["x"]]
    y = [zahl(v) for v in e["y"]]
    if len(x) != len(y):
        return f"FEHLER: {len(x)} x-Werte, aber {len(y)} y-Werte"
    n = len(x)
    if n < 3:
        return f"FEHLER: mindestens drei Wertepaare nötig, {n} gegeben"

    sx, sy = sum(x), sum(y)
    sxy = sum(a * b for a, b in zip(x, y))
    sxx = sum(a * a for a in x)
    nenner = n * sxx - sx * sx
    if abs(nenner) < 1e-15:
        return "FEHLER: alle x-Werte gleich — keine Gerade bestimmbar"

    m = (n * sxy - sx * sy) / nenner
    b = (sy - m * sx) / n

    ymittel = sy / n
    rest = sum((yi - (m * xi + b)) ** 2 for xi, yi in zip(x, y))
    streu = sum((yi - ymittel) ** 2 for yi in y)
    r2 = 1 - rest / streu if streu > 0 else float("nan")
    s = math.sqrt(rest / (n - 2))

    groesste = max(range(n), key=lambda i: abs(y[i] - (m * x[i] + b)))
    abw = y[groesste] - (m * x[groesste] + b)

    name_m = e.get("name_steigung", "Steigung")
    einheit = e.get("einheit", "")
    return (f"Ausgleichsgerade aus {n} Wertepaaren\n"
            f"  {name_m:22s} m  = {m:.6g} {einheit}\n"
            f"  Achsenabschnitt        b  = {b:.6g}\n"
            f"  Bestimmtheitsmaß       R² = {r2:.6f}\n"
            f"  Reststreuung           s  = {s:.4g}\n"
            f"  größte Abweichung         = {abw:+.4g} beim {groesste + 1}. Punkt\n"
            f"  Gleichung:  y = {m:.6g}·x {'+' if b >= 0 else '−'} {abs(b):.4g}")


sys.exit(werkzeug(
    "ausgleichsgerade",
    "Legt eine Ausgleichsgerade nach kleinsten Quadraten durch Wertepaare und gibt Steigung, "
    "Achsenabschnitt, Bestimmtheitsmaß, Reststreuung und die größte Einzelabweichung zurück. "
    "Nimmt Komma oder Punkt als Dezimalzeichen.",
    {"x": {"type": "array", "items": {"type": "string"}, "description": "x-Werte"},
     "y": {"type": "array", "items": {"type": "string"}, "description": "y-Werte"},
     "name_steigung": {"type": "string", "description": "wie die Steigung heißt, z. B. 'Widerstand'"},
     "einheit": {"type": "string", "description": "Einheit der Steigung"}},
    ["x", "y"],
    {"x": ["0", "1", "2", "3"], "y": ["0", "2,01", "3,98", "6,02"],
     "name_steigung": "Steigung", "einheit": ""},
    tun))
