<#
download_wsi.ps1
Usage: Open PowerShell, run:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\download_wsi.ps1 -Concurrency 4

This script reads `breast_wsi_urls.txt` and downloads files into .\breast_wsi_downloads\
Prefers aria2c (if installed). Otherwise uses Start-BitsTransfer in parallel.
#>
param(
  [int]$Concurrency = 4,
  [string]$OutDir = "breast_wsi_downloads",
  [switch]$DryRun,
  [switch]$ShowProgress
  ,
  [int]$MaxUrls = 0
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$urlsFile = Join-Path $root 'breast_wsi_urls.txt'

# Allow absolute or relative OutDir. If user provided an absolute path, use it directly.
if ([System.IO.Path]::IsPathRooted($OutDir)) {
  $outdir = $OutDir
} else {
  $outdir = Join-Path $root $OutDir
}

if (-not (Test-Path $urlsFile)) {
  Write-Error "Missing $urlsFile. Run script.py to generate it."
  exit 2
}

if (-not (Test-Path $outdir)) { New-Item -ItemType Directory -Path $outdir | Out-Null }

# If MaxUrls provided (>0), calculate how many new downloads we should allow
if ($MaxUrls -gt 0) {
  $existingCount = (Get-ChildItem $outdir -File -ErrorAction SilentlyContinue | Measure-Object).Count
  $remaining = $MaxUrls - $existingCount
  if ($remaining -le 0) {
    Write-Output "Already have $existingCount files in $outdir which meets or exceeds --MaxUrls $MaxUrls. Nothing to do."
    exit 0
  }
  Write-Output "MaxUrls specified: $MaxUrls. Existing files: $existingCount. Will download up to $remaining new files."
} else {
  $remaining = 0 # 0 means unlimited
}

# Prefer aria2c. Filter out URLs whose basenames already exist in the outdir.
if (Get-Command aria2c -ErrorAction SilentlyContinue) {
  Write-Output "Using aria2c with concurrency=$Concurrency, outdir=$outdir"
  $tmp = [System.IO.Path]::GetTempFileName()
  try {
    $added = 0
    foreach ($line in Get-Content $urlsFile) {
      if ([string]::IsNullOrWhiteSpace($line)) { continue }
      $name = [System.IO.Path]::GetFileName($line.TrimEnd('/'))
      if (Test-Path (Join-Path $outdir $name)) {
        Write-Output "Skipping existing: $name"
        continue
      }
      # If MaxUrls specified, stop after adding the remaining count
      if ($remaining -gt 0 -and $added -ge $remaining) { break }

      $line | Out-File -FilePath $tmp -Append -Encoding utf8
      $added++
    }

    if ($DryRun) {
      Write-Output "-- Dry run: the following URLs would be passed to aria2c:"
      if ((Get-Item $tmp).Length -gt 0) { Get-Content $tmp | ForEach-Object { Write-Output $_ } } else { Write-Output "(none)" }
    } else {
      if ((Get-Item $tmp).Length -gt 0) {
        & aria2c.exe -i $tmp -d $outdir -x 4 -s 4 -j $Concurrency --auto-file-renaming=false --continue
      } else {
        Write-Output "No new files to download."
      }
    }
  } finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
  }
  exit 0
}

# PowerShell fallback: Start background jobs that use Start-BitsTransfer and skip existing files

$urls = Get-Content $urlsFile | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

$jobs = @()
$added = 0
foreach ($url in $urls) {
  $name = [System.IO.Path]::GetFileName($url.TrimEnd('/'))
  $dest = Join-Path $outdir $name
  if (Test-Path $dest) {
    Write-Output "Skipping existing: $name"
    continue
  }

  # If MaxUrls specified, stop after scheduling the remaining count
  if ($remaining -gt 0 -and $added -ge $remaining) { break }

  if ($DryRun) {
    Write-Output "Would download: $name -> $url"
    $added++
    continue
  }

  $jobs += Start-Job -ArgumentList $url, $dest -ScriptBlock {
    param($u, $d)
    try {
      Write-Output "Starting download: $u -> $d"
      Start-BitsTransfer -Source $u -Destination $d -RetryInterval 10 -RetryTimeout 600 -DisplayName "download $([System.IO.Path]::GetFileName($u))"
      Write-Output "Completed: $d"
    } catch {
      Write-Error "Failed $u: $_"
    }
  }
  $added++
  # throttle: if job count reaches concurrency, wait for any to complete
  while (($jobs | Where-Object { $_.State -eq 'Running' }).Count -ge $Concurrency) {
    Start-Sleep -Seconds 1
  }
}

if (-not $DryRun) {
  if (-not $ShowProgress) {
    Write-Output "Started $($jobs.Count) background jobs. Use Get-Job and Receive-Job to inspect results."
  } else {
    Write-Output "Started $($jobs.Count) background jobs. Showing progress (Ctrl+C to stop monitoring)"

    # Polling loop: show job counts and BITS transfer progress until no running jobs remain
    while ((Get-Job -State Running).Count -gt 0) {
      $running = (Get-Job -State Running).Count
      $completed = (Get-Job -State Completed).Count
      $failed = (Get-Job -State Failed).Count
      $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
      Write-Output "[$timestamp] Running: $running  Completed: $completed  Failed: $failed"

      # Show BITS transfer summary (if any)
      $transfers = Get-BitsTransfer -ErrorAction SilentlyContinue
      if ($transfers) {
        $transfers | ForEach-Object {
          $pct = if ($_.BytesTotal -gt 0) { [math]::Round(($_.BytesTransferred / $_.BytesTotal) * 100, 1) } else { '(?)' }
          $mbTransferred = [math]::Round($_.BytesTransferred / 1MB, 1)
          $mbTotal = if ($_.BytesTotal -gt 0) { [math]::Round($_.BytesTotal / 1MB, 1) } else { '(?)' }
          Write-Output "  BITS: $($_.DisplayName)  State=$($_.JobState)  $mbTransferred MB / $mbTotal MB  $pct%"
        }
      }

      Start-Sleep -Seconds 2
    }

    # All jobs done; show final counts and collect outputs
    $running = (Get-Job -State Running).Count
    $completed = (Get-Job -State Completed).Count
    $failed = (Get-Job -State Failed).Count
    Write-Output "All jobs finished. Running: $running  Completed: $completed  Failed: $failed"

    # Print job outputs and clean up job objects
    $allJobs = Get-Job
    foreach ($j in $allJobs) {
      Write-Output "--- Job Id $($j.Id)  Name: $($j.Name)  State: $($j.State) ---"
      try {
        Receive-Job -Id $j.Id -ErrorAction SilentlyContinue
      } catch {
        # ignore
      }
      Remove-Job -Id $j.Id -ErrorAction SilentlyContinue
    }
  }
}

