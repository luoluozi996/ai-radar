[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$Date,

  [int]$MaxAccounts = 8,
  [int]$MaxQueries = 2,
  [int]$Limit = 8
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$fetchScript = Join-Path $scriptRoot 'fetch_x_posts.py'

function Find-Python {
  foreach ($commandName in @('python', 'py')) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
  }

  $appPathKeys = @(
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\python.exe',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\python.exe'
  )
  foreach ($key in $appPathKeys) {
    if (Test-Path $key) {
      $path = (Get-ItemProperty -Path $key -ErrorAction Stop).'(default)'
      if ($path) { return $path }
    }
  }

  throw 'python_runtime_not_found'
}

$python = Find-Python
& $python $fetchScript --date $Date --max-accounts $MaxAccounts --max-queries $MaxQueries --limit $Limit
exit $LASTEXITCODE
