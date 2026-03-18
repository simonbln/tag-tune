from machine import Pin, UART, lightsleep, SPI
from mfrc522 import MFRC522
import utime
import time
import neopixel
import time
import random
from dfplayermini import DFPlayerMini

class NDEFDataManager:
    def __init__(self, reader):
        self.reader = reader
        self.last_text = None
        self.values = []
        self.current_index = 0
        self.has_error = False
        self._is_resuming = False # Internal state for shall_resume()

    def check(self):
        """Reads the tag and manages the resume/state logic."""
        raw_text = self._read_from_tag()
        self._is_resuming = False # Reset resume state by default

        # Case 1: Tag was removed (raw_text is None)
        if raw_text is None:
            if self.last_text is not None:
                # Tag lost: clear active state but keep index/saved_text for potential resume
                self.last_text = None 
                return True # Status change: tag gone
            return False

        # Case 2: A tag is present
        # Check against hidden buffer to see if it's the SAME tag as before
        if hasattr(self, '_saved_text') and raw_text == self._saved_text:
            # Same tag content detected
            if self.last_text is None: # It was away, now it's back
                self.last_text = raw_text
                # If there are elements left, enable resume; otherwise restart from 0
                if self.current_index < len(self.values):
                    self._is_resuming = True
                else:
                    self.current_index = 0 
                return True
            return False

        # Case 3: A completely new tag (or content changed)
        self.last_text = raw_text
        self._saved_text = raw_text # Persistent memory for resume check
        self.current_index = 0
        self._parse_values(raw_text)
        return True

    def shall_resume(self):
        """Returns True if the same tag was reapplied and has pending values."""
        return self._is_resuming

    def has_valid_tag(self):
        """Returns True if a tag is currently being detected."""
        return self.last_text is not None

    def get_next_value(self):
        """Returns the next integer from the array or None if finished."""
        if self.current_index < len(self.values):
            val = self.values[self.current_index]
            self.current_index += 1
            return val
        return None

    def _parse_values(self, text):
        """Parses comma-separated string into an integer list."""
        self.values = []
        self.current_index = 0
        self.has_error = False
        try:
            parts = text.strip().split(',')
            for p in parts:
                cleaned = p.strip()
                if cleaned:
                    self.values.append(int(cleaned))
        except ValueError:
            # Set error flag if formatting (non-integers) is wrong
            self.has_error = True
            self.values = []

    def _read_from_tag(self):
        """Hybrid read logic for Ultralight and Classic tags."""
        all_raw_data = bytearray()
        
        self.reader.init()
        (stat, _) = self.reader.request(self.reader.REQIDL)
        if stat != self.reader.OK: return None
        (stat, uid) = self.reader.SelectTagSN()
        if stat != self.reader.OK: return None

        # Try Ultralight first (Pages 4-15)
        for page in range(4, 16):
            s, d = self.reader.read(page)
            if s == self.reader.OK and d:
                all_raw_data.extend(bytes(d))
            else: break

        # Try Classic if Ultralight yielded no NDEF data
        if len(all_raw_data) < 7:
            self.reader.stop_crypto1() # Clean up state
            self.reader.init()
            self.reader.request(self.reader.REQIDL)
            self.reader.SelectTagSN()
            nextKey = [0xD3, 0xF7, 0xD3, 0xF7, 0xD3, 0xF7]
            for b in [0, 1, 2]:
                res = self.reader.readSectorBlock(uid, 1, b, nextKey, None)
                s, d = res if isinstance(res, tuple) else (self.reader.OK, res)
                if s == self.reader.OK and d:
                    all_raw_data.extend(bytes(d))
            self.reader.stop_crypto1()

        # NDEF Text Record Parser
        i = 0
        while i < len(all_raw_data) - 4:
            if all_raw_data[i] == 0x03: # NDEF Start
                msg_len = all_raw_data[i+1]
                try:
                    for j in range(i + 2, i + 8):
                        if all_raw_data[j] == 0x54: # 'T' identifier
                            p_len = all_raw_data[j-1]
                            l_len = all_raw_data[j+1] & 0x3F
                            start = j + 2 + l_len
                            end = j + 1 + p_len
                            return all_raw_data[start:end].decode('utf-8')
                except: pass
                i += 2 + msg_len
            elif all_raw_data[i] == 0xFE: break # NDEF End
            else: i += 1
        return None

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
    
last_color =  Colors.OFF

def set_pixel_color(color_rgb):
    if Colors.OFF != color_rgb:
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
manager = NDEFDataManager(reader)

valid_tag = False
color_led = Colors.GREEN
while True:
    if manager.check():
        if manager.has_valid_tag():
            print("new tag")
            if manager.has_error:
                color_led = Colors.RED
            else:
                color_led = Colors.BLUE
                while True:
                    val = manager.get_next_value()
                    if val is None: break
                    print("Zahl:", val)            
        else:
            color_led = Colors.GREEN
            print("no tag")
  
    set_pixel_color(color_led)
    utime.sleep_ms(500)
    

        



