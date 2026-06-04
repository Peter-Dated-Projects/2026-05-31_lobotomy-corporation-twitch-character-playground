# Builds the launcher exe, then creates/updates "Twitch Playground.lnk" in the
# repo root pointing to it. A .lnk stores an ABSOLUTE path, so it cannot be
# portable on its own -- run this once on each computer (or after moving the
# repo) and it rebuilds the exe and regenerates the shortcut for wherever the
# repo currently lives.
$dir = $PSScriptRoot

# --- Build launcher\Twitch Playground.exe from launcher\launcher.cs ---------
# Use the .NET Framework C# compiler (csc.exe). It ships with every Windows
# install, so no .NET SDK is required. /target:winexe suppresses a console
# window; /win32icon embeds the playground icon into the exe.
$src  = Join-Path $dir 'launcher\launcher.cs'
$exe  = Join-Path $dir 'launcher\Twitch Playground.exe'
$icon = Join-Path $dir 'twitch_playground\assets\playground.ico'

$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path $csc)) {
    Write-Error "C# compiler (csc.exe) not found under $env:WINDIR\Microsoft.NET. Cannot build the launcher."
    exit 1
}

Write-Host "Building launcher -> $exe"
& $csc /nologo /target:winexe /out:"$exe" /win32icon:"$icon" `
    /reference:System.Windows.Forms.dll /reference:System.dll "$src"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Launcher build failed (csc exit code $LASTEXITCODE)."
    exit 1
}

# --- Create / update the shortcut -------------------------------------------
$ws  = New-Object -ComObject WScript.Shell
$sc  = $ws.CreateShortcut((Join-Path $dir 'Twitch Playground.lnk'))
$sc.TargetPath       = $exe
$sc.WorkingDirectory = $dir
$sc.IconLocation     = $icon + ',0'
$sc.Description      = 'Lobotomy Corporation Twitch character playground'
$sc.Save()
Write-Host "Shortcut updated -> $($sc.TargetPath)"
