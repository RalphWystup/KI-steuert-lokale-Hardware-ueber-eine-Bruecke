#!/usr/bin/env python3
"""Befehl an die Brücke auf dem PC (Empfänger im Workspace auf Port 8085).

Ohne Angabe geht der Befehl an das Projekt Projekt_A. Ein anderes Projekt mit -p davor:
  python3 befehl.py -p Layout oeffnen "C:\\Layout\\Platine\\Platine.kicad_pcb"

  python3 befehl.py info
  python3 befehl.py cadprog '?'                            DDE-Verbindung zum CAD-Programm prüfen
  python3 befehl.py cadprog 'PrtLoad "C:\\CAD\\Bauteil.PRT"'  Befehl des CAD-Programms (BEFEHLE.INI); mehrere mit ' ;; '
  python3 befehl.py dateiliste cadprog | dateiliste "C:\\CAD" | dateiliste "suche C:\\ *.PRT"
  python3 befehl.py hochladen "C:\\Programme\\CAD\\BEFEHLE.INI"   Datei nach Projekt_A/Bilder/
  python3 befehl.py update "bruecke.py"                  Dateien aus Projekt_A/Arbeitsstand/Laptop/ auf den PC
  python3 befehl.py femm "exportiere_v8_netzfein_basisfelder.lua" 7200   FEMM 4.2 auf dem PC rechnen lassen
  python3 befehl.py bildschirm | selbstupdate
"""
import sys, time, urllib.request, urllib.parse, pathlib
# Das Token steht einmal im Workspace; der Weg dorthin darf nicht davon abhängen, wo dieses
# Skript gerade liegt. Deshalb von hier aus aufwärts suchen, bis der Workspace gefunden ist.
def _token() -> str:
    """Das Token aus der Datei lesen, die der Empfaenger neben sich anlegt.

    Es steht absichtlich nicht im Programm: Wer dieses Skript weitergibt, gaebe es sonst mit.
    Gesucht wird neben dem Empfaenger und von hier aus aufwaerts, damit der Ablageort des
    Skripts frei bleibt.
    """
    orte = [pathlib.Path(__file__).resolve().parent / '.empfaenger_token']
    for basis in pathlib.Path(__file__).resolve().parents:
        orte.append(basis / '.empfaenger_token')
        orte.append(basis / 'empfaenger' / '.empfaenger_token')
    for k in orte:
        if k.is_file(): return k.read_text().strip()
    raise SystemExit('FEHLER: .empfaenger_token nicht gefunden. Es liegt neben empfaenger.py, '
                     'sobald dieser einmal gestartet wurde.')


TOKEN = _token()
B = 'http://127.0.0.1:8085'
# Projekt wählbar: 'befehl.py -p Layout dateiliste C:\\Layout'
PROJEKT = 'Projekt_A'
if len(sys.argv) > 2 and sys.argv[1] in ('-p', '--projekt'):
    PROJEKT = sys.argv[2]; del sys.argv[1:3]
if len(sys.argv) < 2: print(__doc__); sys.exit(1)
typ = sys.argv[1]; arg = sys.argv[2] if len(sys.argv) > 2 else ''
q = {'token': TOKEN, 'projekt': PROJEKT, 'typ': typ, 'url': arg}
warte = {'cadprog': 260, 'dateiliste': 120, 'hochladen': 300, 'update': 300, 'femm': 7500}.get(typ, 40)
i = urllib.request.urlopen(urllib.request.Request(B + '/befehl?' + urllib.parse.urlencode(q), data=b'', method='POST')).read().decode()
t0 = time.time()
while time.time() - t0 < warte:
    a = urllib.request.urlopen(f'{B}/antwort_lesen?id={i}').read().decode()
    if a: print(a); sys.exit(0)
    time.sleep(1)
print(f'keine Antwort (läuft die CAD-Brücke? Befehl {i} wartet weiter)'); sys.exit(2)
