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
  [switch]$DryRun
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$urlsFile = Join-Path $root 'breast_wsi_urls.txt'
$outdir = Join-Path $root $OutDir

if (-not (Test-Path $urlsFile)) {
  Write-Error "Missing $urlsFile. Run script.py to generate it."
  exit 2
}

if (-not (Test-Path $outdir)) { New-Item -ItemType Directory -Path $outdir | Out-Null }

# Prefer aria2c. Filter out URLs whose basenames already exist in the outdir.
if (Get-Command aria2c -ErrorAction SilentlyContinue) {
  Write-Output "Using aria2c with concurrency=$Concurrency, outdir=$outdir"
  $tmp = [System.IO.Path]::GetTempFileName()
  try {
    Get-Content $urlsFile | ForEach-Object {
      if ([string]::IsNullOrWhiteSpace($_)) { return }
      $name = [System.IO.Path]::GetFileName($_.TrimEnd('/'))
      if (-not (Test-Path (Join-Path $outdir $name))) {
        $_ | Out-File -FilePath $tmp -Append -Encoding utf8
      } else {
        Write-Output "Skipping existing: $name"
      }
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
foreach ($url in $urls) {
  $name = [System.IO.Path]::GetFileName($url.TrimEnd('/'))
  $dest = Join-Path $outdir $name
  if (Test-Path $dest) {
    Write-Output "Skipping existing: $name"
    continue
  }
  if ($DryRun) {
    Write-Output "Would download: $name -> $url"
    continue
  }
  $jobs += Start-Job -ArgumentList $url, $dest -ScriptBlock {
    param($u, $d)
    try {
      Start-BitsTransfer -Source $u -Destination $d -RetryInterval 10 -RetryTimeout 600 -DisplayName "download $([System.IO.Path]::GetFileName($u))"
    } catch {
      Write-Error "Failed $u: $_"
    }
  }
  # throttle: if job count reaches concurrency, wait for any to complete
  while (($jobs | Where-Object { $_.State -eq 'Running' }).Count -ge $Concurrency) {
    Start-Sleep -Seconds 1
  }
}

if (-not $DryRun) { Write-Output "Started $($jobs.Count) background jobs. Use Get-Job and Receive-Job to inspect results." }

