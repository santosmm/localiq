#!/usr/bin/env python3
"""
Exporta dados do Airtable (tabela Freguesias) e importa no Supabase.

Uso:
  python migrar-supabase.py

Variáveis de ambiente necessárias:
  AIRTABLE_TOKEN   — Personal Access Token do Airtable
  SUPABASE_URL     — https://<ref>.supabase.co
  SUPABASE_KEY     — service_role key do projecto Supabase
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

# ─── Configuração ─────────────────────────────────────────────────────────────

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
SUPABASE_URL   = os.environ.get("SUPABASE_URL")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY")

AIRTABLE_BASE_ID  = "appzKGnGUD6pafKKn"
AIRTABLE_TABLE_ID = "tbl2mvTKYsrb1h6fc"
AIRTABLE_API      = "https://api.airtable.com/v0"

# Mapeamento Airtable → Supabase (campo Airtable: coluna Supabase)
MAPEAMENTO = {
    "Nome":                 "nome",
    "Município":            "municipio",
    "Codigo_INE":           "codigo_ine",
    "Populacao":            "populacao",
    "Score_Geral":          "score_geral",
    "Transportes_Score":    "transportes_score",
    "Transportes_Valor":    "transportes_valor",
    "Ar_Score":             "ar_score",
    "Ar_Valor":             "ar_valor",
    "Demografia_Score":     "demografia_score",
    "Demografia_Valor":     "demografia_valor",
    "Ensino_Score":         "ensino_score",
    "Ensino_Valor":         "ensino_valor",
    "Saude_Score":          "saude_score",
    "Saude_Valor":          "saude_valor",
    "Arrendamento_Score":   "arrendamento_score",
    "Arrendamento_Valor":   "arrendamento_valor",
    "Rendas_Mediana":       "rendas_mediana",
    "Preco_Avaliacao_m2":   "preco_avaliacao_m2",
    "Resumo_IA":            "resumo_ia",
}

# Todas as colunas Supabase — garante que todos os registos têm as mesmas chaves
TODAS_COLUNAS = list(MAPEAMENTO.values())

CAMPOS_NUMERICOS = {
    "populacao", "score_geral",
    "transportes_score", "transportes_valor",
    "ar_score", "ar_valor",
    "demografia_score", "demografia_valor",
    "ensino_score", "ensino_valor",
    "saude_score", "saude_valor",
    "arrendamento_score", "arrendamento_valor",
    "rendas_mediana", "preco_avaliacao_m2",
}


# ─── Utilitários ──────────────────────────────────────────────────────────────

def _inteiro(val):
    if val is None:
        return None
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return None


def _decimal(val):
    if val is None:
        return None
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return None


def mapear_registo(fields):
    # Inicializa todas as colunas a None — PostgREST exige chaves idênticas em todos os registos do lote
    registo = {col: None for col in TODAS_COLUNAS}
    for campo_at, coluna_sb in MAPEAMENTO.items():
        val = fields.get(campo_at)
        if val is None:
            continue
        if coluna_sb == "populacao":
            registo[coluna_sb] = _inteiro(val)
        elif coluna_sb in CAMPOS_NUMERICOS:
            registo[coluna_sb] = _decimal(val)
        else:
            registo[coluna_sb] = str(val).strip()
    return registo


# ─── Airtable: exportar ───────────────────────────────────────────────────────

def exportar_airtable():
    registos = []
    offset   = None

    while True:
        url = f"{AIRTABLE_API}/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}?pageSize=100"
        if offset:
            url += f"&offset={offset}"

        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
        )
        with urllib.request.urlopen(req) as resp:
            dados = json.loads(resp.read())

        for r in dados.get("records", []):
            registo = mapear_registo(r["fields"])
            if registo.get("nome") and registo.get("municipio"):
                registos.append(registo)

        offset = dados.get("offset")
        if not offset:
            break

        time.sleep(0.22)

    return registos


# ─── Supabase: importar ───────────────────────────────────────────────────────

def _post_supabase(url, headers, payload):
    corpo = json.dumps(payload).encode("utf-8")
    req   = urllib.request.Request(url, data=corpo, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def importar_supabase(registos):
    # ?on_conflict=codigo_ine diz ao PostgREST qual coluna usar no ON CONFLICT DO UPDATE
    url     = f"{SUPABASE_URL}/rest/v1/freguesias?on_conflict=codigo_ine"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=representation",
    }

    LOTE      = 50
    total     = len(registos)
    inseridos = 0
    falhas    = 0

    for i in range(0, total, LOTE):
        lote = registos[i:i + LOTE]
        try:
            resultado  = _post_supabase(url, headers, lote)
            inseridos += len(resultado)
        except urllib.error.HTTPError:
            # Fallback: inserir um a um para não perder o lote inteiro
            for reg in lote:
                try:
                    _post_supabase(url, headers, [reg])
                    inseridos += 1
                except urllib.error.HTTPError as e:
                    falhas += 1

        print(f"  Migrados {inseridos} de {total} registos...", end="\r")

    print()  # nova linha após o \r
    if falhas:
        print(f"  Falhas: {falhas} registos não importados.", file=sys.stderr)

    return inseridos


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    erros = []
    if not AIRTABLE_TOKEN:
        erros.append("AIRTABLE_TOKEN")
    if not SUPABASE_URL:
        erros.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        erros.append("SUPABASE_KEY")
    if erros:
        for e in erros:
            print(f"  export {e}=...", file=sys.stderr)
        sys.exit(1)

    print("1. A exportar do Airtable...")
    registos = exportar_airtable()
    print(f"   {len(registos)} registos exportados.")

    if not registos:
        print("Nenhum registo para importar.")
        sys.exit(0)

    print("2. A importar no Supabase...")
    total = importar_supabase(registos)
    print(f"\nConcluído: {total}/{len(registos)} registos no Supabase.")


if __name__ == "__main__":
    main()
