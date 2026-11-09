$ErrorActionPreference = "Stop"

$noVncPath = Join-Path $env:LOCALAPPDATA "EX200Lab\noVNC"
$noVncParent = Split-Path -Parent $noVncPath

if (-not (Test-Path (Join-Path $noVncPath "vnc.html"))) {
    New-Item -ItemType Directory -Force -Path $noVncParent | Out-Null
    git clone --depth 1 --branch v1.6.0 https://github.com/novnc/noVNC.git $noVncPath
}

py -m pip install -r (Join-Path $PSScriptRoot "..\requirements.txt")
Write-Output "noVNC installed at $noVncPath"
Write-Output "Start the API with: py server.py"
