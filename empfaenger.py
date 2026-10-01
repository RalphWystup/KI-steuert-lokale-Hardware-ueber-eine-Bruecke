#!/usr/bin/env python3
"""Empfänger im Workspace: nimmt Bilder und Statusdateien vom PC-Skript geraete_bruecke.py an
und legt sie im Ordner Bilder/ ab (einziger Bildablageort). Läuft auf Port 8085.

POST /upload?token=…&name=…   Body = Dateiinhalt (JPEG oder JSON)   -> Bilder/<Zeit>_<name>
                                Namen "live_…" -> Bilder/live/ (rollierend, letzte 30; aktuell.jpg/.json; verlauf.jsonl)
GET  /                          kurze Statusseite (zum Prüfen, ob der Zugang von außen klappt)
GET  /befehle?token=…           PC-Skript holt Befehle (esp: URL am ESP; ota/usb: Firmware aus firmware/ flashen; modbus; selbstupdate; usbinfo)
GET  /datei?token=…&name=…      liefert Dateien aus firmware/ (Firmware .bin, espota.py)
POST /befehl?token=…&typ=esp&url=/kal?wert=0     lokal einreihen (esp_befehl.py)      POST /antwort?token=…&id=…  Antwort
Rückweg: der PC führt Befehle aus, die ich hier einreihe; so kann ich kalibrieren, einstellen und per OTA flashen.
Seit 16.09.2026 mehrprojektfähig: Parameter projekt=<Ordnername unter /workspace> (Standard Projekt_Kamera) wählt
Befehlswarteschlange, Firmware-Ordner (<projekt>/Arbeitsstand/firmware, dazu <projekt>/Arbeitsstand/Laptop) und Bildablage
(<projekt>/Bilder). Ein Empfänger für alle Projekte; die Brücke eines Laptops nennt ihr Projekt in jeder Anfrage.
Seit 22.09.2026 KI-Fragen aus dem Browser (Mikroskop_Beispiel.html, Reiter KI, Kanal Workspace): POST /frage?token=…&projekt=…  Body JSON
{text, bild (Base64-JPEG, optional), beschreibung, zustand} -> <projekt>/Arbeitsstand/KI_Fragen/<id>/frage.json + bild.jpg; die Seite fragt
GET /frage_antwort?token=…&id=… ab, bis dort antwort.txt liegt (schreibt der Agent im Workspace mit ki_fragen.py). OPTIONS für CORS-Vorabfragen.
"""
import http.server, pathlib, datetime, urllib.parse, json, sys, threading, time, hashlib

PORT = 8085
WORKSPACE = pathlib.Path(__file__).resolve().parent.parent.parent          # /workspace
STANDARD_PROJEKT = pathlib.Path(__file__).resolve().parent.parent.name     # Projekt_Kamera
BRUECKEN = {'Projekt_Kamera': 'geraete_bruecke.py', 'Projekt_Mikroskop_Beispiel': 'bruecke.py', 'Projekt_A': 'bruecke.py'}   # Skript je Projekt zur Selbstaktualisierung
def projekt_von(q):
    name = ''.join(c for c in q.get('projekt', [STANDARD_PROJEKT])[0] if c.isalnum() or c in '_-') or STANDARD_PROJEKT
    return name if (WORKSPACE / name / 'Arbeitsstand').is_dir() else STANDARD_PROJEKT
def bilder_von(projekt): return WORKSPACE / projekt / 'Bilder'
def firmware_von(projekt): return WORKSPACE / projekt / 'Arbeitsstand' / 'firmware'
def fragen_von(projekt): return WORKSPACE / projekt / 'Arbeitsstand' / 'KI_Fragen'
BILDER = bilder_von(STANDARD_PROJEKT)
LIVE = BILDER / 'live'                 # Live-Reihe: rollierend, nur die letzten BEHALTEN Bilder
BEHALTEN = 30
TOKEN = (pathlib.Path(__file__).with_name('.empfaenger_token').read_text().strip())
empfangen = []
FIRMWARE = pathlib.Path(__file__).resolve().parent / 'firmware'
ANTWORTEN = pathlib.Path(__file__).resolve().parent / 'antworten.log'
befehle = []            # Warteschlange: dict(id, typ, url|datei)
antworten = {}          # id -> Text
sperre = threading.Lock(); naechste_id = [1]

class H(http.server.BaseHTTPRequestHandler):
    def _antwort(self, code, text):
        b = text.encode(); self.send_response(code); self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(b))); self.send_header('Access-Control-Allow-Origin', '*'); self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self):                               # CORS-Vorabfrage des Browsers (Mikroskop_Beispiel.html schickt JSON)
        self.send_response(204); self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'content-type'); self.send_header('Access-Control-Max-Age', '600'); self.send_header('Content-Length', '0'); self.end_headers()
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == '/befehle':                        # PC-Skript holt anstehende Befehle (Token nötig)
            if q.get('token', [''])[0] != TOKEN: self._antwort(403, 'abgelehnt'); return
            pr = projekt_von(q)
            with sperre: heraus = [b for b in befehle if b.get('projekt', STANDARD_PROJEKT) == pr]; befehle[:] = [b for b in befehle if b.get('projekt', STANDARD_PROJEKT) != pr]
            self._antwort(200, json.dumps(heraus)); return
        if u.path == '/datei':                          # Firmware oder OTA-Werkzeug ausliefern
            if q.get('token', [''])[0] != TOKEN: self._antwort(403, 'abgelehnt'); return
            pr = projekt_von(q); fw = firmware_von(pr)
            name = ''.join(c for c in q.get('name', [''])[0] if c.isalnum() or c in '._-'); f = fw / name
            if not f.is_file() and (fw.parent / 'Laptop' / name).is_file(): f = fw.parent / 'Laptop' / name   # Programmdateien für den Laptop
            if name == BRUECKEN.get(pr): f = fw.parent / name                                                # Brücke zur Selbstaktualisierung
            if not f.is_file(): self._antwort(404, 'keine Datei'); return
            b = f.read_bytes(); self.send_response(200); self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path == '/frage_antwort':                   # Browser fragt nach der Antwort des Agenten auf eine KI-Frage
            if q.get('token', [''])[0] != TOKEN: self._antwort(403, 'abgelehnt'); return
            i = ''.join(c for c in q.get('id', [''])[0] if c.isalnum() or c in '_-'); d = fragen_von(projekt_von(q)) / i
            if not i or not d.is_dir(): self._antwort(404, 'unbekannte Frage'); return
            a = d / 'antwort.txt'; self._antwort(200, json.dumps({'fertig': a.is_file(), 'antwort': a.read_text(encoding='utf-8') if a.is_file() else '', 'gesehen': (d / 'gesehen').is_file()}, ensure_ascii=False)); return
        if u.path == '/antwort_lesen':                   # lokal: Antwort zu einer Befehls-Id abfragen
            i = q.get('id', [''])[0]; self._antwort(200, antworten.get(i, '')); return
        self._antwort(200, f'Empfänger läuft. Ablage: {BILDER}\nEmpfangen: {len(empfangen)}\n' + '\n'.join(empfangen[-10:]))
    def do_POST(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if q.get('token', [''])[0] != TOKEN:
            self._antwort(403, 'abgelehnt'); return
        n = int(self.headers.get('Content-Length', '0')); daten = self.rfile.read(n)
        if u.path == '/befehl':                          # lokal (esp_befehl.py): Befehl einreihen
            with sperre: i = str(naechste_id[0]); naechste_id[0] += 1
            pr = projekt_von(q)
            b = {'id': i, 'projekt': pr, 'typ': q.get('typ', ['esp'])[0], 'url': q.get('url', [''])[0], 'datei': q.get('datei', [''])[0]}
            if b['typ'] in ('ota', 'usb') and b['datei']: b['md5'] = hashlib.md5((firmware_von(pr) / b['datei']).read_bytes()).hexdigest()
            with sperre: befehle.append(b)
            self._antwort(200, i); return
        if u.path == '/antwort':                         # PC-Skript liefert die Antwort des ESP
            i = q.get('id', [''])[0]; text = daten.decode(errors='replace'); antworten[i] = text
            with open(ANTWORTEN, 'a') as f: f.write(f"{datetime.datetime.now():%H:%M:%S} [{i}] {text}\n")
            print(f'Antwort [{i}]: {text[:200]}', flush=True); self._antwort(200, 'ok'); return
        if u.path == '/frage':                           # KI-Frage aus dem Browser: Text, Bild, Gerätezustand ablegen; der Agent antwortet über antwort.txt
            try: j = json.loads(daten.decode('utf-8'))
            except Exception: self._antwort(400, 'kein JSON'); return
            pr = projekt_von(q); i = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')[:-3]; d = fragen_von(pr) / i; d.mkdir(parents=True, exist_ok=True)
            bild = j.pop('bild', None)
            if bild:
                try: import base64; (d / 'bild.jpg').write_bytes(base64.b64decode(bild))
                except Exception: pass
            j['zeit'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'); j['id'] = i; j['bild'] = (d / 'bild.jpg').is_file()
            (d / 'frage.json').write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding='utf-8')
            print(f'KI-Frage [{i}] {pr}: {str(j.get("text", ""))[:120]}', flush=True); self._antwort(200, i); return
        if u.path != '/upload': self._antwort(404, 'unbekannt'); return
        name = ''.join(c for c in q.get('name', ['bild.jpg'])[0] if c.isalnum() or c in '._-') or 'bild.jpg'
        BILDER = bilder_von(projekt_von(q)); LIVE = BILDER / 'live'; BILDER.mkdir(exist_ok=True)
        if name.startswith('live_'):
            # Live-Reihe: Unterordner Bilder/live, nur die letzten BEHALTEN Dateien je Endung, Verlaufsdatei
            LIVE.mkdir(exist_ok=True)
            ziel = LIVE / f"{datetime.datetime.now():%H%M%S}_{name}"; ziel.write_bytes(daten)
            (LIVE / ('aktuell' + ziel.suffix)).write_bytes(daten)
            alte = sorted(LIVE.glob('*_live_*' + ziel.suffix))
            for a in alte[:-BEHALTEN]: a.unlink()
            if ziel.suffix == '.json':
                try:
                    j = json.loads(daten.decode()); l = j.get('linie') or {}; lg = j.get('lage') or {}
                    zeile = {'zeit': datetime.datetime.now().strftime('%H:%M:%S'), 'name': name, 'bild': j.get('bilder'), 'ms': j.get('dauer_ms'),
                             'winkel180': l.get('winkel180'), 'punkte': l.get('punkte'), 'kalibriert': j.get('kalibriert'),
                             'wert': j.get('wert_median'), 'winkel': j.get('winkel'), 'sicherheit': j.get('sicherheit'),
                             'lage': [lg.get('dx'), lg.get('dy'), lg.get('dtheta'), lg.get('guete')] if lg else None}
                    with open(LIVE / 'verlauf.jsonl', 'a') as f: f.write(json.dumps(zeile, ensure_ascii=False) + '\n')
                except Exception as e:
                    print('Status nicht lesbar:', e, flush=True)
        else:
            ziel = BILDER / f"{datetime.datetime.now():%Y-%m-%d_%H%M%S}_{name}"; ziel.write_bytes(daten)
        empfangen.append(f'{ziel.name} ({len(daten)} B)'); print('empfangen:', ziel.name, len(daten), 'B', flush=True)
        self._antwort(200, f'gespeichert: {ziel.name}')
    def log_message(self, *a): pass

if __name__ == '__main__':
    print(f'Empfänger auf Port {PORT}, Standardprojekt {STANDARD_PROJEKT}, Ablage {BILDER}', flush=True)
    http.server.ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
