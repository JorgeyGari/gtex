<#
PowerShell wrapper for common `uv` workflows.

Usage examples:
  ./scripts/run.ps1 sync
  ./scripts/run.ps1 main
  ./scripts/run.ps1 gdc-dry 5
  ./scripts/run.ps1 gdc 2
  ./scripts/run.ps1 pytest
  ./scripts/run.ps1 shell
#>

param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$Cmd,
    [Parameter(Position=1, Mandatory=$false)]
    [string]$Arg
)

switch ($Cmd.ToLower()) {
    'sync' {
        Write-Host "Running: uv sync"
        uv sync
    }

    'main' {
        Write-Host "Running: uv run python main.py"
        uv run python main.py
    }

    'gdc-dry' {
        $n = if ($Arg) { $Arg } else { 10 }
        Write-Host "Running: uv run python gdc.py --dry-run --max $n"
        uv run python gdc.py --dry-run --max $n
    }

    'gdc' {
        $n = if ($Arg) { $Arg } else { 0 }
        Write-Host "Running: uv run python gdc.py -y --max $n"
        uv run python gdc.py -y --max $n
    }

    'pytest' {
        Write-Host "Running: uv run pytest"
        uv run pytest
    }

    'shell' {
        Write-Host "Opening a shell inside uv-managed environment"
        uv run powershell
    }

    default {
        Write-Host "Unknown command: $Cmd"
        Write-Host "Usage: ./scripts/run.ps1 {sync|main|gdc-dry|gdc|pytest|shell} [arg]"
        exit 1
    }
}
