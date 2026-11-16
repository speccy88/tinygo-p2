# This must remain a plain script: CmdletBinding/Parameter attributes reserve
# common PowerShell flags such as -o and would swallow TinyGo's own options.
# Optional wrapper arguments -Distro and -WorkRoot go before the TinyGo command.
$ErrorActionPreference = 'Stop'
$Distro = 'Ubuntu-26.04'
$WorkRoot = ''
$index = 0
while ($index -lt $args.Count) {
    $option = [string]$args[$index]
    if ($option -eq '--') { $index++; break }
    if ($option -notin @('-Distro', '--distro', '-WorkRoot', '--work-root')) { break }
    if ($index + 1 -ge $args.Count) { throw "Missing value for $option" }
    if ($option -in @('-Distro', '--distro')) {
        $Distro = [string]$args[$index + 1]
    } else {
        $WorkRoot = [string]$args[$index + 1]
    }
    $index += 2
}
$TinyGoArguments = @()
if ($index -lt $args.Count) { $TinyGoArguments = @($args[$index..($args.Count - 1)]) }
if ($TinyGoArguments.Count -gt 0 -and $TinyGoArguments[0] -eq 'flash') {
    $flashArguments = @('-Distro', $Distro)
    if ($WorkRoot) { $flashArguments += @('-WorkRoot', $WorkRoot) }
    if ($TinyGoArguments.Count -gt 1) { $flashArguments += $TinyGoArguments[1..($TinyGoArguments.Count - 1)] }
    & (Join-Path $PSScriptRoot 'flash.ps1') @flashArguments
    exit $LASTEXITCODE
}

function Convert-ToLinuxPath([string]$Value, [bool]$IsPath = $false) {
    if ($Value -match '^(?:[A-Za-z]:[\\/]|\\\\)') {
        $translated = & wsl.exe -d $Distro --exec wslpath -a $Value
        if ($LASTEXITCODE -ne 0 -or !$translated) { throw "Cannot translate argument path: $Value" }
        return $translated.Trim()
    }
    if ($Value -match '^\.\.?\\' -or
        ($Value.Contains('\') -and ($IsPath -or (Test-Path -LiteralPath $Value)))) {
        return $Value.Replace('\', '/')
    }
    return $Value
}

if (!$WorkRoot) {
    $linuxUserHome = & wsl.exe -d $Distro --exec printenv HOME
    if ($LASTEXITCODE -ne 0 -or !$linuxUserHome) { throw 'Cannot determine WSL home directory.' }
    $linuxUserHome = $linuxUserHome.Trim()
    $WorkRoot = "$linuxUserHome/tinygo-p2-work"
}
$WorkRoot = Convert-ToLinuxPath $WorkRoot $true
if (!$TinyGoArguments.Count) { $TinyGoArguments = @('help') }
$forward = [System.Collections.Generic.List[string]]::new()
$pathFlags = @('-o', '--out', '-target', '-C', '-ocd-config')
$previous = ''
foreach ($arg in $TinyGoArguments) {
    $value = [string]$arg
    if ($value -match '^(-[^=]+)=(.*)$') {
        $flag, $flagValue = $Matches[1], $Matches[2]
        if ($flag -in $pathFlags -or $flagValue -match '^(?:[A-Za-z]:[\\/]|\\\\)') {
            $value = $flag + '=' + (Convert-ToLinuxPath $flagValue $true)
        }
    } elseif (!$value.StartsWith('-')) {
        $value = Convert-ToLinuxPath $value ($previous -in $pathFlags)
    }
    $forward.Add($value)
    $previous = [string]$arg
}
$linuxCwd = & wsl.exe -d $Distro --exec wslpath -a $PWD.Path
if ($LASTEXITCODE -ne 0 -or !$linuxCwd) { throw 'Cannot translate working directory.' }
$linuxCwd = $linuxCwd.Trim()
$toolRoot = "$WorkRoot/tinygo"
$bundleHash = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'source-manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant()
$cacheRoot = "$WorkRoot/cache/$bundleHash"
if ($env:XDG_CACHE_HOME) { $cacheRoot = Convert-ToLinuxPath $env:XDG_CACHE_HOME $true }
$goExperiment = 'nojsonv2'
if (Test-Path Env:GOEXPERIMENT) { $goExperiment = $env:GOEXPERIMENT }
& wsl.exe -d $Distro --cd $linuxCwd --exec env `
    "PATH=$WorkRoot/llvm15-build/bin:$WorkRoot/go/bin:/usr/local/bin:/usr/bin:/bin" `
    "TINYGOROOT=$toolRoot" `
    "GOROOT=$WorkRoot/go" `
    "XDG_CACHE_HOME=$cacheRoot" `
    "GOEXPERIMENT=$goExperiment" `
    "LD_LIBRARY_PATH=$WorkRoot/llvm15-build/lib" `
    "$toolRoot/build/tinygo" @forward
exit $LASTEXITCODE
