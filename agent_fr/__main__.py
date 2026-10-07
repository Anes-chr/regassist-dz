"""CLI : python -m agent_fr "question" [--llm] | python -m agent_fr --serve | python -m agent_fr --eval"""
import argparse
import sys
import textwrap


def show(res: dict):
    print(res["answer"])
    for c in res["citations"]:
        pg = f"p. {c['page']}" + (f"–{c['page_fin']}" if c["page_fin"] and c["page_fin"] != c["page"] else "") + " du PDF"
        print(f"\n[{c['id']}] {c['texte']} — {c['emplacement'] or 'passage'} ({pg}) · statut : {c['statut']}")
        if c["chapitre"] or c["section"]:
            print("    " + " > ".join(x for x in (c["chapitre"], c["section"]) if x))
        print(textwrap.indent(textwrap.fill(c["extrait"][:700] + (" […]" if len(c["extrait"]) > 700 else ""), 96), "    "))
        print(f"    PDF : {c['document_url']}\n    Page du site : {c['source_url']}")
        for k, v in c["relations"].items():
            print(f"    {k} : {' ; '.join(v)}")
        if c["via"]:
            print(f"    ↳ Texte qui {c['via']}")
        if c["alerte"]:
            print(f"    ⚠ {c['alerte']}")
        if c["autres_copies"]:
            print(f"    Autres copies du même texte dans le corpus : {', '.join(c['autres_copies'])}")
        if c["a_verifier"]:
            print("    ⚠ Document signalé « à vérifier » (OCR, numérotation ou métadonnées) : contrôle humain requis.")
    for n in res["notes"]:
        print(f"\nNote : {n}")
    print(f"\n{res['disclaimer']}")


def main():
    ap = argparse.ArgumentParser(prog="agent_fr")
    ap.add_argument("question", nargs="?")
    ap.add_argument("--llm", action="store_true", help="rédige la réponse avec le LLM (LOCAL par défaut ; API distante seulement avec AGENT_LLM=anthropic et AGENT_ALLOW_REMOTE_LLM=1)")
    ap.add_argument("--local-llm", action="store_true", help="rédige la réponse avec le LLM LOCAL (llama-server, Qwen3-4B sur CPU)")
    ap.add_argument("--serve", action="store_true", help="interface web locale (http://127.0.0.1:8765)")
    ap.add_argument("--eval", action="store_true", help="lance les jeux de tests")
    ap.add_argument("--reindex", action="store_true", help="reconstruit l'index depuis corpus/chunks/chunks_fr.jsonl")
    a = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    import os
    if a.local_llm:
        os.environ["AGENT_LLM"] = "local"
        a.llm = True
    from .agent import ask, get_index
    if a.reindex:
        get_index(force=True)
        print("Index reconstruit.")
    if a.serve:
        from .app import run
        return run()
    if a.eval:
        from .evaluate import run_all
        return run_all()
    if a.question:
        show(ask(a.question, use_llm=a.llm))
    elif not a.reindex:
        ap.print_help()


main()
