"""Configuration centrale du pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
STATE_DIR = ROOT / "state"

BASE = "https://www.bank-of-algeria.dz"
HOST = "www.bank-of-algeria.dz"
ALLOWED_HOSTS = {"www.bank-of-algeria.dz", "bank-of-algeria.dz"}
USER_AGENT = "BoA-LegalCorpus-Builder/1.0 (recherche juridique; contact: mabedsalim2019@gmail.com)"

REQUEST_DELAY = 0.6      # secondes entre deux requêtes (poli)
TIMEOUT = 45
RETRIES = 4

# Pages d'entrée du périmètre juridique (FR + AR). Les autres pages juridiques sont
# découvertes par liens depuis ces hubs (cf. scope.py).
LEGAL_HUBS = [
    BASE + "/cadre-legislatif-et-reglementaire/",
    BASE + "/loi-monnaie-et-credit/",
    BASE + "/les-lignes-directrice/",
    BASE + "/les-notes-aux-banques-2/",
    # hub arabe « الإطار التشريعي و التنظيمي » (lien « Arabe » de la page FR)
    BASE + "/ar/%d8%a7%d9%84%d8%a5%d8%b7%d8%a7%d8%b1-%d8%a7%d9%84%d8%aa%d8%b4%d8%b1%d9%8a%d8%b9%d9%8a-%d9%88-%d8%a7%d9%84%d8%aa%d9%86%d8%b8%d9%8a%d9%85%d9%8a/",
]
LEGAL_HUB_AR_HINT = "%d8%a7%d9%84%d8%a5%d8%b7%d8%a7%d8%b1"  # « الإطار » (préfixe slug AR du hub)
LEGAL_BFS_DEPTH = 2

DOC_EXTS = {"pdf", "doc", "docx", "xls", "xlsx", "xlsm", "odt", "ods", "rtf", "zip"}
IMG_EXTS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "mp4", "mp3", "css", "js", "woff", "woff2", "ttf"}

EXCLUDE_URL_PATTERNS = [
    "/wp-json", "/wp-admin", "/xmlrpc", "/feed", "preview=true", "replytocom",
    "/wp-login", "?s=", "&s=", "/wp-content/plugins", "/embed/",
]

# Titres manifestement non normatifs (inventoriés, non intégrés sauf s'ils sont sur une page juridique)
NON_LEGAL_TITLE = r"(rapport annuel|rapport\s+20\d\d|bulletin\s+(statistique|n)|note de conjoncture|taux de change|cotation|billet|pi[èe]ces? |synth[èe]se du rapport|appel d.offre|avis d.appel)"

# Seuils qualité / OCR
OCR_MIN_CHARS_PER_PAGE = 40
LOW_TEXT_AVG_CHARS = 200
MAX_NONALPHA_RATIO = 0.45
OCR_DPI = 300
OCR_DPI_AR = 400
OCR_LOW_CONF = 75.0
CHUNK_MAX_CHARS = 2400
