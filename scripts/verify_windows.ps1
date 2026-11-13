# scripts/verify_windows.ps1 — Windows verification (G7, PCD-011)
#
# Checks that the Windows environment is suitable for JobHunter:
#   * Windows OS
#   * Python 3.12-3.14
#   * WeasyPrint importable (needs GTK/Pango runtime)
#   * data/ directory writable
#   * port availability
#
# Exit code 0 = all checks passed; non-zero = failure.
# CI runs this on windows-latest after the dependency install.

$ErrorActionPreference = "Stop"
$failures = @()

function Check($name, $condition, $detail) {
    if ($condition) {
        Write-Host "  OK   $name"
    } else {
        Write-Host "  FAIL $name - $detail"
        $script:failures += $name
    }
}

Write-Host "=== Windows verification (G7, PCD-011) ==="

# 1. OS
$isWindows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
Check "Windows OS" $isWindows "not running on Windows"

# 2. Python version (try python3.12 first, then python)
$pythonCmd = $null
if (Get-Command python3.12 -ErrorAction SilentlyContinue) { $pythonCmd = "python3.12" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonCmd = "python" }

if (-not $pythonCmd) {
    Check "Python 3.12-3.14" $false "no python command found"
} else {
    $pythonVersion = & $pythonCmd --version 2>&1
    Write-Host "  Python ($pythonCmd): $pythonVersion"
    $pyMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
    if ($pyMatch) {
        $pyMajor = [int]$Matches[1]
        $pyMinor = [int]$Matches[2]
        $pyOk = ($pyMajor -eq 3 -and $pyMinor -ge 12 -and $pyMinor -le 14)
    } else {
        $pyOk = $false
    }
    Check "Python 3.12-3.14" $pyOk "found $pythonVersion with $pythonCmd"
}

# 3. WeasyPrint importable
$weasyOk = $false
try {
    & $pythonCmd -c "import weasyprint; print(weasyprint.__version__)" 2>$null
    if ($LASTEXITCODE -eq 0) { $weasyOk = $true }
} catch {}
Check "WeasyPrint importable" $weasyOk "weasyprint could not be imported (GTK/Pango runtime may be missing)"

# 4. GTK/Pango runtime present (MSYS2)
$gtkDll = Test-Path "C:\msys64\mingw64\bin\libgtk-3-0.dll"
$pangoDll = Test-Path "C:\msys64\mingw64\bin\libpango-1.0-0.dll"
$gobjectDll = Test-Path "C:\msys64\mingw64\bin\libgobject-2.0-0.dll"
$gtkOk = $gtkDll -and $pangoDll -and $gobjectDll
Check "GTK/Pango runtime (MSYS2)" $gtkOk "missing one or more of libgtk-3-0.dll, libpango-1.0-0.dll, libgobject-2.0-0.dll in C:\msys64\mingw64\bin"

# 5. data/ directory writable
$dataDir = Resolve-Path "data" -ErrorAction SilentlyContinue
if (-not $dataDir) { New-Item -ItemType Directory -Path "data" -Force | Out-Null }
$dataWritable = $false
try {
    $testFile = Join-Path $dataDir.Path ".write_test"
    Set-Content -Path $testFile -Value "ok"
    Remove-Item -Path $testFile -Force
    $dataWritable = $true
} catch {}
Check "data/ writable" $dataWritable "data/ directory is not writable"

# 6. Port 8765 availability (app default)
$portFree = $false
try {
    $socket = New-Object System.Net.Sockets.TcpClient
    $result = $socket.BeginConnect("127.0.0.1", 8765, $null, $null)
    $success = $result.AsyncWaitHandle.WaitOne(1000, $false)
    if ($success) { $socket.EndConnect($result); $socket.Close() }
    else { $portFree = $true }
    $socket.Close()
} catch { $portFree = $true }
Check "Port 8765 available" $portFree "port 8765 is in use"

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "VERIFY FAILED: $($failures.Count) check(s) failed: $($failures -join ', ')" -ForegroundColor Red
    exit 1
} else {
    Write-Host "VERIFY PASSED: all checks OK" -ForegroundColor Green
    exit 0
}
