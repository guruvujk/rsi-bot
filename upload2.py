import json, requests
LOCAL_STATE = r"C:\Users\JKRAOWIN\rsi_bot_v2\rsi_bot_v2\bot_state.json"
RENDER_URL  = "https://rsi-bot-4yu1.onrender.com"
data = json.load(open(LOCAL_STATE))
print(f"Uploading: capital={data['capital']}, positions={len(data['positions'])}, trades={len(data['trades'])}")

# Try both routes
for route in ["/api/upload_state", "/upload_state", "/api/state"]:
    r = requests.post(f"{RENDER_URL}{route}", json=data, 
                      headers={"Content-Type": "application/json"}, timeout=30)
    print(f"{route} → {r.status_code}")
    if r.status_code == 200:
        print(r.text)
        break
