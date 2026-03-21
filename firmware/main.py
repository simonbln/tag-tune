from machine import Pin, UART, lightsleep, SPI
from mfrc522 import MFRC522
import utime
import time
import neopixel
import time
import random
from dfplayermini import DFPlayerMini

class NDEFDataManager:
    def __init__(self, reader, max_files):
        self.reader = reader
        self.max_files = max_files
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
                print("check: tag gone")
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
                    print(f"check: tag is back: {raw_text}")
                return True
            return False

        # Case 3: A completely new tag (or content changed)
        self.last_text = raw_text
        self._saved_text = raw_text # Persistent memory for resume check
        self.current_index = 0
        self._parse_values(raw_text)
        print(f"check: tag is new: {raw_text}")
        return True

    def shall_resume(self):
        """Returns True if the same tag was reapplied and has pending values."""
        return self._is_resuming

    def has_valid_tag(self):
        """Returns True if a tag is currently being detected."""
        return self.last_text is not None

    def get_next_value(self):
        while self.current_index < len(self.values):
            val = self.values[self.current_index]
            self.current_index += 1
            print(f"get_next_val: {val}")
            if val <= self.max_files:
                print(f"get_next_val: {val}: OK")
                return val
        print(f"gejt_next_val: nothing found")       
        return None
    
    def get_prev_value(self):
        while self.current_index > 0:
            self.current_index -= 1
            val = self.values[self.current_index]
            
            if val <= self.max_files:
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



# --- Configuration ---
BTN_NEXT_PIN = 6
BTN_PREV_PIN = 7
DEBOUNCE_MS = 50 
LONG_PRESS_MS = 1000
VOL_STEP_MS = 500

BUSY_PIN = 3

LED1_PIN = 16
LED2_PIN = 27

# --- Global States ---
# We store (timestamp, is_pressed)
btn_states = {
    BTN_NEXT_PIN: {"start_time": 0, "active": False, "long_done": False},
    BTN_PREV_PIN: {"start_time": 0, "active": False, "long_done": False}
}


# --- Shared ISR for Buttons ---
def btn_isr(pin):
    pin_num = 6 if "6" in str(pin) else 7 # Simple way to get ID
    if pin.value() == 0: # Pressed (Falling)
        if not btn_states[pin_num]["active"]:
            btn_states[pin_num]["start_time"] = utime.ticks_ms()
            btn_states[pin_num]["active"] = True
            btn_states[pin_num]["long_done"] = False
    else: # Released (Rising)
        btn_states[pin_num]["active"] = False
        
# Setup Pins
btn_next = Pin(BTN_NEXT_PIN, Pin.IN, Pin.PULL_UP)
btn_prev = Pin(BTN_PREV_PIN, Pin.IN, Pin.PULL_UP)
btn_next.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_isr)
btn_prev.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=btn_isr)

pixel = neopixel.NeoPixel(Pin(LED1_PIN), 1)
pixel2 = neopixel.NeoPixel(Pin(LED2_PIN), 1)

busy_pin = Pin(BUSY_PIN, Pin.IN)

class Colors:
    RED     = (50, 0, 0)
    GREEN   = (0, 150, 0)
    BLUE    = (0, 0, 150)
    YELLOW  = (150, 150, 0)
    CYAN    = (0, 150, 150)
    MAGENTA = (150, 0, 150)
    WHITE   = (150, 150, 150)
    OFF     = (0, 0, 0)
    
last_color =  Colors.OFF

def set_pixel_color(color_rgb):
    if Colors.OFF != color_rgb:
        pixel[0] = color_rgb
        pixel2[0]= color_rgb
        pixel.write()
        pixel2.write()

    
set_pixel_color(Colors.WHITE)


time.sleep(2)
player = DFPlayerMini(1,4,5)

def wait_until_playing(timeout_ms=500):
    start = utime.ticks_ms()
    while utime.ticks_diff(utime.ticks_ms(), start) < timeout_ms:
        if busy_pin.value() == 0:
            utime.sleep_ms(10)
    return False

while True:
    print ("Reset")
    if player.reset() == True:
        print ("Reset: OK")
        break
    time.sleep(1)
    break

time.sleep(1)
player.select_source('sdcard')

print ("Read Num files")
count_songs = player.query_num_files()
print (f"Num files {count_songs}")

if count_songs == 0:
    while True:
        set_pixel_color(Colors.RED)
        time.sleep(10)

player.set_volume(15)
print ("Read volume")
current_vol = player.get_volume()
print (f"Volume {current_vol}")


reader = MFRC522(spi_id=1, sck=10, mosi=11, miso=12, cs=13, rst=9)
manager = NDEFDataManager(reader, count_songs)

led_yellow_until = 0
last_vol_tick = 0
color_led = Colors.GREEN
loop_count = 0

while True:
    now = utime.ticks_ms()
    
    # Process both buttons
    for pin_id in [BTN_NEXT_PIN, BTN_PREV_PIN]:
        state = btn_states[pin_id]
        
        if state["active"]:
            duration = utime.ticks_diff(now, state["start_time"])
            
            # 1. Visual Feedback (Yellow LED for short/start press)
            if duration > DEBOUNCE_MS:
                led_yellow_until = now + 200 # Keep yellow for 300ms
            
            # 2. Long Press Logic (Volume)
            if duration > LONG_PRESS_MS:
                if utime.ticks_diff(now, last_vol_tick) > VOL_STEP_MS:
                    
                    if pin_id == BTN_NEXT_PIN:
                        current_vol = min(current_vol + 1, 30)
                        print(f"Volume UP: {current_vol}")
                    else:
                        current_vol = max(current_vol - 1, 0)            
                        print("Volume DOWN")
                    
                    player.set_volume(current_vol)
                    last_vol_tick = now
                    state["long_done"] = True

    #Short Press Logic (Next/Prev Song)
    # Detect release after a short press
    for pin_id in [BTN_NEXT_PIN, BTN_PREV_PIN]:
        state = btn_states[pin_id]
        if not state["active"] and state["start_time"] > 0:
            duration = utime.ticks_diff(now, state["start_time"])
            if DEBOUNCE_MS < duration < LONG_PRESS_MS:
                if manager.has_valid_tag():
                    val = None
                    if pin_id == BTN_NEXT_PIN:
                        print("Action: NEXT SONG")
                        val = manager.get_next_value()
                    else:
                        print("Action: PREV SONG")
                        val = manager.get_prev_value()
                    if val:
                        player.play(val)
                        wait_until_playing()
                    else:
                        #nothing to play
                        color_led = Colors.CYAN
            
            state["start_time"] = 0 
            state["active"] = False

    #LED Control
    if utime.ticks_ms() < led_yellow_until:
        set_pixel_color(Colors.YELLOW)
    else:
        # Fall back to normal tag-based color
        set_pixel_color(color_led)
        
    #check for nfc tag
    if (loop_count % 10) == 0:
        if manager.check():
            if manager.has_valid_tag():
                print("new tag")
                if manager.has_error:
                    color_led = Colors.RED
                else:
                    color_led = Colors.BLUE
                    if manager.shall_resume():
                        player.start()
                        wait_until_playing()
                    else:
                        val = manager.get_next_value()
                        if val:
                            player.play(val)
                            wait_until_playing()
                        else:
                            #nothing to play
                            color_led = Colors.CYAN
            else:
                player.pause()
                color_led = Colors.GREEN
                print("no tag")
                
        if color_led == Colors.BLUE and busy_pin.value() != 0:
            #supposed to playing but not anymore, go to next
            val = manager.get_next_value()
            if val:
                player.play(val)
                wait_until_playing()
            else:
                #nothing to play
                color_led = Colors.CYAN
  
    loop_count = (loop_count + 1) % 100
    utime.sleep_ms(50)
    

        



