import requests
token = "8694229997:AAGfe1savDm39EsXsjuswJdGPbRD_ocGNaU"
url = f"https://api.telegram.org/bot{token}/getUpdates"
r = requests.get(url)
print(r.text)