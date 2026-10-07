#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prüfmittel der Kette: ein Programm bis auf das Brett und wieder zurück — alles gemessen.

    python3 pruefe_kette.py <auftragskennung> [--programm datei.py] [--port COM3]

Was hier geprüft wird, steht in ``Bruecke/PRUEFPLAN.md`` als Gruppe E. Dieses Programm nimmt
keinen Schritt auf Zusage an:

  Glied 3  die Datei und ihre Prüfsumme hier
  Glied 4  Prüfung ohne Gerät: Syntax, verlangte Bauteile, Lebenszeile im Text
  Glied 5  Übertragung; die Prüfsumme kommt VOM BRETT zurück, nicht vom Sender (E3)
  Glied 6  Neustart, dann die Lebenszeile des Programms über die serielle Leitung (E4)
  Glied 7  Messung am Gerät: Takt aus den Gerätezeitstempeln, und bei PWM-Aufträgen die
           Kurvenform aus dem PWM-Register des Gerätes (E5)

Glied 2, der Modellaufruf, ist hier noch nicht drin: dafür fehlt der Zugang zum großen Modell.
Solange gibt man den Programmtext mit ``--programm`` vor und das Protokoll sagt ausdrücklich,
dass dieser Lauf das Modell nicht geprüft hat. Lieber eine Lücke benennen als sie zuschreiben.

Warum die Form über die Steigung geprüft wird
---------------------------------------------
Eine Anpassung an eine feste Periode scheitert, sobald die Periodendauer schwankt — und sie
schwankt, weil die Messung im selben Gerät läuft wie das Programm. Trägt man dagegen den Betrag
der Steigung über dem Tastgrad auf, fällt die Zeit heraus: Ein Sinus ergibt einen Halbkreis
(Steigung null an beiden Umkehrpunkten, größte Steigung in der Mitte), ein Dreieck eine
Waagerechte, ein Rechteck eine Spitze in der Mitte. Das ist von Hand nachrechenbar und
unabhängig davon, ob das Programm gleichmäßig läuft.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import time

HIER = pathlib.Path(__file__).resolve().parent
BEFEHL = HIER.parent / "befehl.py"
AUFTRAEGE = HIER / "auftraege.json"
ABLAGE = pathlib.Path("/workspace/Kurs_Agent/Arbeitsstand/Laptop")   # von hier holt die Brücke mit 'update'
PROJEKT = "Kurs_Agent"

fehler = 0
BEFUNDE: list[str] = []          # die Fehlertexte dieser Runde, wörtlich so, wie das Modell sie bekommt


def sage(gut: bool, text: str) -> None:
    global fehler
    if not gut:
        fehler += 1
        BEFUNDE.append(text)
    print(f"  {'ok  ' if gut else 'FEHLER'}  {text}")


MITSCHRIFT: list[str] = []
MODELL = "claude-sonnet-5"


# ----------------------------------------------------------------- Glied 2: das Modell fragen
def modell_fragen(auftrag: dict, vorher: str = "", befund: str = "") -> tuple[str, dict]:
    """Das Modell um ein Programm bitten — beim ersten Mal nach dem Auftrag, danach zur Berichtigung.

    Gibt (Programmtext, Nachweis) zurück. Der Nachweis trägt die Kennung der Antwort beim Anbieter,
    den Zeitstempel und die Tokenzahl; ohne diese drei ist nach Kriterium E1 nicht belegt, dass der
    Text aus diesem Lauf stammt und nicht aus einer Schublade.

    Ist kein Zugang eingerichtet, wird nichts erfunden: Die Bitte samt Befund landet als Datei
    daneben, und der Lauf sagt, dass das Modell nicht gefragt werden konnte.
    """
    if befund:
        bitte = (f"Dein Programm für den Auftrag „{auftrag['titel']}“ hat die Prüfung am Gerät nicht "
                 f"bestanden. Gemessen wurde:\n\n{befund}\n\nHier ist dein bisheriges Programm:\n\n"
                 f"{vorher}\n\nBerichtige es so, dass die Messung die Erwartung trifft. "
                 f"Gib nur den vollständigen Programmtext zurück, ohne Erklärung.")
    else:
        bitte = auftrag["text"]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        blatt = HIER / f"bitte_an_das_modell_{auftrag['kennung']}_{time.strftime('%H%M%S')}.txt"
        blatt.write_text(bitte, encoding="utf-8")
        return "", {"fehler": "kein Zugang zum Modell (ANTHROPIC_API_KEY fehlt)", "bitte": blatt.name}

    try:
        import anthropic
    except ImportError:
        return "", {"fehler": "die Bibliothek anthropic fehlt (pip install anthropic)"}

    t0 = time.time()
    antwort = anthropic.Anthropic().messages.create(
        model=MODELL, max_tokens=2000, messages=[{"role": "user", "content": bitte}])
    text = "".join(b.text for b in antwort.content if b.type == "text")
    # Der Programmtext steht oft in einem Codeblock; die Zäune gehören nicht in die Datei.
    if "```" in text:
        stuecke = text.split("```")
        text = max(stuecke[1::2], key=len)
        if text.startswith("python"):
            text = text[6:]
    return text.strip() + "\n", {"kennung": antwort.id, "modell": antwort.model,
                                 "zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
                                 "dauer_s": round(time.time() - t0, 1),
                                 "token_ein": antwort.usage.input_tokens,
                                 "token_aus": antwort.usage.output_tokens}


def bruecke(typ: str, arg: str, zeit: int = 300) -> str:
    """Einen Befehl über die Brücke absetzen und die Antwort zurückgeben.

    Jede Antwort wird mitgeschrieben. Schlägt ein Lauf fehl, liegt die Rohfassung daneben --
    ein sporadischer Fehlschlag ohne Rohdaten ist nicht aufzuklären, und genau an solchen
    Fehlschlägen ist der Kurs-Agent gescheitert.
    """
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, str(BEFEHL), "-p", PROJEKT, typ, arg],
                           capture_output=True, text=True, timeout=zeit)
        antwort = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        antwort = f"FEHLER: Zeitgrenze {zeit} s überschritten, die Brücke hat nicht geantwortet"
    MITSCHRIFT.append(f"--- {typ} {arg}  ({time.time()-t0:.0f} s)\n{antwort.rstrip()}")
    return antwort


# ----------------------------------------------------------------- Glied 4: ohne Gerät
def pruefe_text(quelle: bytes, auftrag: dict) -> None:
    text = quelle.decode("utf-8", "replace")
    import ast
    try:
        ast.parse(text)
        sage(True, "Glied 4: Syntax in Ordnung")
    except SyntaxError as e:
        sage(False, f"Glied 4: Syntaxfehler in Zeile {e.lineno}: {e.msg}")
        return
    erw = auftrag.get("erwartung", {})
    for pin in erw.get("pins", []):
        sage(f"Pin({pin}" in text, f"Glied 4: GPIO {pin} kommt im Programm vor")
    if erw.get("pwm"):
        sage("PWM(" in text, "Glied 4: PWM wird benutzt")
    if erw.get("form") == "sinus":
        sage("math.cos" in text or "math.sin" in text,
             "Glied 4: der Tastgrad folgt einer Winkelfunktion, nicht einer Rampe")
    if auftrag.get("lebenszeile"):
        sage(auftrag["lebenszeile"] in text,
             f"Glied 4: die vorgeschriebene Lebenszeile steht im Programm")


# ----------------------------------------------------------------- Glied 7: Takt messen
def takt_aus_zeilen(zeilen: list[str], kennung: str) -> tuple[float, int] | None:
    """Aus den Lebenszeilen 'n=.. t=..' die Periodendauer in ms und die Zahl der Perioden."""
    punkte = []
    for z in zeilen:
        if "n=" not in z or "t=" not in z:
            continue
        try:
            n = int(z.split("n=")[1].split()[0])
            t = int(z.split("t=")[1].split()[0])
        except (ValueError, IndexError):
            continue
        punkte.append((n, t))
    if len(punkte) < 3:
        return None
    (n0, t0), (n1, t1) = punkte[0], punkte[-1]
    if n1 == n0:
        return None
    return (t1 - t0) / (n1 - n0), n1 - n0


# ----------------------------------------------------------------- Formen anpassen
MODELLE = {"Sinus": lambda q: (1 - math.cos(2 * math.pi * q)) / 2,
           "Dreieck": lambda q: 2 * q if q < 0.5 else 2 - 2 * q,
           "Parabel": lambda q: 4 * q * (1 - q),
           "Rechteck": lambda q: 1.0 if 0.25 < q < 0.75 else 0.0}


def formen_anpassen(phase: list[float], kurve: list[float]) -> dict:
    """Kleinste Quadrate je Modell; Rückgabe: Restabweichung in Prozent des Hubs.

    Die Phasenlage ist frei: Geprüft wird die Form, nicht wo die Periode anfängt. Das ist nicht
    nur Bequemlichkeit, sondern notwendig. Beim Zurücklesen des Tastgrads aus der PWM-Einheit
    hinkt der Wert um eine Trägerperiode nach -- die Einheit übernimmt einen neuen Tastgrad erst
    beim nächsten Durchlauf ihres Zählers. Gemessen am 07.10.2026: Der zurückgelesene Wert ist
    genau der zuvor gesetzte. Ohne freie Phase erschiene die saubere Sinuskurve dadurch mit rund
    4 % Restabweichung statt mit 0,1 %.
    """
    h = max(kurve) - min(kurve)
    n = len(kurve)
    erg = {}
    for name, f in MODELLE.items():
        if h <= 0:
            erg[name] = 1e9
            continue
        beste = 1e9
        for k in range(n):                        # jede Verschiebung um ganze Stützstellen
            s = k / n
            v = [f((q + s) % 1.0) for q in phase]
            sv, sy = sum(v), sum(kurve)
            svv = sum(a * a for a in v)
            svy = sum(a * b for a, b in zip(v, kurve))
            nen = n * svv - sv * sv
            if abs(nen) < 1e-12:
                continue
            c1 = (n * svy - sv * sy) / nen
            c0 = (sy - c1 * sv) / n
            r = math.sqrt(sum((y - (c0 + c1 * w)) ** 2 for y, w in zip(kurve, v)) / n) / h * 100
            beste = min(beste, r)
        erg[name] = beste
    return erg


# --------------------------------------------- Glied 7, Weg 1: das Programm misst sich selbst
def form_aus_selbstmessung(text: str) -> dict | None:
    """Die Zeilen 'P t=.. dt=.. D=..' auswerten, die das Programm selbst schickt.

    Das Programm liest den Tastgrad aus der PWM-Einheit zurück und meldet die Rohwerte; die
    Kurvenform wird hier gerechnet, nicht dort behauptet. Dieser Weg bremst das Programm nicht,
    deshalb gilt die hier gemessene Periodendauer -- anders als beim zweiten Weg.
    """
    perioden = []
    for z in text.splitlines():
        if not z.startswith("P ") or "D=" not in z:
            continue
        try:
            dt = int(z.split("dt=")[1].split()[0])
            werte = [int(x) for x in z.split("D=")[1].strip().split(",") if x.isdigit()]
        except (ValueError, IndexError):
            continue
        if len(werte) > 8:
            perioden.append((dt, werte))
    if len(perioden) < 2:
        return None
    laenge = max(len(w) for _, w in perioden)
    voll = [w for _, w in perioden if len(w) == laenge]
    mittel = [sum(w[i] for w in voll) / len(voll) for i in range(laenge)]
    # Phase i/laenge, nicht (i+0.5)/laenge: Die Stufe i wird genau bei dieser Phase gesetzt.
    # Beim zweiten Weg ist die halbe Stufe richtig, dort wird über ein Zeitfenster gemittelt.
    phase = [i / laenge for i in range(laenge)]
    dauern = [dt for dt, _ in perioden]
    return {"perioden": len(perioden), "stufen": laenge, "formen": formen_anpassen(phase, mittel),
            "beste": min(formen_anpassen(phase, mittel), key=lambda k: formen_anpassen(phase, mittel)[k]),
            "periode_ms": sum(dauern) / len(dauern), "periode_streuung_ms": max(dauern) - min(dauern),
            "hub": max(mittel) - min(mittel)}


# --------------------------------------------- Glied 7, Weg 2: von außen, ohne dem Programm zu glauben
def form_aus_messung(text: str) -> dict | None:
    """Die Kurvenform aus den Werten des PWM-Registers bestimmen. Siehe Kopf dieser Datei."""
    reihen, akt, drin = [], [], False
    for z in text.splitlines():
        if "MESSUNG START" in z:
            akt, drin = [], True
            continue
        if "MESSUNG ENDE" in z:
            if drin and len(akt) > 300:
                reihen.append(akt)
            drin = False
            continue
        if drin and z.startswith("M "):
            for p in z[2:].split():
                if p.count(":") != 1:
                    continue                      # beim Mitlesen zusammengelaufenes Feld
                a, b = p.split(":")
                if a.isdigit() and b.isdigit():
                    akt.append((int(a) / 1e6, float(b)))
    if not reihen:
        return None
    r = max(reihen, key=len)
    t = [x for x, _ in r]
    d = [y for _, y in r]
    lo, hi = min(d), max(d)
    hub = hi - lo
    if hub < 100:                                 # weniger als 10 % Hub: da atmet nichts
        return {"hub": hub, "punkte": len(r), "formen": {}, "beste": None}

    # Perioden falten. Jede Periode liegt zwischen zwei Minima; jede wird auf die Phase 0..1
    # gestreckt und alle werden übereinandergelegt. Damit fällt heraus, dass die Periodendauer
    # schwankt -- und nur darum war die Prüfung vorher unscharf (22 % statt 1,5 % Rest).
    schwelle = lo + 0.02 * hub
    gruppen: list[list[int]] = []
    for i, y in enumerate(d):
        if y > schwelle:
            continue
        if gruppen and i - gruppen[-1][-1] <= 3:
            gruppen[-1].append(i)
        else:
            gruppen.append([i])
    mitten = [t[g[len(g) // 2]] for g in gruppen]
    if len(mitten) < 3:                           # weniger als zwei volle Perioden: nicht entscheidbar
        return {"hub": hub, "punkte": len(r), "dauer": t[-1] - t[0], "perioden": len(mitten) - 1,
                "formen": {}, "beste": None}
    dauern = [(mitten[i + 1] - mitten[i]) * 1000 for i in range(len(mitten) - 1)]

    K = 40
    summe = [0.0] * K
    zahl = [0] * K
    for i in range(len(mitten) - 1):
        a, b = mitten[i], mitten[i + 1]
        for x, y in zip(t, d):
            if a <= x < b:
                k = int((x - a) / (b - a) * K) % K
                summe[k] += y
                zahl[k] += 1
    phase = [(k + 0.5) / K for k in range(K) if zahl[k]]
    kurve = [summe[k] / zahl[k] for k in range(K) if zahl[k]]
    h2 = max(kurve) - min(kurve)

    erg = formen_anpassen(phase, kurve)
    beste = min(erg, key=erg.get)
    return {"hub": hub, "punkte": len(r), "dauer": t[-1] - t[0], "formen": erg, "beste": beste,
            "perioden": len(dauern), "periode_ms": sum(dauern) / len(dauern),
            "periode_streuung_ms": max(dauern) - min(dauern)}


# ----------------------------------------------------------------- der Lauf
def durchlauf(auftrag: dict, roh: bytes, name: str, a) -> None:
    """Die Glieder 3 bis 7 für einen Programmtext. Befunde sammelt `sage` in BEFUNDE."""
    # Glied 3
    hier = hashlib.sha256(roh).hexdigest()
    sage(True, f"Glied 3: {len(roh)} Byte, sha256 {hier[:16]}…")
    pruefe_text(roh, auftrag)

    # Glied 5
    (ABLAGE / name).write_bytes(roh)
    print("  " + bruecke("update", name).strip()[:100])
    antwort = bruecke("mpy", f"senden {name} {a.port} main.py")
    sage(antwort.startswith("OK:") and hier in antwort,
         "Glied 5: " + " | ".join(z.strip() for z in antwort.splitlines()[:1] + antwort.splitlines()[2:3]))

    # Glied 6. Ein Neustart kann misslingen -- am 07.10.2026 geschah das einmal in vier Läufen,
    # ohne erkennbare Ursache. Deshalb wird ein zweites Mal versucht, und der Vermerk darüber
    # steht im Bericht: Wiederholen ist erlaubt, Verschweigen nicht.
    t0 = time.time()
    gelesen, zeilen, versuche = "", [], 0
    while versuche < 2 and not zeilen:
        versuche += 1
        bruecke("mpy", f"reset {a.port}")
        gelesen = bruecke("seriell", f"{a.port} 10")
        zeilen = [z for z in gelesen.splitlines()
                  if auftrag.get("lebenszeile") and auftrag["lebenszeile"] in z]
    sage(bool(zeilen), f"Glied 6: {len(zeilen)} Lebenszeilen in {time.time()-t0:.0f} s"
                       + (f" nach {versuche} Neustarts" if versuche > 1 else "")
                       + (f" — „{zeilen[0][:60]}“" if zeilen
                          else " — das Brett meldet sich auch im zweiten Anlauf nicht"))

    # Glied 7a: Takt
    gemessen = takt_aus_zeilen(zeilen, a.kennung)
    soll = auftrag.get("erwartung", {}).get("takt_hz")
    if gemessen and isinstance(soll, (int, float)):
        ms, n = gemessen
        hz = 1000.0 / ms
        ab = abs(hz - soll) / soll * 100
        schranke = auftrag.get("schranke_takt", 0.1) / soll * 100
        sage(ab <= schranke, f"Glied 7: Takt {hz:.4f} Hz aus {n} Perioden (Soll {soll} Hz, "
                             f"Abweichung {ab:.2f} %, Schranke {schranke:.0f} %)")
    elif isinstance(soll, (int, float)):
        sage(False, "Glied 7: aus den Lebenszeilen ließ sich kein Takt bestimmen")

    # Glied 7b, Weg 1: das Programm schickt die aus der Hardware zurückgelesenen Tastgrade mit
    selbst = form_aus_selbstmessung(gelesen)
    if auftrag.get("erwartung", {}).get("form"):
        soll_form = auftrag["erwartung"]["form"].capitalize()
        if selbst:
            liste = ", ".join(f"{k} {v:.2f} %" for k, v in sorted(selbst["formen"].items(), key=lambda x: x[1]))
            zweit = sorted(selbst["formen"].values())[1]
            sage(selbst["beste"] == soll_form and zweit > selbst["formen"][soll_form] * 1.5,
                 f"Glied 7 (Weg 1, das Programm meldet die zurückgelesenen Tastgrade): Form ist "
                 f"{selbst['beste']}, Rest {selbst['formen'][selbst['beste']]:.2f} % vom Hub — {liste}")
            print(f"           {selbst['perioden']} Perioden à {selbst['stufen']} Stufen, "
                  f"Periode {selbst['periode_ms']:.0f} ms (Streuung {selbst['periode_streuung_ms']:.0f} ms), "
                  f"Hub {selbst['hub']:.0f} von 1023 — ungebremst, deshalb gilt diese Periodendauer")
        elif soll_form == "Sinus":
            sage(False, "Glied 7 (Weg 1): das Programm schickt keine Messzeilen 'P t=… dt=… D=…'")

    # Glied 7c, Weg 2: von außen gemessen, ohne dem Programm zu glauben
    if auftrag.get("erwartung", {}).get("form") == "sinus" and not a.ohne_form:
        print("  Glied 7 (Weg 2): Kurvenform am PWM-Register messen, ohne dem Programm zu glauben")
        bruecke("mpy", f"senden {name} {a.port} {name}")
        mess = HIER / "messung.py"
        (ABLAGE / "messung.py").write_bytes(mess.read_bytes().replace(b"atmen.py", name.encode()))
        bruecke("update", "messung.py")
        bruecke("mpy", f"senden messung.py {a.port} main.py")
        bruecke("mpy", f"reset {a.port}")
        roh_mess = bruecke("seriell", f"{a.port} 14", zeit=400)
        f = form_aus_messung(roh_mess)
        if not f or not f["formen"]:
            sage(False, "Glied 7: keine auswertbare Messreihe vom Gerät"
                        + (f" (nur {f.get('perioden', 0)} Periode(n), es braucht zwei)" if f else ""))
        else:
            liste = ", ".join(f"{k} {v:.2f} %" for k, v in sorted(f["formen"].items(), key=lambda x: x[1]))
            zweitbester = sorted(f["formen"].values())[1]
            sage(f["beste"] == "Sinus" and zweitbester > f["formen"]["Sinus"] * 1.5,
                 f"Glied 7 (Weg 2): Form am Gerät ist {f['beste']}, Rest {f['formen'][f['beste']]:.2f} % vom Hub "
                 f"— {liste}")
            if selbst:
                ab = abs(f["formen"][f["beste"]] - selbst["formen"][selbst["beste"]])
                sage(f["beste"] == selbst["beste"],
                     f"Glied 7: beide Wege sagen {f['beste']} bzw. {selbst['beste']} "
                     f"(Restabweichungen {selbst['formen'][selbst['beste']]:.2f} % und "
                     f"{f['formen'][f['beste']]:.2f} %, Unterschied {ab:.2f} Prozentpunkte)")
            print(f"           {f['punkte']} Punkte über {f['dauer']:.1f} s, {f['perioden']} Perioden "
                  f"gefaltet, Hub {f['hub']:.0f} von 1023")
            print(f"           Periode während der Messung {f['periode_ms']:.0f} ms (Streuung "
                  f"{f['periode_streuung_ms']:.0f} ms) — die Messung bremst den Nebenlauf, "
                  f"der gültige Takt steht oben aus den Lebenszeilen")


def main() -> int:
    global fehler
    p = argparse.ArgumentParser()
    p.add_argument("kennung", help="Kennung aus auftraege.json, z. B. atmen-sinus")
    p.add_argument("--programm", help="Programmdatei vorgeben, statt das Modell zu fragen")
    p.add_argument("--port", default="COM3")
    p.add_argument("--ohne-form", action="store_true", help="die Formmessung überspringen")
    p.add_argument("--runden", type=int, default=3, help="höchstens so viele Berichtigungsrunden")
    a = p.parse_args()

    auftraege = {x["kennung"]: x for x in json.loads(AUFTRAEGE.read_text(encoding="utf-8"))}
    if a.kennung not in auftraege:
        print(f"FEHLER: Auftrag {a.kennung} steht nicht in {AUFTRAEGE.name}")
        return 2
    auftrag = auftraege[a.kennung]
    print(f"Auftrag {a.kennung}: {auftrag['titel']}")
    print(f"  Brücke: {bruecke('info', '').splitlines()[0][:70] if BEFEHL.is_file() else '?'}")

    # E6: ohne Gerät kein grüner Haken
    anschluesse = bruecke("anschluesse", "")
    if a.port.upper() not in anschluesse.upper():
        print(f"\nNICHT PRÜFBAR: an {a.port} ist nichts sichtbar.\n{anschluesse.strip()[:200]}")
        return 3
    sage(True, f"Glied 0: {a.port} ist da — {[z for z in anschluesse.splitlines() if a.port in z][0].strip()[:70]}")

    name = auftrag["datei"] or "programm.py"
    nachweis: dict = {}
    befund = ""
    text = ""
    if a.programm:
        text = pathlib.Path(a.programm).read_text(encoding="utf-8")
        name = pathlib.Path(a.programm).name
        print(f"  Glied 2: Programmtext vorgegeben aus {name} — dieser Lauf prüft das MODELL NICHT")

    for runde in range(1, a.runden + 1):
        if not a.programm:
            text, nachweis = modell_fragen(auftrag, text, befund)
            if not text:
                print(f"\n  Glied 2: {nachweis.get('fehler')}")
                if nachweis.get("bitte"):
                    print(f"  Die Bitte an das Modell liegt als {nachweis['bitte']} bereit.")
                print("\nNICHT PRÜFBAR: ohne Modell ist die Kette nicht vollständig zu fahren.")
                return 3
            print(f"  Glied 2: Modell {nachweis['modell']}, Antwort {nachweis['kennung']}, "
                  f"{nachweis['zeit']}, {nachweis['dauer_s']} s, {nachweis['token_aus']} Token")

        print(f"\n  ----- Runde {runde} von höchstens {a.runden} -----")
        fehler = 0
        BEFUNDE.clear()
        durchlauf(auftrag, text.encode("utf-8"), name, a)
        if fehler == 0:
            print(f"\nalles in Ordnung" + (f" (nach {runde} Runden)" if runde > 1 else "")
                  + ("" if not a.programm else " — Glied 2 (Modell) war vorgegeben, also nicht geprüft"))
            return 0
        befund = "\n".join(f"- {b}" for b in BEFUNDE)
        if a.programm:
            break                                   # ein vorgegebener Text berichtigt sich nicht selbst
        print(f"\n  {fehler} Befund(e) — dem Modell zur Berichtigung vorlegen")

    blatt = HIER / f"fehlschlag_{a.kennung}_{time.strftime('%Y-%m-%d_%H%M%S')}.txt"
    blatt.write_text("BEFUNDE\n" + befund + "\n\nPROGRAMM\n" + text + "\n\nROHANTWORTEN DER BRÜCKE\n"
                     + "\n\n".join(MITSCHRIFT), encoding="utf-8")
    print(f"\nRohdaten mitgeschrieben: {blatt.name}")
    print(f"{fehler} Befund(e)" + (" — Glied 2 (Modell) war vorgegeben" if a.programm
                                   else f" nach {a.runden} Runden"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
