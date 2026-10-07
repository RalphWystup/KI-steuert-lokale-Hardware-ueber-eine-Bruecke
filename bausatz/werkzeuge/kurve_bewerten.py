#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Werkzeug: aus gemessenen Werten bestimmen, welche Kurvenform vorliegt.

Ein Sprachmodell soll nicht aus einer Zahlenreihe „sieht sinusförmig aus" ableiten — das wäre
geraten. Dieses Werkzeug rechnet: Es legt Sinus, Dreieck, Parabel und Rechteck nach kleinsten
Quadraten an die Werte und gibt die Restabweichung je Form an. Die kleinste gewinnt.

Zwei Dinge, die hier bedacht sind und ohne die das Ergebnis falsch wird:

* **Die Phasenlage ist frei.** Geprüft wird die Form, nicht wo die Periode anfängt. Das ist
  nötig, weil ein aus der PWM-Einheit zurückgelesener Tastgrad um eine Trägerperiode nachhinkt.
* **Mehrere Perioden werden gefaltet**, wenn die Werte über mehrere Perioden laufen. Sonst
  verdirbt eine schwankende Periodendauer die Anpassung.

Eingabe entweder ``werte`` (eine Periode, der Reihe nach) oder ``zeilen`` (die Ausgabe des
Brettes; Zeilen der Form ``P t=… dt=… D=1,2,3,…`` werden daraus gelesen).
"""
from __future__ import annotations
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _muster import werkzeug                                              # noqa: E402

MODELLE = {
    "Sinus": lambda q: (1 - math.cos(2 * math.pi * q)) / 2,
    "Dreieck": lambda q: 2 * q if q < 0.5 else 2 - 2 * q,
    "Parabel": lambda q: 4 * q * (1 - q),
    "Rechteck": lambda q: 1.0 if 0.25 < q < 0.75 else 0.0,
    "Saegezahn": lambda q: q,
}


def anpassen(kurve: list[float]) -> dict:
    """Restabweichung je Form, in Prozent des Hubs. Phasenlage frei."""
    n = len(kurve)
    h = max(kurve) - min(kurve)
    phase = [i / n for i in range(n)]
    erg = {}
    for name, f in MODELLE.items():
        beste = 1e9
        for k in range(n):
            v = [f((q + k / n) % 1.0) for q in phase]
            sv, sy = sum(v), sum(kurve)
            svv = sum(a * a for a in v)
            svy = sum(a * b for a, b in zip(v, kurve))
            nen = n * svv - sv * sv
            if abs(nen) < 1e-12:
                continue
            c1 = (n * svy - sv * sy) / nen
            c0 = (sy - c1 * sv) / n
            beste = min(beste, math.sqrt(sum((y - (c0 + c1 * w)) ** 2
                                             for y, w in zip(kurve, v)) / n) / h * 100)
        erg[name] = beste
    return erg


def tun(e: dict) -> str:
    perioden = []
    if e.get("zeilen"):
        for z in str(e["zeilen"]).splitlines():
            if z.startswith("P ") and "D=" in z:
                w = [float(x) for x in z.split("D=")[1].strip().split(",") if x.strip().lstrip("-").isdigit()]
                if len(w) > 8:
                    perioden.append(w)
    if e.get("werte"):
        perioden.append([float(x) for x in e["werte"]])
    if not perioden:
        return ("FEHLER: keine auswertbaren Werte. Entweder werte=[…] angeben oder zeilen= mit "
                "Zeilen der Form 'P t=… dt=… D=1,2,3,…' (so, wie das Brett sie ausgibt).")

    laenge = max(len(w) for w in perioden)
    voll = [w for w in perioden if len(w) == laenge]
    kurve = [sum(w[i] for w in voll) / len(voll) for i in range(laenge)]
    if max(kurve) - min(kurve) < 1e-9:
        return "FEHLER: die Werte ändern sich nicht — da ist keine Kurve."

    erg = anpassen(kurve)
    sortiert = sorted(erg.items(), key=lambda x: x[1])
    beste, rest = sortiert[0]
    zweite, rest2 = sortiert[1]
    klar = rest2 > rest * 1.5
    zeilen = [f"{len(voll)} Periode(n) à {laenge} Werte, Hub {max(kurve)-min(kurve):.0f}",
              "Restabweichung je Form, in Prozent des Hubs (kleiner ist besser):"]
    zeilen += [f"   {k:<10} {v:6.2f} %" for k, v in sortiert]
    zeilen.append(f"Ergebnis: {beste}" + (f", eindeutig — die nächste Form ({zweite}) liegt "
                                          f"{rest2/max(rest,1e-9):.1f}-mal daneben." if klar else
                                          f", aber NICHT eindeutig: {zweite} liegt mit {rest2:.2f} % fast gleichauf. "
                                          f"Mehr Perioden messen oder feiner abtasten."))
    return "\n".join(zeilen)


if __name__ == "__main__":
    sys.exit(werkzeug(
        name="kurve_bewerten",
        zweck=("Bestimmt rechnerisch, welche Kurvenform eine Messreihe hat (Sinus, Dreieck, "
               "Parabel, Rechteck, Sägezahn), mit Restabweichung je Form. Nimmt die Zeilen, die "
               "ein Brett ausgibt, oder eine Werteliste."),
        felder={
            "zeilen": {"type": "string", "description": "die Ausgabe des Brettes; Zeilen 'P t=… dt=… D=…' werden gelesen"},
            "werte": {"type": "array", "items": {"type": "number"},
                      "description": "oder unmittelbar die Werte einer Periode, der Reihe nach"},
        },
        pflicht=[],
        probe={"werte": [round(511.5 * (1 - math.cos(2 * math.pi * i / 24)), 1) for i in range(24)]},
        tun=tun))
