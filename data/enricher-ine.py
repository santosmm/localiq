#!/usr/bin/env python3
"""
Enriquece o Airtable (tabela Freguesias) com dados de mercado habitacional do INE.

Indicadores usados:
  0012600 — Rendas: valor mediano de novos contratos (€/m²), anual, município, dados 2024
  0010042 — Preços: avaliação bancária (€/m²), mensal, município (dados até Nov 2023)
  0010043 — Preços: avaliação bancária (€/m²), anual, município

Correspondência de geocódigos:
  Codigo_INE no Airtable = DICOFRE 6 dígitos (ex: 110656 = Arroios/Lisboa)
  Código município       = primeiros 4 dígitos  (ex: 1106  = Lisboa)
  A API INE usa o mesmo formato de 4 dígitos para o nível município (lvl@5)

Uso:
  export AIRTABLE_TOKEN=patXXX
  python enricher-ine.py --dry-run           # antever alterações
  python enricher-ine.py                     # enriquecer todas as freguesias
  python enricher-ine.py --limite 5          # apenas 5 registos (teste)
"""

import json
import os
import sys
import time
import argparse
import unicodedata
import urllib.request
import urllib.error

# ─── Configuração ─────────────────────────────────────────────────────────────

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE  = "https://api.airtable.com/v0"
BASE_ID        = "appzKGnGUD6pafKKn"
TABLE_ID       = "tbl2mvTKYsrb1h6fc"

INE_BASE = "https://www.ine.pt/ine/json_indicador/pindica.jsp"

# Indicadores INE confirmados
IND_RENDAS    = "0012600"  # rendas medianas €/m² (anual, município, 2024)
IND_PRECO_MES = "0010042"  # avaliação bancária €/m² (mensal, município)
IND_PRECO_ANO = "0010043"  # avaliação bancária €/m² (anual, município)

# Dim2 para nível município na API INE
DIM_MUNICIPIO = "lvl@5"

# Últimos períodos conhecidos
PERIODO_RENDAS_DEFAULT  = "S7A2024"   # anual 2024
PERIODO_PRECO_MES       = "S3A202311" # mensal Nov 2023 (último disponível)
PERIODO_PRECO_ANO       = "S7A2023"   # anual 2023 (fallback)


# ─── INE API ──────────────────────────────────────────────────────────────────

def ine_fetch(varcd, dim1, dim2=DIM_MUNICIPIO):
    """
    Chama a API INE e devolve os registos do período pedido.

    A chave do período em Dados pode ser:
      - o código passado ("S7A2024" → chave "2024")
      - só o ano ("2024", "2023")
      - texto em português ("Novembro de 2023") — para dados mensais
    O fallback usa sempre o período disponível mais recente.

    Em caso de erro devolve lista vazia.
    """
    url = f"{INE_BASE}?op=2&varcd={varcd}&Dim1={dim1}&Dim2={dim2}&lang=PT"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MelhorZona/1.0 (melhorzona.pt)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")
        if e.code == 200:
            try:
                payload = json.loads(corpo)
            except Exception:
                return []
        else:
            print(f"  ⚠ HTTP {e.code} ao buscar {varcd}: {corpo[:120]}", file=sys.stderr)
            return []
    except Exception as e:
        print(f"  ⚠ Erro ao buscar {varcd}/{dim1}: {e}", file=sys.stderr)
        return []

    item = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(item, dict):
        return []

    if not item.get("Sucesso", True):
        print(f"  ⚠ API INE recusou {varcd}/{dim1}: {item.get('Msg', '')}", file=sys.stderr)
        return []

    dados_por_periodo = item.get("Dados", {})
    if not dados_por_periodo:
        return []

    # Tentar vários formatos de chave para o período
    ano = dim1.replace("S7A", "").replace("S3A", "")[:4]
    for chave in [dim1, ano, str(int(ano)) if ano.isdigit() else ano]:
        if chave in dados_por_periodo:
            return dados_por_periodo[chave]

    # Fallback: período mais recente disponível
    # Para datas textuais ("Novembro de 2023") a ordenação lexicográfica funciona
    # porque os nomes dos meses em PT + ano garantem ordem cronológica inversa
    periodos = sorted(dados_por_periodo.keys(), reverse=True)
    return dados_por_periodo[periodos[0]]


# ─── Correspondência de geocódigos ───────────────────────────────────────────

def normalizar(texto):
    """Lowercase, sem acentos, sem hífens — para comparação fuzzy."""
    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("-", " ").replace("  ", " ")


def indexar_registos(registos):
    """
    Recebe lista de registos INE e devolve dois índices:
      por_geocod: {chave → float}   — chave = geocod completo OU últimos 4 dígitos (DICOFRE município)
      por_nome:   {nome_norm → (geocod, float)}

    Os indicadores de nível município usam geocódigos NUTS 2024 do tipo:
      '1A01106' = AML + DICOFRE '1106' (Lisboa)
      '11A1312' = AMP + DICOFRE '1312' (Porto)
    Os últimos 4 caracteres são sempre o DICOFRE do município (4 dígitos).
    Indexamos também por esse sufixo para correspondência directa com Codigo_INE[:4].

    Filtra registos sem valor numérico ou marcados como confidenciais.
    """
    por_geocod = {}
    por_nome   = {}

    for r in registos:
        geocod = str(r.get("geocod", "")).strip()
        geodsg = str(r.get("geodsg", "")).strip()
        raw    = r.get("valor")

        if raw is None or str(raw).strip() in ("", "x", "..", "Dado confidencial"):
            continue
        try:
            valor = float(str(raw).replace(",", "."))
        except ValueError:
            continue

        if geocod:
            # Chave 1: geocod completo
            if geocod not in por_geocod:
                por_geocod[geocod] = valor
            # Chave 2: últimos 4 dígitos = DICOFRE município (ex: '1A01106' → '1106')
            sufixo = geocod[-4:]
            if sufixo.isdigit() and sufixo not in por_geocod:
                por_geocod[sufixo] = valor

        if geodsg:
            nome = normalizar(geodsg)
            if nome not in por_nome:
                por_nome[nome] = (geocod, valor)

    return por_geocod, por_nome


def geocod_municipio(codigo_ine):
    """
    Extrai o código de município de um DICOFRE de 6 dígitos.
    Ex: "110656" → "1106"  (Lisboa)
        "131202" → "1312"  (Porto)
        "110508" → "1105"  (Cascais)
    """
    s = str(codigo_ine).strip().zfill(6)
    return s[:4]


def resolver_municipio(codigo_ine, municipio_nome, por_geocod, por_nome):
    """
    Tenta encontrar o valor para o município desta freguesia.

    Estratégia (por ordem de prioridade):
      1. Sufixo DICOFRE:  codigo_ine[:4] vs últimos 4 dígitos dos geocods NUTS 2024
         (indexar_registos já os indexou como por_geocod[sufixo4])
      2. Geocod sem zero: int(codigo_ine[:4]) para casos sem padding
      3. Nome exacto do município
      4. Nome parcial (lida com "Lisboa" vs "Grande Lisboa" etc.)
    """
    cod = geocod_municipio(codigo_ine)  # ex: "1106" para Arroios/Lisboa

    # 1) DICOFRE 4 dígitos — funciona com geocods NUTS 2024 via sufixo (ex: '1A01106' → '1106')
    if cod in por_geocod:
        return por_geocod[cod], "dicofre4_directo"

    # 2) Sem zero à esquerda (ex: "0107" → "107")
    cod_int = str(int(cod)) if cod.isdigit() else cod
    if cod_int != cod and cod_int in por_geocod:
        return por_geocod[cod_int], "dicofre4_sem_zero"

    if not municipio_nome:
        return None, "sem_municipio"

    nome_norm = normalizar(municipio_nome)

    # 3) Nome exacto
    if nome_norm in por_nome:
        return por_nome[nome_norm][1], "nome_exacto"

    # 4) Nome parcial
    for nome_idx, (_, valor) in por_nome.items():
        if nome_norm in nome_idx or nome_idx in nome_norm:
            return valor, "nome_parcial"

    return None, "sem_correspondencia"


# ─── Airtable ─────────────────────────────────────────────────────────────────

def at_request(method, url, body=None):
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type":  "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Airtable {method} {e.code}: {corpo[:300]}")


def listar_campos_tabela():
    """Devolve lista de campos (dicts com 'name' e 'type') da tabela."""
    dados = at_request("GET", f"{AIRTABLE_BASE}/meta/bases/{BASE_ID}/tables")
    for tabela in dados.get("tables", []):
        if tabela["id"] == TABLE_ID:
            return tabela.get("fields", [])
    return []


def criar_campo(nome, tipo="number", precision=2):
    """Cria um campo numérico na tabela. Ignora se já existir."""
    url  = f"{AIRTABLE_BASE}/meta/bases/{BASE_ID}/tables/{TABLE_ID}/fields"
    body = {"name": nome, "type": tipo}
    if tipo == "number":
        body["options"] = {"precision": precision}
    try:
        at_request("POST", url, body)
        print(f"  + Campo '{nome}' criado.")
    except RuntimeError as e:
        # Airtable devolve 422 se o campo já existir — ignorar
        if "INVALID_MULTIPLE_CHOICE_OPTIONS" not in str(e) and "already exists" not in str(e).lower():
            print(f"  ⚠ Não foi possível criar '{nome}': {e}", file=sys.stderr)


def listar_freguesias(apenas_sem_rendas=False):
    """Obtém todas as freguesias com os campos necessários.

    Se apenas_sem_rendas=True, inclui Rendas_Mediana no pedido e
    filtra localmente só as que ainda não têm valor preenchido.
    """
    import urllib.parse
    registos = []
    offset   = None
    campos = [
        ("fields[]", "Nome"),
        ("fields[]", "Município"),
        ("fields[]", "Codigo_INE"),
    ]
    if apenas_sem_rendas:
        campos.append(("fields[]", "Rendas_Mediana"))
    # urlencode com multi-value para fields[] — lida com acentos em "Município"
    params_base = urllib.parse.urlencode(campos)
    while True:
        url = f"{AIRTABLE_BASE}/{BASE_ID}/{TABLE_ID}?{params_base}"
        if offset:
            url += f"&offset={urllib.parse.quote(offset, safe='')}"
        dados    = at_request("GET", url)
        registos += dados.get("records", [])
        offset   = dados.get("offset")
        if not offset:
            break
        time.sleep(0.25)

    if apenas_sem_rendas:
        antes = len(registos)
        registos = [r for r in registos if not r.get("fields", {}).get("Rendas_Mediana")]
        print(f"  Filtro: {antes} total → {len(registos)} sem rendas_mediana.")

    return registos


def actualizar_registo(record_id, fields):
    url = f"{AIRTABLE_BASE}/{BASE_ID}/{TABLE_ID}/{record_id}"
    return at_request("PATCH", url, {"fields": fields})


# ─── Pipeline principal ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enriquece Airtable com dados INE de habitação.")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Mostra o que seria actualizado, sem escrever no Airtable")
    parser.add_argument("--limite",      type=int, default=None,
                        help="Processar apenas N registos (útil para teste)")
    parser.add_argument("--apenas-sem-rendas", action="store_true",
                        help="Saltar freguesias que já têm Rendas_Mediana preenchida")
    parser.add_argument("--ano-rendas",  default=PERIODO_RENDAS_DEFAULT,
                        help=f"Período para rendas (default: {PERIODO_RENDAS_DEFAULT})")
    parser.add_argument("--mes-precos",  default=PERIODO_PRECO_MES,
                        help=f"Período mensal para preços (default: {PERIODO_PRECO_MES})")
    args = parser.parse_args()

    if not AIRTABLE_TOKEN:
        print("Erro: variável de ambiente AIRTABLE_TOKEN não definida.", file=sys.stderr)
        print("  export AIRTABLE_TOKEN=patXXXX", file=sys.stderr)
        sys.exit(1)

    # ── 1. Garantir campos no Airtable ────────────────────────────────────────
    print("A verificar schema Airtable...")
    campos_existentes = {c["name"] for c in listar_campos_tabela()}
    campos_novos_airtable = {
        "Rendas_Mediana":    ("number", 2),  # €/m² rendas medianas 2024
        "Preco_Avaliacao_m2": ("number", 0), # €/m² avaliação bancária
    }
    if not args.dry_run:
        for nome_campo, (tipo, precision) in campos_novos_airtable.items():
            if nome_campo not in campos_existentes:
                criar_campo(nome_campo, tipo, precision)
            else:
                print(f"  ✓ Campo '{nome_campo}' já existe.")

    # ── 2. Buscar dados INE ───────────────────────────────────────────────────
    print(f"\nA buscar dados INE...")

    print(f"  → Rendas ({IND_RENDAS}, {args.ano_rendas}, municípios)...")
    regs_rendas = ine_fetch(IND_RENDAS, args.ano_rendas, DIM_MUNICIPIO)
    # Filtrar totais (sem desagregação por tipologia T0/T1/T2/T3+)
    regs_rendas = [r for r in regs_rendas
                   if r.get("dim_3") in ("T", None) or r.get("dim_3_t") in ("Total", "T")]
    if not regs_rendas:
        # A API pode não ter dim_3 — usar todos os registos
        regs_rendas = ine_fetch(IND_RENDAS, args.ano_rendas, DIM_MUNICIPIO)
    print(f"    {len(regs_rendas)} municípios com dados de rendas.")

    print(f"  → Preços bancários ({IND_PRECO_MES}, {args.mes_precos}, municípios)...")
    regs_precos = ine_fetch(IND_PRECO_MES, args.mes_precos, DIM_MUNICIPIO)
    if not regs_precos:
        print(f"    Sem dados para {args.mes_precos}. A tentar {IND_PRECO_ANO}/{PERIODO_PRECO_ANO}...")
        regs_precos = ine_fetch(IND_PRECO_ANO, PERIODO_PRECO_ANO, DIM_MUNICIPIO)
    # Preferir apartamentos (mais representativo para zonas urbanas)
    regs_precos_apt = [r for r in regs_precos
                       if r.get("dim_3_t") in ("Apartamentos", "Total", "T")
                       or r.get("dim_3") in ("T", "1", None)]
    if regs_precos_apt:
        regs_precos = regs_precos_apt
    print(f"    {len(regs_precos)} municípios com dados de preços.")

    # ── 3. Indexar por geocod e por nome ──────────────────────────────────────
    idx_rendas_geocod, idx_rendas_nome = indexar_registos(regs_rendas)
    idx_precos_geocod, idx_precos_nome = indexar_registos(regs_precos)

    print(f"\n  Rendas:  {len(idx_rendas_geocod)} geocods | {len(idx_rendas_nome)} nomes")
    print(f"  Preços:  {len(idx_precos_geocod)} geocods | {len(idx_precos_nome)} nomes")

    if not idx_rendas_geocod and not idx_rendas_nome:
        print("\n⚠ Nenhum dado de rendas obtido da API INE. Verificar parâmetros e conectividade.")
        sys.exit(1)

    # ── 4. Listar freguesias no Airtable ──────────────────────────────────────
    print("\nA obter freguesias do Airtable...")
    freguesias = listar_freguesias(apenas_sem_rendas=args.apenas_sem_rendas)
    print(f"  {len(freguesias)} registos a processar.")

    if args.limite:
        freguesias = freguesias[:args.limite]
        print(f"  (limitado a {args.limite} por --limite)")

    # ── 5. Actualizar cada freguesia ──────────────────────────────────────────
    contadores = {"ok_renda": 0, "ok_preco": 0, "sem_cod": 0, "sem_renda": 0, "sem_preco": 0, "erros": 0}

    print()
    for reg in freguesias:
        record_id  = reg["id"]
        fields     = reg.get("fields", {})
        nome       = fields.get("Nome", "?")
        municipio  = fields.get("Município", "")
        codigo_ine = str(fields.get("Codigo_INE", "")).strip()

        if not codigo_ine or len(codigo_ine) < 4:
            print(f"  ⚠ {nome}: Codigo_INE ausente ('{codigo_ine}') — a saltar")
            contadores["sem_cod"] += 1
            continue

        renda, metodo_r = resolver_municipio(codigo_ine, municipio, idx_rendas_geocod, idx_rendas_nome)
        preco, metodo_p = resolver_municipio(codigo_ine, municipio, idx_precos_geocod, idx_precos_nome)

        campos_update = {}
        if renda is not None:
            campos_update["Rendas_Mediana"]     = round(renda, 2)
            contadores["ok_renda"] += 1
        else:
            contadores["sem_renda"] += 1

        if preco is not None:
            campos_update["Preco_Avaliacao_m2"] = round(preco, 0)
            contadores["ok_preco"] += 1
        else:
            contadores["sem_preco"] += 1

        # Log de linha
        partes = [f"{nome} ({codigo_ine[:4]})"]
        if renda is not None: partes.append(f"renda={renda:.2f}€/m² [{metodo_r}]")
        else:                 partes.append("renda=N/D")
        if preco is not None: partes.append(f"preço={preco:.0f}€/m² [{metodo_p}]")
        else:                 partes.append("preço=N/D")
        print("  " + " | ".join(partes))

        if args.dry_run or not campos_update:
            continue

        try:
            actualizar_registo(record_id, campos_update)
            time.sleep(0.25)  # rate limit: 4 req/s máximo na API Airtable
        except RuntimeError as e:
            print(f"    ✗ Erro ao actualizar '{nome}': {e}", file=sys.stderr)
            contadores["erros"] += 1

    # ── 6. Relatório final ────────────────────────────────────────────────────
    total = len(freguesias)
    print(f"""
{'=' * 50}
Resultado:
  {total} freguesias processadas
  {contadores['ok_renda']} com renda encontrada ({contadores['sem_renda']} sem cobertura INE)
  {contadores['ok_preco']} com preço encontrado ({contadores['sem_preco']} sem cobertura INE)
  {contadores['sem_cod']} ignoradas (sem Codigo_INE)
  {contadores['erros']} erros de escrita
{'  [DRY-RUN — Airtable não foi alterado]' if args.dry_run else ''}
{'=' * 50}
""")


if __name__ == "__main__":
    main()
