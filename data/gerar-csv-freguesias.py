#!/usr/bin/env python3
"""
Gera um CSV completo de todas as freguesias de Portugal
com dados dos Censos 2021 directamente da API do INE.

Campos gerados:
  codigo_ine  — DICOFRE 6 dígitos (ex: 110656)
  nome        — nome da freguesia
  municipio   — nome do município
  populacao   — população residente (Censos 2021)

Os scores (transportes, saúde, educação, segurança) NÃO estão disponíveis
na API do INE ao nível de freguesia — têm de vir de outras fontes (ACSS,
IMT, DGEEC). O CSV pode ser importado sem scores; o enricher-ine.py
acrescenta depois os dados de arrendamento.

Uso:
  python3 data/gerar-csv-freguesias.py
  python3 data/gerar-csv-freguesias.py --saida data/freguesias2021.csv
"""

import csv
import json
import re
import sys
import time
import argparse
import urllib.request
import urllib.error

INE_BASE = "https://www.ine.pt/ine/json_indicador/pindica.jsp"

IND_POPULACAO = "0014584"  # Pop. residente por sexo (Censos 2021)
PERIODO       = "S7A2021"
LVL_FREGUESIA = "lvl@6"
LVL_MUNICIPIO = "lvl@5"


def nome_curto(nome):
    """Remove prefixo 'União das/do/da/de freguesias de...' dos nomes oficiais INE."""
    # 'Nome (União das freguesias de ...)' → manter só 'Nome'
    m = re.match(r'^(.+?)\s*\(União[^)]+\)$', nome)
    if m:
        return m.group(1).strip()
    # 'União das/do/da/de freguesias de/do/da ...' → remover prefixo
    m = re.match(r'^União\s+(?:das?|dos?)\s+(?:freguesias?\s+)?(?:de|do|da|das)\s+(.+)$', nome, re.I)
    if m:
        return m.group(1).strip()
    # 'União de ...' simples
    m = re.match(r'^União\s+de\s+(.+)$', nome, re.I)
    if m:
        return m.group(1).strip()
    return nome


def ine_fetch(varcd, dim1, dim2):
    url = f"{INE_BASE}?op=2&varcd={varcd}&Dim1={dim1}&Dim2={dim2}&lang=PT"
    req = urllib.request.Request(url, headers={"User-Agent": "MelhorZona/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠ Erro ao buscar {varcd}: {e}", file=sys.stderr)
        return []

    item = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(item, dict):
        return []

    dados = item.get("Dados", {})
    if not dados:
        return []

    periodos = sorted(dados.keys(), reverse=True)
    return dados[periodos[0]]


def main():
    parser = argparse.ArgumentParser(description="Gera CSV de todas as freguesias via API INE.")
    parser.add_argument("--saida", default="data/freguesias2021.csv",
                        help="Caminho do CSV de saída (default: data/freguesias2021.csv)")
    args = parser.parse_args()

    # ── 1. Buscar nomes dos municípios (lvl@5) ─────────────────────────────────
    print("A buscar municípios (Censos 2021)...")
    regs_mun = ine_fetch(IND_POPULACAO, PERIODO, LVL_MUNICIPIO)
    # Filtrar só total (HM) e construir índice {geocod4 → nome_municipio}
    municipios = {}
    for r in regs_mun:
        if r.get("dim_3_t") == "HM":
            cod = str(r["geocod"]).strip().zfill(4)
            municipios[cod] = r["geodsg"].strip()
    print(f"  {len(municipios)} municípios indexados.")

    # ── 2. Buscar todas as freguesias (lvl@6) ──────────────────────────────────
    print("A buscar freguesias (Censos 2021)...")
    regs_freg = ine_fetch(IND_POPULACAO, PERIODO, LVL_FREGUESIA)
    totais = [r for r in regs_freg if r.get("dim_3_t") == "HM"]
    print(f"  {len(totais)} registos de população por freguesia encontrados.")

    # ── 3. Construir linhas do CSV ──────────────────────────────────────────────
    linhas = []
    sem_municipio = 0

    for r in totais:
        geocod = str(r.get("geocod", "")).strip()
        if len(geocod) < 6:
            continue  # ignorar geocods inválidos

        nome    = nome_curto(r.get("geodsg", "").strip())
        pop_raw = r.get("valor", "")
        try:
            pop = int(str(pop_raw).replace(" ", "").replace(" ", ""))
        except ValueError:
            pop = ""

        # Município: primeiros 4 dígitos do DICOFRE
        cod_mun   = geocod[:4]
        municipio = municipios.get(cod_mun, "")
        if not municipio:
            sem_municipio += 1

        linhas.append({
            "codigo_ine": geocod,
            "nome":       nome,
            "municipio":  municipio,
            "populacao":  pop,
        })

    # Ordenar por código INE
    linhas.sort(key=lambda x: x["codigo_ine"])

    # ── 4. Escrever CSV ────────────────────────────────────────────────────────
    with open(args.saida, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["codigo_ine", "nome", "municipio", "populacao"])
        writer.writeheader()
        writer.writerows(linhas)

    print(f"""
{'=' * 50}
CSV gerado: {args.saida}
  {len(linhas)} freguesias
  {sem_municipio} sem município identificado (geocod não encontrado em lvl@5)

Próximos passos:
  1. Importar para o Airtable:
       python3 data/importar-ine.py --csv {args.saida}

  2. Enriquecer com rendas INE 2024:
       python3 data/enricher-ine.py
{'=' * 50}
""")


if __name__ == "__main__":
    main()
