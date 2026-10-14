# Garde le service allume en continu : cree (ou supprime) UNE tache planifiee Windows, au nom de l'utilisateur courant, qui lance le superviseur
# keep_running.ps1 a l'ouverture de session (session verrouillee = sans effet) et le relance s'il s'arrete. Le superviseur controle l'application et le modele local
# toutes les 30 s et les redemarre apres 2 controles rates. Le service ne depend plus de la fenetre ni de l'application qui l'a demarre.
# Pas de droits administrateur, pas de mot de passe stocke : la tache ne tourne que session ouverte (verrouillee ou non). Apres un redemarrage de Windows ou une
# fermeture de session, le service repart a la prochaine ouverture de session. Aucun fichier du systeme fige n'est modifie. Fichier ASCII (PowerShell 5.1).
#
# Usage : .\autostart.ps1 -Install [-Lan [-NoCode | -AccessCode CODE] [-LanIp 10.x.y.z]] [-Port 8790] [-NoStart]
#         .\autostart.ps1 -Status         etat de la tache, du service et fin du journal
#         .\autostart.ps1 -Resume         releve un arret manuel (.\stop_local.ps1) et relance la surveillance
#         .\autostart.ps1 -Uninstall      supprime la tache et arrete le superviseur et ce qu'il a lance
param([switch]$Install, [switch]$Uninstall, [switch]$Status, [switch]$Resume, [int]$Port = 8790, [switch]$Lan, [switch]$NoCode,
      [string]$AccessCode = '', [string]$LanIp = '', [switch]$NoStart)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Runtime = Join-Path $Root 'local_app\runtime'
$Flag = Join-Path $Runtime 'stopped_by_user.flag'
$TaskName = 'RegAssist DZ keep running'
$User = "$env:USERDOMAIN\$env:USERNAME"
function Fail([string]$msg) { Write-Host "ERREUR : $msg" -ForegroundColor Red; exit 1 }
function Probe([string]$url) { try { $null = Invoke-RestMethod -Uri $url -TimeoutSec 4; return $true } catch { return $false } }
$modes = @($Install, $Uninstall, $Status, $Resume) | Where-Object { $_ }
if (@($modes).Count -ne 1) { Write-Host "Choisissez une action : -Install, -Status, -Resume ou -Uninstall (voir l'en-tete du script)." -ForegroundColor Yellow; exit 1 }

if ($Status) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $t) { Write-Host "Tache '$TaskName' : NON installee (le service ne redemarre pas tout seul)." -ForegroundColor Yellow }
    else {
        $i = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "Tache '$TaskName' : installee, etat $($t.State), derniere execution $($i.LastRunTime), resultat $($i.LastTaskResult)"
        Write-Host "  commande : powershell.exe $($t.Actions[0].Arguments -replace '(?i)-AccessCode\s+\S+', '-AccessCode ***')"
    }
    $sup = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -match 'keep_running\.ps1' }
    Write-Host ("Superviseur : " + $(if ($sup) { "actif (PID $(@($sup)[0].ProcessId))" } else { 'non actif' }))
    Write-Host ("Application (127.0.0.1:$Port) : " + $(if (Probe "http://127.0.0.1:$Port/api/health") { 'repond' } else { 'ne repond pas' }))
    Write-Host ("Arret manuel demande : " + $(if (Test-Path $Flag) { 'OUI (stop_local.ps1) : le superviseur ne relance rien ; .\autostart.ps1 -Resume pour reprendre' } else { 'non' }))
    $log = Join-Path $Runtime 'keep_running.log'
    if (Test-Path $log) { Write-Host "--- fin du journal ($log)"; Get-Content $log -Tail 6 }
    exit 0
}

if ($Resume) {
    Remove-Item $Flag -Force -ErrorAction SilentlyContinue
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t -and $t.State -ne 'Running') { Start-ScheduledTask -TaskName $TaskName; Write-Host "Superviseur relance." -ForegroundColor Green }
    elseif ($t) { Write-Host "Arret manuel leve : le superviseur relance le service au prochain controle (30 s)." -ForegroundColor Green }
    else { Write-Host "Aucune tache installee : lancez .\autostart.ps1 -Install, ou demarrez a la main avec .\start_local.ps1." -ForegroundColor Yellow }
    exit 0
}

if ($Uninstall) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) { try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }; Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false; Write-Host "Tache '$TaskName' supprimee." -ForegroundColor Green }
    else { Write-Host "Tache '$TaskName' deja absente." }
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -match 'keep_running\.ps1' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "Superviseur arrete (PID $($_.ProcessId))." }
    & "$Root\stop_local.ps1" -Supervised
    Write-Host "Le service est arrete. Pour le relancer a la main : .\start_local.ps1 [-Lan -NoCode]" -ForegroundColor Green
    exit 0
}

# ---- -Install ----
if ($NoCode -and -not $Lan) { Fail "-NoCode n'a de sens qu'avec -Lan." }
if ($NoCode -and $AccessCode) { Fail "-NoCode et -AccessCode s'excluent." }
if ($Lan -and -not $NoCode -and -not $AccessCode) { Fail "en mode reseau avec code, fournissez -AccessCode CODE (8 caracteres au minimum) : un code genere changerait a chaque redemarrage. Ou choisissez -NoCode." }
if ($AccessCode -and $AccessCode.Length -lt 8) { Fail "code d'acces trop court (8 caracteres au minimum)." }
if (-not (Test-Path "$Root\keep_running.ps1")) { Fail "keep_running.ps1 introuvable." }
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Root\keep_running.ps1`""
if ($Port -ne 8790) { $arg += " -Port $Port" }
if ($Lan) { $arg += ' -Lan'; if ($NoCode) { $arg += ' -NoCode' } elseif ($AccessCode) { $arg += " -AccessCode $AccessCode" }; if ($LanIp) { $arg += " -LanIp $LanIp" } }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -Hidden
try {
    $null = Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force `
        -Description "RegAssist DZ : garde l'application locale et le modele allumes (superviseur keep_running.ps1). Supprimer : autostart.ps1 -Uninstall"
} catch { Fail ("la tache n'a pas pu etre creee (une regle de l'organisation peut l'interdire) : " + $_.Exception.Message) }
Write-Host "Tache '$TaskName' creee : demarrage a l'ouverture de session de $User, relance automatique du service s'il s'arrete." -ForegroundColor Green
if ($AccessCode) { Write-Host "Attention : le code d'acces fait partie de la commande de la tache (lisible par cet utilisateur et les administrateurs)." -ForegroundColor Yellow }
if (-not $NoStart) {
    Remove-Item $Flag -Force -ErrorAction SilentlyContinue
    if (Test-Path (Join-Path $Runtime 'pids.json')) { & "$Root\stop_local.ps1" -Supervised | Out-Null }     # reprend la main sur un service lance a la main, lie a une autre fenetre
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -match 'keep_running\.ps1' -and $_.CommandLine -notmatch 'autostart' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Superviseur lance : le service demarre dans quelques secondes (suivi : .\autostart.ps1 -Status)." -ForegroundColor Green
}
exit 0
