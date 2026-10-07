# Configuration locale du LLM (dot-source : . .\llm_local\config.ps1).
# Tout est sous D:\llm pour ne pas remplir C:. Fichier volontairement ASCII (PowerShell 5.1).
$Global:LLM_ROOT    = "D:\llm"
$Global:LLM_TAG     = (Get-Content "$LLM_ROOT\llama.cpp\CURRENT_TAG.txt" -ErrorAction SilentlyContinue)
$Global:LLM_BIN     = "$LLM_ROOT\llama.cpp\$LLM_TAG"
$Global:LLM_MODEL   = "$LLM_ROOT\models\qwen3-4b-instruct-2507-q4_k_m.gguf"
$Global:LLM_THREADS = 8       # voir le benchmark : meilleur compromis debit / fluidite du PC
$Global:LLM_CTX     = 4096    # contexte (tokens) ; le cache KV coute ~150 Ko/token en f16
$Global:LLM_PORT    = 8187    # 8080 est deja pris par un autre programme de la machine
