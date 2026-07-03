# AI-Agent Workflow Toolkit - installer (PowerShell / Windows)
#
# From your project directory:
#   irm https://raw.githubusercontent.com/EvgenVer/Agents-tollkit/master/install.ps1 | iex
# Local/offline test (skip clone, use a local checkout as source):
#   $env:TK_SRC="C:\path\to\toolkit"; .\install.ps1
$REPO   = "EvgenVer/Agents-tollkit"   # <-- set to your public GitHub repo (owner/name)
$BRANCH = "master"

$ErrorActionPreference = "Stop"
$Dest = (Get-Location).Path
Write-Host "Installing AI-Agent Workflow Toolkit into: $Dest"

$Tmp = $null
try {
  if ($env:TK_SRC) {
    $Src = $env:TK_SRC
    Write-Host "Using local source: $Src"
  } else {
    $Tmp = Join-Path $env:TEMP ("tk_" + [guid]::NewGuid().ToString("N"))
    Write-Host "Fetching toolkit from https://github.com/$REPO ($BRANCH) ..."
    # git writes progress ("Cloning into ...") to stderr; under $ErrorActionPreference='Stop'
    # that becomes a terminating NativeCommandError even on a successful clone, and 2>$null
    # does not prevent it in Windows PowerShell 5.1. Relax EAP for the call, capture both
    # streams into a variable (silent on success), and gate on the real exit code.
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $cloneLog = git clone --depth 1 --branch $BRANCH "https://github.com/$REPO.git" $Tmp --quiet 2>&1
    $cloneExit = $LASTEXITCODE
    $ErrorActionPreference = $eap
    if ($cloneExit -ne 0) { throw "clone failed ($cloneExit) - check REPO/BRANCH and that git is installed.`n$cloneLog" }
    $Src = $Tmp
  }

  # 1. Toolkit files (governance - refreshed on update; instance docs never in source -> untouched)
  foreach ($p in @("AGENTS.md","CLAUDE.md","README.md","docs",".agents")) {
    $s = Join-Path $Src $p
    if (Test-Path $s) {
      $d = Join-Path $Dest $p
      if (Test-Path $d) { Remove-Item -Recurse -Force $d }
      Copy-Item -Recurse -Force $s $d
    }
  }
  # .claude/commands (Claude Code slash commands, e.g. /grill, /orchestrate)
  $sc = Join-Path $Src ".claude\commands"
  if (Test-Path $sc) {
    New-Item -ItemType Directory -Force (Join-Path $Dest ".claude") | Out-Null
    $dc = Join-Path $Dest ".claude\commands"
    if (Test-Path $dc) { Remove-Item -Recurse -Force $dc }
    Copy-Item -Recurse -Force $sc $dc
  }
  # Role agents for orchestration (Claude Code + Codex) - copy-if-absent, so a re-install
  # never overwrites user-tuned `model` values.
  foreach ($ag in @(".claude\agents",".codex\agents")) {
    $sa = Join-Path $Src $ag
    if (Test-Path $sa) {
      $da = Join-Path $Dest $ag
      New-Item -ItemType Directory -Force $da | Out-Null
      Get-ChildItem $sa -File | ForEach-Object {
        $df = Join-Path $da $_.Name
        if (-not (Test-Path $df)) { Copy-Item $_.FullName $df }
      }
    }
  }

  # 2. Generate .claude/skills from .agents/skills (native discovery for Claude Code)
  $ss = Join-Path $Src ".agents\skills"
  if (Test-Path $ss) {
    $ds = Join-Path $Dest ".claude\skills"
    if (Test-Path $ds) { Remove-Item -Recurse -Force $ds }
    New-Item -ItemType Directory -Force $ds | Out-Null
    Copy-Item -Recurse -Force (Join-Path $ss "*") $ds
  }

  # 3. Merge secrets section into .gitignore (idempotent - marker-guarded)
  $gi = Join-Path $Dest ".gitignore"
  if (-not (Test-Path $gi)) { New-Item -ItemType File $gi | Out-Null }
  if (-not (Select-String -Path $gi -Pattern 'AI-Agent toolkit' -Quiet -ErrorAction SilentlyContinue)) {
    $sec = @('','# Secrets / env (from AI-Agent toolkit)','.env','.env.*','*.pem','*.key','*.p12','id_rsa*','.ssh/','secrets/','.claude/settings.local.json')
    Add-Content -Path $gi -Value $sec -Encoding utf8
  }

  # 4. git init if this isn't a repo yet
  if (-not (Test-Path (Join-Path $Dest ".git"))) { git init -q | Out-Null }

  Write-Host "`nDone - toolkit installed."
  Write-Host "Next: open Claude Code or Codex in this directory and say:"
  Write-Host '  "Follow AGENTS.md. No DESCRIPTION yet - grill me on <your idea>, then the planning gate, and stop for approval."'
}
finally {
  if ($Tmp -and (Test-Path $Tmp)) { Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue }
}
