#!/usr/bin/env python3
"""
Recalcula score_geral para todas as freguesias do Supabase usando população como proxy.
Fórmula: min(round((populacao / 50000) * 10, 1), 10)

Uso:
  SUPABASE_URL=https://... SUPABASE_KEY=service_role_key python3 recalcular-scores.py
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def calcular_score(pop):
    if not pop or pop <= 0:
        return None
    return min(round((pop / 50000) * 10, 1), 10.0)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("  export SUPABASE_URL=https://...", file=sys.stderr)
        print("  export SUPABASE_KEY=service_role_key", file=sys.stderr)
        sys.exit(1)

    headers_base = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    # Buscar todas as freguesias com populacao preenchida (paginado — Supabase devolve max 1000/pedido)
    registos = []
    offset = 0
    PAGINA = 1000
    while True:
        url_get = (f"{SUPABASE_URL}/rest/v1/freguesias"
                   f"?select=codigo_ine,populacao"
                   f"&populacao=not.is.null"
                   f"&limit={PAGINA}&offset={offset}")
        req = urllib.request.Request(url_get, headers={**headers_base, "Accept": "application/json"})
        with urllib.request.urlopen(req) as resp:
            pagina = json.loads(resp.read())
        registos.extend(pagina)
        if len(pagina) < PAGINA:
            break
        offset += PAGINA

    print(f"  {len(registos)} freguesias com população encontradas.")

    headers_patch = {
        **headers_base,
        "Content-Type": "application/json",
        "Prefer":       "return=minimal",
    }

    # Agrupar por valor de score — reduz de 3259 pedidos individuais para ~100 lotes
    grupos = {}
    for r in registos:
        score = calcular_score(r["populacao"])
        if score is None:
            continue
        grupos.setdefault(score, []).append(str(r["codigo_ine"]))

    print(f"  {len(grupos)} valores de score únicos. A actualizar em lotes...")

    atualizados = 0
    erros = 0
    LOTE_MAX = 100  # max codigos por pedido IN(...)

    for score, codigos in grupos.items():
        # Partir em sub-lotes se necessário
        for i in range(0, len(codigos), LOTE_MAX):
            sub = codigos[i:i + LOTE_MAX]
            lista = "(" + ",".join(sub) + ")"
            url_patch = (f"{SUPABASE_URL}/rest/v1/freguesias"
                         f"?codigo_ine=in.{urllib.parse.quote(lista)}")
            corpo = json.dumps({"score_geral": score}).encode("utf-8")
            req_p = urllib.request.Request(url_patch, data=corpo,
                                           headers=headers_patch, method="PATCH")
            try:
                with urllib.request.urlopen(req_p):
                    pass
                atualizados += len(sub)
            except urllib.error.HTTPError as e:
                erros += len(sub)

        print(f"  {atualizados}/{len(registos)} actualizados...", end="\r")

    print(f"\n  Concluído: {atualizados} scores recalculados, {erros} erros.")


if __name__ == "__main__":
    main()
