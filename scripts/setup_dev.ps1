$ErrorActionPreference = "Stop"
python -m venv backend/.venv
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Write-Host "Backend dependencies installed. In frontend, run npm install."
