content = open("dashboard.py", encoding="utf-8").read()

# Find what the state variable is actually called in the existing routes
import re
matches = re.findall(r'(bot_state|state)\[', content)
print("State variable name:", set(matches))
