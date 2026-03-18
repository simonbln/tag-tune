from machine import Pin, UART, lightsleep, SPI
from mfrc522 import MFRC522
import utime
import time
import neopixel
import time
import random
from dfplayermini import DFPlayerMini

def get_text_datasets(reader):
    all_raw_data = bytearray()
    text = None
    
    reader.init()
    (stat, tag_type) = reader.request(reader.REQIDL)
    if stat != reader.OK: return text

    (stat, uid) = reader.SelectTagSN()
    if stat != reader.OK: return text

    # Schlüssel definieren
    firstKey = [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5]
    nextKey = [0xD3, 0xF7, 0xD3, 0xF7, 0xD3, 0xF7]
    
    # Relevante Blöcke (Sektor 0 überspringen wir meist, da dort oft nur Config steht)
    # Wenn deine Daten in Sektor 1 beginnen:
    blocks_to_read = [(1, 0, nextKey), (1, 1, nextKey), (1, 2, nextKey)]

    # 1. Alle Rohdaten in einen Puffer laden
    for sector, block, key in blocks_to_read:
        res = reader.readSectorBlock(uid, sector, block, key, None)
        
        # Sicherstellen, dass wir das Daten-Objekt korrekt extrahieren
        # Viele Bibliotheken geben (status, data) zurück
        if isinstance(res, tuple):
            status, data = res
        else:
            status, data = reader.OK, res # Falls nur Daten kommen

        if status == reader.OK and data:
            # In MicroPython sicherstellen, dass data iterierbar ist
            all_raw_data.extend(bytes(data))

    # 2. NDEF Parser Logik
    i = 0
    while i < len(all_raw_data):
        if all_raw_data[i] == 0x03:  # NDEF Message Start
            msg_len = all_raw_data[i + 1]
            
            # Header-Check: [D1][01][PayloadLen] 'T'
            # 'T' ist 0x54. Wir suchen die Position von 0x54
            try:
                # Suche nach dem Typ-Identifier 'T' im aktuellen Fenster
                record_start = i + 2
                type_pos = -1
                for j in range(record_start, record_start + 5):
                    if all_raw_data[j] == 0x54: # 0x54 = 'T'
                        type_pos = j
                        break
                
                if type_pos != -1:
                    payload_len = all_raw_data[type_pos - 1]
                    status_byte = all_raw_data[type_pos + 1]
                    lang_len = status_byte & 0x3F
                    
                    text_start = type_pos + 2 + lang_len
                    text_end = type_pos + 1 + payload_len
                    
                    text_bytes = all_raw_data[text_start : text_end]
                    text = text_bytes.decode('utf-8')
                    return text
            except Exception:
                pass
            
            i += 2 + msg_len # Springe zum nächsten TLV
        elif all_raw_data[i] == 0xFE:
            break
        else:
            i += 1
            
            
            

print("start")


input_signal = Pin(2, Pin.IN, Pin.PULL_UP) 
pixel = neopixel.NeoPixel(Pin(16), 1)
pixel2 = neopixel.NeoPixel(Pin(28), 1)

class Colors:
    RED     = (50, 0, 0)
    GREEN   = (0, 50, 0)
    BLUE    = (0, 0, 50)
    YELLOW  = (50, 50, 0)
    CYAN    = (0, 50, 50)
    MAGENTA = (50, 0, 50)
    WHITE   = (50, 50, 50)
    OFF     = (0, 0, 0)

def set_pixel_color(color_rgb):
    pixel[0] = color_rgb
    pixel2[0]= color_rgb
    pixel.write()
    pixel2.write()
    
set_pixel_color(Colors.WHITE)

#time.sleep(1)
player = DFPlayerMini(1,4,5)
#time.sleep(1)



while True:
    print ("Reset")
    if player.reset() == True:
        print ("Reset: OK")
        break
    #time.sleep(1)
    break



time.sleep(1)
player.select_source('sdcard')

print ("Read Num files")
count_songs = player.query_num_files()
print (f"Num files {count_songs}")

print ("Read volume")
read_value = player.get_volume()
print (f"Volume {read_value}")

player.set_volume(30)

print ("Read volume")
read_value = player.get_volume()
print (f"Volume {read_value}")


# SPI Konfiguration für RP2040-Zero
sck = 10
mosi = 11
miso = 12
sda = 13
rst = 9
reader = MFRC522(spi_id=1, sck=10, mosi=11, miso=12, cs=13, rst=9)

print("")
print("RFID Leser gestartet - Pins: SCK=10, MOSI=11, MISO=12, CS=13, RST=9")
print("Lege eine Karte auf den Leser")
print("")
 


print("")
print("Text-Datensätze Leser")
print("")

while True:
    #print(f"\nCHECK")
    text = get_text_datasets(reader)
    
    print(f"\nTexte: {text}")
    
    utime.sleep_ms(500)



