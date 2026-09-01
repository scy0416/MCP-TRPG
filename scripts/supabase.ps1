param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SupabaseArguments
)

$expectedVersion = '2.116.0'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localCli = Join-Path $projectRoot ".tools\supabase\$expectedVersion\supabase.exe"

if (Test-Path -LiteralPath $localCli) {
    $cli = $localCli
} else {
    $command = Get-Command supabase -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "Supabase CLI $expectedVersion is not installed. See docs/supabase-setup.md."
    }
    $cli = $command.Source
}

$actualVersion = (& $cli --version).Trim()
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to read the Supabase CLI version.'
}
if ($actualVersion -ne $expectedVersion) {
    throw "Supabase CLI $expectedVersion is required; found $actualVersion."
}

& $cli @SupabaseArguments
exit $LASTEXITCODE

