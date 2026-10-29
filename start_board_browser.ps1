# Run from the extracted project directory in PowerShell. No elevation needed.
# Dedicated public-only profile: never log into personal accounts in this browser.
$ErrorActionPreference = 'Stop'
$candidates = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "${env:LOCALAPPDATA}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
)
$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { throw 'Install Chrome or Edge first. No browser will be downloaded automatically.' }
if (Get-NetTCPConnection -LocalPort 9222 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 9222 is already in use. Verify that browser or stop it before running this launcher.'
}
$profile = Join-Path $env:LOCALAPPDATA 'JobHunter\PublicBoardBrowser'
Start-Process -FilePath $browser -ArgumentList @(
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9222',
    "--user-data-dir=`"$profile`"", '--no-first-run', 'about:blank'
)
$env:JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT = 'browser'
$env:JOBHUNTER_BOARD_BROWSER_CDP = 'http://127.0.0.1:9222'
Write-Host 'Dedicated browser started. Run the following in THIS terminal after installing requirements-local-browser.txt:'
Write-Host 'python run_local.py serve'
Write-Host 'Use a public-only profile. Local debugging grants browser control to other local processes. Close it when finished.'
