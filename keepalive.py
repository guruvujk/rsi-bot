import threading, requests, time

def keep_alive():
    while True:
        try:
            requests.get("https://rsi-bot-4yu1.onrender.com/api/health")
        except:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()
