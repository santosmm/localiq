#!/usr/bin/env python3
"""
Enriquece o Supabase com dados e score de clima por município.

Fontes:
  - Nominatim (OpenStreetMap) para geocodificação dos municípios
  - Open-Meteo Historical Weather API (ERA5) — média 2015-2024

Campos calculados:
  clima_temp_media   : temperatura média anual (°C)
  clima_sol_horas    : horas de sol por ano
  clima_precipitacao : precipitação anual (mm)
  clima_score        : 0–10 (sol 50%, temperatura 30%, precipitação 20%)

Granularidade: município. Mesmo score aplicado a todas as freguesias.

Calibração ERA5 para Portugal:
  Sol:   2500h → 0.0 | 4200h → 10.0   (Porto ~3550h, Lisboa ~3770h, Faro ~3930h)
  Temp:  ideal 17°C; −0.8 pts por grau de desvio
  Chuva: 400mm → 10.0 | 1500mm → 0.0  (Faro ~430mm, Lisboa ~540mm, Porto ~1320mm)

Pré-requisito: colunas clima_* devem existir no Supabase antes de correr.
  ALTER TABLE freguesias
    ADD COLUMN IF NOT EXISTS clima_temp_media   NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS clima_sol_horas    NUMERIC(8,1),
    ADD COLUMN IF NOT EXISTS clima_precipitacao NUMERIC(8,1),
    ADD COLUMN IF NOT EXISTS clima_score        NUMERIC(4,1);

Uso:
  export SUPABASE_URL=https://hkxdmregnsmsbxvpykul.supabase.co
  export SUPABASE_KEY=<service_role_key>
  python3 data/enricher-clima.py --dry-run --municipios Lisboa,Porto,Faro
  python3 data/enricher-clima.py --dry-run --limite 5
  python3 data/enricher-clima.py
  python3 data/enricher-clima.py --apenas-sem-clima
"""

import json
import os
import sys
import time
import argparse
import statistics
import urllib.error
import urllib.parse
import urllib.request

# ─── Configuração ─────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

NOMINATIM_BASE    = "https://nominatim.openstreetmap.org/search"
OPEN_METEO_BASE   = "https://archive-api.open-meteo.com/v1/archive"
PERIODO_INICIO    = "2015-01-01"
PERIODO_FIM       = "2024-12-31"

NOMINATIM_PAUSA   = 1.1   # seg — política Nominatim: mínimo 1 req/s
OPEN_METEO_PAUSA  = 0.3   # seg

# Referências fixas para score (evitam distorção por outliers futuros)
SOL_REF_MIN        = 2500.0   # h/ano → score 0.0
SOL_REF_MAX        = 4200.0   # h/ano → score 10.0
TEMP_IDEAL         = 17.0     # °C    → score 10.0 (Lisboa ~16.9°C)
TEMP_SENSIBILIDADE = 0.8      # pts de penalidade por grau de desvio
CHUVA_REF_MIN      = 400.0    # mm/ano → score 10.0
CHUVA_REF_MAX      = 1500.0   # mm/ano → score 0.0


# ─── Nominatim — geocodificação de municípios ─────────────────────────────────

def geocodificar_municipio(nome):
    """Devolve (lat, lon) para um município português. None se não encontrar."""
    params = urllib.parse.urlencode({
        "q":            f"{nome}, Portugal",
        "format":       "json",
        "limit":        "1",
        "countrycodes": "pt",
    })
    url = f"{NOMINATIM_BASE}?{params}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "MelhorZona/1.0 (ola@melhorzona.pt)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resultados = json.loads(resp.read())
    except Exception as e:
        print(f"    ✗ Nominatim erro para {nome}: {e}", file=sys.stderr)
        return None
    if not resultados:
        return None
    r = resultados[0]
    return float(r["lat"]), float(r["lon"])


# ─── Open-Meteo Historical API ────────────────────────────────────────────────

def buscar_clima(lat, lon):
    """
    Devolve (temp_media, sol_horas, precipitacao) — médias anuais 2015-2024.
    Retorna None se a API falhar.
    """
    params = urllib.parse.urlencode({
        "latitude":   round(lat, 4),
        "longitude":  round(lon, 4),
        "daily":      "sunshine_duration,temperature_2m_mean,precipitation_sum",
        "start_date": PERIODO_INICIO,
        "end_date":   PERIODO_FIM,
    })
    url = f"{OPEN_METEO_BASE}?{params}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "MelhorZona/1.0 (ola@melhorzona.pt)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            dados = json.loads(resp.read())
    except Exception as e:
        print(f"    ✗ Open-Meteo erro ({lat:.3f}, {lon:.3f}): {e}", file=sys.stderr)
        return None

    daily = dados.get("daily", {})
    datas  = daily.get("time", [])
    sol_s  = daily.get("sunshine_duration", [])
    temps  = daily.get("temperature_2m_mean", [])
    chuvas = daily.get("precipitation_sum", [])

    if not datas:
        return None

    # Agregar por ano: sol e chuva somados; temperatura em média
    sol_ano   = {}
    chuva_ano = {}
    temp_vals = []

    for i, data in enumerate(datas):
        ano = data[:4]
        s = sol_s[i]  if i < len(sol_s)  else None
        t = temps[i]  if i < len(temps)  else None
        c = chuvas[i] if i < len(chuvas) else None

        if s is not None:
            sol_ano[ano]   = sol_ano.get(ano, 0) + s
        if c is not None:
            chuva_ano[ano] = chuva_ano.get(ano, 0) + c
        if t is not None:
            temp_vals.append(t)

    if not sol_ano or not chuva_ano or not temp_vals:
        return None

    sol_horas    = statistics.mean(v / 3600 for v in sol_ano.values())
    precipitacao = statistics.mean(chuva_ano.values())
    temp_media   = statistics.mean(temp_vals)

    return round(temp_media, 2), round(sol_horas, 1), round(precipitacao, 1)


# ─── Score ────────────────────────────────────────────────────────────────────

def calcular_score(temp_media, sol_horas, precipitacao):
    """Score composto 0–10 com referências fixas calibradas para ERA5 Portugal."""
    sol_score = max(0.0, min(10.0,
        (sol_horas - SOL_REF_MIN) / (SOL_REF_MAX - SOL_REF_MIN) * 10))

    temp_score = max(0.0,
        10.0 - abs(temp_media - TEMP_IDEAL) * TEMP_SENSIBILIDADE)

    chuva_score = max(0.0, min(10.0,
        (CHUVA_REF_MAX - precipitacao) / (CHUVA_REF_MAX - CHUVA_REF_MIN) * 10))

    score = sol_score * 0.50 + temp_score * 0.30 + chuva_score * 0.20
    return round(score, 1)


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
    req  = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"Supabase {method} {path}: HTTP {e.code} — {e.read().decode()[:200]}")


def sb_listar_municipios(apenas_sem_clima=False):
    """Devolve lista ordenada de nomes de municípios únicos do Supabase."""
    registos = []
    offset   = 0
    PAGINA   = 1000
    filtro   = "&clima_score=is.null" if apenas_sem_clima else ""

    while True:
        path = (f"freguesias?select=municipio{filtro}"
                f"&limit={PAGINA}&offset={offset}")
        pagina = sb_request("GET", path, extra_headers={
            "Accept": "application/json",
            "Prefer": "count=none",
        })
        if not pagina:
            break
        registos.extend(pagina)
        if len(pagina) < PAGINA:
            break
        offset += PAGINA

    vistos = {}
    for r in registos:
        m = r.get("municipio", "").strip()
        if m:
            vistos[m] = True
    return sorted(vistos.keys())


def sb_actualizar_municipio(municipio, temp, sol, chuva, score, dry_run):
    """Actualiza os 4 campos de clima em todas as freguesias do município."""
    nome_enc = urllib.parse.quote(municipio)
    path  = f"freguesias?municipio=eq.{nome_enc}"
    corpo = {
        "clima_temp_media":   temp,
        "clima_sol_horas":    sol,
        "clima_precipitacao": chuva,
        "clima_score":        score,
    }
    if dry_run:
        return True
    try:
        sb_request("PATCH", path, corpo)
        return True
    except RuntimeError as e:
        print(f"    ✗ Erro ao actualizar {municipio}: {e}", file=sys.stderr)
        return False


# ─── Pipeline principal ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enriquece Supabase com dados de clima (ERA5) por município.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra valores sem escrever no Supabase")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processar apenas N municípios (útil para teste)")
    parser.add_argument("--apenas-sem-clima", action="store_true",
                        help="Salta municípios que já têm clima_score preenchido")
    parser.add_argument("--municipios", type=str, default=None,
                        help="Lista de municípios separados por vírgula (ex: Lisboa,Porto,Faro). "
                             "Bypassa Supabase — não requer SUPABASE_KEY em dry-run.")
    args = parser.parse_args()

    # ── 1. Determinar lista de municípios ─────────────────────────────────────
    if args.municipios:
        municipios = [m.strip() for m in args.municipios.split(",") if m.strip()]
        print(f"Municípios especificados: {', '.join(municipios)}")
    else:
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("Erro: SUPABASE_URL e SUPABASE_KEY são obrigatórias.", file=sys.stderr)
            print("  (ou usa --municipios Lisboa,Porto para teste sem credenciais)", file=sys.stderr)
            sys.exit(1)
        print("A listar municípios do Supabase...")
        municipios = sb_listar_municipios(args.apenas_sem_clima)
        print(f"  {len(municipios)} municípios únicos encontrados.")

    if args.limite:
        municipios = municipios[:args.limite]
        print(f"  (limitado a {args.limite} por --limite)")

    if not args.municipios and not args.dry_run and (not SUPABASE_URL or not SUPABASE_KEY):
        print("Erro: SUPABASE_URL e SUPABASE_KEY são obrigatórias para escrita.", file=sys.stderr)
        sys.exit(1)

    # ── 2. Processar cada município ───────────────────────────────────────────
    if args.dry_run:
        print("\n  [DRY-RUN — Supabase não será alterado]\n")

    stats = {"ok": 0, "sem_coords": 0, "sem_clima": 0, "erros": 0}
    resultados = []

    for i, municipio in enumerate(municipios, 1):
        print(f"[{i}/{len(municipios)}] {municipio}")

        # Fase 1: Geocodificar via Nominatim
        coords = geocodificar_municipio(municipio)
        time.sleep(NOMINATIM_PAUSA)

        if coords is None:
            print(f"    ✗ Sem coordenadas (Nominatim não encontrou)")
            stats["sem_coords"] += 1
            continue

        lat, lon = coords
        print(f"    → coords: {lat:.4f}, {lon:.4f}")

        # Fase 2: Buscar dados climáticos ERA5
        clima = buscar_clima(lat, lon)
        time.sleep(OPEN_METEO_PAUSA)

        if clima is None:
            print(f"    ✗ Sem dados climáticos (Open-Meteo falhou)")
            stats["sem_clima"] += 1
            continue

        temp, sol, chuva = clima
        score = calcular_score(temp, sol, chuva)

        print(f"    → {temp}°C · {sol}h sol · {chuva}mm chuva → score {score}")
        resultados.append((municipio, temp, sol, chuva, score))

        # Fase 3: Actualizar Supabase
        ok = sb_actualizar_municipio(municipio, temp, sol, chuva, score, args.dry_run)

        if ok:
            if not args.dry_run:
                print(f"    ✓ Actualizado no Supabase")
            stats["ok"] += 1
        else:
            stats["erros"] += 1

        if not args.dry_run:
            time.sleep(0.1)

    # ── 3. Relatório final ────────────────────────────────────────────────────
    print(f"\n{'=' * 56}")
    print(f"Resultado ({PERIODO_INICIO[:4]}–{PERIODO_FIM[:4]}):")
    print(f"  {len(municipios)} municípios processados")
    print(f"  {stats['ok']} actualizados com sucesso")
    print(f"  {stats['sem_coords']} sem coordenadas (Nominatim)")
    print(f"  {stats['sem_clima']} sem dados climáticos (Open-Meteo)")
    print(f"  {stats['erros']} erros de escrita no Supabase")

    if resultados:
        scores = [r[4] for r in resultados]
        print(f"\n  Score mín: {min(scores)} | máx: {max(scores)} | "
              f"média: {round(statistics.mean(scores), 1)}")
        top3 = sorted(resultados, key=lambda x: x[4], reverse=True)[:3]
        bot3 = sorted(resultados, key=lambda x: x[4])[:3]
        print(f"\n  Top 3 melhor clima:")
        for m, t, s, c, sc in top3:
            print(f"    {sc:4.1f}  {m} ({t}°C · {s}h · {c}mm)")
        print(f"\n  Top 3 pior clima:")
        for m, t, s, c, sc in bot3:
            print(f"    {sc:4.1f}  {m} ({t}°C · {s}h · {c}mm)")

    if args.dry_run:
        print(f"\n  [DRY-RUN — Supabase não foi alterado]")
    print(f"{'=' * 56}\n")


if __name__ == "__main__":
    main()
