# Builds the launcher exes, then creates/updates "Twitch Playground.lnk" in the
# repo root pointing to the combined launcher (which starts BOTH the playground
# and the robot renderer at once). A .lnk stores an ABSOLUTE path, so it cannot
# be portable on its own -- run this once on each computer (or after moving the
# repo) and it rebuilds the exes and regenerates the shortcut for wherever the
# repo currently lives.
$dir = $PSScriptRoot

# --- Locate the .NET Framework C# compiler (csc.exe) ------------------------
# It ships with every Windows install, so no .NET SDK is required.
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path $csc)) {
    Write-Error "C# compiler (csc.exe) not found under $env:WINDIR\Microsoft.NET. Cannot build the launchers."
    exit 1
}

$icon = Join-Path $dir 'twitch_playground\assets\playground.ico'

# Helper: build one launcher exe from one .cs source. /target:winexe suppresses
# a console window; /win32icon embeds the playground icon into the exe.
function Build-Launcher {
    param([string]$Source, [string]$Out)
    Write-Host "Building launcher -> $Out"
    & $csc /nologo /target:winexe /out:"$Out" /win32icon:"$icon" `
        /reference:System.Windows.Forms.dll /reference:System.dll "$Source"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Launcher build failed for $Source (csc exit code $LASTEXITCODE)."
        exit 1
    }
}

# --- Build all three launcher exes ------------------------------------------
# launch_all.exe is the entry point; it starts the two sibling exes by name, so
# both must sit next to it (they do -- all live in launcher\).
$playgroundExe = Join-Path $dir 'launcher\Twitch Playground.exe'
$robotExe      = Join-Path $dir 'launcher\Robot.exe'
$allExe        = Join-Path $dir 'launcher\Twitch Playground (All).exe'

Build-Launcher (Join-Path $dir 'launcher\launcher.cs')       $playgroundExe
Build-Launcher (Join-Path $dir 'launcher\robot_launcher.cs') $robotExe
Build-Launcher (Join-Path $dir 'launcher\launch_all.cs')     $allExe

# --- Create / update the shortcut -------------------------------------------
# Points at the combined launcher so one double-click brings up both windows.
$ws  = New-Object -ComObject WScript.Shell
$sc  = $ws.CreateShortcut((Join-Path $dir 'Twitch Playground.lnk'))
$sc.TargetPath       = $allExe
$sc.WorkingDirectory = $dir
$sc.IconLocation     = $icon + ',0'
$sc.Description      = 'Lobotomy Corporation Twitch playground + robot renderer'
$sc.Save()
Write-Host "Shortcut updated -> $($sc.TargetPath)"
