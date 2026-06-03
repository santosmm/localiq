#!/usr/bin/env python3
"""
Importa dados do INE (Censos 2021) para o Airtable.

Uso:
  python importar-ine.py --csv caminho/para/ficheiro.csv [--limite 10]

O CSV deve ter as colunas (nomes flexíveis — ver mapeamento abaixo):
  codigo_ine, nome, municipio, populacao,
  transportes_score, saude_score, educacao_score, seguranca_score

Os scores são calculados internamente se não existirem no CSV.
"""

import csv
import json
import os
import sys
import argparse
import urllib.request
import urllib.error

# ─── Configuração ────────────────────────────────────────────────────────────

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
BASE_ID        = "appzKGnGUD6pafKKn"
TABLE_NAME     = "Freguesias"

AIRTABLE_API   = "https://api.airtable.com/v0"

# Mapeamento flexível de nomes de colunas do CSV para campos do Airtable
# Chave = nome normalizado interno, Valor = lista de aliases aceites no CSV
MAPEAMENTO_COLUNAS = {
    "Codigo_INE":        ["codigo_ine", "cod_ine", "dicofre", "codigo"],
    "Nome":              ["nome", "freguesia", "des_freg", "designacao"],
    "Município":         ["municipio", "concelho", "des_conc", "des_municipio"],
    "Populacao":         ["populacao", "pop_total", "n_individuos", "total"],
    "Transportes_Score": ["transportes_score", "transportes", "score_transportes"],
    "Saude_Score":       ["saude_score", "saude", "score_saude"],
    "Educacao_Score":    ["educacao_score", "educacao", "score_educacao"],
    "Seguranca_Score":   ["seguranca_score", "seguranca", "score_seguranca"],
}


# ─── Utilitários ─────────────────────────────────────────────────────────────

def normalizar(texto):
    """Converte para minúsculas e remove espaços para comparação."""
    return texto.strip().lower().replace(" ", "_")


def mapear_cabecalhos(cabecalhos):
    """
    Recebe a lista de cabeçalhos do CSV e devolve um dicionário
    {campo_airtable: índice_coluna_csv}.
    """
    cabecalhos_norm = [normalizar(c) for c in cabecalhos]
    mapeado = {}
    for campo, aliases in MAPEAMENTO_COLUNAS.items():
        for alias in aliases:
            if alias in cabecalhos_norm:
                mapeado[campo] = cabecalhos_norm.index(alias)
                break
    return mapeado


def calcular_score_geral(campos):
    """Média simples dos scores disponíveis (0–10)."""
    scores = []
    for chave in ["Transportes_Score", "Saude_Score", "Educacao_Score", "Seguranca_Score"]:
        val = campos.get(chave)
        if val is not None:
            scores.append(float(val))
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def obter_table_id():
    """Obtém o ID da tabela 'Freguesias' na base."""
    url = f"{AIRTABLE_API}/meta/bases/{BASE_ID}/tables"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"})
    with urllib.request.urlopen(req) as resp:
        dados = json.loads(resp.read())
    for tabela in dados.get("tables", []):
        if tabela["name"] == TABLE_NAME:
            return tabela["id"]
    raise ValueError(f"Tabela '{TABLE_NAME}' não encontrada na base {BASE_ID}.")


def inserir_registos(table_id, registos):
    """
    Envia registos para o Airtable em lotes de 10 (limite da API).
    Devolve o número de registos inseridos com sucesso.
    """
    url      = f"{AIRTABLE_API}/{BASE_ID}/{table_id}"
    inseridos = 0

    for i in range(0, len(registos), 10):
        lote   = registos[i:i + 10]
        corpo  = json.dumps({"records": [{"fields": r} for r in lote]}).encode("utf-8")
        req    = urllib.request.Request(
            url,
            data    = corpo,
            method  = "POST",
            headers = {
                "Authorization": f"Bearer {AIRTABLE_TOKEN}",
                "Content-Type":  "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                resultado  = json.loads(resp.read())
                inseridos += len(resultado.get("records", []))
                print(f"  Lote {i // 10 + 1}: {len(resultado.get('records', []))} registos inseridos.")
        except urllib.error.HTTPError as e:
            erro = e.read().decode("utf-8")
            print(f"  Erro no lote {i // 10 + 1}: {e.code} — {erro}", file=sys.stderr)

    return inseridos


# ─── Pipeline principal ───────────────────────────────────────────────────────

def processar_csv(caminho_csv, limite=None):
    """Lê o CSV e devolve lista de dicionários prontos para o Airtable."""
    registos = []

    with open(caminho_csv, encoding="utf-8-sig") as f:
        leitor     = csv.reader(f)
        cabecalhos = next(leitor)
        mapeamento = mapear_cabecalhos(cabecalhos)

        campos_obrigatorios = ["Nome", "Município"]
        for campo in campos_obrigatorios:
            if campo not in mapeamento:
                raise ValueError(
                    f"Coluna obrigatória '{campo}' não encontrada. "
                    f"Cabeçalhos detectados: {cabecalhos}"
                )

        for i, linha in enumerate(leitor):
            if limite and i >= limite:
                break

            campos = {}
            for campo, idx in mapeamento.items():
                if idx < len(linha) and linha[idx].strip():
                    valor = linha[idx].strip()
                    # Campos numéricos
                    if campo in ("Populacao", "Transportes_Score", "Saude_Score",
                                 "Educacao_Score", "Seguranca_Score", "Score_Geral"):
                        try:
                            campos[campo] = float(valor.replace(",", "."))
                        except ValueError:
                            pass  # ignora valores não numéricos
                    else:
                        campos[campo] = valor

            # Calcula Score_Geral se não vier no CSV
            if "Score_Geral" not in campos:
                score = calcular_score_geral(campos)
                if score is not None:
                    campos["Score_Geral"] = score

            if campos:
                registos.append(campos)

    return registos


def main():
    parser = argparse.ArgumentParser(description="Importa dados INE para o Airtable.")
    parser.add_argument("--csv",    required=True, help="Caminho para o ficheiro CSV do INE")
    parser.add_argument("--limite", type=int, default=None,
                        help="Número máximo de registos a importar (ex: 10 para teste)")
    args = parser.parse_args()

    if not AIRTABLE_TOKEN:
        print("Erro: variável de ambiente AIRTABLE_TOKEN não definida.", file=sys.stderr)
        print("  export AIRTABLE_TOKEN=patXXXXX", file=sys.stderr)
        sys.exit(1)

    print(f"A ler CSV: {args.csv}")
    registos = processar_csv(args.csv, limite=args.limite)
    print(f"  {len(registos)} registos prontos para importar.")

    if not registos:
        print("Nenhum registo para importar. Verificar CSV.")
        sys.exit(0)

    print("A obter ID da tabela 'Freguesias'...")
    table_id = obter_table_id()
    print(f"  Table ID: {table_id}")

    print("A inserir registos no Airtable...")
    total = inserir_registos(table_id, registos)
    print(f"\nConcluído: {total}/{len(registos)} registos inseridos na tabela '{TABLE_NAME}'.")


if __name__ == "__main__":
    main()
