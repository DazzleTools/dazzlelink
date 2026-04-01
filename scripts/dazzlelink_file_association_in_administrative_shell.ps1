# dazzlelink_association.ps1
# Run from an elevated (Administrator) PowerShell prompt

# Find Python
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Host "Python not found. Please install Python and add it to PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Found Python at: $pythonPath" -ForegroundColor Green

# Find dazzlelink.py -- check parent directory first (scripts/ is a subdirectory)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dazzleLinkScript = Join-Path (Split-Path -Parent $scriptDir) "dazzlelink.py"

if (-not (Test-Path $dazzleLinkScript)) {
    $dazzleLinkScript = Join-Path $scriptDir "dazzlelink.py"
}

if (-not (Test-Path $dazzleLinkScript)) {
    # Fall back to python -m dazzlelink
    Write-Host "dazzlelink.py not found, using python -m dazzlelink" -ForegroundColor Yellow
    $openCmd = "`"$pythonPath`" -m dazzlelink execute `"%1`""
    $infoCmd = "`"$pythonPath`" -m dazzlelink execute --mode info `"%1`""
    $importCmd = "`"$pythonPath`" -m dazzlelink import `"%1`""
} else {
    Write-Host "Using dazzlelink script: $dazzleLinkScript" -ForegroundColor Green
    $openCmd = "`"$pythonPath`" `"$dazzleLinkScript`" execute `"%1`""
    $infoCmd = "`"$pythonPath`" `"$dazzleLinkScript`" execute --mode info `"%1`""
    $importCmd = "`"$pythonPath`" `"$dazzleLinkScript`" import `"%1`""
}

# Registry paths
$fileType = ".dazzlelink"
$progId = "DazzlelinkFile"

# Try HKCR (requires admin) first, fall back to HKCU
$regRoot = "Registry::HKEY_CLASSES_ROOT"
try {
    # Create file type association
    New-Item -Path "$regRoot\$fileType" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$fileType" -Name "(Default)" -Value $progId

    # Create ProgID
    New-Item -Path "$regRoot\$progId" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId" -Name "(Default)" -Value "Dazzlelink Symbolic Link"
    Set-ItemProperty -Path "$regRoot\$progId" -Name "FriendlyTypeName" -Value "Dazzlelink Symbolic Link"

    # Default icon (Python icon)
    New-Item -Path "$regRoot\$progId\DefaultIcon" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\DefaultIcon" -Name "(Default)" -Value "$pythonPath,0"

    # Open command (double-click)
    New-Item -Path "$regRoot\$progId\shell\open\command" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\open\command" -Name "(Default)" -Value $openCmd

    # Context menu: Show Information
    New-Item -Path "$regRoot\$progId\shell\info" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\info" -Name "(Default)" -Value "Show Information"
    New-Item -Path "$regRoot\$progId\shell\info\command" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\info\command" -Name "(Default)" -Value $infoCmd

    # Context menu: Recreate Symlink
    New-Item -Path "$regRoot\$progId\shell\recreate" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\recreate" -Name "(Default)" -Value "Recreate Symlink"
    New-Item -Path "$regRoot\$progId\shell\recreate\command" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\recreate\command" -Name "(Default)" -Value $importCmd

    Write-Host "`nFile association created successfully! (HKCR - system-wide)" -ForegroundColor Green
} catch {
    Write-Host "HKCR failed (need admin?), trying HKCU..." -ForegroundColor Yellow

    $regRoot = "HKCU:\Software\Classes"

    New-Item -Path "$regRoot\$fileType" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$fileType" -Name "(Default)" -Value $progId

    New-Item -Path "$regRoot\$progId" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId" -Name "(Default)" -Value "Dazzlelink Symbolic Link"

    New-Item -Path "$regRoot\$progId\shell\open\command" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\open\command" -Name "(Default)" -Value $openCmd

    New-Item -Path "$regRoot\$progId\shell\info" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\info" -Name "(Default)" -Value "Show Information"
    New-Item -Path "$regRoot\$progId\shell\info\command" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\info\command" -Name "(Default)" -Value $infoCmd

    New-Item -Path "$regRoot\$progId\shell\recreate" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\recreate" -Name "(Default)" -Value "Recreate Symlink"
    New-Item -Path "$regRoot\$progId\shell\recreate\command" -Force | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\recreate\command" -Name "(Default)" -Value $importCmd

    Write-Host "`nFile association created successfully! (HKCU - current user)" -ForegroundColor Green
}

Write-Host "`nYou can now:"
Write-Host "  - Double-click .dazzlelink files to open their targets"
Write-Host "  - Right-click for 'Show Information' or 'Recreate Symlink'"
