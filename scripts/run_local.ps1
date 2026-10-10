$ErrorActionPreference = "Stop"
$root = (Get-Location).Path
Start-Process -FilePath "powershell" -WindowStyle Hidden -ArgumentList @("-NoExit", "-Command", "Set-Location '$root/backend'; ./.venv/Scripts/Activate.ps1; uvicorn app.main:app --reload")
Start-Process -FilePath "powershell" -WindowStyle Hidden -ArgumentList @("-NoExit", "-Command", "Set-Location '$root/frontend'; npm run dev")
