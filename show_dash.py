with open('dashboard.py', encoding='utf-8', errors='ignore') as f:
    src = f.read()
idx = src.find('loadUpstoxPositions')
print(src[idx:idx+1500])
