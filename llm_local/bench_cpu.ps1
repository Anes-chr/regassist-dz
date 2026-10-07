# Benchmark CPU reel avec llama-bench, un processus par nombre de threads, avec echantillonnage de la RAM.
# Usage : .\llm_local\bench_cpu.ps1 [-Threads 4,8,12,16] [-PromptTokens 512] [-GenTokens 128] [-Reps 3]
# Securite : arret automatique si la RAM disponible du systeme tombe sous 400 Mo.
# Reglages memoire : -lm none -b 512 -ub 128 (voir start_server.ps1). Fichier ASCII (PowerShell 5.1).
param([int[]]$Threads = @(4, 8, 12, 16), [int]$PromptTokens = 512, [int]$GenTokens = 128, [int]$Reps = 3)
. "$PSScriptRoot\config.ps1"
New-Item -ItemType Directory -Force "$PSScriptRoot\results" | Out-Null
$avail = New-Object System.Diagnostics.PerformanceCounter("Memory", "Available MBytes")
$out = @()
foreach ($t in $Threads) {
    $json = "$LLM_ROOT\bench\bench_t$t.json"
    $a = @('-m', $LLM_MODEL, '-t', $t, '-p', $PromptTokens, '-n', $GenTokens, '-r', $Reps, '-o', 'json', '-ngl', 0, '-b', 512, '-ub', 128, '-lm', 'none')
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath "$LLM_BIN\llama-bench.exe" -ArgumentList $a -PassThru -WindowStyle Hidden `
         -RedirectStandardOutput $json -RedirectStandardError "$json.err"
    $peak = 0; $minAvail = 1e9; $aborted = $false
    while (-not $p.HasExited) {
        try { $p.Refresh(); if ($p.PeakWorkingSet64 -gt $peak) { $peak = $p.PeakWorkingSet64 } } catch {}
        $av = $avail.NextValue(); if ($av -lt $minAvail) { $minAvail = $av }
        if ($av -lt 400) { Stop-Process -Id $p.Id -Force; $aborted = $true; "ARRET SECURITE : RAM disponible < 400 Mo ($av Mo)"; break }
        Start-Sleep -Milliseconds 400
    }
    $sw.Stop()
    $res = $null
    try { $res = Get-Content $json -Raw | ConvertFrom-Json } catch {}
    $pp = $res | Where-Object { $_.n_prompt -gt 0 -and $_.n_gen -eq 0 } | Select-Object -First 1
    $tg = $res | Where-Object { $_.n_gen -gt 0 -and $_.n_prompt -eq 0 } | Select-Object -First 1
    $row = [pscustomobject]@{
        Threads = $t; PromptTokS = [math]::Round($pp.avg_ts, 1); PromptStd = [math]::Round($pp.stddev_ts, 1)
        GenTokS = [math]::Round($tg.avg_ts, 2); GenStd = [math]::Round($tg.stddev_ts, 2)
        PicRAM_Mo = [math]::Round($peak / 1MB); RAMdispo_min_Mo = [int]$minAvail; Duree_s = [math]::Round($sw.Elapsed.TotalSeconds, 1); Abandon = $aborted
    }
    $out += $row; $row | Format-Table -AutoSize | Out-String | Write-Host
    if ($aborted) { break }
    Start-Sleep 5   # laisse le CPU et la RAM se stabiliser entre deux mesures
}
$out | ConvertTo-Json | Set-Content "$PSScriptRoot\results\bench_cpu.json" -Encoding UTF8
$out | Format-Table -AutoSize
