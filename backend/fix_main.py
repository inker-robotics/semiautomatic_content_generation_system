import os
with open('d:/INKER PROJECTS/backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('os.makedirs("frontend/logos", exist_ok=True)', 'os.makedirs("../frontend/logos", exist_ok=True)')
content = content.replace('open("frontend/index.html", "r"', 'open("../frontend/index.html", "r"')
content = content.replace('os.path.join("frontend", "logos"', 'os.path.join("..", "frontend", "logos"')

with open('d:/INKER PROJECTS/backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
