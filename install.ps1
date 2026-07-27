# AI-Agent Workflow Toolkit - conflict-safe installer (PowerShell / Windows)
#
# From any target project directory (downloads the toolkit automatically):
#   irm https://raw.githubusercontent.com/EvgenVer/Agents-tollkit/master/install.ps1 | iex
# Run a downloaded/local script from the target project directory:
#   .\install.ps1 -DryRun
#   .\install.ps1
# Local source:
#   .\install.ps1 -Source "C:\path\to\toolkit"

[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$MigrateLegacy,
  [string]$Source
)

$REPO = "EvgenVer/Agents-tollkit"
$BRANCH = "master"
$PREVIOUS_COMMIT = "59f7cbc"
$MANIFEST_NAME = ".agent-toolkit-manifest.tsv"
$MANIFEST_HEADER = "# agent-toolkit-manifest-v1"
$LEGACY_AGENTS_SHA256 = @(
  "1b46470215f747767736d7bac454ae621d0a161f0d315bf652ac5b71ee340606",
  "1af36a2126fca6f13941cd48854f1855b63e4deb052b4692c7e6b1a7ce9a1662"
)
$PREVIOUS_AGENTS_SHA256 = @(
  "a336b1c2bdd75dc2aa855d5e2751044a001ca3298273ffd24121605ea3cad392",
  "77b421d1e450bfe691705cc17877a5f63b32d4cac5eb8da17c92522af2e6df58"
)
$GITIGNORE_MARKER = "# Secrets / env (from AI-Agent toolkit)"

$ErrorActionPreference = "Stop"
$Dest = (Get-Location).Path
if ((Get-Item -LiteralPath $Dest -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
  throw "target project root must not be a symbolic link or junction"
}

function Get-Sha256([string]$Path) {
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Get-NormalizedSha256([string]$Path) {
  $text = [System.IO.File]::ReadAllText($Path)
  $text = $text.Replace("`r`n", "`n").Replace("`r", "`n")
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
  $digest = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
  return ([System.BitConverter]::ToString($digest) -replace "-", "").ToLowerInvariant()
}

function Get-RelativeFile([string]$Root, [string]$FullName) {
  $rootPath = (Resolve-Path -LiteralPath $Root).Path.TrimEnd([char[]]"\/")
  return $FullName.Substring($rootPath.Length).TrimStart([char[]]"\/").Replace("\", "/")
}

function Add-ManagedDirectory(
  [System.Collections.Generic.List[object]]$List,
  [string]$SourceRoot,
  [string]$TargetRoot
) {
  if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) { return }
  if ((Get-Item -LiteralPath $SourceRoot -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
    throw "source directory must not be a symbolic link or junction: $SourceRoot"
  }
  Get-ChildItem -LiteralPath $SourceRoot -Recurse -File |
    Sort-Object FullName |
    ForEach-Object {
      if ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "source file must not be a symbolic link: $($_.FullName)"
      }
      $child = Get-RelativeFile $SourceRoot $_.FullName
      $rel = if ($TargetRoot) { "$TargetRoot/$child" } else { $child }
      $List.Add([pscustomobject]@{ Source = $_.FullName; Rel = $rel }) | Out-Null
    }
}

function Convert-ToTargetPath([string]$RelativePath) {
  return Join-Path $Dest $RelativePath.Replace("/", "\")
}

function Test-ParentPath([string]$TargetPath) {
  $parent = Split-Path -Parent $TargetPath
  while ($parent -and $parent.StartsWith($Dest, [System.StringComparison]::OrdinalIgnoreCase) -and $parent -ne $Dest) {
    if (Test-Path -LiteralPath $parent) {
      if ((Get-Item -LiteralPath $parent -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        return "parent path is a symbolic link or junction: $parent"
      }
      if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        return "parent path is not a directory: $parent"
      }
    }
    $parent = Split-Path -Parent $parent
  }
  return $null
}

Write-Host "AI-Agent Workflow Toolkit preflight: $Dest"

try {
  if ($Source) {
    $Src = (Resolve-Path -LiteralPath $Source).Path
  } elseif ($env:TK_SRC) {
    $Src = (Resolve-Path -LiteralPath $env:TK_SRC).Path
  } elseif ($PSScriptRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot "AGENTS.md") -PathType Leaf)) {
    $Src = (Resolve-Path -LiteralPath $PSScriptRoot).Path
  } else {
    $TempRoot = Join-Path $env:TEMP ("agent-toolkit-" + [guid]::NewGuid().ToString("N"))
    $eap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $cloneLog = git clone --depth 32 --branch $BRANCH "https://github.com/$REPO.git" $TempRoot --quiet 2>&1
    $cloneExit = $LASTEXITCODE
    $ErrorActionPreference = $eap
    if ($cloneExit -ne 0) { throw "clone failed ($cloneExit) - check GitHub access and that git is installed.`n$cloneLog" }
    $Src = (Resolve-Path -LiteralPath $TempRoot).Path
  }
  Write-Host "Source: $Src"

  $Managed = [System.Collections.Generic.List[object]]::new()
  foreach ($rel in @("AGENTS.md", "CLAUDE.md")) {
    $sourceFile = Join-Path $Src $rel
    if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
      throw "required source file is missing: $rel"
    }
    if ((Get-Item -LiteralPath $sourceFile -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
      throw "required source file must not be a symbolic link: $rel"
    }
    $Managed.Add([pscustomobject]@{ Source = $sourceFile; Rel = $rel }) | Out-Null
  }
  Add-ManagedDirectory $Managed (Join-Path $Src "docs") "docs"
  Add-ManagedDirectory $Managed (Join-Path $Src ".agents") ".agents"
  Add-ManagedDirectory $Managed (Join-Path $Src ".claude\commands") ".claude/commands"
  Add-ManagedDirectory $Managed (Join-Path $Src ".agents\skills") ".claude/skills"
  Add-ManagedDirectory $Managed (Join-Path $Src ".claude\agents") ".claude/agents"
  Add-ManagedDirectory $Managed (Join-Path $Src ".codex\agents") ".codex/agents"

  $duplicates = @($Managed | Group-Object Rel | Where-Object Count -gt 1)
  if ($duplicates.Count -gt 0) {
    throw "duplicate managed paths: $($duplicates.Name -join ', ')"
  }

  $ManifestPath = Join-Path $Dest $MANIFEST_NAME
  $OldHashes = @{}
  $PreviousModular = $false
  if (Test-Path -LiteralPath $ManifestPath) {
    if ((Get-Item -LiteralPath $ManifestPath -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
      throw "$MANIFEST_NAME must not be a symbolic link"
    }
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
      throw "$MANIFEST_NAME exists but is not a file"
    }
    $manifestLines = @(Get-Content -LiteralPath $ManifestPath)
    if ($manifestLines.Count -eq 0 -or $manifestLines[0] -ne $MANIFEST_HEADER) {
      throw "unsupported or damaged $MANIFEST_NAME"
    }
    foreach ($line in $manifestLines | Select-Object -Skip 1) {
      if (-not $line) { continue }
      $parts = $line -split "`t", 2
      if ($parts.Count -ne 2 -or $parts[1] -notmatch "^[0-9a-fA-F]{64}$") {
        throw "invalid manifest entry: $line"
      }
      $OldHashes[$parts[0]] = $parts[1].ToLowerInvariant()
    }
  } elseif (Test-Path -LiteralPath (Join-Path $Dest "AGENTS.md") -PathType Leaf) {
    $previousAgentsHash = Get-Sha256 (Join-Path $Dest "AGENTS.md")
    $PreviousModular = $previousAgentsHash -in $PREVIOUS_AGENTS_SHA256
  }
  $PreviousRoot = $null
  if ($PreviousModular -and (Test-Path -LiteralPath (Join-Path $Src ".git") -PathType Container)) {
    if (-not $TempRoot) {
      $TempRoot = Join-Path $env:TEMP ("agent-toolkit-" + [guid]::NewGuid().ToString("N"))
    }
    $PreviousRoot = Join-Path $TempRoot "previous"
    New-Item -ItemType Directory -Force -Path $PreviousRoot | Out-Null
    $eap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $archivePath = Join-Path $TempRoot "previous.tar"
    git -C $Src archive --format=tar -o $archivePath $PREVIOUS_COMMIT 2>$null
    tar -xf $archivePath -C $PreviousRoot 2>$null
    $archiveExit = $LASTEXITCODE
    $ErrorActionPreference = $eap
    if ($archiveExit -ne 0) { $PreviousRoot = $null }
  }

  $Plan = [System.Collections.Generic.List[object]]::new()
  $Conflicts = [System.Collections.Generic.List[string]]::new()
  foreach ($item in $Managed) {
    $target = Convert-ToTargetPath $item.Rel
    $parentError = Test-ParentPath $target
    if ($parentError) {
      $Conflicts.Add("$($item.Rel): $parentError") | Out-Null
      continue
    }

    $sourceHash = Get-Sha256 $item.Source
    if (-not (Test-Path -LiteralPath $target)) {
      $action = "CREATE"
    } elseif ((Get-Item -LiteralPath $target -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
      $Conflicts.Add("$($item.Rel): symbolic links are not overwritten") | Out-Null
      continue
    } elseif (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
      $Conflicts.Add("$($item.Rel): target exists but is not a file") | Out-Null
      continue
    } else {
      $targetHash = Get-Sha256 $target
      if ($item.Rel -in @("AGENTS.md", "CLAUDE.md")) {
        $action = if ($targetHash -eq $sourceHash) { "UNCHANGED" } else { "REPLACE_AUTHORITATIVE" }
      } elseif ($item.Rel -eq "AGENTS.md" -and $targetHash -in $LEGACY_AGENTS_SHA256) {
        $action = "MIGRATE_LEGACY"
      } elseif ($PreviousModular) {
        if ($item.Rel -like ".claude/agents/*" -or $item.Rel -like ".codex/agents/*") {
          $action = "PRESERVE_PREVIOUS"
        } elseif ($PreviousRoot -and (Test-Path -LiteralPath (Join-Path $PreviousRoot $item.Rel) -PathType Leaf)) {
          $previousHash = Get-NormalizedSha256 (Join-Path $PreviousRoot $item.Rel)
          $targetNormalizedHash = Get-NormalizedSha256 $target
          if ($targetNormalizedHash -ne $previousHash) {
            $Conflicts.Add("$($item.Rel): locally modified since the previous release") | Out-Null
            continue
          }
          $action = "MIGRATE_PREVIOUS"
        } else {
          $Conflicts.Add("$($item.Rel): cannot verify previous-release ownership") | Out-Null
          continue
        }
      } elseif ($OldHashes.ContainsKey($item.Rel)) {
        if ($targetHash -ne $OldHashes[$item.Rel]) {
          $Conflicts.Add("$($item.Rel): locally modified since the previous install") | Out-Null
          continue
        }
        $action = if ($targetHash -eq $sourceHash) { "UNCHANGED" } else { "UPDATE" }
      } elseif ($targetHash -eq $sourceHash) {
        $action = "ADOPT"
      } else {
        $Conflicts.Add("$($item.Rel): unmanaged file would be overwritten") | Out-Null
        continue
      }
    }
    $Plan.Add([pscustomobject]@{
      Action = $action
      Source = $item.Source
      Rel = $item.Rel
      Hash = if ($action -eq "PRESERVE_PREVIOUS") { $targetHash } else { $sourceHash }
      Target = $target
    }) | Out-Null
  }

  $GitignorePath = Join-Path $Dest ".gitignore"
  if (Test-Path -LiteralPath $GitignorePath) {
    if ((Get-Item -LiteralPath $GitignorePath -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
      $Conflicts.Add(".gitignore: symbolic links are not modified") | Out-Null
    } elseif (-not (Test-Path -LiteralPath $GitignorePath -PathType Leaf)) {
      $Conflicts.Add(".gitignore: target exists but is not a file") | Out-Null
    }
  }

  if ($Conflicts.Count -gt 0) {
    Write-Host "`nCONFLICTS - nothing was changed:" -ForegroundColor Red
    $Conflicts | ForEach-Object { Write-Host "  - $_" }
    Write-Host "Back up or reconcile these files, then rerun the installer."
    exit 2
  }

  Write-Host "`nPlan:"
  $Plan | ForEach-Object { Write-Host ("  {0,-16} {1}" -f $_.Action, $_.Rel) }
  if ($DryRun) {
    Write-Host "`nDry run complete - nothing was changed."
    exit 0
  }

  $migrations = @($Plan | Where-Object Action -in @("REPLACE_AUTHORITATIVE", "MIGRATE_LEGACY", "MIGRATE_PREVIOUS"))
  if ($migrations.Count -gt 0) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDir = Join-Path $Dest ".agent-toolkit-backup\$stamp"
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    foreach ($item in $migrations | Where-Object { Test-Path -LiteralPath $_.Target -PathType Leaf }) {
      $backupTarget = Join-Path $backupDir ($item.Rel.Replace("/", "\"))
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupTarget) | Out-Null
      Copy-Item -LiteralPath $item.Target -Destination $backupTarget
    }
    Write-Host "Previous toolkit backup: $backupDir"
  }

  foreach ($item in $Plan | Where-Object { $_.Action -in @("CREATE", "UPDATE", "REPLACE_AUTHORITATIVE", "MIGRATE_LEGACY", "MIGRATE_PREVIOUS") }) {
    $parent = Split-Path -Parent $item.Target
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $item.Source -Destination $item.Target -Force
  }
  $gitignoreText = if (Test-Path -LiteralPath $GitignorePath) {
    [System.IO.File]::ReadAllText($GitignorePath)
  } else {
    ""
  }
  $requiredIgnoreLines = @(
    $GITIGNORE_MARKER,
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "id_rsa*",
    ".ssh/",
    "secrets/",
    ".claude/settings.local.json",
    ".agent-toolkit-backup/"
  )
  $existingIgnoreLines = @($gitignoreText -split "\r?\n")
  $missingIgnoreLines = @(
    $requiredIgnoreLines | Where-Object { $_ -notin $existingIgnoreLines }
  )
  if ($missingIgnoreLines.Count -gt 0) {
    $section = "`r`n" + ($missingIgnoreLines -join "`r`n") + "`r`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($GitignorePath, $gitignoreText + $section, $utf8NoBom)
  }

  $manifestLines = [System.Collections.Generic.List[string]]::new()
  $manifestLines.Add($MANIFEST_HEADER) | Out-Null
  $Plan | Sort-Object Rel | ForEach-Object {
    $manifestLines.Add("$($_.Rel)`t$($_.Hash)") | Out-Null
  }
  $manifestTemp = "$ManifestPath.tmp.$([guid]::NewGuid().ToString('N'))"
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllLines($manifestTemp, $manifestLines, $utf8NoBom)
  Move-Item -LiteralPath $manifestTemp -Destination $ManifestPath -Force

  Write-Host "`nDone - toolkit installed without deleting project directories."
  Write-Host "No Git repository was created. Run git init yourself if this project needs it."
}
catch {
  Write-Error $_
  exit 1
}
finally {
  if ($TempRoot -and (Test-Path -LiteralPath $TempRoot)) {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
