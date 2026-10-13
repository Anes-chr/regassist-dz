# Cree (ou supprime) la regle du pare-feu Windows qui laisse les AUTRES machines du meme reseau joindre l'application en mode reseau (.\start_local.ps1 -Lan).
# La regle est la plus etroite possible : entrant TCP, UNIQUEMENT le port de l'application, UNIQUEMENT le profil Domaine, UNIQUEMENT le sous-reseau local
# (RemoteAddress = LocalSubnet) et UNIQUEMENT pour le programme Python de ce projet. Rien d'autre n'est ouvert, Internet n'est pas concerne.
# A executer par la personne qui administre la machine (elevation UAC demandee) ; lancer d'abord la regle, puis .\start_local.ps1 -Lan.
# Usage : .\lan_firewall.ps1 [-Port 8790] [-RemoteAddress LocalSubnet] [-Remove]
# Fichier ASCII (PowerShell 5.1).
param([int]$Port = 8790, [string]$RemoteAddress = 'LocalSubnet', [switch]$Remove)
$ErrorActionPreference = 'Stop'
$RuleName = 'RegAssist DZ (LAN)'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host "Droits d'administrateur requis : demande d'elevation (UAC)..." -ForegroundColor Yellow
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Port', $Port, '-RemoteAddress', "`"$RemoteAddress`"")
    if ($Remove) { $argList += '-Remove' }
    try { Start-Process -FilePath powershell.exe -ArgumentList $argList -Verb RunAs -Wait } catch { Write-Host "Elevation refusee ou impossible : la regle n'a pas ete modifiee." -ForegroundColor Red; exit 1 }
    exit 0
}
if ($Remove) {
    Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Host "Regle '$RuleName' supprimee (si elle existait)." -ForegroundColor Green
    Read-Host "Entree pour fermer" | Out-Null
    exit 0
}
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { Write-Host "ERREUR : Python introuvable dans le PATH." -ForegroundColor Red; Read-Host "Entree pour fermer" | Out-Null; exit 1 }
Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
$null = New-NetFirewallRule -DisplayName $RuleName -Description "RegAssist DZ : acces des collegues du meme reseau (mode -Lan). Supprimer avec .\lan_firewall.ps1 -Remove" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Domain -RemoteAddress $RemoteAddress -Program $python.Source
Write-Host "Regle '$RuleName' creee :" -ForegroundColor Green
Get-NetFirewallRule -DisplayName $RuleName | ForEach-Object {
    $pf = $_ | Get-NetFirewallPortFilter; $af = $_ | Get-NetFirewallAddressFilter; $app = $_ | Get-NetFirewallApplicationFilter
    Write-Host ("  entrant TCP port {0} | profil {1} | depuis {2} | programme {3}" -f $pf.LocalPort, $_.Profile, ($af.RemoteAddress -join ','), $app.Program)
}
$fwDomain = Get-NetFirewallProfile -Name Domain -ErrorAction SilentlyContinue
if ($fwDomain -and -not $fwDomain.Enabled) { Write-Host "ATTENTION : le pare-feu Windows est DESACTIVE pour le profil Domaine sur ce poste : cette regle est sans effet tant qu'il l'est (le port reste joignable par tout le reseau)." -ForegroundColor Yellow }
Write-Host "Etape suivante : .\start_local.ps1 -Lan   (suppression de la regle : .\lan_firewall.ps1 -Remove)"
Read-Host "Entree pour fermer" | Out-Null
