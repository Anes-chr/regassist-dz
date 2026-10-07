# Arrete UNIQUEMENT les processus lances par .\start_local.ps1 (enregistres dans local_app\runtime\pids.json avec leur heure de demarrage).
# Ne touche jamais aux autres processus Python ni a un llama-server que vous aviez lance vous-meme.
# Usage : .\stop_local.ps1 [-KeepLlm]     (-KeepLlm : laisse tourner le llama-server demarre par start_local.ps1)
# Fichier ASCII (PowerShell 5.1).
param([switch]$KeepLlm)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$PidFile = Join-Path $Root 'local_app\runtime\pids.json'

function Same-Process([int]$id, $startedIso, [string]$nameLike) {
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $p) { return $null }
    if ($p.ProcessName -notlike $nameLike) { return $null }
    if (-not $startedIso) { return $null }
    try { if ([math]::Abs(($p.StartTime.ToUniversalTime() - [datetime]::Parse($startedIso).ToUniversalTime()).TotalSeconds) -ge 2) { return $null } } catch { return $null }
    return $p
}

if (-not (Test-Path $PidFile)) { Write-Host "Aucun processus enregistre par start_local.ps1 : rien a arreter."; exit 0 }
$s = Get-Content $PidFile -Raw | ConvertFrom-Json

if ($s.app_pid) {
    $p = Same-Process ([int]$s.app_pid) $s.app_started 'python*'
    if ($p) { Stop-Process -Id $p.Id -Force; Write-Host "Application arretee (PID $($p.Id))." }
    else { Write-Host "Application : processus $($s.app_pid) deja arrete (ou PID reutilise : non touche)." }
}
if ($s.llm_started_by_app -and $s.llm_pid) {
    if ($KeepLlm) { Write-Host "llama-server (PID $($s.llm_pid)) laisse en marche (-KeepLlm)." }
    else {
        $p = Same-Process ([int]$s.llm_pid) $s.llm_started 'llama-server*'
        if ($p) { Stop-Process -Id $p.Id -Force; Write-Host "llama-server arrete (PID $($p.Id)), lance par start_local.ps1." }
        else { Write-Host "llama-server : processus $($s.llm_pid) deja arrete (ou PID reutilise : non touche)." }
    }
} else { Write-Host "llama-server : non lance par start_local.ps1, laisse en marche." }
Remove-Item $PidFile -Force
exit 0
