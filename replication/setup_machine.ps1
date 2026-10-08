# Installe sur une autre machine ce qui n'est PAS dans le depot Git : modeles (embeddings, reranker, LLM), llama.cpp, vecteurs et
# instantane du corpus. Chaque fichier est verifie par SHA-256 contre agent_fr\eval\human\PHASE_4_FROZEN.manifest.json (source unique
# de verite) ; un fichier telecharge dont l'empreinte differe est supprime. Ne modifie JAMAIS le depot. Fichier ASCII (PowerShell 5.1).
#
# Usage : .\replication\setup_machine.ps1 [-VerifyOnly] [-SkipLlm] [-WithOcr] [-Yes] [-NoFreezeCheck] [-LlmRoot D:\llm]
#   -VerifyOnly     ne telecharge ni ne copie rien : controle seulement et affiche l'etat (code de sortie 1 s'il manque quelque chose)
#   -SkipLlm        n'installe pas le LLM (2,5 Go) ni llama.cpp : la recherche fonctionne, pas la redaction des reponses
#   -WithOcr        telecharge aussi ara.traineddata (tessdata_best, 12 Mo) : utile seulement pour refaire l'OCR du corpus
#   -Yes            ne demande pas de confirmation avant de telecharger
#   -NoFreezeCheck  ne lance pas la verification finale du gel
# Le manifeste du gel contient des chemins absolus D:/llm/... : sur une machine sans lecteur D:, creez-en un (ex. subst D: C:\donnees).
param([string]$LlmRoot = 'D:\llm', [switch]$VerifyOnly, [switch]$SkipLlm, [switch]$WithOcr, [switch]$Yes, [switch]$NoFreezeCheck)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path $PSScriptRoot -Parent
$ManifestPath = Join-Path $Repo 'agent_fr\eval\human\PHASE_4_FROZEN.manifest.json'
if (-not (Test-Path $ManifestPath)) { Write-Host "ERREUR : manifeste introuvable : $ManifestPath" -ForegroundColor Red; exit 1 }
$man = Get-Content -Raw -Encoding UTF8 $ManifestPath | ConvertFrom-Json

# ---- Sources publiques (les tailles ont ete verifiees contre le manifeste) ----
$E5 = 'https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/'
$RR = 'https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/resolve/main/'
$LlamaZipUrl = 'https://github.com/ggml-org/llama.cpp/releases/download/b11411/llama-b11411-bin-win-cpu-x64.zip'
$LlamaZipBytes = 19391335
$Models = @(
    @{ Rel = 'models/embeddings/multilingual-e5-small/onnx/model.onnx';               Url = $E5 + 'onnx/model.onnx';              Llm = $false }
    @{ Rel = 'models/embeddings/multilingual-e5-small/tokenizer.json';                Url = $E5 + 'tokenizer.json';               Llm = $false }
    @{ Rel = 'models/rerankers/mmarco-mMiniLMv2-L12-H384/onnx/model_quint8_avx2.onnx'; Url = $RR + 'onnx/model_quint8_avx2.onnx'; Llm = $false }
    @{ Rel = 'models/rerankers/mmarco-mMiniLMv2-L12-H384/tokenizer.json';             Url = $RR + 'tokenizer.json';               Llm = $false }
    @{ Rel = 'models/qwen3-4b-instruct-2507-q4_k_m.gguf'; Url = 'https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'; Llm = $true }
)
if ($WithOcr) { $Models += @{ Rel = 'tessdata_best/ara.traineddata'; Url = 'https://github.com/tesseract-ocr/tessdata_best/raw/main/ara.traineddata'; Llm = $false } }

function Get-Sha([string]$p) { (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower() }
function Expected([string]$rel) {
    $e = $man.modeles.PSObject.Properties | Where-Object { $_.Name -eq ("D:/llm/" + $rel) } | Select-Object -First 1
    if ($e) { return @{ Sha = $e.Value.sha256; Bytes = [int64]$e.Value.bytes } }
    return $null
}
function Test-Item([string]$path, $exp) {
    if (-not (Test-Path -LiteralPath $path)) { return 'ABSENT' }
    if ((Get-Item -LiteralPath $path).Length -ne $exp.Bytes) { return 'TAILLE' }
    if ((Get-Sha $path) -ne $exp.Sha) { return 'EMPREINTE' }
    return 'OK'
}
function Get-Remote([string]$url, [string]$dst, [int64]$bytes) {
    $null = New-Item -ItemType Directory -Force (Split-Path $dst)
    $part = "$dst.part"
    for ($i = 1; $i -le 20; $i++) {
        $cur = if (Test-Path -LiteralPath $part) { (Get-Item -LiteralPath $part).Length } else { 0 }
        if ($cur -ge $bytes) { break }
        & curl.exe -L --fail -C - --retry 10 --retry-all-errors --retry-delay 3 --connect-timeout 20 -sS -o $part $url
        Start-Sleep 1
    }
    if (-not (Test-Path -LiteralPath $part)) { throw "telechargement echoue : $url" }
}

Write-Host "RegAssist DZ - installation / controle de la machine (racine des donnees : $LlmRoot)"
if ($LlmRoot -ne 'D:\llm') { Write-Host "ATTENTION : le manifeste du gel et les scripts du projet attendent D:\llm ; une autre racine ne passera pas la verification du gel." -ForegroundColor Yellow }
if (-not (Test-Path (Split-Path $LlmRoot -Qualifier))) { Write-Host "ERREUR : le lecteur $(Split-Path $LlmRoot -Qualifier) n'existe pas (astuce : subst D: C:\donnees)." -ForegroundColor Red; exit 1 }
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "ATTENTION : Python introuvable (le projet a ete gele avec Python $($man.versions.python))." -ForegroundColor Yellow }
elseif (-not ((& python --version 2>&1) -match [regex]::Escape(($man.versions.python -replace '\.\d+$', '')))) { Write-Host "ATTENTION : version de Python differente de celle du gel ($($man.versions.python)) : $(& python --version 2>&1)" -ForegroundColor Yellow }

# ---- 1. Etat des fichiers ----
$todo = @(); $bad = 0
Write-Host "`n[1/4] Modeles"
foreach ($m in $Models) {
    if ($SkipLlm -and $m.Llm) { Write-Host ("  IGNORE    {0}  (-SkipLlm)" -f $m.Rel); continue }
    $exp = Expected $m.Rel
    if (-not $exp) { Write-Host "  ERREUR : $($m.Rel) absent du manifeste" -ForegroundColor Red; exit 1 }
    $dst = Join-Path $LlmRoot ($m.Rel -replace '/', '\')
    $st = Test-Item $dst $exp
    Write-Host ("  {0,-9} {1}  ({2:N1} Mo)" -f $st, $m.Rel, ($exp.Bytes / 1MB))
    if ($st -ne 'OK') { $bad++; $todo += @{ Kind = 'model'; Rel = $m.Rel; Url = $m.Url; Dst = $dst; Exp = $exp } }
}
if (-not $SkipLlm) {
    Write-Host "`n[2/4] llama.cpp b11411"
    $srvRel = 'llama.cpp/b11411/llama-server.exe'; $srvExp = Expected $srvRel; $srv = Join-Path $LlmRoot 'llama.cpp\b11411\llama-server.exe'
    $st = Test-Item $srv $srvExp
    Write-Host ("  {0,-9} {1}" -f $st, $srvRel)
    if ($st -ne 'OK') { $bad++; $todo += @{ Kind = 'llama'; Rel = 'llama.cpp/b11411.zip'; Url = $LlamaZipUrl; Dst = (Join-Path $LlmRoot 'llama.cpp\llama-b11411-bin-win-cpu-x64.zip'); Exp = @{ Bytes = [int64]$LlamaZipBytes }; Srv = $srv; SrvExp = $srvExp } }
    $tagFile = Join-Path $LlmRoot 'llama.cpp\CURRENT_TAG.txt'
    $tagOk = (Test-Path $tagFile) -and ((Get-Content $tagFile -Raw).Trim() -eq 'b11411')
    Write-Host ("  {0,-9} llama.cpp/CURRENT_TAG.txt" -f $(if ($tagOk) { 'OK' } else { 'ABSENT' }))
} else { Write-Host "`n[2/4] llama.cpp : ignore (-SkipLlm)" }

Write-Host "`n[3/4] Vecteurs et instantane du corpus (copies depuis replication\)"
$copies = @()
foreach ($p in $man.index.vecteurs.PSObject.Properties) { $fn = ($p.Name -split ':', 2)[1]; $copies += @{ Src = (Join-Path $PSScriptRoot "index\$fn"); Dst = (Join-Path $LlmRoot "index\$fn"); Exp = @{ Sha = $p.Value.sha256; Bytes = [int64]$p.Value.bytes } } }
foreach ($p in $man.corpus.instantane_fichiers.PSObject.Properties) {
    $src = Join-Path $PSScriptRoot "snapshots\corpus_phase4\$($p.Name)"
    $copies += @{ Src = $src; Dst = (Join-Path $LlmRoot "snapshots\corpus_phase4\$($p.Name)"); Exp = @{ Sha = $p.Value; Bytes = (Get-Item -LiteralPath $src).Length } }
}
$cacheKey = 'D:/llm/index/vec_cache_e5small.npz'; $cacheEntry = $man.informatif_non_strict.cache_vecteurs.$cacheKey
foreach ($c in $copies) {
    $st = Test-Item $c.Dst $c.Exp
    Write-Host ("  {0,-9} {1}" -f $st, $c.Dst.Substring($LlmRoot.Length + 1))
    if ($st -ne 'OK') { $bad++; $todo += @{ Kind = 'copy'; Src = $c.Src; Dst = $c.Dst; Exp = $c.Exp } }
}

if ($bad -eq 0) { Write-Host "`nTout est conforme au manifeste du gel." -ForegroundColor Green }
if ($VerifyOnly) { if ($bad -gt 0) { Write-Host "`n$bad element(s) a installer (relancer sans -VerifyOnly)." -ForegroundColor Yellow; exit 1 } ; exit 0 }

# ---- 2. Installation ----
if ($todo.Count -gt 0) {
    $dl = $todo | Where-Object { $_.Kind -ne 'copy' }
    if ($dl) {
        Write-Host "`nTelechargements necessaires (sources publiques) :"
        foreach ($d in $dl) { Write-Host ("  {0:N1} Mo  {1}`n            {2}" -f ($d.Exp.Bytes / 1MB), $d.Rel, $d.Url) }
        $free = (Get-PSDrive -Name (Split-Path $LlmRoot -Qualifier).TrimEnd(':')).Free
        $need = 0; foreach ($d in $dl) { $need += $d.Exp.Bytes }
        if ($free -lt ($need * 1.2)) { Write-Host "ERREUR : espace disque insuffisant ($([math]::Round($free/1GB,1)) Go libres)." -ForegroundColor Red; exit 1 }
        if (-not $Yes) { $r = Read-Host "Telecharger ces fichiers ? (o/N)"; if ($r -notmatch '^(o|O|y|Y)') { Write-Host "Annule."; exit 1 } }
    }
    foreach ($t in $todo) {
        if ($t.Kind -eq 'copy') {
            $null = New-Item -ItemType Directory -Force (Split-Path $t.Dst)
            Copy-Item -LiteralPath $t.Src -Destination $t.Dst -Force
            if ((Get-Sha $t.Dst) -ne $t.Exp.Sha) { throw "copie non conforme : $($t.Dst)" }
            continue
        }
        Write-Host "Telechargement : $($t.Rel)"
        Get-Remote $t.Url $t.Dst $t.Exp.Bytes
        $part = "$($t.Dst).part"
        if ($t.Kind -eq 'model') {
            if (((Get-Item -LiteralPath $part).Length -ne $t.Exp.Bytes) -or ((Get-Sha $part) -ne $t.Exp.Sha)) { Remove-Item -LiteralPath $part -Force; throw "empreinte differente du manifeste, fichier supprime : $($t.Rel)" }
            Move-Item -LiteralPath $part -Destination $t.Dst -Force
        } else {
            if ((Get-Item -LiteralPath $part).Length -ne $t.Exp.Bytes) { Remove-Item -LiteralPath $part -Force; throw "taille inattendue pour l'archive llama.cpp" }
            Move-Item -LiteralPath $part -Destination $t.Dst -Force
            $out = Join-Path $LlmRoot 'llama.cpp\b11411'
            Expand-Archive -LiteralPath $t.Dst -DestinationPath $out -Force
            if (-not (Test-Path $t.Srv)) { $f = Get-ChildItem $out -Recurse -Filter llama-server.exe | Select-Object -First 1; if ($f) { Get-ChildItem $f.DirectoryName | Move-Item -Destination $out -Force } }
            if ((Test-Item $t.Srv $t.SrvExp) -ne 'OK') { throw "llama-server.exe non conforme au manifeste apres extraction" }
        }
    }
}
if (-not $SkipLlm) { Set-Content -Path (Join-Path $LlmRoot 'llama.cpp\CURRENT_TAG.txt') -Value 'b11411' -Encoding ASCII }
if ($cacheEntry) {
    $cdst = Join-Path $LlmRoot 'index\vec_cache_e5small.npz'
    if (-not (Test-Path $cdst)) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'index\vec_cache_e5small.npz') -Destination $cdst }
}
Write-Host "`nInstallation terminee." -ForegroundColor Green

# ---- 3. Verification finale du gel ----
if (-not $NoFreezeCheck -and $py) {
    Write-Host "`n[4/4] Verification du gel (python -m agent_fr.eval.human.freeze_phase4 verify)"
    Push-Location $Repo
    try { & python -m agent_fr.eval.human.freeze_phase4 verify } finally { Pop-Location }
}
Write-Host "`nSuite : pip install -r requirements.txt  puis  .\start_local.ps1  (http://127.0.0.1:8790)"
