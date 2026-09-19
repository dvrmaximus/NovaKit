param(
  [Parameter(Mandatory = $true)][string]$ExePath,
  [string]$IconPath = ""
)

$ErrorActionPreference = "Stop"
$Wsh = New-Object -ComObject WScript.Shell

function New-AppShortcut([string]$Path, [string]$Target, [string]$Icon) {
  $dir = Split-Path -Parent $Path
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $s = $Wsh.CreateShortcut($Path)
  $s.TargetPath = $Target
  $s.WorkingDirectory = Split-Path -Parent $Target
  $s.Description = "NovaKit - assistant HUD"
  $s.WindowStyle = 1
  if ($Icon -and (Test-Path $Icon)) {
    $s.IconLocation = "$Icon,0"
  } else {
    $s.IconLocation = "$Target,0"
  }
  $s.Save()
}

$desktop = [Environment]::GetFolderPath("Desktop")
$start = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\NovaKit"
$installDir = Split-Path -Parent $ExePath

New-AppShortcut (Join-Path $desktop "NovaKit.lnk") $ExePath $IconPath
New-AppShortcut (Join-Path $start "NovaKit.lnk") $ExePath $IconPath

# Uninstaller helper bat next to app
$unBat = Join-Path $installDir "Desinstaller.bat"
@"
@echo off
rmdir /s /q "%LOCALAPPDATA%\Programs\NovaKit"
del "%USERPROFILE%\Desktop\NovaKit.lnk" 2>nul
rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\NovaKit" 2>nul
echo NovaKit desinstalle.
pause
"@ | Set-Content -Encoding ASCII $unBat

New-AppShortcut (Join-Path $start "Desinstaller NovaKit.lnk") $unBat $IconPath

Write-Host "Raccourcis crees."
