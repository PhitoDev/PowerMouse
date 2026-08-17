# Copy tkinter into a Briefcase Windows app bundle.
#
# Briefcase Windows apps embed the python.org "embeddable" distribution,
# which ships without tkinter, but the dwell palette (powermouse.palette)
# is a Tk app. This script copies tkinter from a full CPython install of
# the same feature version (e.g. one provided by actions/setup-python)
# into the bundle, mirroring the full-install layout (DLLs\, tcl\, Lib\)
# so Tcl's default init-script search works.
#
# Run it after `briefcase create` and before `briefcase build`:
#   .\scripts\windows_add_tkinter.ps1 -BundleRoot build\powermouse\windows\app -SourcePrefix C:\hostedtoolcache\...\python\3.14.x\x64
param(
    [Parameter(Mandatory = $true)][string]$BundleRoot,
    [Parameter(Mandatory = $true)][string]$SourcePrefix
)
$ErrorActionPreference = "Stop"

# Locate the embedded Python directory (it contains python3XY._pth).
$pth = Get-ChildItem -Path $BundleRoot -Recurse -Filter "python3*._pth" | Select-Object -First 1
if (-not $pth) { throw "No embedded python ._pth found under $BundleRoot" }
$embed = $pth.DirectoryName
Write-Host "Embedded Python found at $embed"

if (-not (Test-Path "$SourcePrefix\Lib\tkinter")) {
    throw "$SourcePrefix does not look like a full CPython install (no Lib\tkinter)"
}

# 1. Native pieces: _tkinter.pyd plus the Tcl/Tk (and zlib) DLLs it loads.
New-Item -ItemType Directory -Force -Path "$embed\DLLs" | Out-Null
Copy-Item "$SourcePrefix\DLLs\_tkinter.pyd" "$embed\DLLs\"
Copy-Item "$SourcePrefix\DLLs\tcl*.dll" "$embed\DLLs\"
Copy-Item "$SourcePrefix\DLLs\tk*.dll" "$embed\DLLs\"
if (Test-Path "$SourcePrefix\DLLs\zlib1.dll") {
    Copy-Item "$SourcePrefix\DLLs\zlib1.dll" "$embed\DLLs\"
}

# 2. Tcl/Tk init scripts; Tcl searches <dll dir>\..\tcl\tclX.Y by default.
Copy-Item -Recurse -Force "$SourcePrefix\tcl" "$embed\tcl"

# 3. The tkinter stdlib package.
New-Item -ItemType Directory -Force -Path "$embed\Lib" | Out-Null
Copy-Item -Recurse -Force "$SourcePrefix\Lib\tkinter" "$embed\Lib\tkinter"

# 4. Put Lib and DLLs on the embedded interpreter's path.
$lines = Get-Content $pth.FullName
foreach ($entry in @("Lib", "DLLs")) {
    if ($lines -notcontains $entry) { Add-Content -Path $pth.FullName -Value $entry }
}

# 5. Smoke test: initialize Tcl headlessly with the bundled interpreter.
$bundledPython = Join-Path $embed "python.exe"
if (Test-Path $bundledPython) {
    $version = & $bundledPython -c "import tkinter; print(tkinter.Tcl().eval('info patchlevel'))"
    Write-Host "tkinter bundled OK (Tcl $version)"
} else {
    Write-Warning "No python.exe in bundle; skipped tkinter smoke test"
}
