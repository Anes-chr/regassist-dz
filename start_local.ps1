# Demarre l'assistant juridique local (phase 6) : verifie l'environnement, demarre llama-server SEULEMENT s'il est absent
# (en reutilisant llm_local\start_server.ps1), demarre l'application (API + interface, une seule origine) et affiche les URL.
# Usage : .\start_local.ps1 [-Port 8790] [-SkipLlm] [-TimeoutSec 300]
# Ports : 3000 (Grafana) et 8000 (IncrediBuild) sont deja utilises sur cette machine ; 8765 = ancienne interface Flask ; 8187 = llama-server.
# Le serveur n'ecoute que sur 127.0.0.1. Aucun fichier du systeme fige n'est modifie. Fichier ASCII (PowerShell 5.1).
param([int]$Port = 8790, [switch]$SkipLlm, [int]$TimeoutSec = 300)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root
$Runtime = Join-Path $Root 'local_app\runtime'
$PidFile = Join-Path $Runtime 'pids.json'
$null = New-Item -ItemType Directory -Force $Runtime

function Fail([string]$msg) { Write-Host "ERREUR : $msg" -ForegroundColor Red; exit 1 }
function Get-Json([string]$url, [int]$timeout = 3) { try { Invoke-RestMethod -Uri $url -TimeoutSec $timeout } catch { $null } }
function Test-Pid([int]$id, $startedIso) {
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $p) { return $false }
    if ($startedIso) { try { return ([math]::Abs(($p.StartTime.ToUniversalTime() - [datetime]::Parse($startedIso).ToUniversalTime()).TotalSeconds) -lt 2) } catch { return $false } }
    return $true
}

# ---- 1. Environnement et fichiers requis ----
. "$Root\llm_local\config.ps1"                      # source unique de verite pour le LLM : $LLM_ROOT, $LLM_BIN, $LLM_MODEL, $LLM_PORT
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { Fail "Python introuvable dans le PATH." }
$required = @(
    "$Root\local_app\server.py", "$Root\local_app\static\index.html", "$Root\PHASE_4_FROZEN", "$Root\agent_fr\eval\human\PHASE_4_FROZEN.manifest.json",
    "$Root\corpus\chunks\chunks_fr.jsonl", "$Root\corpus\metadata\documents_fr.json",
    "$LLM_ROOT\models\embeddings\multilingual-e5-small\onnx\model.onnx", "$LLM_ROOT\models\rerankers\mmarco-mMiniLMv2-L12-H384\onnx\model_quint8_avx2.onnx",
    "$LLM_BIN\llama-server.exe", $LLM_MODEL)
$missing = $required | Where-Object { -not (Test-Path $_) }
if ($missing) { Fail ("fichier(s) requis introuvable(s) :`n  " + ($missing -join "`n  ")) }
$engineVars = 'AGENT_RETRIEVER','AGENT_RERANK_N','AGENT_W_RERANK','AGENT_RR_MIN','AGENT_LANGS','AGENT_RERANK_DIR','AGENT_RERANK_MODEL','AGENT_EMBED_DIR','AGENT_VECTOR_DIR','AGENT_JSON_SCHEMA'
$setVars = $engineVars | Where-Object { [Environment]::GetEnvironmentVariable($_) -and -not ($_ -eq 'AGENT_RETRIEVER' -and @('auto','default','hybrid_rerank') -contains [Environment]::GetEnvironmentVariable($_).ToLower()) }
if ($setVars) { Fail ("variable(s) d'environnement qui modifient le systeme fige : " + ($setVars -join ', ') + ". Retirez-les (Remove-Item Env:NOM) avant de demarrer.") }

# ---- 2. Deja demarre ? (jamais deux instances) ----
$state = $null
if (Test-Path $PidFile) { try { $state = Get-Content $PidFile -Raw | ConvertFrom-Json } catch { $state = $null } }
if ($state -and $state.app_pid -and (Test-Pid ([int]$state.app_pid) $state.app_started)) {
    $st = Get-Json "http://127.0.0.1:$($state.port)/api/status"
    if ($st) { Write-Host "L'application est deja demarree : http://127.0.0.1:$($state.port)  (arret : .\stop_local.ps1)" -ForegroundColor Yellow; exit 0 }
    Fail "Un processus enregistre (PID $($state.app_pid)) existe mais ne repond pas. Lancez .\stop_local.ps1 puis reessayez."
}
if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
$busy = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($busy) {
    $who = (Get-Process -Id $busy.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Fail "le port $Port est deja utilise par '$who' (PID $($busy.OwningProcess)). Choisissez un autre port : .\start_local.ps1 -Port 8791"
}

# ---- 3. llama-server : reutilise s'il repond, demarre seulement s'il est absent (jamais deux instances) ----
$llmUrl = "http://127.0.0.1:$LLM_PORT"
$llmStartedByApp = $false; $llmPid = $null
if (-not $SkipLlm) {
    $h = Get-Json "$llmUrl/health" 2
    if ($h -and $h.status -eq 'ok') {
        Write-Host "llama-server deja actif sur $llmUrl : reutilise (non arrete par stop_local.ps1)."
    } elseif (Get-Process llama-server -ErrorAction SilentlyContinue) {
        Write-Host "llama-server est lance mais ne repond pas encore : attente (60 s max), aucune seconde instance ne sera creee..."
        for ($i = 0; $i -lt 30 -and -not ($h -and $h.status -eq 'ok'); $i++) { Start-Sleep 2; $h = Get-Json "$llmUrl/health" 2 }
        if (-not ($h -and $h.status -eq 'ok')) { Fail "llama-server (deja lance) ne repond pas sur $llmUrl. Arretez-le vous-meme puis relancez ce script." }
    } else {
        Write-Host "Demarrage de llama-server (llm_local\start_server.ps1, 127.0.0.1:$LLM_PORT)..."
        try { & "$Root\llm_local\start_server.ps1" | ForEach-Object { Write-Host "  $_" } } catch { Fail "llama-server n'a pas demarre : $($_.Exception.Message)" }
        $proc = Get-Process llama-server -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($proc) { $llmStartedByApp = $true; $llmPid = $proc.Id; $llmStarted = $proc.StartTime.ToUniversalTime().ToString('o') }
    }
} else { Write-Host "Option -SkipLlm : llama-server n'est pas demarre (l'interface affichera que le modele local n'est pas disponible)." }

# ---- 4. Application (API + interface) ----
$env:LOCAL_APP_PORT = "$Port"; $env:PYTHONIOENCODING = 'utf-8'
$out = Join-Path $Runtime 'server.out.log'; $err = Join-Path $Runtime 'server.err.log'
$app = Start-Process -FilePath $python.Source -ArgumentList @('-m', 'local_app') -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
Remove-Item Env:LOCAL_APP_PORT -ErrorAction SilentlyContinue
$rec = [ordered]@{ app_pid = $app.Id; app_started = $app.StartTime.ToUniversalTime().ToString('o'); port = $Port; llm_started_by_app = $llmStartedByApp; llm_pid = $llmPid; llm_started = $llmStarted }
$rec | ConvertTo-Json | Set-Content -Path $PidFile -Encoding ASCII
Write-Host "Application demarree (PID $($app.Id)) : chargement du moteur de recherche et du reranker..."

$st = $null; $t0 = Get-Date
while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSec) {
    Start-Sleep 2
    if ($app.HasExited) {
        $tail = if (Test-Path $err) { (Get-Content $err -Tail 8) -join "`n  " } else { '' }
        $tail2 = if (Test-Path $out) { (Get-Content $out -Tail 4) -join "`n  " } else { '' }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Fail "l'application s'est arretee (code $($app.ExitCode)).`n  $tail2`n  $tail"
    }
    $st = Get-Json "http://127.0.0.1:$Port/api/status" 3
    if ($st -and $st.app.state -ne 'starting') { break }
}
if (-not $st -or $st.app.state -eq 'starting') {
    Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue; Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    Fail "l'application n'est pas prete apres $TimeoutSec s (voir $err)."
}

# ---- 5. Bilan (valeurs lues dans /api/status : controles reels) ----
function Mark($ok, $text) { if ($ok) { "OK   $text" } else { "KO   $text" } }
$llmTxt = if ($st.llm.online) { "LLM local    " + (Mark $true "($($st.llm.model), 127.0.0.1:$LLM_PORT)") } else { "LLM local    " + (Mark $false "(hors ligne : le modele local n'est pas disponible)") }
Write-Host ""
Write-Host "RegAssist DZ - assistant juridique LOCAL" -ForegroundColor Cyan
Write-Host $llmTxt
Write-Host ("Agent        " + (Mark $st.agent.ready ''))
Write-Host ("Retrieval    " + (Mark $st.retrieval.ready "($($st.retrieval.engine))"))
Write-Host ("Reranker     " + (Mark $st.reranker.ready ''))
Write-Host ("Interface    " + (Mark $true "http://127.0.0.1:$Port"))
Write-Host ("API          " + (Mark $true "http://127.0.0.1:$Port/api  (health, status, chat)"))
Write-Host ("LLM distant  " + $(if ($st.remote_llm) { 'ACTIF (anormal)' } else { 'desactive' }))
Write-Host ("Phase        $($st.phase)")
Write-Host ("Statut       $($st.status)")
Write-Host ""
if ($st.app.state -ne 'ready') { Write-Host "Attention : etat '$($st.app.state)' (voir le panneau Etat du systeme de l'interface)." -ForegroundColor Yellow }
if (-not $st.llm.online) { Write-Host "Le modele local n'est pas disponible. Veuillez demarrer llama-server (.\llm_local\start_server.ps1)." -ForegroundColor Yellow }
Write-Host "Ouvrez http://127.0.0.1:$Port dans votre navigateur.  Arret : .\stop_local.ps1"
exit 0
