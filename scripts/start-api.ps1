Set-Location "C:\Users\gizem\OneDrive\Desktop\hr-bitirme\talentforge"
$env:UV_CACHE_DIR = "$env:TEMP\talentforge-uv-cache"
$env:UV_PYTHON = "C:\Users\gizem\AppData\Local\Programs\Python\Python313\python.exe"
uv run --no-dev --no-python-downloads uvicorn app.main:app --host 127.0.0.1 --port 8000
