#!/usr/bin/env python3
"""
Gera resumos de IA (Claude Haiku) para freguesias e guarda no campo resumo_ia do Supabase.

Uso:
  export SUPABASE_URL=https://hkxdmregnsmsbxvpykul.supabase.co
  export SUPABASE_KEY=<service_role_key>
  export ANTHROPIC_API_KEY=<chave>

  python gerar-resumos-ia.py --dry-run --limite 3   # valida sem escrever
  python gerar-resumos-ia.py --limite 50             # top 50 por populacao
  python gerar-resumos-ia.py                         # todas as que têm resumo_ia NULL
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Configuração

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

MODELO = "claude-haiku-4-5-20251001"

# Supabase

def sb_request(method, path, body=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase {method} {path} -> {e.code}: {corpo[:300]}")


def listar_freguesias(limite):
    """Devolve freguesias com resumo_ia NULL, ordenadas por populacao DESC."""
    params = {
        "select":    "codigo_ine,nome,municipio,populacao,score_geral,rendas_mediana,"
                     "seguranca_score,seguranca_valor,"
                     "transportes_score,ar_score,ensino_score,saude_score,arrendamento_score",
        "resumo_ia": "is.null",
        "order":     "populacao.desc.nullslast",
        "limit":     str(limite),
    }
    return sb_request("GET", "freguesias", params=params)


def guardar_resumo(codigo_ine, resumo):
    sb_request(
        "PATCH",
        "freguesias",
        body={"resumo_ia": resumo},
        params={"codigo_ine": f"eq.{codigo_ine}"},
    )


# Prompt

def construir_dados(f):
    """Constrói lista de dados reais disponíveis para incluir no prompt."""
    pop  = f.get("populacao") or 0
    perf = "urbana" if pop > 50000 else "suburbana" if pop > 10000 else "semi-urbana" if pop > 2000 else "rural"

    partes = []
    if pop:
        partes.append(f"populacao {pop:,} hab ({perf})".replace(",", " "))
    if f.get("rendas_mediana") is not None:
        partes.append(f"renda mediana {f['rendas_mediana']:.2f} euros/m2 (INE 2024; media nacional ~10 euros/m2; Lisboa ~17 euros/m2)")
    if f.get("seguranca_score") is not None:
        if f.get("seguranca_valor") is not None:
            partes.append(f"seguranca {f['seguranca_score']}/10 ({f['seguranca_valor']:.1f} crimes/1000 hab; media nacional ~35)")
        else:
            partes.append(f"seguranca {f['seguranca_score']}/10")
    if f.get("score_geral") is not None:
        partes.append(f"score geral {f['score_geral']}/10 (indice Melhor Zona)")

    return "\n- ".join(partes) if partes else "(sem dados disponiveis)"


PROMPT_SISTEMA = (
    "Es um especialista em qualidade de vida urbana em Portugal. "
    "Escreves em portugues europeu (nao brasileiro), tom editorial sobrio, factual. "
    "Nunca inventas dados -- usas apenas os que te sao fornecidos. "
    "Evitas adjectivos vagos (bonito, excelente, vibrante) e linguagem de marketing."
)

PROMPT_UTILIZADOR = """\
Escreve 3 frases sobre a qualidade de vida em {nome}, {municipio}.

Dados reais:
- {dados}

Estrutura obrigatoria das 3 frases:
1. Caracterizacao da zona (tipo urbano/rural, dimensao, o que a define).
2. Mercado de arrendamento em contexto (face a media nacional e regional, se disponivel).
3. Para quem e ideal -- familias, jovens profissionais ou reformados -- deduzido dos dados.

Escreve apenas as 3 frases em texto corrido. Sem titulos, sem bullets.\
"""


# Claude API

def gerar_resumo(f):
    dados   = construir_dados(f)
    content = PROMPT_UTILIZADOR.format(nome=f["nome"], municipio=f["municipio"], dados=dados)
    payload = {
        "model":      MODELO,
        "max_tokens": 300,
        "system":     PROMPT_SISTEMA,
        "messages":   [{"role": "user", "content": content}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "x-api-key":         ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            dados_resp = json.loads(resp.read())
        return dados_resp["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic API {e.code}: {corpo[:300]}")


# Pipeline principal

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Gera resumos mas nao escreve no Supabase")
    parser.add_argument("--limite", type=int, default=3259,
                        help="Numero maximo de freguesias a processar (padrao: todas)")
    args = parser.parse_args()

    erros_config = []
    for var, nome in [(SUPABASE_URL, "SUPABASE_URL"), (SUPABASE_KEY, "SUPABASE_KEY"),
                      (ANTHROPIC_KEY, "ANTHROPIC_API_KEY")]:
        if not var:
            erros_config.append(f"  export {nome}=...")
    if erros_config:
        print("Erro: variaveis nao definidas:\n" + "\n".join(erros_config), file=sys.stderr)
        sys.exit(1)

    print(f"A obter ate {args.limite} freguesias sem resumo_ia...")
    freguesias = listar_freguesias(args.limite)
    print(f"  {len(freguesias)} encontradas.\n")

    if not freguesias:
        print("Nenhuma freguesia sem resumo. Tudo actualizado.")
        return

    ok = 0
    for i, f in enumerate(freguesias, 1):
        nome_display = f"{f['nome']} ({f['municipio']})"
        print(f"[{i}/{len(freguesias)}] {nome_display}")

        try:
            resumo = gerar_resumo(f)
        except RuntimeError as e:
            print(f"  x Erro API: {e}", file=sys.stderr)
            continue

        print(f"  -> {resumo}\n")

        if not args.dry_run:
            try:
                guardar_resumo(f["codigo_ine"], resumo)
                ok += 1
            except RuntimeError as e:
                print(f"  x Erro Supabase: {e}", file=sys.stderr)
                continue
        else:
            ok += 1

        if i < len(freguesias):
            time.sleep(1)

    modo = "[DRY-RUN] " if args.dry_run else ""
    print("=" * 50)
    print(f"Resultado {modo}{ok}/{len(freguesias)} resumos gerados.")
    if args.dry_run:
        print("Nenhum dado foi escrito no Supabase.")


if __name__ == "__main__":
    main()
