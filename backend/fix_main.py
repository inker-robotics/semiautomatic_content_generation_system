with open('d:/INKER PROJECTS/backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('directory="frontend"', 'directory="../frontend"')
content = content.replace('directory="frontend/logos"', 'directory="../frontend/logos"')
content = content.replace('FileResponse("frontend/index.html")', 'FileResponse("../frontend/index.html")')

with open('d:/INKER PROJECTS/backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
