$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcPath = Join-Path $projectRoot "src"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found. Create .venv or install Python 3.10+ and add it to PATH."
    }
    $pythonExe = $pythonCommand.Source
}

Push-Location $projectRoot
try {
    $env:PYTHONIOENCODING = "utf-8"
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$srcPath;$($env:PYTHONPATH)"
    } else {
        $env:PYTHONPATH = $srcPath
    }

    & $pythonExe -m voice_typing_ro.app
} finally {
    Pop-Location
}
