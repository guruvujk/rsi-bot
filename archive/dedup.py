content = open("dashboard.py", encoding="utf-8").read()
count = content.count('@app.route("/portfolio")')
print(f"Found {count} portfolio routes")
if count > 1:
    first = content.find('@app.route("/portfolio")')
    second = content.find('@app.route("/portfolio")', first+1)
    main_route = content.find("@app.route('/')", second)
    content = content[:second] + content[main_route:]
    open("dashboard.py", "w", encoding="utf-8").write(content)
    print("Fixed - duplicates removed")
else:
    print("No duplicates found")
