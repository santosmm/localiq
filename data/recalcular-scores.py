#!/usr/bin/env python3
"""
Recalcula score_geral para todas as freguesias do Supabase.

Fórmula: média simples de todos os scores reais disponíveis (não nulos).
  score_geral = mean(seguranca_score, clima_score, transportes_score, ...)

Quando um novo enricher preenche um score_*, basta correr este script para
actualizar score_geral de forma a reflectir os dados mais recentes.

Fallback: se nenhum score real estiver disponível, usa proxy de população
  (min(round((populacao/50000)*10, 1), 10)) para não deixar score_geral a null.

Scores considerados (adicionados à medida que os enrichers são criados):
  seguranca_score    — preenchido (INE criminalidade 2023)
  clima_score        — preenchido (ERA5 média 2015-2024)
  arrendamento_score — parcialmente preenchido (INE rendas 2024, 2608/3259)
  transportes_score  — pendente
  ar_score           — pendente
  demografia_score   — pendente
  ensino_score       — pendente
  saude_score        — pendente

Uso:
  export SUPABASE_URL=https://hkxdmregnsmsbxvpykul.supabase.co
  export SUPABASE_KEY=<service_role_key>
  python3 data/recalcular-scores.py
  python3 data/recalcular-scores.py --dry-run
  python3 data/recalcular-scores.py --limite 10
"""

import json
import os
import sys
import time
import argparse
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Scores reais a incluir na média — ordem não afecta o resultado
SCORE_CAMPOS = [
    "seguranca_score",
    "clima_score",
    "arrendamento_score",
    "transportes_score",
    "ar_score",
    "demografia_score",
    "ensino_score",
    "saude_score",
]

PAGINA   = 1000
LOTE_MAX = 100   # máx de codigo_ine por PATCH IN(...)


# ─── Score ────────────────────────────────────────────────────────────────────

def calcular_score_geral(registro):
    """
    Média dos scores reais não nulos.
    Fallback para proxy de população se nenhum score real existir.
    """
    valores = [registro[c] for c in SCORE_CAMPOS if registro.get(c) is not None]
    if valores:
        return round(sum(valores) / len(valores), 1)

    # Fallback: proxy de população (temporário — só para freguesias sem nenhum score real)
    pop = registro.get("populacao")
    if pop and pop > 0:
        return min(round((pop / 50000) * 10, 1), 10.0)
    return None


# ─── Supabase ─────────────────────────────────────────────────────────────────

def sb_headers():
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def sb_listar_freguesias():
    """Devolve todos os registos com codigo_ine, populacao e todos os score_*."""
    campos   = ",".join(["codigo_ine", "populacao"] + SCORE_CAMPOS)
    registos = []
    offset   = 0

    while True:
        url = (f"{SUPABASE_URL}/rest/v1/freguesias"
               f"?select={campos}&limit={PAGINA}&offset={offset}")
        req = urllib.request.Request(
            url, headers={**sb_headers(), "Accept": "application/json"})
        with urllib.request.urlopen(req) as resp:
            pagina = json.loads(resp.read())
        registos.extend(pagina)
        if len(pagina) < PAGINA:
            break
        offset += PAGINA

    return registos


def sb_actualizar_lote(codigos, score, dry_run):
    """PATCH score_geral em lote por lista de codigo_ine."""
    lista    = "(" + ",".join(codigos) + ")"
    url      = (f"{SUPABASE_URL}/rest/v1/freguesias"
                f"?codigo_ine=in.{urllib.parse.quote(lista)}")
    corpo    = json.dumps({"score_geral": score}).encode("utf-8")
    headers  = {
        **sb_headers(),
        "Content-Type": "application/json",
        "Prefer":       "return=minimal",
    }
    if dry_run:
        return True
    req = urllib.request.Request(url, data=corpo, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req):
            return True
    except urllib.error.HTTPError as e:
        print(f"\n    ✗ HTTP {e.code}: {e.read().decode()[:150]}", file=sys.stderr)
        return False


# ─── Pipeline principal ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Recalcula score_geral como média dos scores reais disponíveis.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra distribuição de scores sem escrever no Supabase")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processar apenas N freguesias (teste)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Erro: SUPABASE_URL e SUPABASE_KEY são obrigatórias.", file=sys.stderr)
        sys.exit(1)

    # ── 1. Buscar todas as freguesias ─────────────────────────────────────────
    print("A buscar freguesias do Supabase...")
    registos = sb_listar_freguesias()
    print(f"  {len(registos)} registos encontrados.")

    if args.limite:
        registos = registos[:args.limite]
        print(f"  (limitado a {args.limite} por --limite)")

    # ── 2. Calcular novo score_geral para cada freguesia ──────────────────────
    grupos      = {}   # {score_geral: [codigo_ine, ...]}
    com_reais   = 0
    com_proxy   = 0
    sem_score   = 0
    n_campos    = {}   # {nº_scores_usados: count}

    for r in registos:
        scores_reais = [r[c] for c in SCORE_CAMPOS if r.get(c) is not None]
        novo_score   = calcular_score_geral(r)

        if novo_score is None:
            sem_score += 1
            continue
        if scores_reais:
            com_reais += 1
            n = len(scores_reais)
            n_campos[n] = n_campos.get(n, 0) + 1
        else:
            com_proxy += 1

        grupos.setdefault(novo_score, []).append(str(r["codigo_ine"]))

    scores_unicos = len(grupos)
    total_update  = sum(len(v) for v in grupos.values())

    print(f"\n  Distribuição do novo score_geral:")
    print(f"    {com_reais} freguesias — média de scores reais")
    if n_campos:
        for n, cnt in sorted(n_campos.items(), reverse=True):
            nomes = [SCORE_CAMPOS[i] for i in range(len(SCORE_CAMPOS))
                     if any(r.get(SCORE_CAMPOS[i]) is not None for r in registos[:5])]
            print(f"      {cnt:4d} com {n} score(s) preenchido(s)")
    if com_proxy:
        print(f"    {com_proxy} freguesias — fallback proxy de população")
    if sem_score:
        print(f"    {sem_score} freguesias — sem score (ficam inalteradas)")
    print(f"    {scores_unicos} valores únicos de score_geral")

    if args.dry_run:
        # Mostrar amostra da distribuição
        amostra = sorted(grupos.items())
        print(f"\n  Amostra da distribuição (primeiros/últimos valores):")
        for sc, cods in amostra[:5]:
            print(f"    score {sc:4.1f} → {len(cods)} freguesias")
        if len(amostra) > 10:
            print(f"    ...")
        for sc, cods in amostra[-5:]:
            print(f"    score {sc:4.1f} → {len(cods)} freguesias")
        print(f"\n  [DRY-RUN — Supabase não foi alterado]")
        return

    # ── 3. Actualizar em lotes por valor de score_geral ───────────────────────
    print(f"\nA actualizar {total_update} freguesias em {scores_unicos} lotes...")

    actualizados = 0
    erros        = 0

    for score, codigos in grupos.items():
        for i in range(0, len(codigos), LOTE_MAX):
            sub = codigos[i:i + LOTE_MAX]
            ok  = sb_actualizar_lote(sub, score, dry_run=False)
            if ok:
                actualizados += len(sub)
            else:
                erros += len(sub)
        print(f"  {actualizados}/{total_update} actualizados...", end="\r")
        time.sleep(0.05)

    print(f"\n\n{'=' * 52}")
    print(f"Concluído:")
    print(f"  {actualizados} scores actualizados")
    print(f"  {erros} erros")
    print(f"  Scores reais usados: {', '.join(SCORE_CAMPOS[:3])} ...")
    print(f"{'=' * 52}\n")


if __name__ == "__main__":
    main()
