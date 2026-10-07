# Demarre llama-server (API compatible OpenAI) en arriere-plan, sur 127.0.0.1 uniquement.
# Usage : .\llm_local\start_server.ps1 [-Threads 8] [-Ctx 6144]
# Reglages memoire retenus apres mesure : -lm none (pas de mappage du fichier -> pic RAM 2,5 Go au lieu de 4,2 Go, meme vitesse),
# -b 512 -ub 128 (tampons de calcul reduits), -cram 256 (le cache de prompts vaut 8192 Mo par defaut : il faisait grimper le serveur a 4,3 Go),
# cache KV en q8_0 avec flash-attention. Fichier ASCII (PowerShell 5.1).
param([int]$Threads = 0, [int]$Ctx = 0)
. "$PSScriptRoot\config.ps1"
if ($Threads -le 0) { $Threads = $LLM_THREADS }
if ($Ctx -le 0) { $Ctx = $LLM_CTX }
if (-not (Test-Path $LLM_MODEL)) { throw "Modele introuvable : $LLM_MODEL" }
$running = Get-Process llama-server -ErrorAction SilentlyContinue
if ($running) { "llama-server deja lance (PID $($running.Id))"; exit 0 }
$log = "$LLM_ROOT\bench\server.log"
$srvArgs = @('-m', $LLM_MODEL, '-t', $Threads, '-tb', $Threads, '-c', $Ctx, '--host', '127.0.0.1', '--port', $LLM_PORT,
             '-np', 1, '--no-webui', '-ngl', 0, '-b', 512, '-ub', 128, '-lm', 'none',
             '-cram', 256, '-ctxcp', 2, '-ctk', 'q8_0', '-ctv', 'q8_0', '-fa', 'on')
Start-Process -FilePath "$LLM_BIN\llama-server.exe" -ArgumentList $srvArgs -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err"
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep 2
    try {
        if ((Invoke-RestMethod "http://127.0.0.1:$LLM_PORT/health" -TimeoutSec 2).status -eq 'ok') {
            "llama-server pret sur http://127.0.0.1:$LLM_PORT (threads=$Threads, ctx=$Ctx)"; exit 0
        }
    } catch {}
}
throw "llama-server n'a pas demarre (voir $log.err)"
