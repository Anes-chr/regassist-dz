"""Vérifications automatiques et déterministes. Elles mesurent le RESPECT de critères simples (mots attendus, format, nombre),
pas la qualité rédactionnelle : un score élevé ne prouve pas qu'une réponse est bonne, un score bas signale un défaut probable."""
import json
import re

AR = re.compile(r"[؀-ۿ]")
LAT = re.compile(r"[A-Za-zÀ-ÿ]")


def arabic_ratio(t: str) -> float:
    a, l = len(AR.findall(t)), len(LAT.findall(t))
    return a / (a + l) if (a + l) else 0.0


def _norm_num(s: str) -> str:
    return re.sub(r"[\s  .,]", "", s)


def _extract_json(t: str):
    t = t.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    try:
        return json.loads(t), True
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return json.loads(m.group(0)), False   # JSON présent mais entouré d'autre texte
            except Exception:
                pass
    return None, False


def score(item: dict, text: str):
    """Retourne (ok: bool, échecs: list[str])."""
    fails = []
    t = text.strip()
    low = t.lower()
    words = len(t.split())
    if not t:
        return False, ["réponse vide"]
    if "expect_any" in item and not any(k.lower() in low for k in item["expect_any"]):
        fails.append("aucun mot attendu")
    for grp in item.get("expect_all_groups", []):
        if not any(k.lower() in low for k in grp):
            fails.append(f"groupe absent {grp[:2]}")
    if "min_arabic_ratio" in item and arabic_ratio(t) < item["min_arabic_ratio"]:
        fails.append(f"pas assez d'arabe ({arabic_ratio(t):.2f})")
    if "max_arabic_ratio" in item and arabic_ratio(t) > item["max_arabic_ratio"]:
        fails.append("arabe inattendu dans une réponse française")
    if "min_words" in item and words < item["min_words"]:
        fails.append(f"trop court ({words} mots)")
    if "max_words" in item and words > item["max_words"]:
        fails.append(f"trop long ({words} mots)")
    if "max_sentences" in item and len([s for s in re.split(r"[.!?؟]+\s", t) if s.strip()]) > item["max_sentences"]:
        fails.append("plus d'une phrase")
    for rx in item.get("regex_all", []):
        if not re.search(rx, t, re.I | re.S):
            fails.append(f"motif absent /{rx[:25]}/")
    for rx in item.get("regex_cs", []):   # sensible à la casse
        if not re.search(rx, t, re.S):
            fails.append(f"motif (casse) absent /{rx[:25]}/")
    for rx in item.get("regex_none", []):
        if re.search(rx, t, re.I | re.S):
            fails.append(f"motif interdit /{rx[:25]}/")
    if "contains_number" in item:
        nums = {_norm_num(x) for x in re.findall(r"\d[\d\s  .,]*", t)}
        if not any(_norm_num(n) in nums or any(_norm_num(n) == x for x in nums) for n in item["contains_number"]):
            fails.append(f"nombre attendu absent {item['contains_number']}")
    if "final_number" in item:
        last = re.findall(r"\d+(?:[.,]\d+)?", t)
        if not last or float(last[-1].replace(",", ".")) != item["final_number"]:
            fails.append(f"réponse finale ≠ {item['final_number']}")
    if "exact_oneword" in item:
        if re.sub(r"[^\wÀ-ÿ؀-ۿ]", "", low) != item["exact_oneword"]:
            fails.append(f"réponse ≠ « {item['exact_oneword']} » seule")
    if "bullets_exact" in item:
        bl = [l for l in t.splitlines() if re.match(r"^\s*[-•*]\s+\S", l)]
        if len(bl) != item["bullets_exact"]:
            fails.append(f"{len(bl)} puces au lieu de {item['bullets_exact']}")
        if item.get("only_bullets") and [l for l in t.splitlines() if l.strip() and not re.match(r"^\s*[-•*]\s+\S", l)]:
            fails.append("texte hors puces")
    if "json_list_len" in item:
        m = re.search(r"\[.*\]", re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S), re.S)
        try:
            lst = json.loads(m.group(0)) if m else None
        except Exception:
            lst = None
        if not isinstance(lst, list):
            fails.append("tableau JSON invalide")
        elif len(lst) != item["json_list_len"]:
            fails.append(f"{len(lst)} éléments au lieu de {item['json_list_len']}")
        elif item.get("json_list_item_str") and not all(isinstance(x, str) for x in lst):
            fails.append("éléments non-chaînes (objets/nombres) alors que des chaînes étaient demandées")
    if any(k in item for k in ("json_keys", "json_equals", "json_contains", "json_number_in")):
        obj, pure = _extract_json(t)
        if obj is None or not isinstance(obj, dict):
            fails.append("JSON invalide")
        else:
            if not pure:
                fails.append("JSON entouré d'autre texte")
            for k in item.get("json_keys", []):
                if k not in obj:
                    fails.append(f"clé absente {k}")
            for k, v in item.get("json_equals", {}).items():
                if obj.get(k) != v:
                    fails.append(f"{k} ≠ {v}")
            for k, v in item.get("json_contains", {}).items():
                if v.lower() not in str(obj.get(k, "")).lower():
                    fails.append(f"{k} ne contient pas {v}")
            for k, vs in item.get("json_number_in", {}).items():
                try:
                    if float(str(obj.get(k)).replace(",", ".")) not in vs:
                        fails.append(f"{k} hors {vs}")
                except Exception:
                    fails.append(f"{k} non numérique")
    return (not fails), fails
