$ErrorActionPreference = 'Stop'
$wrapper = Join-Path $PSScriptRoot '..\tinygo.ps1'
$global:P2FlashBuilds = [Collections.Generic.List[object]]::new()
$global:P2FlashLoads = [Collections.Generic.List[object]]::new()
$global:P2FlashBuildExit = 0
$previousPython = $env:P2_FLASH_PYTHON
$env:P2_FLASH_PYTHON = 'P2FlashMockPython'
$testDirectory = Join-Path ([IO.Path]::GetTempPath()) ('p2-flash-test-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $testDirectory

function global:P2FlashMockPython {
    if (!(Test-Path -LiteralPath $args[-1])) { throw 'Loader received a missing image.' }
    $global:P2FlashLoads.Add(@($args))
    $global:LASTEXITCODE = 0
}

function global:wsl.exe {
    $global:LASTEXITCODE = 0
    if ($args -contains 'wslpath') {
        $path = [string]$args[-1]
        if ($args -contains '-w') { return $path.Replace('/mnt/c/', 'C:\').Replace('/', '\') }
        return '/mnt/' + $path.Substring(0, 1).ToLowerInvariant() + '/' + $path.Substring(3).Replace('\', '/')
    }
    if ($args -contains 'printenv') { return '/home/p2test' }
    $global:P2FlashBuilds.Add(@($args))
    $global:LASTEXITCODE = $global:P2FlashBuildExit
    if ($global:P2FlashBuildExit -ne 0) { return }
    $out = ''
    for ($i = 0; $i -lt $args.Count; $i++) {
        if ($args[$i] -eq '-o') { $out = [string]$args[$i + 1] }
        if ([string]$args[$i] -like '-o=*') { $out = ([string]$args[$i]).Substring(3) }
    }
    if (!$out) { throw 'Missing build output.' }
    $out = $out.Replace('/mnt/c/', 'C:\').Replace('/', '\')
    if (![IO.Path]::IsPathRooted($out)) {
        $cwdIndex = [Array]::IndexOf($args, '--cd')
        $cwd = ([string]$args[$cwdIndex + 1]).Replace('/mnt/c/', 'C:\').Replace('/', '\')
        $out = Join-Path $cwd $out
    }
    [IO.File]::WriteAllBytes($out, [byte[]]@(0x7f, 0x45, 0x4c, 0x46))
}

try {
    & $wrapper flash -port=COM12 '-monitor=2.5' -opt=z -scheduler=cores '.\app'
    if ($LASTEXITCODE -ne 0 -or $global:P2FlashLoads.Count -ne 1) { throw 'Flash did not reach loader.' }
    $build = $global:P2FlashBuilds[0]
    foreach ($flag in @('build', '-target=p2', '-opt=z', '-scheduler=cores', './app')) {
        if ($build -notcontains $flag) { throw "Build flag lost: $flag" }
    }
    if ($build -contains '-port=COM12' -or $build -contains '-monitor=2.5') { throw 'Upload options leaked into build.' }
    $load = $global:P2FlashLoads[0]
    if ($load -notcontains 'COM12' -or $load -notcontains '--monitor' -or $load -notcontains '2.5') {
        throw ('Explicit monitor/port options lost: ' + ($load | ConvertTo-Json -Compress))
    }
    if (Test-Path -LiteralPath $load[-1]) { throw 'Temporary ELF was not cleaned up.' }

    $savedOutput = Join-Path $testDirectory 'kept output.elf'
    & $wrapper -WorkRoot '/home/custom' flash -port COM12 -target=p2-gc -o $savedOutput '.\app'
    if (!(Test-Path -LiteralPath $savedOutput)) { throw 'User output should remain available.' }
    if ($global:P2FlashLoads[1] -contains '--monitor') { throw 'Monitoring was enabled without request.' }

    Push-Location $testDirectory
    try {
        & $wrapper flash -o '.\relative output.elf' '.\app'
        $relativeOutput = Join-Path $testDirectory 'relative output.elf'
        if ($global:P2FlashLoads[2][-1] -ne $relativeOutput) { throw 'Relative output did not follow PowerShell current directory.' }
    } finally { Pop-Location }

    $global:P2FlashBuildExit = 23
    & $wrapper flash -port COM12 '.\app'
    if ($LASTEXITCODE -ne 23 -or $global:P2FlashLoads.Count -ne 3) { throw 'Build failure did not prevent upload.' }
    'PASS: RAM flash dispatch, build flags, monitor opt-in, output cleanup, build failure'
} finally {
    Remove-Item Function:\wsl.exe, Function:\P2FlashMockPython
    Remove-Variable P2FlashBuilds, P2FlashLoads, P2FlashBuildExit -Scope Global
    $env:P2_FLASH_PYTHON = $previousPython
    $resolved = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $testDirectory).Path)
    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (!$resolved.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($resolved) -notmatch '^p2-flash-test-[0-9a-f]{32}$') {
        throw 'Unexpected test cleanup directory.'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
