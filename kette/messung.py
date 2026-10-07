# Messprogramm: misst, was die PWM-Einheit des ESP32 wirklich ausgibt.
#
# Es glaubt dem Programm nichts. atmen.py laeuft in einem Nebenlauf; im Hauptlauf wird der
# Tastgrad aus der LEDC-Einheit des Geraetes abgefragt (pwm.duty() liest das Hardwareregister,
# nicht eine Variable des Programms) und mit dem Mikrosekundenzaehler des Geraetes gestempelt.
# Erst nach der Messung werden die Werte ausgegeben, damit das Senden die Zeitpunkte nicht verzieht.
import _thread
import time

ns = {}


def nebenlauf():
    try:
        exec(open('atmen.py').read(), ns)
    except Exception as e:
        print('THREADFEHLER', e)


_thread.start_new_thread(nebenlauf, ())
time.sleep_ms(1200)                      # dem Nebenlauf Zeit geben, die PWM zu stellen

pwm = ns.get('pwm')
if pwm is None:
    print('MESSUNG FEHLER kein pwm im Namensraum')
else:
    # Immer wieder messen, nicht nur einmal: wer erst Sekunden spaeter mitliest, soll trotzdem
    # eine vollstaendige Reihe bekommen und nicht auf das Wort des Programms angewiesen sein.
    while True:
        # Mindestens drei volle Perioden: mit weniger als einer Periode laesst sich keine Kurvenform
        # von einer anderen unterscheiden -- jede passt dann mit irgendeiner Periodendauer.
        werte = []
        t0 = time.ticks_us()
        for k in range(600):
            werte.append((time.ticks_diff(time.ticks_us(), t0), pwm.duty()))
            time.sleep_ms(8)
        print('MESSUNG START', len(werte))
        for k in range(0, len(werte), 25):      # 25 Punkte je Zeile: das Mitlesen gibt nur die letzten Zeilen zurueck
            print('M ' + ' '.join('%d:%d' % (t, d) for t, d in werte[k:k + 25]))
        print('MESSUNG ENDE')
        time.sleep_ms(500)
