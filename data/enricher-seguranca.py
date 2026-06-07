#!/usr/bin/env python3
"""
Enriquece o Supabase com o score de segurança por município.

Fonte: INE, indicador 0008254 — taxa de criminalidade (crimes/1000 hab),
       nível município (lvl@5), ano mais recente disponível (2023).

Score (invertido — mais crimes = score mais baixo):
  seguranca_valor : crimes por 1000 hab (valor bruto INE)
  seguranca_score : 0–10, calculado com referências fixas 20–60 crimes/1000 hab
  Fórmula: max(0, min(10, round((1 - (valor - 20) / 40) * 10, 1)))

Granularidade: município. O mesmo score é aplicado a todas as freguesias do município.
Estratégia de match: últimos 4 dígitos do geocod INE = DICOFRE município
  ex: '1701106' → '1106' = Lisboa; '11A1312' → '1312' = Porto

Uso:
  export SUPABASE_URL=https://hkxdmregnsmsbxvpykul.supabase.co
  export SUPABASE_KEY=<service_role_key>
  python3 data/enricher-seguranca.py --dry-run
  python3 data/enricher-seguranca.py
  python3 data/enricher-seguranca.py --limite 5
"""

import json
import os
import sys
import time
import argparse
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

# ─── Configuração ─────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

INE_BASE    = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
IND_CRIMES  = "0008254"   # taxa de criminalidade — crimes/1000 hab, município
PERIODO     = "S7A2023"   # anual 2023 (mais recente publicado)
DIM_MUN     = "lvl@5"

# Referências fixas para normalização (evitam que outliers futuros distorçam o score)
REF_MIN = 20.0   # muito seguro (abaixo → score 10)
REF_MAX = 60.0   # muito inseguro (acima → score 0)


# ─── INE API ──────────────────────────────────────────────────────────────────

def ine_fetch():
    url = f"{INE_BASE}?op=2&varcd={IND_CRIMES}&Dim1={PERIODO}&Dim2={DIM_MUN}&lang=PT"
    req = urllib.request.Request(url, headers={"User-Agent": "MelhorZona/1.0 (melhorzona.pt)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
    except Exception as e:
        print(f"  ✗ Erro ao contactar API INE: {e}", file=sys.stderr)
        sys.exit(1)

    item = payload[0] if isinstance(payload, list) and payload else payload
    dados_por_periodo = item.get("Dados", {})
    if not dados_por_periodo:
        print("  ✗ API INE devolveu dados vazios.", file=sys.stderr)
        sys.exit(1)

    # Usar o período pedido ou o mais recente disponível
    ano = PERIODO.replace("S7A", "")
    for chave in [PERIODO, ano]:
        if chave in dados_por_periodo:
            return dados_por_periodo[chave]
    periodos = sorted(dados_por_periodo.keys(), reverse=True)
    print(f"  ⚠ Período {PERIODO} não encontrado — a usar {periodos[0]}")
    return dados_por_periodo[periodos[0]]


# ─── Score ────────────────────────────────────────────────────────────────────

def calcular_score(crimes_por_mil):
    score = (1 - (crimes_por_mil - REF_MIN) / (REF_MAX - REF_MIN)) * 10
    return round(max(0.0, min(10.0, score)), 1)


# ─── Indexação dos registos INE ───────────────────────────────────────────────

def normalizar(texto):
    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("-", " ")


def indexar(registos):
    """
    Devolve dois dicts:
      por_dicofre : { dicofre4 → (valor, score) }   ex: {'1106': (41.9, 4.5)}
      por_nome    : { nome_norm → (valor, score) }
    """
    por_dicofre = {}
    por_nome    = {}

    for r in registos:
        geocod = str(r.get("geocod", "")).strip()
        geodsg = str(r.get("geodsg", "")).strip()
        raw    = r.get("valor")
        if raw is None or str(raw).strip() in ("", "x", ".."):
            continue
        try:
            valor = float(str(raw).replace(",", "."))
        except ValueError:
            continue

        score = calcular_score(valor)

        sufixo = geocod[-4:] if len(geocod) >= 4 else ""
        if sufixo.isdigit() and sufixo not in por_dicofre:
            por_dicofre[sufixo] = (valor, score)

        if geodsg:
            nome = normalizar(geodsg)
            if nome not in por_nome:
                por_nome[nome] = (valor, score)

    return por_dicofre, por_nome


def resolver(codigo_ine, municipio_nome, por_dicofre, por_nome):
    """
    Encontra (valor, score) para o município desta freguesia.
    Estratégia: DICOFRE4 → nome exacto → nome parcial.
    """
    cod4 = str(codigo_ine).zfill(6)[:4]   # ex: '110656' → '1106'

    if cod4 in por_dicofre:
        return por_dicofre[cod4], "dicofre4"

    if municipio_nome:
        nome = normalizar(municipio_nome)
        if nome in por_nome:
            return por_nome[nome], "nome_exacto"
        for n, v in por_nome.items():
            if nome in n or n in nome:
                return v, "nome_parcial"

    return None, "sem_correspondencia"


# ─── Supabase ─────────────────────────────────────────────────────────────────

def sb_request(method, path, body=None, extra_headers=None):
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {method} {path}: HTTP {e.code} — {e.read().decode()[:200]}")


def sb_listar_freguesias():
    """Devolve todos os registos com codigo_ine e municipio (paginado)."""
    registos = []
    offset   = 0
    PAGINA   = 1000
    while True:
        path = (f"freguesias?select=codigo_ine,municipio"
                f"&limit={PAGINA}&offset={offset}")
        pagina = sb_request("GET", path, extra_headers={"Accept": "application/json",
                                                         "Prefer": "count=none"})
        if not pagina:
            break
        registos.extend(pagina)
        if len(pagina) < PAGINA:
            break
        offset += PAGINA
    return registos


def sb_actualizar_municipio(dicofre4, valor, score, dry_run):
    """
    Actualiza seguranca_score e seguranca_valor em todas as freguesias
    do município (codigo_ine começa com dicofre4).
    """
    path = f"freguesias?codigo_ine=like.{urllib.parse.quote(dicofre4 + '%')}"
    corpo = {"seguranca_score": score, "seguranca_valor": valor}
    if dry_run:
        return True
    try:
        sb_request("PATCH", path, corpo)
        return True
    except RuntimeError as e:
        print(f"    ✗ Erro ao actualizar município {dicofre4}: {e}", file=sys.stderr)
        return False


# ─── Pipeline principal ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enriquece Supabase com score de segurança (INE criminalidade).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que seria actualizado sem escrever no Supabase")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processar apenas N municípios (útil para teste)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Erro: SUPABASE_URL e SUPABASE_KEY são obrigatórias.", file=sys.stderr)
        print("  export SUPABASE_URL=https://hkxdmregnsmsbxvpykul.supabase.co", file=sys.stderr)
        print("  export SUPABASE_KEY=<service_role_key>", file=sys.stderr)
        sys.exit(1)

    # ── 1. Buscar dados INE ───────────────────────────────────────────────────
    print(f"A buscar dados INE (indicador {IND_CRIMES}, {PERIODO})...")
    registos_ine = ine_fetch()
    print(f"  {len(registos_ine)} municípios recebidos da API INE.")

    por_dicofre, por_nome = indexar(registos_ine)
    print(f"  {len(por_dicofre)} municípios indexados por DICOFRE4.")

    # ── 2. Buscar freguesias do Supabase ─────────────────────────────────────
    print("\nA listar freguesias do Supabase...")
    freguesias = sb_listar_freguesias()
    print(f"  {len(freguesias)} registos encontrados.")

    # Agrupar por município (DICOFRE4) para evitar pesquisas repetidas
    municipios_vistos = {}
    for f in freguesias:
        cod = str(f.get("codigo_ine", "")).zfill(6)
        mun = f.get("municipio", "")
        d4  = cod[:4]
        if d4 not in municipios_vistos:
            municipios_vistos[d4] = mun

    municipios = list(municipios_vistos.items())   # [(dicofre4, nome_municipio)]
    if args.limite:
        municipios = municipios[:args.limite]
        print(f"  (limitado a {args.limite} municípios por --limite)")

    # ── 3. Actualizar cada município ──────────────────────────────────────────
    print(f"\nA actualizar {len(municipios)} municípios...")
    if args.dry_run:
        print("  [DRY-RUN — Supabase não será alterado]\n")

    stats = {"ok": 0, "sem_dados": 0, "erros": 0}

    for dicofre4, nome_mun in municipios:
        resultado, metodo = resolver(dicofre4, nome_mun, por_dicofre, por_nome)

        if resultado is None:
            print(f"  ✗ {nome_mun} ({dicofre4}): sem dados INE")
            stats["sem_dados"] += 1
            continue

        valor, score = resultado
        ok = sb_actualizar_municipio(dicofre4, round(valor, 1), score, args.dry_run)

        prefixo = "  [dry] " if args.dry_run else "  ✓ "
        print(f"{prefixo}{nome_mun} ({dicofre4}): {valor:.1f} crimes/1000 hab → score {score} [{metodo}]")

        if ok:
            stats["ok"] += 1
        else:
            stats["erros"] += 1

        if not args.dry_run:
            time.sleep(0.1)  # evitar throttle no Supabase

    # ── 4. Relatório final ────────────────────────────────────────────────────
    total_mun = len(municipios)
    total_freg = len(freguesias) if not args.limite else "—"
    print(f"""
{'=' * 52}
Resultado:
  {total_mun} municípios processados
  {stats['ok']} actualizados com sucesso
  {stats['sem_dados']} sem dados INE (interior/ilhas)
  {stats['erros']} erros de escrita
  {total_freg} freguesias cobertas (todas do município)
  Referência: {REF_MIN}–{REF_MAX} crimes/1000 hab → score 10–0
{'  [DRY-RUN — Supabase não foi alterado]' if args.dry_run else ''}
{'=' * 52}
""")


if __name__ == "__main__":
    main()
