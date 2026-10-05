# npm replaces a linked node_modules with a real folder. This project sits in OneDrive,
# where thousands of small package files cause sync load and file locks, so after
# `npm install` run `npm run relink` to move node_modules (and .next) out to
# %LOCALAPPDATA%\atrader\web and leave a junction behind.
$web = Split-Path -Parent $PSScriptRoot
$store = Join-Path $env:LOCALAPPDATA "atrader\web"

foreach ($name in "node_modules", ".next") {
    $link = Join-Path $web $name
    $target = Join-Path $store $name
    $item = Get-Item $link -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType -eq "Junction") { continue }   # already linked
    New-Item -ItemType Directory -Force -Path $store | Out-Null
    if (Test-Path $target) { Remove-Item $target -Recurse -Force }
    if ($item) { Move-Item $link $target } else { New-Item -ItemType Directory -Path $target | Out-Null }
    cmd /c mklink /J "$link" "$target" | Out-Null
    "linked $name -> $target"
}
