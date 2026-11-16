# RAM-only P2 upload. Plain argument parsing preserves TinyGo flags such as -o.
$ErrorActionPreference = 'Stop'
$Distro = 'Ubuntu-26.04'
$WorkRoot = ''
$Port = 'COM12'
$monitorSeconds = 0.0
$outputFile = ''
$hasTarget = $false
$buildArguments = [System.Collections.Generic.List[string]]::new()
for ($index = 0; $index -lt $args.Count; $index++) {
    $arg = [string]$args[$index]
    if ($arg -in @('-Distro', '--distro', '-WorkRoot', '--work-root', '-port', '--port')) {
        if ($index + 1 -ge $args.Count) { throw "Missing value for $arg" }
        $index++
        $value = [string]$args[$index]
        switch ($arg) {
            { $_ -in @('-Distro', '--distro') } { $Distro = $value }
            { $_ -in @('-WorkRoot', '--work-root') } { $WorkRoot = $value }
            default { $Port = $value }
        }
        continue
    }
    if ($arg -match '^--?port=(.+)$') { $Port = $Matches[1]; continue }
    if ($arg -in @('-monitor', '--monitor') -or $arg -match '^--?monitor=') {
        $value = '10'
        if ($arg.Contains('=')) {
            $value = $arg.Substring($arg.IndexOf('=') + 1)
        } elseif ($index + 1 -lt $args.Count -and [string]$args[$index + 1] -match '^\d+(\.\d+)?$') {
            $index++
            $value = [string]$args[$index]
        }
        $monitorSeconds = [double]::Parse($value, [Globalization.CultureInfo]::InvariantCulture)
        if ([double]::IsNaN($monitorSeconds) -or $monitorSeconds -lt 0 -or $monitorSeconds -gt 3600) {
            throw 'Monitor duration must be between 0 and 3600 seconds.'
        }
        continue
    }
    if ($arg -eq '-o') {
        if ($index + 1 -ge $args.Count) { throw 'Missing -o output path.' }
        $index++
        $outputFile = [string]$args[$index]
        $buildArguments.Add('-o')
        $buildArguments.Add($outputFile)
        continue
    }
    if ($arg -match '^-o=(.+)$') { $outputFile = $Matches[1] }
    if ($arg -eq '-target' -or $arg.StartsWith('-target=')) { $hasTarget = $true }
    $buildArguments.Add($arg)
}
if ($outputFile -and [IO.Path]::GetExtension($outputFile) -ne '.elf') {
    throw 'RAM upload requires an ELF output path ending in .elf.'
}
$python = $env:P2_FLASH_PYTHON
if (!$python) {
    $python = Join-Path $PSScriptRoot 'hil\.venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) { $python = 'python' }
}
$null = Get-Command $python -ErrorAction Stop
$temporaryDirectory = $null
try {
    if (!$outputFile) {
        $temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ('tinygo-p2-' + [guid]::NewGuid().ToString('N'))
        $null = New-Item -ItemType Directory -Path $temporaryDirectory
        $outputFile = Join-Path $temporaryDirectory 'application.elf'
        $buildArguments.Insert(0, $outputFile)
        $buildArguments.Insert(0, '-o')
    }
    if (!$hasTarget) { $buildArguments.Insert(0, '-target=p2') }
    $compilerArguments = @('-Distro', $Distro)
    if ($WorkRoot) { $compilerArguments += @('-WorkRoot', $WorkRoot) }
    $compilerArguments += 'build'
    $compilerArguments += $buildArguments.ToArray()
    & (Join-Path $PSScriptRoot 'tinygo.ps1') @compilerArguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if ($outputFile.StartsWith('/') -and !$outputFile.StartsWith('//')) {
        $windowsOutput = & wsl.exe -d $Distro --exec wslpath -w $outputFile
        if ($LASTEXITCODE -ne 0 -or !$windowsOutput) { throw 'Cannot translate ELF path for Windows upload.' }
        $windowsOutput = $windowsOutput.Trim()
    } else {
        $windowsOutput = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($outputFile.Replace('/', '\'))
    }
    if (!(Test-Path -LiteralPath $windowsOutput -PathType Leaf)) { throw "Compiler did not produce $windowsOutput" }
    $loaderArguments = @((Join-Path $PSScriptRoot 'hil\p2ram.py'), '--port', $Port)
    if ($monitorSeconds -gt 0) {
        $loaderArguments += @('--monitor', $monitorSeconds.ToString([Globalization.CultureInfo]::InvariantCulture))
    }
    $loaderArguments += $windowsOutput
    & $python @loaderArguments
    exit $LASTEXITCODE
} finally {
    if ($temporaryDirectory -and (Test-Path -LiteralPath $temporaryDirectory)) {
        $resolved = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $temporaryDirectory).Path)
        $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        if (!$resolved.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -or
            [IO.Path]::GetFileName($resolved) -notmatch '^tinygo-p2-[0-9a-f]{32}$') {
            throw "Refusing to remove unexpected temporary directory: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
