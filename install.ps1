# jakpost-scraper installer for Windows (PowerShell 5.1+).
# Usage:
#   irm https://raw.githubusercontent.com/pear25/scraper/main/install.ps1 | iex

$ErrorActionPreference = 'Stop'

$AppName  = 'jakpost-scraper'
$CmdName  = 'jakpost-scrape'
$UvInstallerUrl = 'https://astral.sh/uv/install.ps1'

function Write-Header($text) {
    Write-Host ""
    Write-Host "=== $text ===" -ForegroundColor Cyan
}

function Write-Warn($text) {
    Write-Host $text -ForegroundColor Yellow
}

function Fail($text) {
    Write-Host "Error: $text" -ForegroundColor Red
    exit 1
}

Write-Header "Checking prerequisites"
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "PowerShell 5.1 or newer is required."
}
Write-Host "PowerShell: $($PSVersionTable.PSVersion)"

Write-Header "Installing uv (Python tool manager)"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Write-Host "uv: already installed ($(& uv --version))"
} else {
    Write-Host "Installing uv from $UvInstallerUrl ..."
    Invoke-RestMethod $UvInstallerUrl | Invoke-Expression
    # uv installs to %USERPROFILE%\.local\bin and updates the User PATH.
    # Make it visible to this session so the next step finds it.
    $userLocalBin = Join-Path $env:USERPROFILE '.local\bin'
    if (Test-Path $userLocalBin) {
        $env:PATH = "$userLocalBin;$env:PATH"
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail "uv installed but not on PATH. Open a new PowerShell and re-run."
    }
    Write-Host "uv: installed ($(& uv --version))"
}

Write-Header "Installing $AppName"
& uv tool install --upgrade $AppName
if ($LASTEXITCODE -ne 0) {
    Fail "uv tool install failed (exit $LASTEXITCODE)."
}

Write-Header "Checking for the claude CLI (used for summarization)"
$claude = Get-Command claude -ErrorAction SilentlyContinue
$claudeMissing = $false
if ($claude) {
    Write-Host "claude: found ($($claude.Source))"
} else {
    Write-Warn "claude CLI not found."
    Write-Warn "Summarization needs the claude CLI installed and authenticated."
    Write-Warn "Install: https://docs.claude.com/en/docs/claude-code/quickstart"
    Write-Warn "Without it, run jakpost-scrape with --no-summary."
    $claudeMissing = $true
}

Write-Header "Detecting config location"
$configPath = Join-Path $env:APPDATA "$AppName\config.yaml"

Write-Header "Install complete"
Write-Host ""
Write-Host "Command:  $CmdName"
Write-Host "Config:   $configPath"
Write-Host "          (written automatically on first run)"
Write-Host ""
Write-Host "Try:      $CmdName --help"
if ($claudeMissing) {
    Write-Host "          $CmdName --no-summary           # works without claude CLI"
}
Write-Host ""
Write-Host "Upgrade:  $CmdName --upgrade"
Write-Host ""
