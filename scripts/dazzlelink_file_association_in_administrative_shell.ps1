# dazzlelink_association.ps1
# Run from an elevated (Administrator) PowerShell prompt

# Find Python
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Host "Python not found. Please install Python and add it to PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Found Python at: $pythonPath" -ForegroundColor Green

# Determine dazzlelink invocation method
# Priority: 1) pip-installed module  2) monolith dazzlelink.py (legacy)

# Find pythonw.exe for windowless execution (no console flash on double-click)
$pythonwPath = $pythonPath -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $pythonwPath)) {
    $pythonwPath = $pythonPath
    Write-Host "pythonw.exe not found, using python.exe (console window will flash)" -ForegroundColor Yellow
} else {
    Write-Host "Found pythonw at: $pythonwPath" -ForegroundColor Green
}

# Check if dazzlelink is importable as a Python module
$moduleCheck = & $pythonPath -c "import dazzlelink" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Using installed dazzlelink package (python -m dazzlelink)" -ForegroundColor Green
    $openCmd = "`"$pythonwPath`" -m dazzlelink execute `"%1`""
    # info runs in a paused console so the output survives the window
    $infoCmd = "cmd.exe /c `"`"$pythonPath`" -m dazzlelink execute --mode info `"%1`" & pause`""
    $importCmd = "`"$pythonPath`" -m dazzlelink import `"%1`""
} else {
    # Fall back to the legacy monolith (may not exist)
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = Split-Path -Parent $scriptDir
    $dazzleLinkScript = Join-Path $repoRoot "legacy\dazzlelink_monolith.py"

    if (-not (Test-Path $dazzleLinkScript)) {
        $dazzleLinkScript = Join-Path $repoRoot "dazzlelink.py"
    }

    if (-not (Test-Path $dazzleLinkScript)) {
        $dazzleLinkScript = Join-Path $scriptDir "dazzlelink.py"
    }

    if (-not (Test-Path $dazzleLinkScript)) {
        Write-Host "dazzlelink not found! Neither pip module nor dazzlelink.py available." -ForegroundColor Red
        exit 1
    }

    Write-Host "Using legacy monolith: $dazzleLinkScript" -ForegroundColor Yellow
    $openCmd = "`"$pythonwPath`" `"$dazzleLinkScript`" execute `"%1`""
    $infoCmd = "cmd.exe /c `"`"$pythonPath`" `"$dazzleLinkScript`" execute --mode info `"%1`" & pause`""
    $importCmd = "`"$pythonPath`" `"$dazzleLinkScript`" import `"%1`""
}

# Registry paths
$fileType = ".dazzlelink"
$progId = "DazzlelinkFile"

# One registration implementation for both roots. Every write uses
# -ErrorAction Stop: registry cmdlet failures are NON-terminating by default,
# so without it a permission-denied run would sail past the catch and still
# print the success banner (the bug this replaced).
function Register-DazzlelinkAssociation([string]$regRoot) {
    # File type -> ProgID
    New-Item -Path "$regRoot\$fileType" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$fileType" -Name "(Default)" -Value $progId -ErrorAction Stop

    # ProgID + friendly name + icon
    New-Item -Path "$regRoot\$progId" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId" -Name "(Default)" -Value "Dazzlelink Symbolic Link" -ErrorAction Stop
    Set-ItemProperty -Path "$regRoot\$progId" -Name "FriendlyTypeName" -Value "Dazzlelink Symbolic Link" -ErrorAction Stop
    New-Item -Path "$regRoot\$progId\DefaultIcon" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\DefaultIcon" -Name "(Default)" -Value "$pythonPath,0" -ErrorAction Stop

    # Open command (double-click)
    New-Item -Path "$regRoot\$progId\shell\open\command" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\open\command" -Name "(Default)" -Value $openCmd -ErrorAction Stop

    # Context menu: Show Information
    New-Item -Path "$regRoot\$progId\shell\info" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\info" -Name "(Default)" -Value "Show Information" -ErrorAction Stop
    New-Item -Path "$regRoot\$progId\shell\info\command" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\info\command" -Name "(Default)" -Value $infoCmd -ErrorAction Stop

    # Context menu: Recreate Symlink
    New-Item -Path "$regRoot\$progId\shell\recreate" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\recreate" -Name "(Default)" -Value "Recreate Symlink" -ErrorAction Stop
    New-Item -Path "$regRoot\$progId\shell\recreate\command" -Force -ErrorAction Stop | Out-Null
    Set-ItemProperty -Path "$regRoot\$progId\shell\recreate\command" -Name "(Default)" -Value $importCmd -ErrorAction Stop
}

# Try HKCR (requires admin) first, fall back to HKCU (current user only)
try {
    Register-DazzlelinkAssociation "Registry::HKEY_CLASSES_ROOT"
    Write-Host "`nFile association created successfully! (HKCR - system-wide)" -ForegroundColor Green
} catch {
    Write-Host "HKCR failed (need admin?), trying HKCU..." -ForegroundColor Yellow
    try {
        Register-DazzlelinkAssociation "HKCU:\Software\Classes"
        Write-Host "`nFile association created successfully! (HKCU - current user)" -ForegroundColor Green
    } catch {
        Write-Host "`nRegistration FAILED: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nYou can now:"
Write-Host "  - Double-click .dazzlelink files to open their targets"
Write-Host "  - Right-click for 'Show Information' or 'Recreate Symlink'"
