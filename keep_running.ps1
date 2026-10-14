# Superviseur : garde l'application (et le modele local) allumes tant que la session Windows est ouverte (verrouillee ou non).
# Toutes les $IntervalSec secondes il controle l'application (/api/health) et llama-server (/health) ; apres $FailuresBeforeRestart controles rates de suite
# il arrete proprement ce que start_local.ps1 avait lance (stop_local.ps1 -Supervised) puis relance start_local.ps1 avec les memes options.
# Il respecte un arret demande a la main : si .\stop_local.ps1 a ete lance (drapeau local_app\runtime\stopped_by_user.flag), il ne relance rien.
# Lance normalement par la tache planifiee creee avec .\autostart.ps1 -Install ; peut aussi etre lance a la main (fenetre PowerShell, Ctrl+C pour sortir).
# Journal : local_app\runtime\keep_running.log (tronque a 200 Ko). Aucun fichier du systeme fige n'est modifie. Fichier ASCII (PowerShell 5.1).
# Usage : .\keep_running.ps1 [-Port 8790] [-Lan [-NoCode | -AccessCode CODE] [-LanIp 10.x.y.z]] [-IntervalSec 30] [-FailuresBeforeRestart 2]
param([int]$Port = 8790, [switch]$Lan, [switch]$NoCode, [string]$AccessCode = '', [string]$LanIp = '', [int]$IntervalSec = 30, [int]$FailuresBeforeRestart = 2)
$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
Set-Location $Root
$Runtime = Join-Path $Root 'local_app\runtime'
$null = New-Item -ItemType Directory -Force $Runtime
$LogFile = Join-Path $Runtime 'keep_running.log'
$Flag = Join-Path $Runtime 'stopped_by_user.flag'
. "$Root\llm_local\config.ps1"                                   # $LLM_PORT

function Log([string]$m) {
    if ($AccessCode) { $m = $m.Replace($AccessCode, '***') }        # le code d'acces ne doit jamais apparaitre dans le journal
    try {
        if ((Test-Path $LogFile) -and (Get-Item $LogFile).Length -gt 200KB) { Set-Content -Path $LogFile -Value "(journal tronque)" -Encoding ASCII }
        Add-Content -Path $LogFile -Value ("{0} {1}" -f (Get-Date -Format 's'), $m) -Encoding ASCII
    } catch { }
}
function Probe([string]$url) { try { $r = Invoke-RestMethod -Uri $url -TimeoutSec 5; return $true } catch { return $false } }
function Healthy { return ((Probe "http://127.0.0.1:$Port/api/health") -and (Probe "http://127.0.0.1:$LLM_PORT/health")) }

if ($Lan -and -not $NoCode -and -not $AccessCode) { Log "ERREUR : en mode reseau avec code, fournissez -AccessCode (un code genere changerait a chaque redemarrage) ou choisissez -NoCode"; Write-Host "ERREUR : fournissez -AccessCode CODE (8 caracteres au minimum) ou -NoCode." -ForegroundColor Red; exit 2 }
$startParams = @{}                                              # table nommee : un tableau serait passe en parametres positionnels (et -Lan lu comme valeur de -Port)
if ($Port -ne 8790) { $startParams['Port'] = $Port }
if ($Lan) {
    $startParams['Lan'] = $true
    if ($NoCode) { $startParams['NoCode'] = $true } elseif ($AccessCode) { $startParams['AccessCode'] = $AccessCode }
    if ($LanIp) { $startParams['LanIp'] = $LanIp }
}

# Un seul superviseur a la fois (le planificateur ne lance pas d'instance en double, mais une execution manuelle le pourrait).
$mutex = New-Object System.Threading.Mutex($false, 'Global\RegAssistDZ_keep_running')
if (-not $mutex.WaitOne(0)) { Log "un autre superviseur est deja actif : sortie"; exit 0 }

Log ("superviseur demarre (PID {0}, port {1}, options start_local : {2})" -f $PID, $Port, (($startParams.Keys | Where-Object { $_ -ne 'AccessCode' }) -join ' '))
$fails = $FailuresBeforeRestart - 1          # au tout premier controle : si le service est absent, on le demarre tout de suite
while ($true) {
    if (Test-Path $Flag) {
        if ($fails -ne -1) { Log "arret demande a la main (stop_local.ps1) : le superviseur ne relance rien"; $fails = -1 }
    } else {
        if ($fails -eq -1) { $fails = 0; Log "arret manuel leve : surveillance reprise" }
        if (Healthy) {
            if ($fails -gt 0) { Log "service de nouveau disponible" }
            $fails = 0
        } else {
            $fails++
            Log ("controle rate ({0}/{1})" -f $fails, $FailuresBeforeRestart)
            if ($fails -ge $FailuresBeforeRestart) {
                Log "service indisponible : arret de ce que start_local.ps1 avait lance, puis redemarrage"
                try { $o = & "$Root\stop_local.ps1" -Supervised *>&1 | Out-String; Log ("stop_local : " + (($o -replace '\s+', ' ').Trim())) } catch { Log ("stop_local : " + $_.Exception.Message) }
                try { $o = & "$Root\start_local.ps1" @startParams *>&1 | Out-String; Log ("start_local : " + (($o -replace '\s+', ' ').Trim())) } catch { Log ("start_local : " + $_.Exception.Message) }
                if (Healthy) { Log "redemarrage reussi" } else { Log "redemarrage NON reussi : nouvel essai au prochain cycle" }
                $fails = 0
            }
        }
    }
    Start-Sleep -Seconds $IntervalSec
}
