# sounds.py — RSI Bot Sound Alerts
# Usage: from sounds import play_sound
#        play_sound("buy") / play_sound("target") / play_sound("stoploss") / play_sound("startup")

import os
import threading

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "static", "sounds")

SOUND_MAP = {
    "buy"      : "buy.wav",
    "target"   : "target.wav",
    "stoploss" : "stoploss.wav",
    "startup"  : "startup.wav",
    "ping"     : "startup.wav",   # RSI approaching — reuse startup ping
}

def play_sound(event: str):
    """Play sound for given event. Runs in background thread so bot doesn't pause."""
    try:
        filename = SOUND_MAP.get(event)
        if not filename:
            return
        path = os.path.join(SOUNDS_DIR, filename)
        if not os.path.exists(path):
            print(f"  [Sound] File not found: {path}")
            return
        # Run in background thread — non-blocking
        threading.Thread(target=_play, args=(path,), daemon=True).start()
    except Exception as e:
        print(f"  [Sound] Error: {e}")

def _play(path: str):
    try:
        from playsound import playsound
        playsound(path)
    except Exception as e:
        print(f"  [Sound] Playback error: {e}")


# ── Quick test ────────────────────────────────────────────
if __name__ == "__main__":
    import time
    print("Testing sounds...")
    print("  Playing: startup")
    play_sound("startup");  time.sleep(3)
    print("  Playing: buy")
    play_sound("buy");      time.sleep(3)
    print("  Playing: target")
    play_sound("target");   time.sleep(3)
    print("  Playing: stoploss")
    play_sound("stoploss"); time.sleep(3)
    print("Done.")
