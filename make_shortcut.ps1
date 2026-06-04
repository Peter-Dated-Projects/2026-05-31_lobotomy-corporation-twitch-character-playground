# Creates/updates "Twitch Playground.lnk" in the repo root, pointing to the
# local launch_playground.bat. A .lnk stores an ABSOLUTE path, so it cannot be
# portable on its own -- run this once on each computer (or after moving the
# repo) and it regenerates the shortcut for wherever the repo currently lives.
$dir = $PSScriptRoot
$ws  = New-Object -ComObject WScript.Shell
$sc  = $ws.CreateShortcut((Join-Path $dir 'Twitch Playground.lnk'))
$sc.TargetPath       = Join-Path $dir 'launcher\Twitch Playground.exe'
$sc.WorkingDirectory = $dir
$sc.IconLocation     = (Join-Path $dir 'twitch_playground\assets\playground.ico') + ',0'
$sc.Description      = 'Lobotomy Corporation Twitch character playground'
$sc.Save()
Write-Host "Shortcut updated -> $($sc.TargetPath)"
