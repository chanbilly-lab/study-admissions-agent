param([ValidateSet('install', 'dev', 'test', 'build', 'typecheck')][string]$Action = 'dev')
$ErrorActionPreference = 'Stop'
$m0Root = Split-Path -Parent $PSScriptRoot
$m0Runtime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$m0NodeDir = Join-Path $m0Runtime 'node\bin'
if (Test-Path -LiteralPath (Join-Path $m0NodeDir 'node.exe')) {
    # Applies only to this process and its child scripts, never to global settings.
    $env:PATH = $m0NodeDir + [IO.Path]::PathSeparator + $env:PATH
}
$m0NodeVersion = (& node --version).TrimStart('v')
if ([version]$m0NodeVersion -lt [version]'22.12.0') {
    throw 'M0 requires Node 22.12+ (tested on Node 24.19.0).'
}
$m0PnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
$m0PnpmPath = if ($m0PnpmCommand) { $m0PnpmCommand.Source } else { Join-Path $m0Runtime 'bin\fallback\pnpm.cmd' }
if (-not (Test-Path -LiteralPath $m0PnpmPath)) { throw 'Install pnpm 11.19.0 before running the web app.' }
if ($Action -eq 'install') {
    & $m0PnpmPath --dir (Join-Path $m0Root 'apps\web') install --frozen-lockfile --store-dir (Join-Path $m0Root '.cache\pnpm')
} else {
    & $m0PnpmPath --dir (Join-Path $m0Root 'apps\web') $Action
}
exit $LASTEXITCODE
