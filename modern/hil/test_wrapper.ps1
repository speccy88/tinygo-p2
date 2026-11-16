$ErrorActionPreference = 'Stop'
$wrapper = Join-Path $PSScriptRoot '..\tinygo.ps1'
$global:P2MockCalls = [System.Collections.Generic.List[object]]::new()
$global:P2MockExitCode = 0
$hadGoExperiment = Test-Path Env:GOEXPERIMENT
$previousGoExperiment = $env:GOEXPERIMENT

# Exercise PowerShell's real script argument binder; the WSL process itself is
# replaced so these tests never invoke a compiler or mutate a build tree.
function global:wsl.exe {
    $global:LASTEXITCODE = 0
    if ($args -contains 'wslpath') {
        $path = [string]$args[-1]
        if ($path -match '^\\\\wsl(?:\.localhost|\$)\\[^\\]+(.*)$') {
            $Matches[1].Replace('\', '/')
        } elseif ($path -match '^[A-Za-z]:[\\/]') {
            '/mnt/' + $path.Substring(0, 1).ToLowerInvariant() + '/' + $path.Substring(3).Replace('\', '/')
        } else { throw "Unexpected mock path $path" }
    } elseif ($args -contains 'printenv') {
        '/home/p2test'
    } else {
        $global:P2MockCalls.Add(@($args))
        $global:LASTEXITCODE = $global:P2MockExitCode
    }
}

function Assert-Arguments([string[]]$Expected) {
    $call = $global:P2MockCalls[$global:P2MockCalls.Count - 1]
    $tool = -1
    for ($i = 0; $i -lt $call.Count; $i++) {
        if ([string]$call[$i] -like '*/tinygo/build/tinygo') { $tool = $i; break }
    }
    if ($tool -lt 0) { throw 'Missing TinyGo executable in forwarded command' }
    $actual = @($call[($tool + 1)..($call.Count - 1)])
    if (($actual | ConvertTo-Json -Compress) -cne ($Expected | ConvertTo-Json -Compress)) {
        throw "Forwarded arguments differ: $($actual | ConvertTo-Json -Compress)"
    }
}

try {
    Remove-Item Env:GOEXPERIMENT -ErrorAction SilentlyContinue
    & $wrapper -WorkRoot '/home/p2 work' build -target=p2 -o 'C:\Test Folder\out.elf' '.\main.go'
    Assert-Arguments @('build', '-target=p2', '-o', '/mnt/c/Test Folder/out.elf', './main.go')
    if ($global:P2MockCalls[-1] -notcontains 'GOEXPERIMENT=nojsonv2') { throw 'Compact JSON default was lost' }

    $env:GOEXPERIMENT = 'jsonv2'
    & $wrapper version
    if ($global:P2MockCalls[-1] -notcontains 'GOEXPERIMENT=jsonv2') { throw 'Explicit GOEXPERIMENT override was lost' }
    $env:GOEXPERIMENT = ''
    & $wrapper version
    if ($global:P2MockCalls[-1] -notcontains 'GOEXPERIMENT=') { throw 'Explicit empty GOEXPERIMENT override was lost' }
    Remove-Item Env:GOEXPERIMENT

    & $wrapper -Distro 'Ubuntu-26.04' build '-target=C:\Test Folder\board.json' '-o=build\app.elf' -ldflags '-X=main.value=a\b' '..\app'
    Assert-Arguments @('build', '-target=/mnt/c/Test Folder/board.json', '-o=build/app.elf', '-ldflags', '-X=main.value=a\b', '../app')

    & $wrapper build '-o=\\wsl.localhost\Ubuntu-26.04\home\p2test\out.elf' '\\wsl$\Ubuntu-26.04\home\p2test\main.go'
    Assert-Arguments @('build', '-o=/home/p2test/out.elf', '/home/p2test/main.go')

    & $wrapper -- -help
    Assert-Arguments @('-help')

    & $wrapper
    Assert-Arguments @('help')

    $global:P2MockExitCode = 17
    & $wrapper version
    if ($LASTEXITCODE -ne 17) { throw 'Compiler exit code was lost' }
    'PASS: wrapper forwarding, paths, GOEXPERIMENT default/overrides, help, and exit status'
} finally {
    if ($hadGoExperiment) { $env:GOEXPERIMENT = $previousGoExperiment }
    else { Remove-Item Env:GOEXPERIMENT -ErrorAction SilentlyContinue }
    Remove-Item Function:\wsl.exe
    Remove-Variable P2MockCalls, P2MockExitCode -Scope Global
}
