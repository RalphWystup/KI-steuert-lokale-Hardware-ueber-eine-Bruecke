#!/usr/bin/env python3
"""Brücke zwischen dem PC und dem Workspace — eine für alle Projekte.

Läuft in ``C:\\Bruecke`` und bedient jedes Projekt, das im Workspace einen Empfänger-Kanal hat.
Sie fragt in jedem Durchlauf alle Projekte aus ``PROJEKTE`` ab, führt die gefundenen Befehle aus
und liefert die Antwort an dasselbe Projekt zurück. Dateien werden dabei immer im Ordner des
Projekts abgelegt, aus dem der Befehl kam.

Vorher gab es drei Brücken nebeneinander — eine für das Mikroskop_Beispiel, eine für das Anzeigegerät, eine
für CAD. Jede konnte etwas, das die anderen nicht konnten, und keine lief, wenn gerade eine andere
gebraucht wurde. Diese hier kann alles und läuft immer.

Befehle (aus dem Workspace mit befehl.py):
  cadprog <Befehl>        Kommandozeile des CAD-Programms per DDE-Execute an das laufende Programm (Dienst CAD_3D, Thema System);
                          mehrere Befehle mit ' ;; ' trennen; 'cadprog ?' prüft nur die Verbindung; 'cadprog @Dienst <Befehl>' erzwingt den Dienst
  dateiliste <Ordner>     Ordner listen; 'dateiliste cadprog' sucht die Installation des CAD-Programms (EXE, BEFEHLE.INI, Menüdateien);
                          'dateiliste suche <Ordner> <Muster>' sucht rekursiv (z. B. suche C:\\ *.PRT)
  klick [rechts|links|doppel] [x y]  echter Mausklick in das CAD-Programm oder einen seiner Dialoge (bestätigt eine Elementauswahl, „R: genug“);
                          x y optional als Anteil 0..1 der Fenstergröße, Standard Mitte; 'klick links abs X Y' = Bildschirmpixel (Dialog auf anderem Monitor)
  hochladen <Datei>       Datei vom PC in den Workspace (Projekt_A/Bilder/), z. B. BEFEHLE.INI oder ein SAT-Export
  update <Dateien> [-> <Zielordner>]  Dateien aus dem Workspace (Projekt_A/Arbeitsstand/Laptop/) holen (kommagetrennt);
                          ohne Zielordner in diesen Ordner, sonst in den angegebenen, der bei Bedarf angelegt wird
  bildschirm [alles]      Bildschirmfoto in den Workspace: Standard = das das CAD-Programm-Fenster (auch auf einem zweiten oder virtuellen Monitor),
                          'bildschirm alles' = alle Monitore zusammen
  fenster [alle]          sichtbare Fenster des das CAD-Programm-Prozesses; 'alle' listet jedes Fenster (z. B. FEMM-Meldungen)
  zeigen <Titelteil> [x y]  ein Fenster ganz nach oben stellen und an die Stelle x y legen (Standard 60 60)
  oeffnen <Pfad>          eine Datei mit ihrem Standardprogramm oeffnen (Layout in KiCad, Gerber, PDF, Bild);
                          nur in den erlaubten Zweigen und nur Datenendungen, nichts Ausfuehrbares
  schliessen <Titelteil>  einem Fenster die Schließen-Nachricht schicken (blockierende Meldungen)
  prozesse [Namensteil]   laufende Programme mit Speicherbedarf anzeigen (rechnet der Löser wirklich?)
  femm <Lua-Datei> [s|start]  FEMM 4.2 mit einem Lua-Skript rechnen lassen; 'start' kehrt sofort zurück, sonst wird gewartet
  cad_nach <Nr>       Hauptfenster des CAD-Programms auf Monitor Nr legen und maximieren
  dialoge                 das CAD-Programm-Dialoge vom anderen Monitor in die Mitte des das CAD-Programm-Fensters verschieben (wird vor jedem Klick auch automatisch gemacht)
  monitore                angeschlossene Monitore (auch virtuelle) mit Lage und Größe, dazu die Lage des das CAD-Programm-Fensters
  info                    Python, Ordner, pywin32 vorhanden, DDE erreichbar
  selbstupdate            diese Brücke aus dem Workspace erneuern (im laufenden Betrieb)
  verschieben <Ordner> :: n1,n2  die genannten Dateien in <Ordner>\\alt legen (nie löschen, nie überschreiben; nur C:\\Projekt_A, C:\\Ablage, C:\\CAD, C:\\Fahrzeug, C:\\Sicherung)
Außer FEMM startet die Brücke keine Programme; das CAD-Programm öffnet der Nutzer selbst.
Einrichtung: pip install pywin32 pillow   – dann Doppelklick auf Bruecke_starten.bat (wird beim ersten Start geschrieben).
"""
import argparse, sys, time, urllib.request, urllib.parse, json, os, datetime, shutil, io, threading, fnmatch, subprocess, glob
if os.name == 'nt':                      # Pro-Monitor-DPI: Fensterlagen, Mauspunkte und Bildschirmfotos in echten Pixeln, auch bei 150 % Skalierung
    try:
        import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass

VERSION = ('Brücke 3.0 — eine Brücke für alle Projekte. Fragt in jedem Durchlauf alle Projekte aus PROJEKTE ab und antwortet jeweils demselben; Dateien landen im Ordner des Projekts, aus dem der Befehl kam. Befehle: Dateiliste, Hochladen, Update, Öffnen, Bildschirmfoto, Fenster anordnen, Mausklick, Verschieben, Löschen, Feldrechnung, Selbstaktualisierung.')
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
# Alle Projekte, die der Empfänger kennt. Die Brücke fragt sie der Reihe nach ab.
# Die Namen hier sind Beispiele — einzutragen sind die eigenen Projektordner.
# Ein neues Projekt braucht hier nur eine Zeile — und im Workspace einen Ordner mit
# <Projekt>/Arbeitsstand/Laptop (für update) und <Projekt>/Bilder (für hochladen).
PROJEKTE = ('Projekt_A', 'Projekt_B', 'Messplatz', 'Layout')

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

# ---------------------------------------------------------------- das CAD-Programm per DDE ------------------------------------------------------------
def cadprog(spec):
    """DDE-Execute an das CAD-Programm. DDE ist an den aufrufenden Thread gebunden, deshalb läuft alles in einem Arbeits-Thread mit Zeitgrenze."""
    spec = (spec or '').strip(); dienste = ('CAD_3D', 'CAD3D', 'das CAD-Programm', 'CADPROG', 'CAD_2D')
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
            if conv is None: ergebnis['text'] = 'FEHLER: kein DDE-Dienst erreichbar (' + ', '.join(dienste) + ') – läuft das CAD-Programm?'; return
            if not befehle or befehle == ['?']: ergebnis['text'] = f'DDE-Dienst {benutzt} erreichbar'; return
            teile = []
            for i, b in enumerate(befehle):
                if b.lower().startswith('pause'):                                       # 'pause 3' wartet 3 s (Standard 1,5 s)
                    try: time.sleep(float(b.split()[1].replace(',', '.')))
                    except (IndexError, ValueError): time.sleep(1.5)
                    teile.append(b); continue
                if i: time.sleep(1.5)                                                  # das CAD-Programm braucht Zeit, bevor es den nächsten Befehl annimmt
                t0 = time.time(); fehler = None
                for versuch in range(3):                                               # 'Exec failed' heißt meist: das CAD-Programm noch beschäftigt – kurz warten, erneut
                    try: conv.Exec(b); fehler = None; break
                    except Exception as e: fehler = e; time.sleep(1.5)
                if fehler is None: teile.append(f'{b} -> ok ({time.time() - t0:.1f} s)')
                else: teile.append(f'{b} -> FEHLER {fehler}'); break
            ergebnis['text'] = f'DDE {benutzt}: ' + ' | '.join(teile)
        finally:
            try: server.Shutdown()
            except Exception: pass
    th = threading.Thread(target=arbeit, daemon=True); th.start(); th.join(240)
    if th.is_alive(): return 'FEHLER: das CAD-Programm antwortet nicht innerhalb von 240 s (wartet es auf eine Eingabe oder ein Dialogfenster?)'
    return ergebnis['text'] or 'FEHLER: keine Rückmeldung'

def cad_fenster():
    """Fenster-Handle des größten sichtbaren Hauptfenster des CAD-Programmss (Titel enthält 'das CAD-Programm'); minimierte Fenster zählen nicht."""
    import win32gui
    treffer = []
    def pruefe(h, _):
        titel = win32gui.GetWindowText(h)
        if win32gui.IsWindowVisible(h) and not win32gui.IsIconic(h) and 'cadprog' in titel.lower() and 'cad-bruecke' not in titel.lower():   # eigenes Konsolenfenster ausnehmen
            l, t, r, b = win32gui.GetWindowRect(h)
            if r - l > 300 and b - t > 300: treffer.append(((r - l) * (b - t), h))
    win32gui.EnumWindows(pruefe, None)
    return max(treffer)[1] if treffer else None
def klick(spec):
    """'klick rechts' | 'klick links' [x y]: echter Mausklick in die Zeichenfläche von das CAD-Programm, um eine Elementauswahl zu bestätigen
    ('R: genug'). Der Mauszeiger wird an den Punkt gesetzt (Standard: 60 % Breite, 55 % Höhe des Fensters, die Zeichenfläche rechts der
    Seitenleisten), geklickt und zurückgestellt. Vorher wird geprüft, dass an der Stelle wirklich das CAD-Programm vorne liegt; sonst Fehlermeldung.
    Die Brücke holt kein Fenster nach vorne und sendet keine Tastatureingaben."""
    import win32gui, win32con, win32api
    teile = (spec or 'rechts').split(); taste = teile[0].lower() if teile else 'rechts'
    h = cad_fenster()
    if not h: return 'FEHLER: kein sichtbares das CAD-Programm-Fenster gefunden (minimiert?)'
    try: dialoge_holen(); time.sleep(0.3)
    except Exception: pass
    # Die Brücke holt das CAD-Programm nicht selbst nach vorne (keine Tastatur-Emulation); der Nutzer lässt das das CAD-Programm-Fenster vorne liegen.
    if len(teile) > 3 and teile[1].lower() == 'abs':                         # 'klick links abs X Y': Bildschirmpixel (für Dialoge, die auf einem anderen Monitor aufgehen)
        x, y = int(float(teile[2])), int(float(teile[3]))
    else:
        fx = float(teile[1]) if len(teile) > 2 else 0.6; fy = float(teile[2]) if len(teile) > 2 else 0.55
        l, t, r, b = win32gui.GetWindowRect(h); x = l + int((r - l) * fx); y = t + int((b - t) * fy)
    try:
        unter = win32gui.WindowFromPoint((x, y)); wurzel = win32gui.GetAncestor(unter, 2)
        titel = win32gui.GetWindowText(wurzel); eigner = win32gui.GetWindow(wurzel, 4)                # GW_OWNER: Dialoge von das CAD-Programm gehören zum Hauptfenster
        import win32process
        gleicher_prozess = win32process.GetWindowThreadProcessId(wurzel)[1] == win32process.GetWindowThreadProcessId(h)[1]   # Dialoge von das CAD-Programm gehören zu seinem Prozess
        # erlaubt sind das CAD-Programm, seine Dialoge und FEMM: beide werden von der Brücke bedient
        erlaubt = ('cadprog' in titel.lower() or 'femm' in titel.lower()
                   or titel.strip() in ('Öffnen', 'Speichern unter', 'Baugruppe', 'Z. als Referenz einfg.'))
        if wurzel != h and eigner != h and not gleicher_prozess and not erlaubt:
            return f'FEHLER: an der Klickstelle liegt ein anderes Fenster vorne („{titel[:50]}“) – das CAD-Programm bitte nach vorne holen'
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
    if spec.lower() == 'cadprog':
        funde = []
        for basis in dict.fromkeys([os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), os.environ.get('ProgramW6432', ''), 'C:\\']):
            if not basis or not os.path.isdir(basis): continue
            for name in os.listdir(basis):
                if 'mega' in name.lower():
                    pfad = os.path.join(basis, name); funde.append(pfad)
                    for wurzel, unter, dateien in os.walk(pfad):
                        for f in dateien:
                            fl = f.lower()
                            if (fl.endswith('.exe') and 'cad' in fl) or fl in ('befehle.ini', 'cadprog.ini', 'megamenu.ini'): funde.append('  ' + os.path.join(wurzel, f))
                        if wurzel.count(os.sep) - pfad.count(os.sep) >= 2: unter[:] = []
        return '\n'.join(funde) if funde else 'kein das CAD-Programm-Ordner unter den Programmordnern gefunden'
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
    'hochladen C:\\Layout\\Platine\\*.kicad_*'. Ein ganzes Layoutprojekt kommt so
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
    'update a.lua,b.fem -> C:\\Projekt_A'. Der Zielordner wird angelegt, wenn er fehlt. Gesichert wird eine
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
ERLAUBT_LOESCHEN = (r'C:\Projekt_A', r'C:\Ablage', r'C:\CAD\Sicherung', r'C:\Bruecke\Sicherung')

ERLAUBT_VERSCHIEBEN = (r'C:\Projekt_A', r'C:\Ablage', r'C:\CAD', r'C:\Fahrzeug', r'C:\Sicherung',
                       r'C:\Kamera', r'C:\Garten', r'C:\Waerme',
                       r'C:\Fuellstand', r'C:\Messplatz', r'C:\Bauteile', r'C:\Messplatz_2',
                       r'C:\Beispiel_Privat', r'C:\Layout', r'C:\Bruecke',
                       r'C:\Projekt_B')

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
    """Foto des das CAD-Programm-Fensters, wo immer es liegt (Hauptmonitor, zweiter oder virtueller Monitor); 'alles' = gesamter virtueller Bildschirm."""
    from PIL import ImageGrab
    h = None if (spec or '').strip().lower() == 'alles' else cad_fenster()
    if h:
        import win32gui
        l, t, r, b_ = win32gui.GetWindowRect(h)
        im = ImageGrab.grab(bbox=(l, t, r, b_), all_screens=True).convert('RGB'); lage = f'das CAD-Programm-Fenster bei ({l},{t})'
    else:
        im = ImageGrab.grab(all_screens=True).convert('RGB'); lage = 'alle Monitore'
    b = io.BytesIO(); im.save(b, 'JPEG', quality=70)
    return f'Bildschirm {im.size[0]}x{im.size[1]} ({lage}): ' + senden(b.getvalue(), 'bildschirm.jpg')
def fenster(spec=''):
    """Sichtbare Top-Level-Fenster auflisten. Ohne Angabe nur die des das CAD-Programm-Prozesses (auch dessen Dialoge);
    'fenster alle' listet alle Fenster mit Titel, Größe und Lage – so lassen sich auch FEMM-Meldungen finden."""
    import win32gui, win32process
    alle = (spec or '').strip().lower().startswith('alle')
    pid = None
    if not alle:
        h = cad_fenster()
        if not h: return 'FEHLER: kein sichtbares das CAD-Programm-Fenster (für alle Fenster: fenster alle)'
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

    Gedacht fuer den Blick auf ein Ergebnis: ein Layoutlayout in KiCad, ein Gerber im
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
    """das CAD-Programm-Dialoge, die auf einem anderen Monitor als das Hauptfenster aufgegangen sind, in die Mitte des das CAD-Programm-Fensters verschieben
    (reine Lageänderung ohne Aktivierung: SetWindowPos mit NOACTIVATE/NOZORDER/NOSIZE)."""
    import win32gui, win32process, win32con
    h = cad_fenster()
    if not h: return 'FEHLER: kein sichtbares das CAD-Programm-Fenster'
    pid = win32process.GetWindowThreadProcessId(h)[1]; L, T, R, B = win32gui.GetWindowRect(h); bewegt = []
    def pruefe(w, _):
        if w == h or not win32gui.IsWindowVisible(w) or win32process.GetWindowThreadProcessId(w)[1] != pid: return
        l, t, r, b = win32gui.GetWindowRect(w)
        if r - l < 20 or b - t < 20: return
        if (l + r) // 2 < L or (l + r) // 2 > R or (t + b) // 2 < T or (t + b) // 2 > B:            # Mitte außerhalb des das CAD-Programm-Fensters
            nx, ny = (L + R) // 2 - (r - l) // 2, (T + B) // 2 - (b - t) // 2
            win32gui.SetWindowPos(w, 0, nx, ny, 0, 0, win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE)
            bewegt.append(f'„{win32gui.GetWindowText(w)[:50].strip()}“ von ({l},{t}) nach ({nx},{ny})')
    win32gui.EnumWindows(pruefe, None)
    return 'verschoben: ' + '; '.join(bewegt) if bewegt else 'kein Dialog außerhalb des das CAD-Programm-Fensters'
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

def cad_nach(spec):
    """'cad_nach 2': Hauptfenster des CAD-Programms auf Monitor Nr. legen und dort maximieren (Fensterlage per SetWindowPlacement, keine Tastatur)."""
    import win32api, win32gui, win32con
    h = cad_fenster()
    if not h: return 'FEHLER: kein sichtbares das CAD-Programm-Fenster'
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
    return f'das CAD-Programm auf Monitor {n}: Fenster {R - L}x{B - T} bei ({L},{T})'
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
    """Monitore laut Windows (EnumDisplayMonitors) und die Lage des das CAD-Programm-Fensters."""
    import win32api, win32gui
    zeilen = []
    for i, (hm, hdc, rect) in enumerate(win32api.EnumDisplayMonitors(None, None)):
        info = win32api.GetMonitorInfo(hm); l, t, r, b = rect
        zeilen.append(f"Monitor {i + 1}{' (Hauptmonitor)' if info.get('Flags', 0) & 1 else ''}: {info.get('Device', '?')} {r - l}x{b - t} bei ({l},{t})")
    h = cad_fenster()
    if h:
        l, t, r, b = win32gui.GetWindowRect(h); zeilen.append(f'das CAD-Programm-Fenster: {r - l}x{b - t} bei ({l},{t}) – „{win32gui.GetWindowText(h)[:60]}“')
    else: zeilen.append('das CAD-Programm-Fenster: nicht sichtbar')
    return '\n'.join(zeilen)
def info():
    import importlib.util as ilu
    return f'{VERSION} | Python {sys.version.split()[0]} {sys.executable} | Ordner {ORDNER} | pywin32: {"ja" if ilu.find_spec("win32ui") else "FEHLT"} | Pillow: {"ja" if ilu.find_spec("PIL") else "fehlt"} | {cadprog("?")}'
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
            if typ == 'cadprog': text = cadprog(arg)
            elif typ == 'dateiliste': text = dateiliste(arg)
            elif typ == 'klick': text = klick(arg)
            elif typ == 'hochladen': text = hochladen(arg)
            elif typ == 'update': text = update(arg)
            elif typ == 'loeschen': text = loeschen(arg)
            elif typ == 'verschieben': text = verschieben(arg)
            elif typ == 'bildschirm': text = bildschirm(arg)
            elif typ == 'monitore': text = monitore()
            elif typ == 'femm': text = femm(arg)
            elif typ == 'fenster': text = fenster(arg)
            elif typ == 'zeigen': text = zeigen(arg)
            elif typ == 'oeffnen': text = oeffnen(arg)
            elif typ == 'schliessen': text = schliessen(arg)
            elif typ == 'prozesse': text = prozesse(arg)
            elif typ == 'dialoge': text = dialoge_holen()
            elif typ == 'cad_nach': text = cad_nach(arg)
            elif typ == 'info': text = info()
            elif typ == 'selbstupdate': text = selbstupdate()
            else: text = f'unbekannter Befehlstyp {typ} (Brücke kennt: cadprog, dateiliste, hochladen, update, loeschen, verschieben, oeffnen, bildschirm, info, selbstupdate)'
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
