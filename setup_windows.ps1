$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location $projectRoot
try {
    try {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Python was not found. Install Python 3.10+ and add it to PATH."
        }

        $requirementsPath = Join-Path $projectRoot "requirements.txt"
        if (-not (Test-Path $requirementsPath)) {
            throw "requirements.txt was not found in the project root."
        }

        $venvPath = Join-Path $projectRoot ".venv"
        if (-not (Test-Path $venvPath)) {
            Write-Output "Creating virtual environment in .venv ..."
            & $pythonCommand.Source -m venv $venvPath
        } else {
            Write-Output "Using existing virtual environment in .venv ..."
        }

        $venvPython = Join-Path $venvPath "Scripts\python.exe"
        if (-not (Test-Path $venvPython)) {
            throw "Virtual environment creation failed: .venv\\Scripts\\python.exe was not found."
        }

        Write-Output "Upgrading pip ..."
        & $venvPython -m pip install --upgrade pip

        Write-Output "Installing requirements from requirements.txt ..."
        & $venvPython -m pip install -r $requirementsPath

        Write-Output "Setup complete."
        Write-Output "Next step: .\\run_overlay.ps1"
    } catch {
        Write-Error "Setup failed: $($_.Exception.Message)"
        exit 1
    }
} finally {
    Pop-Location
}
