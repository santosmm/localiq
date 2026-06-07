#!/usr/bin/env python3
"""
Gera resumos de IA (Claude Haiku) para freguesias e guarda no campo resumo_ia do Supabase.

Uso:
  export SUPABASE_URL=https://hkxdmregnsmsbxvpykul.supabase.co
  export SUPABASE_KEY=<service_role_key>
  export ANTHROPIC_API_KEY=<chave>

  python gerar-resumos-ia.py --dry-run --limite 3   # valida sem escrever
  python gerar-resumos-ia.py --limite 50             # top 50 por score
  python gerar-resumos-ia.py                         # todas as que têm resumo_ia NULL
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# ─── Configuração ─────────────────────────────────────────────────────────────

SUPABASE_URL   = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY", "")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")

MODELO = "claude-haiku-4-5-20251001"

# ─── Supabase ─────────────────────────────────────────────────────────────────

def sb_request(method, path, body=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    headers = {
        "apikey":          SUPABASE_KEY,
        "Authorization":   f"Bearer {SUPABASE_KEY}",
        "Content-Type":    "application/json",
        "Prefer":          "return=minimal",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase {method} {path} → {e.code}: {corpo[:300]}")


def listar_freguesias(limite):
    """Devolve freguesias com resumo_ia NULL, ordenadas por score_geral DESC."""
    params = {
        "select":    "codigo_ine,nome,municipio,populacao,score_geral,rendas_mediana,"
                     "transportes_score,transportes_valor,ar_score,ar_valor,"
                     "demografia_score,demografia_valor,ensino_score,ensino_valor,"
                     "saude_score,saude_valor,arrendamento_score,arrendamento_valor",
        "resumo_ia": "is.null",
        "order":     "score_geral.desc.nullslast",
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


# ─── Prompt ───────────────────────────────────────────────────────────────────

def construir_contexto(f):
    """Serializa os dados da freguesia num bloco de texto para o prompt."""
    linhas = [
        f"Freguesia: {f['nome']}",
        f"Município: {f['municipio']}",
    ]

    if f.get("populacao"):
        linhas.append(f"População residente (Censos 2021): {f['populacao']:,} habitantes".replace(",", " "))

    if f.get("score_geral") is not None:
        s = f["score_geral"]
        if   s >= 8:   classe = "excelente"
        elif s >= 6.5: classe = "boa"
        elif s >= 5:   classe = "razoável"
        else:          classe = "abaixo da média nacional"
        linhas.append(f"Score de qualidade de vida: {s}/10 ({classe})")

    if f.get("rendas_mediana") is not None:
        linhas.append(f"Renda mediana de novos contratos (INE 2024): {f['rendas_mediana']:.2f} €/m²")

    for campo, etiqueta in [
        ("transportes_score",  "Score de transportes públicos"),
        ("ar_score",           "Score de qualidade do ar"),
        ("demografia_score",   "Score de evolução demográfica"),
        ("ensino_score",       "Score de ensino"),
        ("saude_score",        "Score de saúde"),
        ("arrendamento_score", "Score do mercado de arrendamento"),
    ]:
        if f.get(campo) is not None:
            linhas.append(f"{etiqueta}: {f[campo]}/10")

    for campo, etiqueta in [
        ("transportes_valor",  "Transportes"),
        ("ar_valor",           "Qualidade do ar"),
        ("demografia_valor",   "Evolução demográfica"),
        ("ensino_valor",       "Ensino"),
        ("saude_valor",        "Saúde"),
        ("arrendamento_valor", "Arrendamento"),
    ]:
        if f.get(campo):
            linhas.append(f"{etiqueta}: {f[campo]}")

    return "\n".join(linhas)


PROMPT_SISTEMA = """\
És um redactor editorial especializado em qualidade de vida urbana em Portugal.
Escreves parágrafos curtos, factuais e em português europeu (não brasileiro).
Nunca inventas dados — usas apenas os que te são fornecidos.
Evitas superlativos vazios e linguagem de marketing.
O tom é sóbrio, informativo e útil para alguém a decidir onde viver."""

PROMPT_UTILIZADOR = """\
Com base nos dados abaixo, escreve um resumo de 2 a 3 frases sobre esta freguesia.
O resumo deve ser directo, factual e útil para alguém que pondera mudar para esta zona.
Menciona a população e o contexto urbano/rural, e o mercado de arrendamento se disponível.
Não uses introduções como "Esta freguesia" — começa pelo nome ou por uma característica.

{contexto}

Escreve apenas o resumo. Sem bullet points, sem títulos."""


# ─── Claude API ───────────────────────────────────────────────────────────────

def gerar_resumo(f):
    contexto = construir_contexto(f)
    payload  = {
        "model":      MODELO,
        "max_tokens": 200,
        "system":     PROMPT_SISTEMA,
        "messages": [
            {
                "role":    "user",
                "content": PROMPT_UTILIZADOR.format(contexto=contexto),
            }
        ],
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
            dados = json.loads(resp.read())
        return dados["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic API {e.code}: {corpo[:300]}")


# ─── Pipeline principal ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Gera resumos mas não escreve no Supabase")
    parser.add_argument("--limite", type=int, default=3259,
                        help="Número máximo de freguesias a processar")
    args = parser.parse_args()

    erros = []
    for var, nome in [(SUPABASE_URL, "SUPABASE_URL"), (SUPABASE_KEY, "SUPABASE_KEY"),
                      (ANTHROPIC_KEY, "ANTHROPIC_API_KEY")]:
        if not var:
            erros.append(f"  export {nome}=...")
    if erros:
        print("Erro: variáveis não definidas:\n" + "\n".join(erros), file=sys.stderr)
        sys.exit(1)

    print(f"A obter até {args.limite} freguesias sem resumo_ia...")
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
            print(f"  ✗ Erro API: {e}", file=sys.stderr)
            continue

        print(f"  → {resumo}\n")

        if not args.dry_run:
            try:
                guardar_resumo(f["codigo_ine"], resumo)
                ok += 1
            except RuntimeError as e:
                print(f"  ✗ Erro Supabase: {e}", file=sys.stderr)
                continue
        else:
            ok += 1

        if i < len(freguesias):
            time.sleep(1)  # rate limit: 1 req/s

    modo = "[DRY-RUN]" if args.dry_run else ""
    print(f"{'='*50}")
    print(f"Resultado {modo}: {ok}/{len(freguesias)} resumos gerados.")
    if args.dry_run:
        print("Nenhum dado foi escrito no Supabase.")


if __name__ == "__main__":
    main()
