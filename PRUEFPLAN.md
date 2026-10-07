---
title: "Prüfplan — KI steuert lokale Hardware über eine Brücke"
author: "Prof. Dr.-Ing. Ralph Wystup M.Sc."
date: "7. Oktober 2026"
---

# Prüfplan

Dieses Blatt gehört zur Arbeit „KI steuert lokale Hardware über eine Brücke". Es ist am
7. Oktober 2026 angelegt worden, **bevor** die darin beschriebene Erweiterung gebaut wurde:
ein großes Sprachmodell schreibt ein Programm, und dieses Programm läuft am Ende auf einem
ESP32 auf dem Schreibtisch.

Jedes Kriterium hat eine Nummer, eine **Schranke** und ein **Prüfmittel**. Ein Kriterium ohne
Prüfmittel ist eine Absichtserklärung und wird als solche gekennzeichnet. Die Buchstaben gelten
in diesem Blatt; der Kurs-Agent führt eigene Gruppen A bis K in `Kurs_Agent/PRUEFPROTOKOLL.md`.

Der Anlass steht im Klartext: Der Kurs-Agent mit kleinem Modell galt dem Auftraggeber am
5. Oktober 2026 als misslungen, weil ein Knopf, der „geprüft" hieß, am Gerät ins Leere lief.
Daraus folgt die Forderung vom 6. Oktober 2026, 10:18 Uhr, wörtlich:

> „… zuerst nur mit fest vorgefertigten Anweisungen, die müssen dann aber 100 % echt durch die
> Kette laufen, und das Echt muss in den Prüfplan."

## Was „echt" heißt

Ein fester Auftrag durchläuft sieben Glieder. Echt ist ein Lauf nur, wenn **jedes** Glied eine
gemessene Spur hinterlässt. Eine behauptete Spur ist keine.

| Glied | Was geschieht | Die Spur, die es hinterlassen muss | Stand 7. Oktober 2026 |
|:--|:--|:--|:--|
| 1 | Auftrag aus fester Liste, mit erwartetem Ende | Auftragskennung, erwartete Messgröße | `kette/auftraege.json`, sechs Aufträge |
| 2 | Modell schreibt das Programm | Kennung der Antwort beim Anbieter, Zeitstempel, Modellname, Token | **offen**, kein Zugang zum großen Modell |
| 3 | Programm wird in eine Datei geschrieben | Inhalt und SHA-256 der Datei | gemessen |
| 4 | Prüfung ohne Gerät | Syntax, verlangte Bauteile, Lebenszeile im Text | gemessen |
| 5 | Übertragen auf den ESP32 | SHA-256, **vom Gerät zurückgelesen** | gemessen, Brücke 3.6 `mpy senden` |
| 6 | Das Gerät meldet sich | serielle Zeile mit dem Zähler des Gerätes | gemessen, `seriell` |
| 7 | Messung am Gerät | Takt aus den Gerätezeitstempeln, bei PWM dazu die Kurvenform | gemessen, `kette/pruefe_kette.py` |

Am 7. Oktober 2026 liefen die Glieder 3 bis 7 für zwei Aufträge vollständig durch, jeder Schritt
am Gerät gemessen. Offen bleibt Glied 2: Solange kein Zugang zum großen Modell eingerichtet ist,
wird der Programmtext vorgegeben, und jedes Protokoll sagt ausdrücklich, dass dieser Lauf das
Modell nicht geprüft hat. Eine benannte Lücke ist keine Täuschung, eine verschwiegene wäre es.

## E — Echtheit der Kette

| Nr. | Kriterium | Schranke | Prüfmittel |
|:--|:--|:--|:--|
| E0 | **Keine vorgefertigte Kette.** Die Reihenfolge der Schritte bestimmt das Modell aus dem Auftrag, nicht ein Programm. Die Werkzeuge liegen als einzelne, selbstbeschreibende Programme im Werkzeugordner (`esp32` mit den Handgriffen schreiben, uebertragen, starten, mitlesen, anschluesse, liste; `kurve_bewerten`); der Agent findet sie und ruft sie, wie er es für richtig hält. Ein Prüfprogramm, das die Schritte fest hintereinander aufruft, ist Prüfmittel der Strecke und **nicht** der Betrieb. Anweisung des Auftraggebers vom 7.10.2026: „alles muss über das LLM laufen, und vom Agenten gesteuert werden allein aufgrund des Promptes oder bei Rückfragen, keine vorgefertigte Kette!" | jedes Werkzeug beschreibt sich selbst und ist einzeln aufrufbar; `agent.py --probe` ruft jedes mit eigenen Beispieldaten | `agent.py --probe` |
| E1 | **Nichts ist hinterlegt.** Jeder Lauf eines festen Auftrags erzeugt einen neuen Aufruf beim Anbieter. Die Antwortkennung des Anbieters steht im Protokoll. | zwei Läufe desselben Auftrags geben zwei verschiedene Kennungen; beide Zeitstempel liegen im Zeitfenster des jeweiligen Laufs | `pruefe_echtheit.py` |
| E2 | **Die Datei ist die Antwort des Modells.** Was das Modell geliefert hat und was in die Datei geschrieben wurde, ist dasselbe — kein stiller Austausch gegen eine Vorlage. | SHA-256 des Programmtextes aus der Modellantwort gleich SHA-256 der Datei | `pruefe_echtheit.py` |
| E3 | **Auf dem Gerät liegt genau diese Datei.** Die Prüfsumme wird **auf dem Gerät** gebildet und zurückgelesen, nicht beim Sender gemerkt. | SHA-256 vom Gerät gleich SHA-256 der Datei; Länge gleich | `pruefe_echtheit.py` über die Brücke |
| E4 | **Das Gerät meldet seinen Lauf.** Jeder feste Auftrag schreibt eine Lebenszeile vor, die das Programm auf der seriellen Schnittstelle ausgibt. Sie muss nach dem Neustart erscheinen. | Zeile im Wortlaut des Auftrags, innerhalb von 10 s, Zeit gemessen | `pruefe_echtheit.py` über `seriell` |
| E5 | **Das Gerät tut, was der Auftrag verlangt.** Der Takt wird aus den Zeitstempeln des Gerätezählers gerechnet, die das Programm in seinen Lebenszeilen mitschickt. | je Auftrag angegeben, z. B. Takt 1 Hz ± 10 % | `pruefe_kette.py` |
| E5a | **Das Programm bringt seine Messroutine mit, und sie misst statt zu behaupten.** Der Auftrag verlangt vom Modell eine eingebaute Messung: Jeder gesetzte Tastgrad wird aus der PWM-Einheit **zurückgelesen** (`pwm.duty()` ohne Argument liefert den Registerwert) und als Rohwert geschickt, je Periode eine Zeile `P t=… dt=… D=…`. Gerechnet wird außen. Ein Programm, das über sich selbst urteilt, erfüllt dieses Kriterium nicht. | Messzeilen vorhanden, mindestens zwei Perioden, Hub über 10 %; Form des Auftrags passt am besten, nächstbeste Form mindestens anderthalbfache Restabweichung | `pruefe_kette.py` |
| E5b | **Die Form wird zusätzlich von außen gemessen**, ohne dem Programm zu glauben: Ein eigenes Messprogramm liest den Tastgrad aus der PWM-Einheit, während das Programm des Modells in einem Nebenlauf läuft. Ausgewertet wird über die **Faltung der Perioden** (Minima trennen die Perioden, jede wird auf Phase 0 bis 1 gestreckt, alle übereinandergelegt). Beide Wege müssen dieselbe Form ergeben (Grundsatz der zwei unabhängigen Wege). | beide Wege nennen dieselbe Form; nächstbeste Form mindestens anderthalbfach | `pruefe_kette.py` mit `messung.py` |
| E5c | **Die Phasenlage ist bei der Formprüfung frei.** Geprüft wird die Form, nicht wo die Periode beginnt. Das ist notwendig, weil der zurückgelesene Tastgrad der PWM-Einheit um eine Trägerperiode nachhinkt: Sie übernimmt einen neuen Wert erst beim nächsten Durchlauf ihres Zählers (am 7.10.2026 gemessen, der zurückgelesene Wert ist genau der zuvor gesetzte). | ohne freie Phase erschiene die saubere Sinuskurve mit rund 4 % statt 0,2 % Rest | `pruefe_kette.py`, Handrechnung im Protokoll |
| E6 | **Ohne Gerät kein grüner Haken.** Ist kein ESP32 sichtbar oder die Brücke nicht erreichbar, endet der Lauf als „nicht prüfbar". Nie als „bestanden". | Zustand „nicht prüfbar" im Bericht, Rückgabewert verschieden von 0 | `pruefe_echtheit.py` mit abgezogenem Kabel |
| E7 | **Jeder feste Auftrag ist ein eigener Prüffall.** Eingabe, erwartetes Ende, gemessene Zeile, Dauer und Protokoll je Lauf. Als „geprüft" gilt nur, was in **jedem** Lauf besteht. | n von n Läufen, n ≥ 3, je Auftrag; eine Fehlrunde macht den Auftrag offen | `pruefe_alle_auftraege.py` |
| E8 | **Fehlerprotokoll mit Ursache.** Jeder Fehlschlag steht mit Glied (1–7), Ursache und Behebung in `FEHLERPROTOKOLL.md`; nach der Behebung wird derselbe Fall wiederholt. | kein Eintrag ohne Wiederholungslauf | von Hand, Blatt |
| E9 | **Der Bericht nennt, womit gemessen wurde.** Modellname, Fassung der Brücke, Anschluss, Datum — in jedem Protokoll. | vier Angaben vorhanden | `pruefe_echtheit.py` |
| E10 | **Die Berichtigungsrunden stehen im Protokoll.** Hat das Modell nachgebessert, steht jede Runde mit Fehlertext da; ein Lauf ohne Nachbesserung sagt das ausdrücklich. | Rundenzahl im Bericht, höchstens drei | `pruefe_echtheit.py` |

## S — Was die Erweiterung nicht beschädigen darf

| Nr. | Kriterium | Schranke | Prüfmittel |
|:--|:--|:--|:--|
| S1 | **Die laufende Brücke bleibt stehen.** Ein neuer Befehlstyp ist additiv; jeder bisherige Typ antwortet danach wie zuvor. | Stichprobe `info`, `dateiliste`, `anschluesse` vor und nach der Änderung gleich | `pruefe_bruecke_unveraendert.py` |
| S2 | **Nur Dateien, keine Befehle.** Der neue Typ überträgt eine Datei auf ein serielles Gerät; er führt nichts auf dem Rechner aus, was der Aufrufer bestimmt. | kein Durchreichen von Zeichenketten an eine Kommandozeile; Name und Anschluss gegen Muster geprüft | Durchsicht und `pruefe_echtheit.py` |
| S3 | **Zugangsdaten stehen außerhalb.** Schlüssel des Anbieters und Token der Brücke nur in den Zugangsdateien, nie in Seite, Protokoll oder Repositorium. | Suche über alle ausgelieferten Dateien ohne Treffer | `AUSFUHR/pruefe_veroeffentlichung.py` |
| S4 | **Der Kursweg ohne Internet bleibt offen.** Das lokale kleine Modell bleibt wählbar; der Prüfbericht weist je Modell getrennt aus, wie viele Läufe bestanden haben. | zwei Spalten im Bericht, je Modell | `pruefe_alle_auftraege.py` |

## Offen, und als offen gekennzeichnet

- Glied 5 verlangt einen neuen Befehlstyp in der laufenden Brücke. Das ist ein Eingriff in ein
  System im Betrieb (Grundsatz 34) und wartet auf das Wort des Auftraggebers.
- E8 hat kein Prüfprogramm und bekommt keines; ein Fehlerprotokoll schreibt ein Mensch.
- Die Zahl der festen Aufträge steht noch nicht fest. Der Kurs-Agent hatte neun; sie werden
  einzeln übernommen, nicht als Block.
