# Clean installation only. For an existing project, follow README: Update an existing project.
[CmdletBinding()]
param([switch]$DryRun, [switch]$MigrateLegacy, [string]$Source)
$ErrorActionPreference = "Stop"
if ($MigrateLegacy) { throw "Automatic migration was removed. Follow README: Update an existing project." }
$destination = (Get-Location).Path
$download = $null
$utf8 = New-Object System.Text.UTF8Encoding($false)
$files = New-Object 'System.Collections.Generic.List[object]'

function Assert-PlainPath([string]$Path) {
  $item = Get-Item -LiteralPath $Path -Force
  while ($null -ne $item) {
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Links and junctions are not supported." }
    if ($item.Name -match '^(?i:secrets|\.ssh|\.aws|\.azure|gcloud|credentials|credential-store|token-store|\.env.*|id_rsa.*)$' -or
        $item.Name -match '(?i)\.(pem|key|p12)$') { throw "Protected paths are not supported." }
    if ($item.LinkType -eq "HardLink") { throw "Hard links are not supported." }
    $item = if ($item.PSIsContainer) { $item.Parent } else { $item.Directory }
  }
}
function Assert-Clean {
  Assert-PlainPath $destination
  foreach ($item in Get-ChildItem -LiteralPath $destination -Force) {
    if ($item.Name -eq ".git" -and $item.PSIsContainer -and
        -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
    if (-not $item.PSIsContainer -and $item.Name -cmatch '^(README(\.md)?|LICENSE(\.md)?|\.gitignore|\.gitattributes)$') {
      Assert-PlainPath $item.FullName
      continue
    }
    throw "Existing project detected. Nothing installed. Follow README: Update an existing project."
  }
}
function Add-File([string]$Path, [string]$Relative) {
  Assert-PlainPath $Path
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing source file." }
  if ($Relative -match "[\t\r\n]") { throw "Unsupported filename." }
  $files.Add([pscustomobject]@{ Source=$Path; Relative=$Relative }) | Out-Null
}
function Add-Tree([string]$Path, [string]$Relative) {
  Assert-PlainPath $Path
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) { throw "Missing source directory." }
  foreach ($item in Get-ChildItem -LiteralPath $Path -Force | Sort-Object Name) {
    if ($item.Name -eq "__pycache__" -or $item.Name -like "*.pyc") { continue }
    Assert-PlainPath $item.FullName
    $child = "$Relative/$($item.Name)"
    if ($item.PSIsContainer) { Add-Tree $item.FullName $child } else { Add-File $item.FullName $child }
  }
}
function Write-New([string]$Path, [byte[]]$Bytes) {
  $parent = Split-Path -Parent $Path
  [IO.Directory]::CreateDirectory($parent) | Out-Null
  Assert-PlainPath $parent
  $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
  try { $stream.Write($Bytes, 0, $Bytes.Length) } finally { $stream.Dispose() }
}

# Refuse an existing project before cloning, hashing, or writing anything.
Assert-Clean
try {
  if (-not $Source) { $Source = $env:TK_SRC }
  if (-not $Source -and $PSScriptRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot "AGENTS.md"))) {
    $Source = $PSScriptRoot
  }
  if (-not $Source) {
    if ($DryRun) { throw "Dry run requires a local source: -Source PATH or TK_SRC." }
    $download = Join-Path ([IO.Path]::GetTempPath()) ("agent-toolkit-" + [guid]::NewGuid().ToString("N"))
    & git clone --quiet --depth 1 --branch master https://github.com/EvgenVer/Agents-tollkit.git $download
    if ($LASTEXITCODE -ne 0) { throw "Toolkit download failed." }
    $Source = $download
  }
  $Source = (Resolve-Path -LiteralPath $Source).Path
  Assert-PlainPath $Source
  Add-File (Join-Path $Source "AGENTS.md") "AGENTS.md"
  Add-File (Join-Path $Source "CLAUDE.md") "CLAUDE.md"
  Add-Tree (Join-Path $Source ".agents") ".agents"
  Add-Tree (Join-Path $Source ".agents/skills") ".claude/skills"
  Add-Tree (Join-Path $Source ".claude/commands") ".claude/commands"
  Add-Tree (Join-Path $Source ".claude/agents") ".claude/agents"
  Add-Tree (Join-Path $Source ".codex/agents") ".codex/agents"
  if (-not (Test-Path -LiteralPath (Join-Path $Source ".agents/docs/AGENT_WORKFLOWS.md") -PathType Leaf)) {
    throw "Source is not the current clean-install layout."
  }
  $inventory = New-Object 'System.Collections.Generic.List[string]'
  $inventory.Add("# agent-toolkit-inventory-v2 (informational; no automatic upgrades)")
  $revision = "local-unversioned"
  if (Test-Path -LiteralPath (Join-Path $Source ".git")) {
    $commit = & git -C $Source rev-parse HEAD 2>$null
    if ($LASTEXITCODE -eq 0) {
      $revision = "git:$commit"
      $changes = & git -C $Source status --porcelain 2>$null
      if ($LASTEXITCODE -ne 0 -or $changes) { $revision += "+working-tree" }
    }
  }
  $inventory.Add("# source: $revision; per-file hashes identify installed contents")
  foreach ($file in $files) {
    $hash = (Get-FileHash -LiteralPath $file.Source -Algorithm SHA256).Hash.ToLowerInvariant()
    $inventory.Add("$hash`t$($file.Relative)")
    Write-Output "ADD $($file.Relative)"
  }
  if ($DryRun) { Write-Output "Dry run: nothing was changed."; return }
  Assert-Clean
  foreach ($file in $files) {
    Assert-PlainPath $file.Source
    Write-New (Join-Path $destination $file.Relative) ([IO.File]::ReadAllBytes($file.Source))
  }
  Write-New (Join-Path $destination ".agent-toolkit-manifest.tsv") ($utf8.GetBytes(($inventory -join "`n") + "`n"))
  Write-Output "Installed. Describe your project to the agent. Existing projects use the README update instruction."
} finally {
  if ($download -and (Test-Path -LiteralPath $download)) {
    $resolvedDownload = [IO.Path]::GetFullPath($download)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([char[]]"\/") + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedDownload.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolvedDownload) -notmatch '^agent-toolkit-[a-f0-9]{32}$') {
      throw "Unexpected download cleanup path."
    }
    Remove-Item -LiteralPath $resolvedDownload -Recurse -Force
  }
}
