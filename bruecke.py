#!/usr/bin/env python3
"""Brücke zwischen dem PC und dem Workspace — eine für alle Projekte.

Läuft in ``C:\\Bruecke`` und bedient jedes Projekt, das im Workspace einen Empfänger-Kanal hat.
Sie fragt in jedem Durchlauf alle Projekte aus ``PROJEKTE`` ab, führt die gefundenen Befehle aus
und liefert die Antwort an dasselbe Projekt zurück. Dateien werden dabei immer im Ordner des
Projekts abgelegt, aus dem der Befehl kam.

Vorher gab es drei Brücken nebeneinander — eine für das Mikroskop, eine für das Anzeigegerät, eine
für CAD. Jede konnte etwas, das die anderen nicht konnten, und keine lief, wenn gerade eine andere
gebraucht wurde. Diese hier kann alles und läuft immer.

Befehle (aus dem Workspace mit cad_befehl.py):
  megacad <Befehl>        MegaCAD-Kommandozeile per DDE-Execute an das laufende MegaCAD (Dienst MegaCAD_3D, Thema System);
                          mehrere Befehle mit ' ;; ' trennen; 'megacad ?' prüft nur die Verbindung; 'megacad @Dienst <Befehl>' erzwingt den Dienst
  dateiliste <Ordner>     Ordner listen; 'dateiliste megacad' sucht die MegaCAD-Installation (EXE, FUNCNAM.INI, Menüdateien);
                          'dateiliste suche <Ordner> <Muster>' sucht rekursiv (z. B. suche C:\\ *.PRT)
  klick [rechts|links|doppel] [x y]  echter Mausklick in MegaCAD oder einen seiner Dialoge (bestätigt eine Elementauswahl, „R: genug“);
                          x y optional als Anteil 0..1 der Fenstergröße, Standard Mitte; 'klick links abs X Y' = Bildschirmpixel (Dialog auf anderem Monitor)
  hochladen <Datei>       Datei vom PC in den Workspace (EOPT/Bilder/), z. B. FUNCNAM.INI oder ein SAT-Export
  update <Dateien> [-> <Zielordner>]  Dateien aus dem Workspace (EOPT/Arbeitsstand/Laptop/) holen (kommagetrennt);
                          ohne Zielordner in diesen Ordner, sonst in den angegebenen, der bei Bedarf angelegt wird
  bildschirm [alles]      Bildschirmfoto in den Workspace: Standard = das MegaCAD-Fenster (auch auf einem zweiten oder virtuellen Monitor),
                          'bildschirm alles' = alle Monitore zusammen
  fenster [alle]          sichtbare Fenster des MegaCAD-Prozesses; 'alle' listet jedes Fenster (z. B. FEMM-Meldungen)
  zeigen <Titelteil> [x y]  ein Fenster ganz nach oben stellen und an die Stelle x y legen (Standard 60 60)
  oeffnen <Pfad>          eine Datei mit ihrem Standardprogramm oeffnen (Layout in KiCad, Gerber, PDF, Bild);
                          nur in den erlaubten Zweigen und nur Datenendungen, nichts Ausfuehrbares
  schliessen <Titelteil>  einem Fenster die Schließen-Nachricht schicken (blockierende Meldungen)
  prozesse [Namensteil]   laufende Programme mit Speicherbedarf anzeigen (rechnet der Löser wirklich?)
  femm <Lua-Datei> [s|start]  FEMM 4.2 mit einem Lua-Skript rechnen lassen; 'start' kehrt sofort zurück, sonst wird gewartet
  megacad_nach <Nr>       MegaCAD-Hauptfenster auf Monitor Nr legen und maximieren
  dialoge                 MegaCAD-Dialoge vom anderen Monitor in die Mitte des MegaCAD-Fensters verschieben (wird vor jedem Klick auch automatisch gemacht)
  monitore                angeschlossene Monitore (auch virtuelle) mit Lage und Größe, dazu die Lage des MegaCAD-Fensters
  info                    Python, Ordner, pywin32 vorhanden, DDE erreichbar
  selbstupdate            diese Brücke aus dem Workspace erneuern (im laufenden Betrieb)
  verschieben <Ordner> :: n1,n2  die genannten Dateien in <Ordner>\\alt legen (nie löschen, nie überschreiben; nur C:\\PMSM, C:\\git, C:\\REM_CAD, C:\\Segway, C:\\Sicherungskopien)
Außer FEMM startet die Brücke keine Programme; MegaCAD öffnet der Nutzer selbst.
Einrichtung: pip install pywin32 pillow   – dann Doppelklick auf Bruecke_starten.bat (wird beim ersten Start geschrieben).
"""
import argparse, socket, sys, time, urllib.request, urllib.parse, json, os, datetime, shutil, io, threading, fnmatch, subprocess, glob, re, hashlib, base64
if os.name == 'nt':                      # Pro-Monitor-DPI: Fensterlagen, Mauspunkte und Bildschirmfotos in echten Pixeln, auch bei 150 % Skalierung
    try:
        import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass

VERSION = ('Brücke 3.8 (07.10.2026, modell frage_datei dazu: lange Gespraeche kommen als Datei statt in der Befehlszeile. | aus 3.7 (07.10.2026, modell dazu: das Sprachmodell aus dem Kurspaket starten, befragen und beenden (llama-server auf 127.0.0.1:8099, nur von hier aus erreichbar) -- damit ein Agent im Arbeitsbereich das Modell auf DIESEM Rechner beauftragen kann, ohne Konto und ohne Netz. Enger Rahmen wie bei flashen: genau ein Programm aus C:\\Kurs_Agent\\paket, Modellwahl ueber Schluesselwort, Befehlszeile hier gebaut. | aus 3.6 (07.10.2026, mpy dazu: eine einzelne Python-Datei auf ein MicroPython-Brett schreiben und die Pruefsumme VOM BRETT zurueckholen, dazu liste, pruefsumme und reset. Weg ist die Raw-REPL ueber pyserial; auf dem Rechner wird nichts gestartet. Anlass: ohne diesen Schritt endet die Kette Modell-Programm-Geraet am Rechner, und ob auf dem Brett etwas laeuft, weiss nur wer danebensteht. | aus 3.5 (04.10.2026, sende dazu: eine kurze JSON-Nachricht an ein Programm auf dem Rechner selbst (nur 127.x), damit der laufende Kurs-Agent aus dem Arbeitsbereich bedient werden kann -- auf Wort des Auftraggebers. | aus 3.4 (04.10.2026, hole nimmt auch 127.0.0.1 an -- die Auskunft eines Programms auf dem Arbeitsplatzrechner selbst, etwa der Kurs-Agent unter 127.0.0.1:8777/zustand, lesbar ohne den Browser-Reiter nach vorn zu holen; nur lesen, nur HTTP, wie bisher. | aus 3.3 (03.10.2026, hole nimmt auch Namen der Form <name>.local an -- der Heizoelanzeiger meldet sich als heizoel.local an, damit er auch dann erreichbar bleibt, wenn der Router eine andere Zahl vergibt. Keine Ausweitung ins Internet: .local wird nur auf dem eigenen Netzstrang aufgeloest.) | aus 3.2 (02.10.2026, ota dazu: Firmware ueber WLAN statt Kabel, espota.py aus dem Brueckenordner, gleicher enger Rahmen wie flashen. | aus 3.1: flashen und seriell dazu: ein ESP32-Brett laesst sich jetzt aus dem Workspace neu beschreiben und mitlesen, ohne eine zweite Bruecke daneben. Eng gefasst - nur esptool, nur eine .bin aus dem Brueckenordner, nur COM<Zahl>, nur 0x0 oder 0x10000; die Befehlszeile wird hier gebaut. Anlass: die CYD-Bruecke lag nicht mehr auf dem Rechner, und zwei Bruecken nebeneinander waren schon einmal die Fehlerquelle.) | aus Brücke 3.0 (01.10.2026, Universalbrücke: ein Programm für alle Projekte statt dreier nebeneinander. Fragt in jedem Durchlauf alle Projekte aus PROJEKTE ab und antwortet jeweils demselben; Dateien landen im Ordner des Projekts, aus dem der Befehl kam. Ordner C:\\Bruecke, Startdatei Bruecke_starten.bat, Selbstaktualisierung holt bruecke.py. Erlaubte Zweige um C:\\Bruecke, C:\\Antigravitation und C:\\Kurs_Agent erweitert; Projekt Kurs_Agent aufgenommen.'
           ' | aus CAD-Brücke 2.5 (30.09.2026): Ordner C:\\Leiterplatten, Hochladen mit Dateimuster, Befehl oeffnen; 2.5 davor: Gehalt-Ordner, Kennlinienschreiber, Verschieben in Projektordnern; 2026-09-29: Verschieben nach alt; 2026-09-26: Löschen benannter Dateien, Sicherungskopie nur bei echter Änderung, Update mit Zielordner, MegaCAD per DDE, Mausklick, Dateiliste, Hochladen, Bildschirmfoto, DPI-bewusst, Monitorliste, FEMM-Lauf, Selbstupdate)')
# ---------------------------------------------------------------- Zugang
# Adresse und Token stehen NICHT im Programm, sondern in bruecke_zugang.json daneben.
# Grund: Dieses Programm wird weitergegeben; die Zugangsdaten dürfen das nicht. Wer den
# Erzeuger veröffentlicht, veröffentlicht sonst das Geheimnis mit.
#
#   { "workspace": "https://…", "token": "…" }
#
# Fehlt die Datei, sagt die Brücke beim Start, was hineingehört, und beendet sich.
def _zugang():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bruecke_zugang.json')
    if not os.path.isfile(d):
        raise SystemExit(
            'Zugangsdatei fehlt: ' + d + '\n'
            'Inhalt:  { "workspace": "https://<Adresse des Empfaengers>", "token": "<Token>" }\n'
            'Die Adresse ist die, unter der der Empfaenger im Workspace erreichbar ist;\n'
            'das Token steht dort in .empfaenger_token.')
    with open(d, encoding='utf-8') as f:
        j = json.load(f)
    fehlt = [k for k in ('workspace', 'token') if not j.get(k)]
    if fehlt:
        raise SystemExit('In ' + d + ' fehlt: ' + ', '.join(fehlt))
    return j['workspace'].rstrip('/'), j['token']


WORKSPACE, TOKEN = _zugang()
# Alle Projekte, die der Empfänger im Workspace kennt. Die Brücke fragt sie der Reihe nach ab.
# Ein neues Projekt braucht hier nur eine Zeile — und im Workspace einen Ordner mit
# <Projekt>/Arbeitsstand/Laptop (für update) und <Projekt>/Bilder (für hochladen).
PROJEKTE = ('EOPT', 'Mikroskop_Laborstation', 'CYD_Display', 'Analoganzeige_lesen',
            'Leiterplatten', 'Antigravitation', 'Transistoren', 'PMSM',
            'Regelungstechnik2_Segway', 'Kennlinienschreiber', 'Wasserstand', 'DGL_Nichtlinear',
            'Kurs_Agent')

# Das Projekt des Befehls, der gerade bearbeitet wird. Jede Anfrage an den Workspace trägt es mit,
# damit Antwort, Hochladen und Update im richtigen Ordner landen.
AKTUELL = PROJEKTE[0]
ORDNER = os.path.dirname(os.path.abspath(__file__))
SICHERUNG = os.path.join(ORDNER, 'Sicherung')
ALT_BEHALTEN = 3                          # so viele frühere Fassungen je Datei bleiben im Sicherungsordner

def q(**kw): kw.update(token=TOKEN, projekt=AKTUELL); return urllib.parse.urlencode(kw)
def holen(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r: return r.read()
def senden(daten, name):
    req = urllib.request.Request(f'{WORKSPACE}/upload?' + q(name=name), data=daten, method='POST', headers={'Content-Type': 'application/octet-stream'})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode()
def datei_holen(name, timeout=120): return holen(f'{WORKSPACE}/datei?' + q(name=name), timeout)

# ---------------------------------------------------------------- MegaCAD per DDE ------------------------------------------------------------
def megacad(spec):
    """DDE-Execute an MegaCAD. DDE ist an den aufrufenden Thread gebunden, deshalb läuft alles in einem Arbeits-Thread mit Zeitgrenze."""
    spec = (spec or '').strip(); dienste = ('MegaCAD_3D', 'MegaCAD3D', 'MegaCAD', 'MEGACAD', 'MegaCAD_2D')
    if spec.startswith('@'): d, _, spec = spec[1:].partition(' '); dienste = (d,)
    befehle = [b.strip() for b in spec.split(' ;; ') if b.strip()]
    ergebnis = {'text': None}
    def arbeit():
        try: import win32ui, dde                                                       # pywin32
        except ImportError: ergebnis['text'] = 'FEHLER: pywin32 fehlt ("' + sys.executable + '" -m pip install pywin32)'; return
        server = dde.CreateServer(); server.Create('CADBruecke')
        try:
            conv = None; benutzt = None
            for d in dienste:
                c = dde.CreateConversation(server)
                try: c.ConnectTo(d, 'System'); conv = c; benutzt = d; break
                except Exception: continue
            if conv is None: ergebnis['text'] = 'FEHLER: kein DDE-Dienst erreichbar (' + ', '.join(dienste) + ') – läuft MegaCAD?'; return
            if not befehle or befehle == ['?']: ergebnis['text'] = f'DDE-Dienst {benutzt} erreichbar'; return
            teile = []
            for i, b in enumerate(befehle):
                if b.lower().startswith('pause'):                                       # 'pause 3' wartet 3 s (Standard 1,5 s)
                    try: time.sleep(float(b.split()[1].replace(',', '.')))
                    except (IndexError, ValueError): time.sleep(1.5)
                    teile.append(b); continue
                if i: time.sleep(1.5)                                                  # MegaCAD braucht Zeit, bevor es den nächsten Befehl annimmt
                t0 = time.time(); fehler = None
                for versuch in range(3):                                               # 'Exec failed' heißt meist: MegaCAD noch beschäftigt – kurz warten, erneut
                    try: conv.Exec(b); fehler = None; break
                    except Exception as e: fehler = e; time.sleep(1.5)
                if fehler is None: teile.append(f'{b} -> ok ({time.time() - t0:.1f} s)')
                else: teile.append(f'{b} -> FEHLER {fehler}'); break
            ergebnis['text'] = f'DDE {benutzt}: ' + ' | '.join(teile)
        finally:
            try: server.Shutdown()
            except Exception: pass
    th = threading.Thread(target=arbeit, daemon=True); th.start(); th.join(240)
    if th.is_alive(): return 'FEHLER: MegaCAD antwortet nicht innerhalb von 240 s (wartet es auf eine Eingabe oder ein Dialogfenster?)'
    return ergebnis['text'] or 'FEHLER: keine Rückmeldung'

def megacad_fenster():
    """Fenster-Handle des größten sichtbaren MegaCAD-Hauptfensters (Titel enthält 'MegaCAD'); minimierte Fenster zählen nicht."""
    import win32gui
    treffer = []
    def pruefe(h, _):
        titel = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and not win32gui.IsIconic(h) and 'megacad' in titel.lower() and 'cad-bruecke' not in titel.lower():   # eigenes Konsolenfenster ausnehmen
            l, t, r, b = win32gui.GetWindowRect(h)
            if r - l > 300 and b - t > 300: treffer.append(((r - l) * (b - t), h))
    win32gui.EnumWindows(pruefe, None)
    return max(treffer)[1] if treffer else None
def klick(spec):
    """'klick rechts' | 'klick links' [x y]: echter Mausklick in die Zeichenfläche von MegaCAD, um eine Elementauswahl zu bestätigen
    ('R: genug'). Der Mauszeiger wird an den Punkt gesetzt (Standard: 60 % Breite, 55 % Höhe des Fensters, die Zeichenfläche rechts der
    Seitenleisten), geklickt und zurückgestellt. Vorher wird geprüft, dass an der Stelle wirklich MegaCAD vorne liegt; sonst Fehlermeldung.
    Die Brücke holt kein Fenster nach vorne und sendet keine Tastatureingaben."""
    import win32gui, win32con, win32api
    teile = (spec or 'rechts').split(); taste = teile[0].lower() if teile else 'rechts'
    h = megacad_fenster()
    if not h: return 'FEHLER: kein sichtbares MegaCAD-Fenster gefunden (minimiert?)'
    try: dialoge_holen(); time.sleep(0.3)
    except Exception: pass
    # Die Brücke holt MegaCAD nicht selbst nach vorne (keine Tastatur-Emulation); der Nutzer lässt das MegaCAD-Fenster vorne liegen.
    if len(teile) > 3 and teile[1].lower() == 'abs':                         # 'klick links abs X Y': Bildschirmpixel (für Dialoge, die auf einem anderen Monitor aufgehen)
        x, y = int(float(teile[2])), int(float(teile[3]))
    else:
        fx = float(teile[1]) if len(teile) > 2 else 0.6; fy = float(teile[2]) if len(teile) > 2 else 0.55
        l, t, r, b = win32gui.GetWindowRect(h); x = l + int((r - l) * fx); y = t + int((b - t) * fy)
    try:
        unter = win32gui.WindowFromPoint((x, y)); wurzel = win32gui.GetAncestor(unter, 2)
        titel = win32gui.GetWindowText(wurzel); eigner = win32gui.GetWindow(wurzel, 4)                # GW_OWNER: Dialoge von MegaCAD gehören zum Hauptfenster
        import win32process
        gleicher_prozess = win32process.GetWindowThreadProcessId(wurzel)[1] == win32process.GetWindowThreadProcessId(h)[1]   # Dialoge von MegaCAD gehören zu seinem Prozess
        # erlaubt sind MegaCAD, seine Dialoge und FEMM: beide werden von der Brücke bedient
        erlaubt = ('megacad' in titel.lower() or 'femm' in titel.lower()
                   or titel.strip() in ('Öffnen', 'Speichern unter', 'Baugruppe', 'Z. als Referenz einfg.'))
        if wurzel != h and eigner != h and not gleicher_prozess and not erlaubt:
            return f'FEHLER: an der Klickstelle liegt ein anderes Fenster vorne („{titel[:50]}“) – MegaCAD bitte nach vorne holen'
    except Exception: pass
    alt = win32api.GetCursorPos(); win32api.SetCursorPos((x, y)); time.sleep(0.15)
    if taste.startswith('r'): down, up = win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP
    else: down, up = win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP
    win32api.mouse_event(down, 0, 0, 0, 0); time.sleep(0.08); win32api.mouse_event(up, 0, 0, 0, 0); time.sleep(0.2)
    if taste.startswith('d'):                                                  # 'klick doppel x y': Doppelklick links (Ordner/Datei im Dialog öffnen)
        time.sleep(0.05); win32api.mouse_event(down, 0, 0, 0, 0); time.sleep(0.06); win32api.mouse_event(up, 0, 0, 0, 0); time.sleep(0.2)
    try: win32api.SetCursorPos(alt)
    except Exception: pass
    return f'{taste}-Klick bei ({x}, {y}) in „{win32gui.GetWindowText(h)[:60]}“ ausgeführt'

# ---------------------------------------------------------------- Dateien (nur lesend) -------------------------------------------------------
def dateiliste(spec):
    spec = (spec or '').strip().strip('"')
    if spec.lower() == 'megacad':
        funde = []
        for basis in dict.fromkeys([os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), os.environ.get('ProgramW6432', ''), 'C:\\']):
            if not basis or not os.path.isdir(basis): continue
            for name in os.listdir(basis):
                if 'mega' in name.lower():
                    pfad = os.path.join(basis, name); funde.append(pfad)
                    for wurzel, unter, dateien in os.walk(pfad):
                        for f in dateien:
                            fl = f.lower()
                            if (fl.endswith('.exe') and 'mega' in fl) or fl in ('funcnam.ini', 'megafluent.ini', 'megamenu.ini'): funde.append('  ' + os.path.join(wurzel, f))
                        if wurzel.count(os.sep) - pfad.count(os.sep) >= 2: unter[:] = []
        return '\n'.join(funde) if funde else 'kein MegaCAD-Ordner unter den Programmordnern gefunden'
    if spec.lower().startswith('suche '):
        _, ordner, muster = spec.split(' ', 2); ordner = ordner.strip('"'); treffer = []
        for wurzel, unter, dateien in os.walk(ordner):
            if any(t in wurzel.lower() for t in ('\\windows', '\\$recycle', '\\appdata', '\\program files')): unter[:] = []; continue
            for f in dateien:
                if fnmatch.fnmatch(f.lower(), muster.lower()): treffer.append(os.path.join(wurzel, f))
            if len(treffer) >= 300: break
        return f'{len(treffer)} Treffer für {muster} unter {ordner}:\n' + '\n'.join(treffer[:300])
    ordner = spec or ORDNER
    if not os.path.isdir(ordner): return f'FEHLER: kein Ordner: {ordner}'
    zeilen = []
    for name in sorted(os.listdir(ordner))[:300]:
        pfad = os.path.join(ordner, name)
        try: st = os.stat(pfad); zeilen.append(f'{"<DIR>" if os.path.isdir(pfad) else st.st_size:>12}  {datetime.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M}  {name}')
        except Exception as e: zeilen.append(f'{"?":>12}  {name} ({e})')
    return f'{ordner} ({len(zeilen)} Einträge):\n' + '\n'.join(zeilen)
HOCHLADEN_MAX = 40            # Dateien je Musteraufruf
HOCHLADEN_BYTE = 60_000_000   # je Datei


def _eine_hochladen(pfad):
    daten = open(pfad, 'rb').read()
    if len(daten) > HOCHLADEN_BYTE: return f'{os.path.basename(pfad)}: zu groß ({len(daten)} Byte)'
    return f'{os.path.basename(pfad)}: {len(daten)} Byte, ' + senden(daten, os.path.basename(pfad))


def hochladen(spec):
    """'hochladen <Datei>' holt eine Datei vom PC in den Workspace.

    Enthält der Pfad * oder ?, werden alle passenden Dateien geholt, zum Beispiel
    'hochladen C:\\Leiterplatten\\Kurventracer\\*.kicad_*'. Ein ganzes Leiterplattenprojekt kommt so
    in einem Zug zurück, statt Datei für Datei. Unterordner werden nicht durchsucht; höchstens
    HOCHLADEN_MAX Dateien je Aufruf, damit ein unbedachtes Muster nicht den ganzen Zweig überträgt.
    """
    pfad = (spec or '').strip().strip('"'); pfad = pfad if os.path.isabs(pfad) else os.path.join(ORDNER, pfad)
    if '*' in pfad or '?' in pfad:
        treffer = sorted(f for f in glob.glob(pfad) if os.path.isfile(f))
        if not treffer: return f'kein Treffer für {pfad}'
        if len(treffer) > HOCHLADEN_MAX:
            return (f'FEHLER: {len(treffer)} Treffer für {pfad}, höchstens {HOCHLADEN_MAX} je Aufruf. '
                    'Muster enger fassen.')
        return f'{len(treffer)} Dateien:\n' + '\n'.join('  ' + _eine_hochladen(f) for f in treffer)
    if not os.path.isfile(pfad): return f'FEHLER: Datei fehlt: {pfad}'
    daten = open(pfad, 'rb').read()
    if len(daten) > HOCHLADEN_BYTE: return f'FEHLER: Datei zu groß ({len(daten)} Byte)'
    return f'{len(daten)} Byte: ' + senden(daten, os.path.basename(pfad))
def update(spec):
    """'update <Dateien>' holt Dateien aus dem Workspace in diesen Ordner.

    Mit '-> <Zielordner>' am Ende gehen sie stattdessen dorthin, zum Beispiel
    'update a.lua,b.fem -> C:\\PMSM'. Der Zielordner wird angelegt, wenn er fehlt. Gesichert wird eine
    vorhandene gleichnamige Datei wie bisher, damit nichts unbemerkt überschrieben wird.
    """
    spec = spec or ''
    ziel_ordner = ORDNER
    if '->' in spec:
        spec, _, ziel_ordner = spec.partition('->')
        ziel_ordner = ziel_ordner.strip().strip('"')
        if not os.path.isabs(ziel_ordner): return f'FEHLER: Zielordner muss absolut sein: {ziel_ordner}'
        os.makedirs(ziel_ordner, exist_ok=True)
    namen = [n.strip() for n in spec.split(',') if n.strip()]
    if not namen: return 'FEHLER: keine Dateinamen'
    stempel = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'); sich = os.path.join(SICHERUNG, stempel)
    bericht = []
    for n in namen:
        ziel = os.path.join(ziel_ordner, n)
        try: daten = datei_holen(n)
        except Exception as e: bericht.append(f'{n}: FEHLER beim Holen ({e})'); continue
        # Gesichert wird nur, was sich wirklich ändert, und höchstens ALT_BEHALTEN Fassungen je Datei.
        # Vorher lag nach jedem Update eine Kopie da, auch wenn sie mit der vorigen Byte für Byte
        # übereinstimmte: nach einem Tag Arbeit dreizehn gleiche Seiten zu je 2,2 MB.
        if os.path.isfile(ziel) and open(ziel, 'rb').read() != daten:
            os.makedirs(sich, exist_ok=True); shutil.copy2(ziel, os.path.join(sich, n))
            alt = sorted(d for d in glob.glob(os.path.join(SICHERUNG, '*', n)))
            for ueberzaehlig in alt[:-ALT_BEHALTEN]:
                try:
                    os.remove(ueberzaehlig)
                    d = os.path.dirname(ueberzaehlig)
                    if not os.listdir(d): os.rmdir(d)
                except OSError: pass
        if n.endswith('.py'):
            try: compile(daten.decode('utf-8'), n, 'exec')
            except SyntaxError as e: bericht.append(f'{n}: SYNTAXFEHLER Zeile {e.lineno}: {e.msg} – nicht übernommen'); continue
        open(ziel, 'wb').write(daten); bericht.append(f'{n}: {len(daten)} Byte übernommen')
    return f'Update ({stempel}) nach {ziel_ordner}: ' + '; '.join(bericht)

# Tiefer als in diesen Zweigen wird nichts angefasst. Der Sicherungsordner steht dabei, weil sich
# dort bei jedem Update eine Kopie der überschriebenen Datei ansammelt — nach einem Tag Arbeit
# dreizehn Fassungen derselben Seite. Gelöscht wird auch dort nur, was namentlich genannt ist.
ERLAUBT_LOESCHEN = (r'C:\PMSM', r'C:\git', r'C:\REM_CAD\Sicherung', r'C:\Bruecke\Sicherung')

ERLAUBT_VERSCHIEBEN = (r'C:\PMSM', r'C:\git', r'C:\REM_CAD', r'C:\Segway', r'C:\Sicherungskopien', r'C:\Kurs_Agent',
                       r'C:\Analoganzeige', r'C:\Tomatenwaechter', r'C:\Waermebild',
                       r'C:\Wasserstand', r'C:\Fernschreiber', r'C:\Transistoren', r'C:\Kennlinienschreiber',
                       r'C:\Gehalt', r'C:\Leiterplatten', r'C:\Bruecke',
                       r'C:\Antigravitation')

def verschieben(spec):
    """'verschieben <Ordner> :: name1,name2' legt die genannten Dateien in den Unterordner alt desselben Ordners.

    Auftrag 29.09.2026: „alles Alte auf C bereinigen, es gibt dafür den Ordner alt, da alles Alte rein.“ Nichts wird gelöscht:
    die Datei wandert nach <Ordner>\alt (wird angelegt); liegt dort schon eine gleichnamige, bekommt die neue einen Zeitstempel
    im Namen — nie überschreiben. Nur einfache Dateinamen, keine Platzhalter, keine Ordner, nur in erlaubten Zweigen.
    """
    ordner, _, namen = (spec or '').partition('::')
    ordner = ordner.strip().strip('"').rstrip('\\')
    namen = [n.strip() for n in namen.split(',') if n.strip()]
    if not ordner or not namen: return 'FEHLER: Aufruf ist "verschieben <Ordner> :: name1,name2"'
    voll = os.path.abspath(ordner)
    if not any(voll.lower() == e.lower() or voll.lower().startswith(e.lower() + '\\') for e in ERLAUBT_VERSCHIEBEN):
        return f'FEHLER: {voll} liegt nicht in einem erlaubten Zweig ({", ".join(ERLAUBT_VERSCHIEBEN)})'
    if not os.path.isdir(voll): return f'FEHLER: {voll} ist kein Ordner'
    if os.path.basename(voll).lower() == 'alt': return 'FEHLER: aus einem alt-Ordner wird nichts verschoben'
    alt = os.path.join(voll, 'alt'); os.makedirs(alt, exist_ok=True)
    bericht, n_ok = [], 0
    for n in namen:
        if any(c in n for c in '\\/:*?"<>|') or n in ('.', '..'):
            bericht.append(f'{n}: abgelehnt (kein einfacher Dateiname)'); continue
        quelle = os.path.join(voll, n)
        if os.path.dirname(os.path.abspath(quelle)) != voll:
            bericht.append(f'{n}: abgelehnt (führt aus dem Ordner heraus)'); continue
        if os.path.isdir(quelle): bericht.append(f'{n}: ist ein Ordner, nicht angerührt'); continue
        if not os.path.isfile(quelle): bericht.append(f'{n}: nicht vorhanden'); continue
        ziel = os.path.join(alt, n)
        if os.path.exists(ziel):
            stamm, erw = os.path.splitext(n); ziel = os.path.join(alt, f'{stamm}_{datetime.datetime.now():%Y-%m-%d_%H%M%S}{erw}')
        shutil.move(quelle, ziel); n_ok += 1; bericht.append(f'{n} -> alt\\{os.path.basename(ziel)}')
    return f'{n_ok} von {len(namen)} nach {alt} verschoben: ' + '; '.join(bericht)

def loeschen(spec):
    """'loeschen <Ordner> :: name1,name2' entfernt die genannten Dateien — nur diese, nur dort.

    Warum so eng: ein Löschbefehl auf einem fremden Rechner lässt sich nicht zurücknehmen. Deshalb
    keine Platzhalter, keine Unterordner, keine Pfadtrenner im Namen, und der Ordner muss in einem
    ausdrücklich erlaubten Zweig liegen. Was gar nicht da ist, wird gemeldet und nicht als Fehler
    behandelt; was ein Ordner ist, bleibt unberührt.
    """
    ordner, _, namen = (spec or '').partition('::')
    ordner = ordner.strip().strip('"').rstrip('\\')
    namen = [n.strip() for n in namen.split(',') if n.strip()]
    if not ordner or not namen: return 'FEHLER: Aufruf ist "loeschen <Ordner> :: name1,name2"'
    voll = os.path.abspath(ordner)
    if not any(voll.lower() == e.lower() or voll.lower().startswith(e.lower() + '\\') for e in ERLAUBT_LOESCHEN):
        return f'FEHLER: {voll} liegt nicht in einem erlaubten Zweig ({", ".join(ERLAUBT_LOESCHEN)})'
    if not os.path.isdir(voll): return f'FEHLER: {voll} ist kein Ordner'
    bericht, weg, byte = [], 0, 0
    for n in namen:
        if any(c in n for c in '\\/:*?"<>|') or n in ('.', '..'):
            bericht.append(f'{n}: abgelehnt (kein einfacher Dateiname)'); continue
        ziel = os.path.join(voll, n)
        if os.path.dirname(os.path.abspath(ziel)) != voll:
            bericht.append(f'{n}: abgelehnt (führt aus dem Ordner heraus)'); continue
        if os.path.isdir(ziel): bericht.append(f'{n}: ist ein Ordner, nicht angerührt'); continue
        if not os.path.isfile(ziel): bericht.append(f'{n}: war nicht da'); continue
        g = os.path.getsize(ziel)
        try: os.remove(ziel); weg += 1; byte += g; bericht.append(f'{n}: {g} Byte gelöscht')
        except Exception as e: bericht.append(f'{n}: FEHLER {e}')
    return f'Löschen in {voll}: {weg} Datei(en), {byte} Byte. ' + '; '.join(bericht)

def selbstupdate():
    quelle = datei_holen('bruecke.py', 60).decode('utf-8')
    if 'VERSION = ' not in quelle or 'def befehle_ausfuehren' not in quelle: return 'FEHLER: geholte Datei sieht nicht wie die Brücke aus'
    ns = {'__name__': 'nachgeladen', '__file__': __file__}; exec(compile(quelle, __file__, 'exec'), ns)
    open(__file__, 'w', encoding='utf-8').write(quelle)
    return f"Selbstaktualisierung: {ns['VERSION']} (ins Hauptprogramm eingetragen: {ns.get('_EINGETRAGEN', '?')} Namen)"
def bildschirm(spec=''):
    """Foto des MegaCAD-Fensters, wo immer es liegt (Hauptmonitor, zweiter oder virtueller Monitor); 'alles' = gesamter virtueller Bildschirm."""
    from PIL import ImageGrab
    h = None if (spec or '').strip().lower() == 'alles' else megacad_fenster()
    if h:
        import win32gui
        l, t, r, b_ = win32gui.GetWindowRect(h)
        im = ImageGrab.grab(bbox=(l, t, r, b_), all_screens=True).convert('RGB'); lage = f'MegaCAD-Fenster bei ({l},{t})'
    else:
        im = ImageGrab.grab(all_screens=True).convert('RGB'); lage = 'alle Monitore'
    b = io.BytesIO(); im.save(b, 'JPEG', quality=70)
    return f'Bildschirm {im.size[0]}x{im.size[1]} ({lage}): ' + senden(b.getvalue(), 'bildschirm.jpg')
def fenster(spec=''):
    """Sichtbare Top-Level-Fenster auflisten. Ohne Angabe nur die des MegaCAD-Prozesses (auch dessen Dialoge);
    'fenster alle' listet alle Fenster mit Titel, Größe und Lage – so lassen sich auch FEMM-Meldungen finden."""
    import win32gui, win32process
    alle = (spec or '').strip().lower().startswith('alle')
    pid = None
    if not alle:
        h = megacad_fenster()
        if not h: return 'FEHLER: kein sichtbares MegaCAD-Fenster (für alle Fenster: fenster alle)'
        pid = win32process.GetWindowThreadProcessId(h)[1]
    zeilen = []
    def pruefe(w, _):
        if not win32gui.IsWindowVisible(w): return
        if pid is not None and win32process.GetWindowThreadProcessId(w)[1] != pid: return
        l, t, r, b = win32gui.GetWindowRect(w)
        titel = win32gui.GetWindowText(w)
        if r - l > 20 and b - t > 20 and (titel or pid is not None):
            zeilen.append(f'„{titel[:60]}“ {r - l}x{b - t} bei ({l},{t}) Mitte ({(l + r) // 2},{(t + b) // 2})')
    win32gui.EnumWindows(pruefe, None)
    return '\n'.join(zeilen) or 'keine Fenster'

# Datenendungen, die geoeffnet werden duerfen. Ausfuehrbares ist bewusst nicht dabei: die Bruecke
# soll Dateien anzeigen, nicht Programme starten. KiCad, Gerber, Bilder, PDF, Text.
OEFFNEN_ENDUNGEN = ('.kicad_pro', '.kicad_sch', '.kicad_pcb', '.kicad_prl', '.kicad_dru',
                    '.gbr', '.gbrjob', '.drl', '.step', '.stp', '.pdf', '.svg', '.png', '.jpg',
                    '.jpeg', '.csv', '.txt', '.md', '.html', '.json', '.zip')


def oeffnen(spec):
    """'oeffnen <Pfad>': die Datei mit dem Programm starten, das Windows dafuer vorgesehen hat.

    Gedacht fuer den Blick auf ein Ergebnis: ein Leiterplattenlayout in KiCad, ein Gerber im
    Betrachter, ein PDF. Es gelten zwei Schranken. Die Datei muss in einem der Zweige aus
    ERLAUBT_VERSCHIEBEN liegen, und ihre Endung muss in OEFFNEN_ENDUNGEN stehen — damit sich ueber
    diesen Weg kein Programm starten laesst, sondern nur etwas ansehen.
    """
    pfad = (spec or '').strip().strip('"')
    if not pfad: return 'FEHLER: Aufruf oeffnen <Pfad>'
    if not os.path.isabs(pfad): pfad = os.path.join(ORDNER, pfad)
    voll = os.path.normpath(os.path.abspath(pfad))
    if not os.path.isfile(voll): return f'FEHLER: Datei fehlt: {voll}'
    # os.sep statt eines festen Backslash: auf Windows dasselbe, aber so laesst sich die Schranke
    # auch im Workspace pruefen, ohne Windows.
    if not any(voll.lower() == e.lower() or voll.lower().startswith(e.lower().rstrip(os.sep) + os.sep)
               for e in ERLAUBT_VERSCHIEBEN):
        return f'FEHLER: {voll} liegt nicht in einem erlaubten Zweig ({", ".join(ERLAUBT_VERSCHIEBEN)})'
    if not voll.lower().endswith(OEFFNEN_ENDUNGEN):
        return (f'FEHLER: {os.path.splitext(voll)[1]} wird nicht geoeffnet. '
                f'Erlaubt: {", ".join(OEFFNEN_ENDUNGEN)}')
    try:
        os.startfile(voll)
    except Exception as e:
        return f'FEHLER beim Oeffnen von {voll}: {e}'
    return f'{voll} geoeffnet ({os.path.getsize(voll)} Byte)'


def zeigen(spec):
    """'zeigen <Titelteil>': das erste sichtbare Fenster mit diesem Titelteil sichtbar machen und in die Bildschirmmitte legen.
    Es wird nur die Lage geändert und das Fenster nach oben gebracht, keine Tastatureingabe gesendet."""
    import win32gui, win32con
    worte = (spec or '').split()
    suche = ' '.join(w for w in worte if not w.lstrip('-').isdigit()).strip().lower()
    if not suche: return 'FEHLER: Aufruf zeigen <Titelteil>'
    treffer = []
    def pruefe(w, _):
        if win32gui.IsWindowVisible(w) and suche in win32gui.GetWindowText(w).lower():
            l, t, r, b = win32gui.GetWindowRect(w)
            if r - l > 20 and b - t > 20: treffer.append((w, win32gui.GetWindowText(w), r - l, b - t))
    win32gui.EnumWindows(pruefe, None)
    if not treffer: return f'kein sichtbares Fenster mit „{spec}“'
    w, titel, breite, hoehe = treffer[0]
    if win32gui.IsIconic(w): win32gui.ShowWindow(w, win32con.SW_RESTORE)
    teile = (spec or '').split()
    x, y = (int(teile[-2]), int(teile[-1])) if len(teile) > 2 and teile[-1].lstrip('-').isdigit() and teile[-2].lstrip('-').isdigit() else (60, 60)
    win32gui.SetWindowPos(w, win32con.HWND_TOPMOST, x, y, 0, 0, win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
    return f'„{titel[:60]}“ {breite}x{hoehe} nach ({x},{y}) gelegt und ganz nach oben gestellt'
def dialoge_holen():
    """MegaCAD-Dialoge, die auf einem anderen Monitor als das Hauptfenster aufgegangen sind, in die Mitte des MegaCAD-Fensters verschieben
    (reine Lageänderung ohne Aktivierung: SetWindowPos mit NOACTIVATE/NOZORDER/NOSIZE)."""
    import win32gui, win32process, win32con
    h = megacad_fenster()
    if not h: return 'FEHLER: kein sichtbares MegaCAD-Fenster'
    pid = win32process.GetWindowThreadProcessId(h)[1]; L, T, R, B = win32gui.GetWindowRect(h); bewegt = []
    def pruefe(w, _):
        if w == h or not win32gui.IsWindowVisible(w) or win32process.GetWindowThreadProcessId(w)[1] != pid: return
        l, t, r, b = win32gui.GetWindowRect(w)
        if r - l < 20 or b - t < 20: return
        if (l + r) // 2 < L or (l + r) // 2 > R or (t + b) // 2 < T or (t + b) // 2 > B:            # Mitte außerhalb des MegaCAD-Fensters
            nx, ny = (L + R) // 2 - (r - l) // 2, (T + B) // 2 - (b - t) // 2
            win32gui.SetWindowPos(w, 0, nx, ny, 0, 0, win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE)
            bewegt.append(f'„{win32gui.GetWindowText(w)[:50].strip()}“ von ({l},{t}) nach ({nx},{ny})')
    win32gui.EnumWindows(pruefe, None)
    return 'verschoben: ' + '; '.join(bewegt) if bewegt else 'kein Dialog außerhalb des MegaCAD-Fensters'
def anschluesse(spec):
    """'anschluesse': zaehlt die seriellen Anschluesse auf, mit Geraetenamen.

    Liest nur. Ohne diese Auskunft bleibt beim Flashen die Frage offen, ob der Anschluss
    falsch war oder das Brett stumm -- und man probiert im Dunkeln.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return 'FEHLER: pyserial fehlt. Einmalig: python -m pip install pyserial'
    gefunden = sorted(list_ports.comports(), key=lambda p: p.device)
    if not gefunden:
        return ('Kein serieller Anschluss sichtbar. Steckt ein Kabel? Ist es ein Datenkabel '
                'und kein reines Ladekabel? Fehlt der Treiber (CH340 oder CP2102)?')
    zeilen = []
    for a in gefunden:
        kenn = f'{a.vid:04X}:{a.pid:04X}' if a.vid is not None else '-'
        marke = ''
        bez = (a.description or '') + ' ' + (a.manufacturer or '')
        for muster, name in (('CH340', 'CH340'), ('CP210', 'CP2102'), ('FTDI', 'FTDI'),
                             ('CH910', 'CH9102'), ('USB Serial', 'USB-seriell')):
            if muster.lower() in bez.lower():
                marke = f'  <- {name}, typisch fuer ESP32-Bretter'
                break
        zeilen.append(f'  {a.device:8s} {kenn:9s} {(a.description or "")[:48]}{marke}')
    return f'{len(gefunden)} Anschluss/Anschluesse:\n' + '\n'.join(zeilen)


def firewall(spec):
    """'firewall [Muster]': zeigt bestehende Firewall-Regeln. Liest NUR.

    Es wird ausschliesslich 'show' aufgerufen -- nie 'add', nie 'set', nie 'delete'. Eine
    Regel anzulegen ist ein Eingriff in den Rechner und braucht Adminrechte; das entscheidet
    ein Mensch, nicht die Bruecke.

    Die Frage, die das beantwortet: Gibt es hier schon eine Freigabe fuer Python? Auf dem
    frueheren Rechner lief das Update ueber WLAN -- dort hatte die Arduino-Umgebung beim
    ersten Mal danach gefragt und sie bekommen. Auf einem neuen Rechner fehlt sie.
    """
    muster = (spec or '').strip().lower()
    r = subprocess.run(['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all',
                        'dir=in', 'status=enabled', 'verbose'],
                       capture_output=True, text=True, timeout=180,
                       encoding='cp850', errors='replace')
    if r.returncode != 0:
        return 'FEHLER: netsh laesst sich nicht lesen\n' + (r.stderr or '')[-200:]
    bloecke, jetzt = [], []
    for z in (r.stdout or '').splitlines():
        if z.strip().startswith('---'):
            if jetzt: bloecke.append(jetzt)
            jetzt = []
        else:
            jetzt.append(z.rstrip())
    if jetzt: bloecke.append(jetzt)

    treffer = []
    for b in bloecke:
        text = '\n'.join(b)
        if muster and muster not in text.lower():
            continue
        name = next((z.split(':', 1)[1].strip() for z in b if z.lower().startswith('regelname')), '')
        prog = next((z.split(':', 1)[1].strip() for z in b if z.lower().startswith('programm')), '')
        port = next((z.split(':', 1)[1].strip() for z in b if 'lokaler port' in z.lower()), '')
        akt  = next((z.split(':', 1)[1].strip() for z in b if z.lower().startswith('aktion')), '')
        if name:
            #  Der Programmpfad ist das Entscheidende: "python.exe" sagt nichts, solange
            #  nicht dasteht, WELCHES. Darum zwei Zeilen je Regel statt einer gekuerzten.
            treffer.append(f'  {name[:50]}\n      {akt or "?"}   Port {port or "beliebig"}'
                           f'\n      {prog or "(kein Programm genannt)"}')
    if not treffer:
        return (f'Keine eingehende Regel{" zu " + muster if muster else ""} gefunden.\n'
                f'  {len(bloecke)} Regeln insgesamt durchgesehen.')
    return (f'{len(treffer)} eingehende Regel(n){" zu " + muster if muster else ""}:\n'
            + '\n'.join(treffer[:25]))


def hole(spec):
    """'hole <Adresse> [Pfad]': ruft eine Auskunft im eigenen Netz ab. Liest NUR.

    Eng gefasst: nur HTTP (kein HTTPS, kein Umweg), nur Adressen aus den privaten Bereichen
    (192.168.x, 10.x, 172.16-31.x) und der Rechner selbst (127.x), nur GET, hoechstens 64 kB, hoechstens 20 Sekunden. Es
    wird nichts gesendet ausser der Anfrage selbst.

    Seit 03.10.2026 auch Namen der Form "<name>.local" (mDNS). Grund: Die Zahl verteilt der
    Router und sie kann sich aendern; der Name bleibt. Das ist keine Ausweitung ins Internet
    -- ein .local-Name wird ausschliesslich auf dem eigenen Netzstrang aufgeloest, es gibt
    dafuer keine Namensserver draussen. Erlaubt sind nur Kleinbuchstaben, Ziffern und
    Bindestriche vor dem Punkt, hoechstens 32 Zeichen.

    Damit laesst sich lesen, was ein Geraet im Haus ueber sich sagt -- der Ölpreis-Anzeiger
    etwa unter /status --, ohne dass jemand danebenstehen muss.
    """
    teile = (spec or '').split()
    if not teile:
        return 'FEHLER: Aufruf hole <Adresse> [Pfad]'
    adresse = teile[0]
    pfad = teile[1] if len(teile) > 1 else '/status'
    name_im_netz = re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}\.local(:\d{2,5})?', adresse)
    if not name_im_netz:
        if not re.fullmatch(r'(\d{1,3}\.){3}\d{1,3}(:\d{2,5})?', adresse):
            return (f'FEHLER: "{adresse}" ist weder eine Adresse der Form 192.168.1.2[:80] '
                    'noch ein Name der Form geraet.local')
        nur_ip = adresse.split(':')[0]
        z = [int(x) for x in nur_ip.split('.')]
        if any(x > 255 for x in z):
            return f'FEHLER: "{nur_ip}" ist keine gueltige Adresse'
        # 127.x ist der Arbeitsplatzrechner selbst: So laesst sich lesen, was ein Programm hier
        # ueber sich sagt -- der Kurs-Agent etwa unter 127.0.0.1:8777/zustand --, ohne dass
        # jemand den Browser-Reiter nach vorn holen muss (04.10.2026). Weiterhin nur lesen.
        privat = (z[0] == 10) or (z[0] == 192 and z[1] == 168) or (z[0] == 172 and 16 <= z[1] <= 31) or (z[0] == 127)
        if not privat:
            return (f'FEHLER: {nur_ip} liegt nicht im eigenen Netz. Dieser Befehl ruft nur '
                    'Geraete im Haus ab, nichts im Internet.')
    # Auch Abfragen zulassen (?r=255&g=0) -- ohne sie liesse sich nichts einstellen.
    # Die Zeichen bleiben eng begrenzt: keine Leerzeichen, keine Anfuehrungszeichen.
    if not re.fullmatch(r'/[A-Za-z0-9._/?=&%-]{0,120}', pfad):
        return f'FEHLER: "{pfad}" ist kein zulaessiger Pfad'
    url = f'http://{adresse}{pfad}'
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            roh = r.read(65536)
    except Exception as e:
        return (f'FEHLER: {url} antwortet nicht: {e}\n'
                '  Laeuft das Geraet? Stimmt die Adresse? Ist es im selben Netz?')
    return f'{url}:\n' + roh.decode('utf-8', 'replace')


def sende(spec):
    """'sende <Adresse> <Pfad> <JSON>': schickt eine kurze JSON-Nachricht an ein Programm auf dem
    Arbeitsplatzrechner SELBST (nur 127.x) -- so laesst sich der laufende Kurs-Agent bedienen
    (127.0.0.1:8777 /start {"auftrag": "..."}), ohne dass jemand im Browser klickt.

    Eng gefasst wie hole: nur HTTP, nur der eigene Rechner, Pfad aus denselben Zeichen, Nachricht
    hoechstens 4000 Zeichen und gueltiges JSON, 20 Sekunden. Anlass 04.10.2026: „kannst du nicht
    den Kursagenten gleich selber bedienen?" Nach Grundsatz 34 nur auf Wort des Auftraggebers."""
    import json as _json
    teile = (spec or '').split(None, 2)
    if len(teile) < 3:
        return 'FEHLER: Aufruf sende <Adresse> <Pfad> <JSON>'
    adresse, pfad, nachricht = teile
    if not re.fullmatch(r'127\.(\d{1,3}\.){2}\d{1,3}(:\d{2,5})?', adresse):
        return f'FEHLER: sende geht nur an den Rechner selbst (127.x), nicht an {adresse}'
    if not re.fullmatch(r'/[A-Za-z0-9._/?=&%-]{0,120}', pfad):
        return f'FEHLER: "{pfad}" ist kein zulaessiger Pfad'
    if len(nachricht) > 4000:
        return 'FEHLER: Nachricht laenger als 4000 Zeichen'
    try:
        daten = _json.dumps(_json.loads(nachricht), ensure_ascii=False).encode('utf-8')
    except ValueError as e:
        return f'FEHLER: Nachricht ist kein JSON: {e}'
    url = f'http://{adresse}{pfad}'
    try:
        req = urllib.request.Request(url, data=daten, method='POST', headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=20) as r:
            roh = r.read(65536)
    except urllib.error.HTTPError as e:
        return f'{url} antwortet {e.code}: ' + e.read(4096).decode('utf-8', 'replace')
    except Exception as e:
        return f'FEHLER: {url} antwortet nicht: {e}'
    return f'{url}:\n' + roh.decode('utf-8', 'replace')


def netz(spec):
    """'netz [Muster]': zeigt, welche Geraete im Netz bekannt sind (arp -a). Liest nur.

    Ohne diese Auskunft bleibt beim Update ueber WLAN die Frage offen, ob die Adresse
    falsch war oder das Geraet stumm -- und man probiert im Dunkeln. arp liest die Tabelle,
    die Windows ohnehin fuehrt; es wird nichts gesendet und nichts geaendert.
    """
    muster = (spec or '').strip()
    r = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return 'FEHLER: arp laesst sich nicht aufrufen\n' + (r.stderr or '')[-200:]
    zeilen = [z.rstrip() for z in (r.stdout or '').splitlines() if z.strip()]
    if muster:
        zeilen = [z for z in zeilen if muster.lower() in z.lower()]
    if not zeilen:
        return f'nichts gefunden{" fuer " + muster if muster else ""}'
    return f'{len(zeilen)} Zeile(n):\n' + '\n'.join('  ' + z for z in zeilen[:60])


def ota(spec):
    """'ota <Datei.bin> <IP> [Port]': Firmware ueber WLAN auf ein ESP32-Brett schreiben.

    Derselbe enge Rahmen wie bei flashen: die Datei muss in DIESEM Ordner liegen, der Name
    nur Buchstaben, Ziffern, Punkt, Strich, Unterstrich und auf .bin endend, die Adresse
    eine gueltige IPv4. Gestartet wird genau ein Programm -- espota.py, das Werkzeug des
    ESP32-Kerns, das ebenfalls hier liegen muss.

    Warum ueber WLAN und nicht ueber das Kabel: Kabel-Uploads brechen ab ("Unable to verify
    flash chip connection"), und ein Geraet an der Wand schraubt niemand ab. Hausregel seit
    dem 07.08.2026.
    """
    teile = (spec or '').split()
    if len(teile) < 2:
        return 'FEHLER: Aufruf ota <Datei.bin> <IP> [Port]'
    name, adresse = teile[0], teile[1]
    if not re.fullmatch(r'[A-Za-z0-9._-]+\.bin', name):
        return f'FEHLER: "{name}" ist kein zulaessiger Dateiname (nur <name>.bin, ohne Pfad)'
    if not re.fullmatch(r'(\d{1,3}\.){3}\d{1,3}', adresse) or any(
            int(x) > 255 for x in adresse.split('.')):
        return f'FEHLER: "{adresse}" ist keine gueltige Adresse'
    port = teile[2] if len(teile) > 2 else '3232'
    if not re.fullmatch(r'\d{2,5}', port):
        return f'FEHLER: "{port}" ist kein gueltiger Port'

    datei = os.path.join(ORDNER, name)
    werkzeug = os.path.join(ORDNER, 'espota.py')
    if not os.path.isfile(datei):
        return f'FEHLER: {name} liegt nicht in {ORDNER}. Erst mit update herschieben.'
    if not os.path.isfile(werkzeug):
        return ('FEHLER: espota.py liegt nicht in diesem Ordner. Es gehoert zum ESP32-Kern '
                '(packages/esp32/hardware/esp32/<Fassung>/tools/espota.py) und wird einmalig '
                'mit update hergeschoben.')

    groesse = os.path.getsize(datei)
    md5 = hashlib.md5(open(datei, 'rb').read()).hexdigest()
    #  Mitlesen, waehrend die Einladung laeuft. Nur so laesst sich unterscheiden, WO es
    #  hakt: Meldet das Geraet "[OTA] Update beginnt", kam die Einladung an und der
    #  Ruckweg scheitert (meist die Firewall des Rechners). Kommt gar nichts, erreicht die
    #  Einladung das Geraet nicht. Ohne diese Unterscheidung sucht man an der falschen Stelle.
    mitschrift = []
    def lauschen():
        try:
            import serial
        except ImportError:
            return
        for p_ in ('COM3', 'COM4', 'COM5'):
            try:
                with serial.Serial(p_, 115200, timeout=1) as s:
                    ende = time.time() + 45
                    while time.time() < ende and len(mitschrift) < 60:
                        z = s.readline()
                        if z:
                            mitschrift.append(z.decode('utf-8', 'replace').rstrip())
                return
            except Exception:
                continue
    horcher = threading.Thread(target=lauschen, daemon=True)
    horcher.start()
    time.sleep(1.0)

    #  Mit welchem Python? Nicht mit dem, unter dem die Bruecke laeuft -- das ist hier
    #  Thonnys, und genau das sperrt die Firewall fuer eingehende Verbindungen. espota
    #  braucht aber eine: Es laedt das Geraet ein, sich ZURUECK zu verbinden.
    #
    #  Darum das eigene Python aus python\ -- dasselbe eingebettete, das auch der
    #  Kurs-Agent mitbringt. Beim ersten Lauf fragt Windows danach; ein "Zulassen" genuegt,
    #  und es braucht keine Adminrechte. So lief es frueher auch, mit einem eigenen Python
    #  statt mit Thonny.
    eigenes = os.path.join(ORDNER, 'python', 'python.exe')
    womit = eigenes if os.path.isfile(eigenes) else sys.executable
    #  Dem Geraet ausdruecklich sagen, WOHIN es zurueckrufen soll. espota bindet sonst auf
    #  0.0.0.0 und ueberlaesst die Rueckadresse dem Zufall der Route -- hat der Rechner
    #  mehrere Schnittstellen (Kabel, WLAN, VPN), nennt es womoeglich die falsche, und das
    #  Geraet ruft ins Leere. Die eigene Adresse im selben Netz wie das Geraet wird dafuer
    #  ermittelt: eine Probeverbindung dorthin sagt, ueber welche Schnittstelle es ginge.
    eigen = ''
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect((adresse, 3232))
        eigen = probe.getsockname()[0]
        probe.close()
    except Exception:
        eigen = ''
    befehl = [womit, werkzeug, '-i', adresse, '-p', port, '-f', datei, '-r']
    if eigen:
        befehl += ['-I', eigen]
    r = subprocess.run(befehl, capture_output=True, text=True, timeout=600)
    horcher.join(timeout=3)
    aus = ((r.stdout or '') + (r.stderr or '')).strip()
    ota_zeilen = [z for z in mitschrift if 'OTA' in z or 'Update' in z]
    if ota_zeilen:
        aus += '\n  Das Geraet sagte dabei: ' + ' | '.join(ota_zeilen[:4])
    elif mitschrift:
        aus += f'\n  Das Geraet lief ({len(mitschrift)} Zeilen), meldete aber nichts zu OTA: ' \
               'die Einladung kam nicht an.'
    else:
        aus += '\n  Vom Geraet kam waehrenddessen keine Zeile (Anschluss belegt oder stumm).'
    if r.returncode == 0:
        return (f'OTA OK: {name} ({groesse} Byte, md5 {md5[:8]}) ueber WLAN an {adresse}:{port}.\n'
                f'  gestartet mit {womit}\n' + aus[-400:])
    return (f'FEHLER: {name} liess sich nicht ueber WLAN schreiben ({adresse}:{port}).\n'
            f'  gestartet mit {womit}, Rueckadresse {eigen or "(nicht ermittelt)"}\n' + aus[-500:]
            + '\n  Antwortet das Geraet? Steht es im selben Netz? Laeuft eine Fassung MIT '
              'ArduinoOTA darauf? Ein Port 3232 wird erst nach der WLAN-Verbindung geoeffnet.')


def flashen(spec):
    """'flashen <Datei.bin> [COM3] [0x10000]': eine Firmware auf ein ESP32-Brett schreiben.

    Warum diese Ausnahme von "keine Programme starten" eng gefasst ist
    -----------------------------------------------------------------
    Die Bruecke startet grundsaetzlich keine Programme; sie reicht Dateien und liest.
    Hier wird genau ein Programm gestartet -- esptool -- und auch das nur so:

      * Die Datei muss in DIESEM Ordner liegen (per update hergeschoben). Kein Pfad,
        keine Platzhalter, kein Verzeichniswechsel.
      * Der Name muss auf .bin enden und darf nur Buchstaben, Ziffern, Punkt, Strich
        und Unterstrich enthalten.
      * Der Anschluss muss der Form COM<Zahl> entsprechen.
      * Die Adresse ist entweder 0x0 oder 0x10000 -- sonst nichts.
      * Die Befehlszeile wird hier gebaut, nicht uebernommen: nichts vom Aufrufer
        landet ungeprueft darin.

    Damit kann dieser Befehl ein Brett neu beschreiben und sonst nichts. Ein Brett neu zu
    beschreiben ist die eine bleibende Veraenderung, die gewollt ist; sie trifft das
    Steckbrett, nicht den Rechner.
    """
    teile = (spec or '').split()
    if not teile:
        return 'FEHLER: Aufruf flashen <Datei.bin> [COM3] [0x10000]'
    name = teile[0]
    if not re.fullmatch(r'[A-Za-z0-9._-]+\.bin', name):
        return f'FEHLER: "{name}" ist kein zulaessiger Dateiname (nur <name>.bin, ohne Pfad)'
    datei = os.path.join(ORDNER, name)
    if not os.path.isfile(datei):
        return f'FEHLER: {name} liegt nicht in {ORDNER}. Erst mit update herschieben.'
    port = teile[1] if len(teile) > 1 else 'COM3'
    if not re.fullmatch(r'COM\d{1,3}', port, re.I):
        return f'FEHLER: "{port}" ist kein Anschluss der Form COM3'
    adresse = teile[2] if len(teile) > 2 else ('0x0' if 'merged' in name.lower() else '0x10000')
    if adresse not in ('0x0', '0x10000'):
        return f'FEHLER: Adresse {adresse} nicht erlaubt (nur 0x0 oder 0x10000)'

    groesse = os.path.getsize(datei)
    md5 = hashlib.md5(open(datei, 'rb').read()).hexdigest()
    werkzeug = [sys.executable, '-m', 'esptool']
    probe = subprocess.run(werkzeug + ['version'], capture_output=True, text=True, timeout=60)
    if probe.returncode != 0:
        return ('FEHLER: esptool laeuft hier nicht. Einmalig: python -m pip install esptool\n'
                + (probe.stderr or probe.stdout)[-300:])

    meldungen = []
    for baud in ('921600', '460800', '115200'):
        befehl = werkzeug + ['--chip', 'esp32', '--port', port, '--baud', baud,
                             '--before', 'default_reset', '--after', 'hard_reset',
                             'write_flash', '-z', adresse, datei]
        r = subprocess.run(befehl, capture_output=True, text=True, timeout=600)
        aus = (r.stdout or '') + (r.stderr or '')
        if r.returncode == 0:
            return (f'USB-Flash OK: {name} ({groesse} Byte, md5 {md5[:8]}) nach {adresse} '
                    f'auf {port} mit {baud} Baud.\n' + aus[-500:])
        meldungen.append(f'{baud}: ' + aus.strip().splitlines()[-1][:120] if aus.strip() else f'{baud}: ohne Ausgabe')
    return (f'FEHLER: {name} liess sich auf {port} nicht schreiben.\n  ' + '\n  '.join(meldungen)
            + '\n  Haengt das Brett an diesem Anschluss? Haelt ein anderes Programm ihn fest '
              '(Arduino-Monitor, Thonny)? Bei manchen Brettern beim Start BOOT druecken.')


def seriell(spec):
    """'seriell [COM3] [Sekunden]': liest mit, was das Brett sagt, und gibt es zurueck.

    Liest nur. Es wird nichts gesendet und nichts geschrieben -- das Brett merkt davon
    nichts ausser dem Oeffnen des Anschlusses.
    """
    teile = (spec or '').split()
    port = teile[0] if teile else 'COM3'
    if not re.fullmatch(r'COM\d{1,3}', port, re.I):
        return f'FEHLER: "{port}" ist kein Anschluss der Form COM3'
    dauer = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else 20
    dauer = max(1, min(dauer, 120))
    try:
        import serial
    except ImportError:
        return 'FEHLER: pyserial fehlt. Einmalig: python -m pip install pyserial'
    zeilen = []
    try:
        with serial.Serial(port, 115200, timeout=1) as s:
            ende = time.time() + dauer
            while time.time() < ende and len(zeilen) < 400:
                z = s.readline()
                if z:
                    zeilen.append(z.decode('utf-8', 'replace').rstrip())
    except Exception as e:
        return f'FEHLER: {port} laesst sich nicht lesen: {e}'
    if not zeilen:
        return f'{port}: in {dauer} s kam keine Zeile. Laeuft das Programm? Richtiger Anschluss?'
    return f'{port}, {dauer} s, {len(zeilen)} Zeilen:\n' + '\n'.join(zeilen[-60:])


# ---------------------------------------------------------------- MicroPython-Dateien -------------------------------------------------------
def _mpy_lies(verbindung, ende, zeit):
    """Von der seriellen Leitung lesen, bis das Endezeichen da ist oder die Zeit um ist."""
    t0 = time.time(); puffer = b''
    while time.time() - t0 < zeit:
        teil = verbindung.read(512)
        if teil:
            puffer += teil
            if ende in puffer:
                break
        else:
            time.sleep(0.01)
    return puffer


def _mpy_repl(port, code, zeit=30):
    """Ein Stueck MicroPython auf dem BRETT ausfuehren und zurueckgeben, was es ausgibt.

    Der Weg ist die Raw-REPL, die jede MicroPython-Firmware mitbringt: Strg-A schaltet um,
    Strg-D fuehrt aus, Strg-B schaltet zurueck. Auf dem RECHNER wird dabei nichts gestartet --
    es gehen Bytes ueber eine serielle Leitung, sonst nichts. Darum braucht dieser Weg weder
    mpremote noch sonst eine Installation; pyserial genuegt, das fuer 'seriell' ohnehin da ist.

    Rueckgabe: (Ausgabe, Fehlertext). Genau einer von beiden ist gesetzt.
    """
    try:
        import serial
    except ImportError:
        return None, 'pyserial fehlt. Einmalig: python -m pip install pyserial'
    try:
        verbindung = serial.Serial(port, 115200, timeout=1)
    except Exception as e:
        return None, (f'{port} laesst sich nicht oeffnen: {e}. '
                      'Haelt ein anderes Programm ihn fest (Thonny, Arduino-Monitor)?')
    try:
        verbindung.write(b'\r\x03\x03')                 # zweimal Strg-C: ein laufendes Programm anhalten
        time.sleep(0.3); verbindung.reset_input_buffer()
        verbindung.write(b'\x01')                       # Strg-A: Raw-REPL
        begruessung = _mpy_lies(verbindung, b'>', 5)
        if b'raw REPL' not in begruessung:
            return None, ('Das Brett meldet keine Raw-REPL. Laeuft MicroPython darauf? Antwort war: '
                          + repr(begruessung[-120:]))
        verbindung.write(code.encode('utf-8') + b'\x04')   # Strg-D: ausfuehren
        roh = _mpy_lies(verbindung, b'\x04>', zeit)
        verbindung.write(b'\x02')                       # Strg-B: zurueck in die gewohnte REPL
        if b'OK' not in roh:
            return None, 'Das Brett hat den Auftrag nicht angenommen: ' + repr(roh[-160:])
        teile = roh.split(b'OK', 1)[1].split(b'\x04')
        aus = teile[0].decode('utf-8', 'replace').strip()
        fehler = teile[1].decode('utf-8', 'replace').strip() if len(teile) > 1 else ''
        if fehler:
            return None, 'Das Brett meldet einen Fehler:\n' + fehler[-400:]
        return aus, None
    finally:
        try: verbindung.close()
        except Exception: pass


# Dieses Stueck laeuft AUF DEM BRETT und bildet die Pruefsumme dort. Das ist der Kern der Sache:
# Wer die Summe beim Sender bildet und mitteilt, hat nichts geprueft, sondern sich selbst bestaetigt.
_MPY_SUMME = """
import uhashlib, ubinascii
h = uhashlib.sha256()
f = open({ziel!r}, 'rb')
n = 0
while True:
    b = f.read(256)
    if not b: break
    n += len(b); h.update(b)
f.close()
print(ubinascii.hexlify(h.digest()).decode(), n)
"""


def mpy(spec):
    """'mpy senden|pruefsumme|liste|reset ...': eine einzelne Python-Datei auf ein MicroPython-Brett.

    Warum es diesen Befehl gibt
    ---------------------------
    'flashen' schreibt eine Firmware (.bin). Fuer den Kursbetrieb wird das Gegenteil gebraucht:
    die Firmware bleibt liegen, und es wandert eine einzelne Python-Datei auf das Brett -- das
    Programm, das ein Sprachmodell gerade geschrieben hat. Ohne diesen Schritt endet jede Kette
    am Rechner, und ob auf dem Brett etwas laeuft, weiss nur, wer danebensteht.

    Der enge Rahmen, wie bei 'flashen'
    ----------------------------------
      * Die Datei muss in DIESEM Ordner liegen (per update hergeschoben). Kein Pfad.
      * Der Name endet auf .py, nur Buchstaben, Ziffern, Punkt, Strich, Unterstrich.
      * Der Zielname auf dem Brett folgt derselben Regel.
      * Der Anschluss hat die Form COM<Zahl>.
      * Der Inhalt geht als Base64 hinueber und wird erst auf dem Brett zurueckgewandelt. Base64
        kennt keine Anfuehrungszeichen; aus dem Dateiinhalt kann also nichts in den Steuercode
        geraten. Geprueft wird das trotzdem, Zeichen fuer Zeichen.
      * Auf dem Rechner wird kein Programm gestartet.

    Unterbefehle
    ------------
      mpy senden <datei.py> [COM3] [zielname]   schreiben und die Summe VOM BRETT zurueckholen
      mpy pruefsumme <zielname> [COM3]          SHA-256 und Laenge, auf dem Brett gebildet
      mpy liste [COM3]                          was auf dem Brett liegt
      mpy reset [COM3]                          Brett neu starten (danach laeuft main.py)
    """
    teile = (spec or '').split()
    if not teile:
        return ('FEHLER: Aufruf mpy senden <datei.py> [COM3] [zielname] | mpy pruefsumme <zielname> [COM3] | '
                'mpy liste [COM3] | mpy reset [COM3]')
    was = teile[0].lower()
    muster = r'[A-Za-z0-9._-]+\.py'

    def anschluss(i):
        p = teile[i] if len(teile) > i else 'COM3'
        return p if re.fullmatch(r'COM\d{1,3}', p, re.I) else None

    if was == 'liste':
        port = anschluss(1)
        if not port: return f'FEHLER: "{teile[1]}" ist kein Anschluss der Form COM3'
        aus, fehler = _mpy_repl(port, 'import os\nfor n in os.listdir():\n    print(n, os.stat(n)[6])\n')
        if fehler: return 'FEHLER: ' + fehler
        return f'Auf dem Brett an {port}:\n  ' + (aus.replace('\n', '\n  ') if aus else '(leer)')

    if was == 'reset':
        port = anschluss(1)
        if not port: return f'FEHLER: "{teile[1]}" ist kein Anschluss der Form COM3'
        # Beim Neustart bricht die Verbindung ab. Das ist kein Fehler, sondern der Zweck.
        _mpy_repl(port, 'import machine\nmachine.reset()\n', zeit=6)
        return f'Brett an {port} neu gestartet. MicroPython fuehrt jetzt main.py aus.'

    if was == 'pruefsumme':
        if len(teile) < 2 or not re.fullmatch(muster, teile[1]):
            return 'FEHLER: Aufruf mpy pruefsumme <zielname.py> [COM3]'
        port = anschluss(2)
        if not port: return f'FEHLER: "{teile[2]}" ist kein Anschluss der Form COM3'
        aus, fehler = _mpy_repl(port, _MPY_SUMME.format(ziel=teile[1]))
        if fehler: return 'FEHLER: ' + fehler
        stueck = aus.split()
        if len(stueck) != 2: return f'FEHLER: unerwartete Antwort des Bretts: {aus[:160]}'
        return f'{teile[1]} auf dem Brett an {port}: {stueck[1]} Byte, sha256 {stueck[0]}'

    if was != 'senden':
        return f'FEHLER: unbekannter Unterbefehl "{was}" (senden, pruefsumme, liste, reset)'

    if len(teile) < 2 or not re.fullmatch(muster, teile[1]):
        return 'FEHLER: Aufruf mpy senden <datei.py> [COM3] [zielname]'
    name = teile[1]
    datei = os.path.join(ORDNER, name)
    if not os.path.isfile(datei):
        return f'FEHLER: {name} liegt nicht in {ORDNER}. Erst mit update herschieben.'
    port = anschluss(2)
    if not port: return f'FEHLER: "{teile[2]}" ist kein Anschluss der Form COM3'
    ziel = teile[3] if len(teile) > 3 else 'main.py'
    if not re.fullmatch(muster, ziel):
        return f'FEHLER: "{ziel}" ist kein zulaessiger Name auf dem Brett'

    with open(datei, 'rb') as f:
        inhalt = f.read()
    hier = hashlib.sha256(inhalt).hexdigest()
    roh = base64.b64encode(inhalt).decode('ascii')
    if not re.fullmatch(r'[A-Za-z0-9+/=]*', roh):
        return 'FEHLER: die Kodierung enthaelt unerwartete Zeichen -- abgebrochen'

    # In Stuecken schreiben: das Brett uebersetzt den gesendeten Block erst beim Ausfuehren,
    # und sein Speicher ist klein. 1 kB Base64 je Durchgang laeuft auf jedem ESP32.
    stuecke = [roh[i:i + 1024] for i in range(0, len(roh), 1024)] or ['']
    for k, st in enumerate(stuecke):
        code = ('import ubinascii\nf = open(%r, %r)\nf.write(ubinascii.a2b_base64(%r))\nf.close()\n'
                % (ziel, 'wb' if k == 0 else 'ab', st))
        aus, fehler = _mpy_repl(port, code)
        if fehler:
            return f'FEHLER beim Schreiben von {ziel} (Block {k + 1} von {len(stuecke)}): {fehler}'

    aus, fehler = _mpy_repl(port, _MPY_SUMME.format(ziel=ziel))
    if fehler:
        return f'FEHLER: {ziel} wurde geschrieben, aber die Pruefsumme kam nicht zurueck: {fehler}'
    stueck = aus.split()
    if len(stueck) != 2:
        return f'FEHLER: unerwartete Antwort des Bretts: {aus[:160]}'
    dort, laenge = stueck[0], int(stueck[1])
    gleich = (dort == hier and laenge == len(inhalt))
    return (f'{"OK" if gleich else "FEHLER"}: {name} -> {ziel} auf dem Brett an {port}.\n'
            f'  hier:          {len(inhalt)} Byte, sha256 {hier}\n'
            f'  auf dem Brett: {laenge} Byte, sha256 {dort}\n'
            + ('  Beides gleich -- auf dem Brett liegt genau diese Datei.'
               if gleich else '  NICHT gleich. Die Uebertragung ist fehlgeschlagen.'))


# ---------------------------------------------------------------- Das lokale Sprachmodell ---------------------------------------------------
_MODELL_ORDNER = r'C:\Kurs_Agent\paket'
_MODELL_PORT = 8099


def _modell_laeuft():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{_MODELL_PORT}/health', timeout=3) as r:
            return r.read(200).decode('utf-8', 'replace')
    except Exception:
        return None


def modell(spec):
    """'modell start|status|frage|stop': das Sprachmodell auf DIESEM Rechner bedienen.

    Warum das hier steht
    --------------------
    Ein Agent im Arbeitsbereich kann ein Modell beauftragen, das beim Anbieter laeuft -- dafuer
    braucht er nur einen Schluessel. Er kann aber auch das Modell beauftragen, das hier im
    Kurspaket liegt, und das ist der eigentliche Kursfall: kein Netz, kein Konto, nichts laedt
    nach. Dieser Befehl macht es erreichbar, ohne dass jemand am Rechner sitzt und klickt.

    Der enge Rahmen, wie bei flashen und femm
    -----------------------------------------
      * Gestartet wird genau ein Programm: llama-server.exe aus C:\\Kurs_Agent\\paket.
      * Das Modell ist eine .gguf-Datei aus C:\\Kurs_Agent\\paket\\modell; gewaehlt wird ueber
        ein Schluesselwort (coder, 3b, 7b), nicht ueber einen Pfad des Aufrufers.
      * Die Befehlszeile wird hier gebaut. Vom Aufrufer kommt nichts hinein.
      * Der Server hoert nur auf 127.0.0.1. Nichts davon verlaesst den Rechner.
      * 'frage' reicht JSON an /v1/chat/completions weiter und wartet laenger als 'sende':
        ein Modell auf einem Laptop braucht fuer eine Antwort Minuten, nicht Sekunden.

    Unterbefehle
    ------------
      modell start [coder|3b|7b]   Modellserver starten (laeuft er schon, wird das gesagt)
      modell status                antwortet er, und mit welchem Modell
      modell frage <JSON>          eine Anfrage an /v1/chat/completions, bis 15 Minuten
      modell frage_datei <x.json>  dieselbe Anfrage, aber aus einer Datei in diesem Ordner
                                   (fuer lange Gespraeche, die keine Befehlszeile mehr traegt)
      modell stop                  Modellserver beenden
    """
    teile = (spec or '').split(None, 1)
    was = (teile[0] if teile else 'status').lower()

    if was == 'status':
        h = _modell_laeuft()
        if not h:
            return f'Das Modell antwortet nicht auf 127.0.0.1:{_MODELL_PORT}. Mit "modell start" starten.'
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{_MODELL_PORT}/v1/models', timeout=5) as r:
                welches = _json_laden(r.read(4096))
            name = welches.get('data', [{}])[0].get('id', '?')
        except Exception:
            name = '?'
        return f'Das Modell laeuft auf 127.0.0.1:{_MODELL_PORT} ({h.strip()[:60]}), geladen: {name}'

    if was == 'stop':
        r = subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True, text=True, timeout=30)
        return ('Modellserver beendet.' if r.returncode == 0
                else 'Kein laufender Modellserver gefunden: ' + (r.stdout or r.stderr).strip()[:150])

    if was == 'start':
        if _modell_laeuft():
            return f'Das Modell laeuft schon auf 127.0.0.1:{_MODELL_PORT}.'
        wahl = (teile[1].strip().lower() if len(teile) > 1 else 'coder')
        muster = {'coder': 'Coder', '3b': '3B-Instruct', '7b': '7B-Instruct'}
        if wahl not in muster:
            return f'FEHLER: "{wahl}" kenne ich nicht (coder, 3b, 7b)'
        ordner = os.path.join(_MODELL_ORDNER, 'modell')
        treffer = [f for f in sorted(os.listdir(ordner)) if f.endswith('.gguf') and muster[wahl] in f]
        if not treffer:
            return f'FEHLER: kein Modell mit "{muster[wahl]}" in {ordner}'
        gguf = os.path.join(ordner, treffer[0])
        exe = None
        for zweig in ('llama_signiert', 'llama'):
            p = os.path.join(_MODELL_ORDNER, zweig, 'llama-server.exe')
            if os.path.isfile(p):
                exe = p
                break
        if not exe:
            return f'FEHLER: llama-server.exe liegt nicht unter {_MODELL_ORDNER}'
        befehl = [exe, '-m', gguf, '--host', '127.0.0.1', '--port', str(_MODELL_PORT),
                  '-c', '16384', '-ngl', '99', '--jinja', '--no-webui']
        subprocess.Popen(befehl, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd=os.path.dirname(exe))
        t0 = time.time()
        while time.time() - t0 < 300:                       # ein 7B-Modell braucht zum Laden Minuten
            time.sleep(3)
            if _modell_laeuft():
                return (f'Modell gestartet: {treffer[0]} ({os.path.getsize(gguf)/1e9:.1f} GB) '
                        f'auf 127.0.0.1:{_MODELL_PORT} nach {time.time()-t0:.0f} s.')
        return f'FEHLER: {treffer[0]} war nach 300 s noch nicht bereit.'

    if was in ('frage', 'frage_datei'):
        if len(teile) < 2:
            return f'FEHLER: Aufruf modell {was} ' + ('<JSON mit messages>' if was == 'frage' else '<datei.json>')
        if was == 'frage_datei':
            # Ein Gespraech mit Werkzeugliste und Zwischenergebnissen wird schnell laenger, als
            # eine Befehlszeile traegt. Dann kommt die Anfrage als Datei (per update), und hier
            # steht nur ihr Name. Gelesen wird ausschliesslich aus diesem Ordner.
            name = teile[1].strip()
            if not re.fullmatch(r'[A-Za-z0-9._-]+\.json', name):
                return f'FEHLER: "{name}" ist kein zulaessiger Dateiname (nur <name>.json, ohne Pfad)'
            pfad = os.path.join(ORDNER, name)
            if not os.path.isfile(pfad):
                return f'FEHLER: {name} liegt nicht in {ORDNER}. Erst mit update herschieben.'
            with open(pfad, 'rb') as f:
                teile = [was, f.read().decode('utf-8')]
        if not _modell_laeuft():
            return f'FEHLER: das Modell antwortet nicht. Erst "modell start".'
        try:
            inhalt = _json_laden(teile[1].encode('utf-8'))
        except ValueError as e:
            return f'FEHLER: Anfrage ist kein JSON: {e}'
        daten = _json_schreiben(inhalt).encode('utf-8')
        req = urllib.request.Request(f'http://127.0.0.1:{_MODELL_PORT}/v1/chat/completions',
                                     data=daten, method='POST',
                                     headers={'Content-Type': 'application/json'})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=900) as r:   # bis 15 Minuten: ein Laptop rechnet langsam
                roh = r.read(400000)
        except urllib.error.HTTPError as e:
            return f'Das Modell antwortet {e.code}: ' + e.read(4096).decode('utf-8', 'replace')
        except Exception as e:
            return f'FEHLER: das Modell antwortet nicht: {e}'
        return f'({time.time()-t0:.0f} s)\n' + roh.decode('utf-8', 'replace')

    return f'FEHLER: "{was}" kenne ich nicht (start, status, frage, frage_datei, stop)'


def _json_laden(roh):
    import json as _j
    return _j.loads(roh.decode('utf-8') if isinstance(roh, bytes) else roh)


def _json_schreiben(x):
    import json as _j
    return _j.dumps(x, ensure_ascii=False)


def femm(spec):
    """'femm <Lua-Datei> [Sekunden]': FEMM 4.2 mit einem Lua-Skript starten und auf das Ende warten.

    Die Lua-Datei liegt in diesem Ordner (per update hergeschoben). FEMM rechnet ohne Fenster durch, weil das Skript mit
    quit() endet. Zurück kommt die Laufzeit und, falls vorhanden, die letzte Zeile der FEMM-Konsolenausgabe. Gerechnet wird
    nur, was im Lua-Skript steht; die Brücke selbst rechnet nichts und verändert keine Datei.
    """
    teile = (spec or '').split()
    if not teile:
        return 'FEHLER: Aufruf femm <Lua-Datei> [Sekunden]'
    name = teile[0]
    grenze = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else 7200
    skript = name if os.path.isabs(name) else os.path.join(ORDNER, name)
    if not os.path.isfile(skript):
        return f'FEHLER: Lua-Datei fehlt: {skript}'
    kandidaten = [r'C:\femm42\bin\femm.exe', r'C:\Program Files\femm42\bin\femm.exe',
                  r'C:\Program Files (x86)\femm42\bin\femm.exe']
    exe = next((k for k in kandidaten if os.path.isfile(k)), None)
    if not exe:
        gefunden = glob.glob(r'C:\**\femm.exe', recursive=True)[:1]
        exe = gefunden[0] if gefunden else None
    if not exe:
        return 'FEHLER: femm.exe nicht gefunden (erwartet C:\\femm42\\bin\\femm.exe)'
    if len(teile) > 1 and teile[1].lower() == 'start':
        # ohne Warten starten: die Brücke bleibt bedienbar, der Bildschirm lässt sich währenddessen ansehen
        subprocess.Popen([exe, '-lua-script=' + skript], cwd=ORDNER)
        return f'FEMM gestartet (ohne Warten) mit {name}. Fortschritt über bildschirm/fenster verfolgen.'
    t0 = time.time()
    try:
        lauf = subprocess.run([exe, '-lua-script=' + skript], capture_output=True, text=True, timeout=grenze,
                              cwd=ORDNER, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired:
        return f'FEHLER: FEMM lief länger als {grenze} s und wurde abgebrochen ({name})'
    except Exception as e:
        return f'FEHLER beim Start von FEMM: {e}'
    dauer = time.time() - t0
    ausgabe = (lauf.stdout or '').strip().splitlines()
    letzte = ausgabe[-1][:200] if ausgabe else ''
    return f'FEMM {os.path.basename(exe)} mit {name}: Rückgabe {lauf.returncode} nach {dauer:.0f} s. {letzte}'.strip()

def megacad_nach(spec):
    """'megacad_nach 2': MegaCAD-Hauptfenster auf Monitor Nr. legen und dort maximieren (Fensterlage per SetWindowPlacement, keine Tastatur)."""
    import win32api, win32gui, win32con
    h = megacad_fenster()
    if not h: return 'FEHLER: kein sichtbares MegaCAD-Fenster'
    n = int((spec or '2').split()[0]); mons = win32api.EnumDisplayMonitors(None, None)
    if not 1 <= n <= len(mons): return f'FEHLER: Monitor {n} gibt es nicht ({len(mons)} vorhanden)'
    l, t, r, b = win32api.GetMonitorInfo(mons[n - 1][0])['Work']
    flags, show, minpos, maxpos, normal = win32gui.GetWindowPlacement(h)
    # 1) ohne Aktivierung in Normalgröße auf den Zielmonitor legen, 2) dort maximieren (Windows maximiert auf dem Monitor der aktuellen Lage)
    win32gui.SetWindowPlacement(h, (flags, win32con.SW_SHOWNOACTIVATE, minpos, maxpos, (l + 40, t + 40, r - 40, b - 40)))
    time.sleep(0.4)
    win32gui.SetWindowPos(h, 0, l + 40, t + 40, r - l - 80, b - t - 80, win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER)
    time.sleep(0.4)
    win32gui.SetWindowPlacement(h, (flags, win32con.SW_SHOWMAXIMIZED, minpos, maxpos, (l + 40, t + 40, r - 40, b - 40)))
    time.sleep(0.5); L, T, R, B = win32gui.GetWindowRect(h)
    return f'MegaCAD auf Monitor {n}: Fenster {R - L}x{B - T} bei ({L},{T})'
def schliessen(spec):
    """'schliessen <Titelteil>': einem Fenster die Schließen-Nachricht schicken (WM_CLOSE). Für Meldungsfenster, die einen
    Lauf blockieren. Es wird keine Maus bewegt und keine Taste gesendet; das Fenster entscheidet selbst, was es tut."""
    import win32gui, win32con
    suche = (spec or '').strip().lower()
    if not suche: return 'FEHLER: Aufruf schliessen <Titelteil>'
    treffer = []
    def pruefe(w, _):
        if win32gui.IsWindowVisible(w) and suche in win32gui.GetWindowText(w).lower():
            treffer.append((w, win32gui.GetWindowText(w)))
    win32gui.EnumWindows(pruefe, None)
    if not treffer: return f'kein sichtbares Fenster mit „{spec}“'
    aus = []
    for w, titel in treffer:
        win32gui.PostMessage(w, win32con.WM_CLOSE, 0, 0); aus.append(titel[:40])
    return 'Schließen-Nachricht an: ' + '; '.join(f'„{t}“' for t in aus)

def prozesse(spec=''):
    """'prozesse [Namensteil]': laufende Programme mit Rechenzeit und Speicher. So lässt sich sehen, ob ein Löser wirklich
    arbeitet oder nur ein Fenster offen steht. Nur Leserecht; es wird nichts gestartet und nichts beendet."""
    suche = (spec or '').strip().lower()
    try:
        roh = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        return f'FEHLER: Prozessliste nicht lesbar: {e}'
    zeilen = []
    for z in roh.splitlines():
        t = [x.strip('" ') for x in z.split('","')]
        if len(t) < 5: continue
        name, pid, speicher = t[0], t[1], t[-1]
        if suche and suche not in name.lower(): continue
        zeilen.append((name, pid, speicher))
    if not zeilen: return f'kein Programm mit „{spec}“ gefunden' if suche else 'keine Programme gefunden'
    return '\n'.join(f'{n:28s} PID {p:>7s}  {m}' for n, p, m in zeilen[:25])

def monitore():
    """Monitore laut Windows (EnumDisplayMonitors) und die Lage des MegaCAD-Fensters."""
    import win32api, win32gui
    zeilen = []
    for i, (hm, hdc, rect) in enumerate(win32api.EnumDisplayMonitors(None, None)):
        info = win32api.GetMonitorInfo(hm); l, t, r, b = rect
        zeilen.append(f"Monitor {i + 1}{' (Hauptmonitor)' if info.get('Flags', 0) & 1 else ''}: {info.get('Device', '?')} {r - l}x{b - t} bei ({l},{t})")
    h = megacad_fenster()
    if h:
        l, t, r, b = win32gui.GetWindowRect(h); zeilen.append(f'MegaCAD-Fenster: {r - l}x{b - t} bei ({l},{t}) – „{win32gui.GetWindowText(h)[:60]}“')
    else: zeilen.append('MegaCAD-Fenster: nicht sichtbar')
    return '\n'.join(zeilen)
def info():
    import importlib.util as ilu
    return f'{VERSION} | Python {sys.version.split()[0]} {sys.executable} | Ordner {ORDNER} | pywin32: {"ja" if ilu.find_spec("win32ui") else "FEHLT"} | Pillow: {"ja" if ilu.find_spec("PIL") else "fehlt"} | {megacad("?")}'
def startdatei_schreiben():
    if os.name != 'nt': return
    bat = os.path.join(ORDNER, 'Bruecke_starten.bat')
    inhalt = ('@echo off\r\ntitle Bruecke - alle Projekte\r\ncd /d "%~dp0"\r\n:schleife\r\n"' + sys.executable + '" bruecke.py %*\r\n'
              'echo Bruecke beendet (Code %errorlevel%), Neustart in 5 s - Fenster schliessen zum Beenden\r\ntimeout /t 5 >nul\r\ngoto schleife\r\n')
    try:
        if not os.path.isfile(bat) or open(bat, encoding='utf-8', errors='replace').read() != inhalt: open(bat, 'w', encoding='utf-8').write(inhalt); print('Startdatei geschrieben:', bat)
    except Exception as e: print('Startdatei nicht geschrieben:', e)

# ---------------------------------------------------------------- Befehlsschleife ------------------------------------------------------------
def befehle_ausfuehren():
    """Alle Projekte der Reihe nach abfragen und die gefundenen Befehle ausführen.

    Der Empfänger im Workspace hält je Projekt eine eigene Warteschlange. Die Brücke fragt sie
    nacheinander ab; AKTUELL steht dabei auf dem Projekt, dessen Befehl gerade bearbeitet wird,
    und jede Anfrage (Antwort, Hochladen, Update) trägt es mit. So landet nichts im falschen Ordner.
    """
    global AKTUELL
    for _projekt in PROJEKTE:
        AKTUELL = _projekt
        try: liste = json.loads(holen(f'{WORKSPACE}/befehle?' + q(), 8).decode())
        except Exception as e:
            print(f'  Befehle fuer {_projekt} nicht abrufbar:', e); continue
        if not liste: continue
        _ausfuehren(liste)


def _ausfuehren(liste):
    """Die Befehle eines Projekts abarbeiten. AKTUELL steht dabei fest."""
    for b in liste:
        typ, arg = b.get('typ', ''), b.get('url', '') or ''
        print(f"  Befehl [{b['id']}] {AKTUELL}/{typ.upper()} {arg[:120]}")
        try:
            if typ == 'megacad': text = megacad(arg)
            elif typ == 'dateiliste': text = dateiliste(arg)
            elif typ == 'klick': text = klick(arg)
            elif typ == 'hochladen': text = hochladen(arg)
            elif typ == 'update': text = update(arg)
            elif typ == 'loeschen': text = loeschen(arg)
            elif typ == 'verschieben': text = verschieben(arg)
            elif typ == 'bildschirm': text = bildschirm(arg)
            elif typ == 'monitore': text = monitore()
            elif typ == 'anschluesse': text = anschluesse(arg)
            elif typ == 'firewall': text = firewall(arg)
            elif typ == 'hole': text = hole(arg)
            elif typ == 'sende': text = sende(arg)
            elif typ == 'netz': text = netz(arg)
            elif typ == 'ota': text = ota(arg)
            elif typ == 'flashen': text = flashen(arg)
            elif typ == 'seriell': text = seriell(arg)
            elif typ == 'mpy': text = mpy(arg)
            elif typ == 'modell': text = modell(arg)
            elif typ == 'femm': text = femm(arg)
            elif typ == 'fenster': text = fenster(arg)
            elif typ == 'zeigen': text = zeigen(arg)
            elif typ == 'oeffnen': text = oeffnen(arg)
            elif typ == 'schliessen': text = schliessen(arg)
            elif typ == 'prozesse': text = prozesse(arg)
            elif typ == 'dialoge': text = dialoge_holen()
            elif typ == 'megacad_nach': text = megacad_nach(arg)
            elif typ == 'info': text = info()
            elif typ == 'selbstupdate': text = selbstupdate()
            else: text = f'unbekannter Befehlstyp {typ} (Brücke kennt: megacad, dateiliste, hochladen, update, loeschen, verschieben, oeffnen, bildschirm, anschluesse, flashen, ota, seriell, mpy, modell, femm, hole, sende, info, selbstupdate)'
        except Exception as e: text = f'FEHLER: {e}'
        try:
            req = urllib.request.Request(f'{WORKSPACE}/antwort?' + q(id=b['id']), data=text.encode('utf-8'), method='POST'); urllib.request.urlopen(req, timeout=30).read()
        except Exception as e: print('  Antwort nicht abgeliefert:', e)
        print('   ->', text[:300].replace('\n', ' | '))

if __name__ != '__main__':                                                          # nachgeladen per selbstupdate: Funktionen ins Hauptprogramm eintragen
    import sys as _sys
    _haupt = _sys.modules['__main__'].__dict__; _n = 0
    for _k, _v in list(globals().items()):
        if _k.startswith('_'): continue
        if callable(_v) or _k == 'VERSION': _haupt[_k] = _v; _n += 1
    _EINGETRAGEN = _n

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--alle', type=float, default=2.0); a = p.parse_args()
    print(VERSION); print('Ordner:', ORDNER)
    print('Projekte:', ', '.join(PROJEKTE))
    print('Python:', sys.version.split()[0], sys.executable)
    try:
        import importlib.util as _ilu
        _fehlt = [m for m in ('win32ui', 'PIL') if _ilu.find_spec(m) is None]
        if _fehlt: print('FEHLENDE PAKETE:', ', '.join(_fehlt), '\n  ->  "' + sys.executable + '" -m pip install ' + ' '.join(dict(win32ui='pywin32', PIL='pillow').get(m, m) for m in _fehlt), flush=True)
        startdatei_schreiben()
    except Exception as e: print('Startprüfung übersprungen:', e)
    try: print('Workspace-Empfänger:', holen(f'{WORKSPACE}/', 15).decode().splitlines()[0])
    except Exception as e: print('Workspace nicht erreichbar:', e, '– Brücke versucht es weiter')
    letzterHerzschlag = 0
    while True:
        t0 = time.time()
        try: befehle_ausfuehren()
        except Exception as e: print('  Fehler in der Befehlsschleife:', e)
        if time.time() - letzterHerzschlag > 60: letzterHerzschlag = time.time(); print(f'{datetime.datetime.now():%H:%M:%S} Brücke wartet auf Befehle aus {len(PROJEKTE)} Projekten')
        time.sleep(max(0.2, a.alle - (time.time() - t0)))
