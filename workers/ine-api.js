/**
 * Worker: INE API → Airtable
 *
 * Endpoints:
 *   GET /sync?freguesia=NOME   — sincroniza uma freguesia com dados reais do INE
 *   GET /healthcheck           — devolve status do Worker
 *
 * Indicadores INE usados:
 *   0014584 — Pop. residente (Censos 2021, freguesia, DICOFRE 6 dígitos)
 *   0014620 — Edifícios (Censos 2021, freguesia)
 *   0014626 — Alojamentos familiares clássicos (Censos 2021, freguesia)
 *   0012227 — Valor mediano de vendas €/m² (trimestral, município)
 *   0012749 — Rendimento mediano IRS (anual, município)
 *   0012600 — Rendas medianas de novos contratos €/m² (anual, município, dados 2024)
 *
 * Correspondência de geocódigos (para indicadores de nível município):
 *   DICOFRE 6 dígitos (ex: 110656 = Arroios/Lisboa)
 *   → primeiros 4 dígitos = código município (ex: 1106 = Lisboa)
 *   A API INE usa este mesmo formato de 4 dígitos a lvl@5
 *
 * Scores que o INE não fornece a nível de freguesia (precisam de outras fontes):
 *   Transportes → IMT / GTFS
 *   Saúde → ACSS (SNS)
 *   Educação → DGEEC
 *   Segurança → DGAI / MAI
 */

const AIRTABLE_BASE_ID  = 'appzKGnGUD6pafKKn';
const AIRTABLE_TABLE_ID = 'tbl2mvTKYsrb1h6fc';
const INE_BASE          = 'https://www.ine.pt/ine/json_indicador/pindica.jsp';

// Indicadores a nível de freguesia (DICOFRE 6 dígitos) — Censos 2021
const IND_POPULACAO   = '0014584';
const IND_EDIFICIOS   = '0014620';
const IND_ALOJAMENTOS = '0014626';

// Indicadores a nível de município (DICOFRE 4 dígitos = primeiros 4 de Codigo_INE)
const IND_VENDAS_M2   = '0012227'; // valor mediano de vendas €/m² (trimestral)
const IND_RENDIMENTO  = '0012749'; // rendimento mediano IRS por sujeito passivo (anual)
const IND_RENDAS      = '0012600'; // rendas medianas novos contratos €/m² (anual, 2024)

const ORIGENS_PERMITIDAS = [
  'https://melhorzona.netlify.app',
  'https://melhorzona.pt',
  'https://www.melhorzona.pt',
  'http://localhost:8745',
  'http://localhost:8080',
  'http://127.0.0.1:8745',
];

/* ─── CORS ────────────────────────────────────────────────────────────────── */

function corsHeaders(origin) {
  const permitida = ORIGENS_PERMITIDAS.includes(origin) ? origin : ORIGENS_PERMITIDAS[0];
  return {
    'Access-Control-Allow-Origin':  permitida,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function json(dados, status, cors) {
  return new Response(JSON.stringify(dados, null, 2), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

/* ─── API INE ─────────────────────────────────────────────────────────────── */

/**
 * Chama a API INE e devolve o array de registos do período pedido (ou o mais recente).
 *
 * @param {string}      varcd  — código do indicador (7 dígitos)
 * @param {string|null} dim1   — período (ex: 'S7A2024', 'S3A202311'); null = mais recente
 * @param {string|null} dim2   — nível geográfico (ex: 'lvl@5' = município); null = todos
 */
async function fetchIndicador(varcd, dim1 = null, dim2 = null) {
  let url = `${INE_BASE}?op=2&varcd=${varcd}&lang=PT`;
  if (dim1) url += `&Dim1=${dim1}`;
  if (dim2) url += `&Dim2=${dim2}`;

  try {
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'MelhorZona/1.0 (melhorzona.pt)' },
    });
    if (!resp.ok) return [];
    const lista = await resp.json();
    const item  = Array.isArray(lista) ? lista[0] : lista;
    if (item?.Sucesso === false) return []; // erro explícito da API INE
    const dados = item?.Dados || {};
    const anos  = Object.keys(dados).sort().reverse();
    return anos.length ? dados[anos[0]] : [];
  } catch {
    return [];
  }
}

/**
 * Extrai o código de município a partir de um geocod DICOFRE de 6 dígitos.
 * Ex: '110656' → '1106'  (Lisboa)
 *     '131202' → '1312'  (Porto)
 *     '110508' → '1105'  (Cascais)
 */
function codigoMunicipio(geocodFreguesia) {
  return String(geocodFreguesia || '').padStart(6, '0').slice(0, 4);
}

/**
 * Pesquisa uma freguesia por nome nos dados do indicador de população.
 * Devolve { geocod, geodsg, municipioGeocod } ou null se não encontrar.
 *
 * Estratégia: normaliza espaços e acentos para comparação aproximada.
 */
function normalizarNome(nome) {
  return nome
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // remove acentos
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function encontrarFreguesia(registos, nome, municipio) {
  const nomeBusca  = normalizarNome(nome);
  const muniBusca  = municipio ? normalizarNome(municipio) : null;

  // Filtrar registos com população total (HM)
  const totais = registos.filter(r => r.dim_3_t === 'HM' || r.dim_3 === 'T');

  // 1.ª passagem: correspondência exacta do nome + município (se fornecido)
  let candidatos = totais.filter(r => normalizarNome(r.geodsg || '') === nomeBusca);

  if (!candidatos.length) {
    // 2.ª passagem: nome contido (ex: "Cascais e Estoril" ao pesquisar "Cascais")
    candidatos = totais.filter(r => normalizarNome(r.geodsg || '').includes(nomeBusca));
  }

  if (!candidatos.length) return null;

  // Filtrar por município se fornecido
  if (muniBusca && candidatos.length > 1) {
    // O município não está directamente no registo — usar os primeiros 4 dígitos do geocod
    // e cruzar com os geocods de municípios que contenham o nome
    const muniCandidatos = candidatos.filter(r => {
      const muniGeocod = r.geocod?.slice(0, 4);
      // Procurar um registo de nível município (geocod de 4 dígitos) com esse nome
      const muniReg = registos.find(m =>
        m.geocod === muniGeocod &&
        normalizarNome(m.geodsg || '').includes(muniBusca)
      );
      return !!muniReg;
    });
    if (muniCandidatos.length) candidatos = muniCandidatos;
  }

  // Entre múltiplos candidatos, escolher o de maior população
  candidatos.sort((a, b) => (parseInt(b.valor, 10) || 0) - (parseInt(a.valor, 10) || 0));
  const encontrado = candidatos[0];

  const geocod = encontrado.geocod;
  const municipioGeocod = geocod.length === 6 ? geocod.slice(0, 4) : null;

  return {
    geocod,
    geodsg:          encontrado.geodsg,
    populacao:       parseInt(encontrado.valor, 10) || null,
    municipioGeocod,
    total_candidatos: candidatos.length,
    outros_candidatos: candidatos.slice(1).map(r => ({ geocod: r.geocod, geodsg: r.geodsg, pop: r.valor })),
  };
}

/**
 * Extrai o total de um indicador para um geocod específico (nível freguesia).
 * Tenta primeiro dim_3='T', depois soma sub-dimensões.
 */
function extrairTotal(registos, geocod) {
  const total = registos.find(r => r.geocod === geocod && (r.dim_3 === 'T' || !r.dim_3));
  if (total) return parseInt(total.valor, 10) || null;
  const todos = registos.filter(r => r.geocod === geocod);
  if (!todos.length) return null;
  return todos.reduce((s, r) => s + (parseInt(r.valor, 10) || 0), 0);
}

/**
 * Extrai um valor numérico para nível MUNICÍPIO a partir de indicadores lvl@5.
 *
 * A correspondência faz-se em três passos:
 *   1. Geocod directo:  codigoMunicipio(geocodFreguesia) — ex: '1106' para Lisboa
 *   2. Geocod sem zero: útil se a API omitir zeros à esquerda
 *   3. Nome:            correspondência exacta ou parcial com geodsg
 *
 * @param {Array}  registos        — registos da API INE (lvl@5)
 * @param {string} geocodFreguesia — DICOFRE 6 dígitos da freguesia
 * @param {string} nomeMunicipio   — nome do município (fallback de nome)
 */
function extrairValorMunicipio(registos, geocodFreguesia, nomeMunicipio) {
  if (!registos?.length) return null;

  const codMuni    = codigoMunicipio(geocodFreguesia); // ex: '1106' para Lisboa
  const codMuniInt = String(parseInt(codMuni, 10));
  const nomeBusca  = normalizarNome(nomeMunicipio || '');

  // Prioridade: registos de total (dim_3='T') para evitar sub-categorias
  const candidatos = registos.filter(r =>
    r.dim_3 === 'T' || r.dim_3 === 'Total' || r.dim_3 == null
  );
  const pool = candidatos.length ? candidatos : registos;

  // 1) NUTS 2024: últimos 4 dígitos do geocod = DICOFRE município (ex: '1A01106' → '1106')
  let reg = pool.find(r => (r.geocod || '').endsWith(codMuni) && (r.geocod || '').length > 4);
  // 2) Geocod directo de 4 dígitos (indicadores mais antigos)
  if (!reg) reg = pool.find(r => r.geocod === codMuni);
  // 3) Sem zero à esquerda
  if (!reg) reg = pool.find(r => r.geocod === codMuniInt);
  // 4) Nome exacto
  if (!reg && nomeBusca) reg = pool.find(r => normalizarNome(r.geodsg || '') === nomeBusca);
  // 5) Nome parcial
  if (!reg && nomeBusca) {
    reg = pool.find(r => {
      const n = normalizarNome(r.geodsg || '');
      return n.includes(nomeBusca) || nomeBusca.includes(n);
    });
  }

  if (!reg) return null;
  const raw = reg.valor;
  if (raw == null || String(raw).trim() === 'x') return null;
  return parseFloat(String(raw).replace(',', '.')) || null;
}

/** Alias para retro-compatibilidade com o código de extracção de vendas. */
function extrairVendasM2(registos, geocod, geodsg) {
  return extrairValorMunicipio(registos, geocod, geodsg);
}

/** Alias para retro-compatibilidade com o código de extracção de rendimento. */
function extrairRendimento(registos, geocod) {
  return extrairValorMunicipio(registos, geocod, null);
}

/* ─── Cálculo de scores ───────────────────────────────────────────────────── */

/**
 * Calcula scores de 0 a 10 a partir dos dados INE disponíveis.
 * Nota: estes são proxies aproximados — os scores reais requerem dados de
 * ACSS (saúde), IMT (transportes), DGEEC (educação) e DGAI (segurança).
 *
 * Referências nacionais usadas (médias aproximadas dos Censos 2021):
 *   - Pop. média por freguesia: ~5 200 hab.
 *   - Edifícios médios por freguesia: ~2 500
 *   - Vendas medianas nacionais: ~1 800 €/m²
 *   - Rendimento mediano nacional: ~13 000 €/ano
 */
function calcularScores(populacao, edificios, alojamentos, vendasM2, rendimento) {
  const scores = {};

  // Score de urbanização (proxy para qualidade de vida geral):
  // Normaliza a população num intervalo 0–10, com pico óptimo entre 10k–50k hab.
  if (populacao !== null) {
    if (populacao < 500)        scores.urbanizacao = 3.0;
    else if (populacao < 2000)  scores.urbanizacao = 4.5;
    else if (populacao < 5000)  scores.urbanizacao = 6.0;
    else if (populacao < 15000) scores.urbanizacao = 7.5;
    else if (populacao < 50000) scores.urbanizacao = 8.5;
    else if (populacao < 100000)scores.urbanizacao = 9.0;
    else                        scores.urbanizacao = 9.5;
  }

  // Densidade habitacional (alojamentos por 1000 habitantes) — proxy sobrelotação
  let densidadeScore = null;
  if (populacao && alojamentos) {
    const densidade = (alojamentos / populacao) * 1000;
    // Ideal: 400–600 alojamentos por 1000 hab.
    if (densidade > 200 && densidade < 800) densidadeScore = 7.0 + Math.min((densidade - 200) / 600 * 2, 2.0);
    else densidadeScore = 5.0;
  }

  // Score de mercado imobiliário (€/m²) — proxy acessibilidade habitação
  // Paradoxo: preço alto = zona desejável mas menos acessível
  // Normaliza como indicador de procura/qualidade
  let mercadoScore = null;
  if (vendasM2 !== null) {
    if (vendasM2 < 1000)       mercadoScore = 4.0;
    else if (vendasM2 < 1500)  mercadoScore = 5.5;
    else if (vendasM2 < 2500)  mercadoScore = 7.0;
    else if (vendasM2 < 4000)  mercadoScore = 8.0;
    else if (vendasM2 < 6000)  mercadoScore = 8.5;
    else                       mercadoScore = 9.0;
  }

  // Score económico (rendimento IRS por sujeito passivo)
  let economicoScore = null;
  if (rendimento !== null) {
    if (rendimento < 8000)      economicoScore = 4.0;
    else if (rendimento < 11000) economicoScore = 5.5;
    else if (rendimento < 15000) economicoScore = 7.0;
    else if (rendimento < 22000) economicoScore = 8.0;
    else if (rendimento < 35000) economicoScore = 9.0;
    else                         economicoScore = 9.5;
  }

  return { scores, densidadeScore, mercadoScore, economicoScore };
}

/* ─── Airtable ────────────────────────────────────────────────────────────── */

async function obterTableId(token) {
  const url  = `https://api.airtable.com/v0/meta/bases/${AIRTABLE_BASE_ID}/tables`;
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok) throw new Error(`Airtable meta ${resp.status}`);
  const data = await resp.json();
  const tab  = data.tables?.find(t => t.id === AIRTABLE_TABLE_ID);
  return tab?.id || AIRTABLE_TABLE_ID;
}

async function encontrarRegistoAirtable(token, nomeFrguesia) {
  const formula = `LOWER({Nome})=LOWER("${nomeFrguesia.replace(/"/g, '')}")`;
  const url = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}`
            + `?filterByFormula=${encodeURIComponent(formula)}&maxRecords=1`;
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok) return null;
  const data = await resp.json();
  return data.records?.[0] || null;
}

async function actualizarAirtable(token, recordId, fields) {
  const url  = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}/${recordId}`;
  const resp = await fetch(url, {
    method:  'PATCH',
    headers: {
      Authorization:  `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ fields }),
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Airtable PATCH ${resp.status}: ${err}`);
  }
  return resp.json();
}

async function criarRegistoAirtable(token, fields) {
  const url  = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}`;
  const resp = await fetch(url, {
    method:  'POST',
    headers: {
      Authorization:  `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ records: [{ fields }] }),
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Airtable POST ${resp.status}: ${err}`);
  }
  return resp.json();
}

/* ─── Handler principal ───────────────────────────────────────────────────── */

async function handleSync(nome, token, municipio) {
  const resultado = {
    freguesia:   nome,
    geocod:      null,
    populacao:   null,
    municipio:   municipio || null,
    ine_dados:   {},
    scores_calculados: {},
    airtable:    { acção: null, campos_actualizados: [] },
    avisos:      [],
  };

  /* 1. Carregar dados INE em paralelo
   *    Indicadores de freguesia: sem Dim2 (pesquisa por nome depois)
   *    Indicadores de município: Dim2=lvl@5 + último período conhecido */
  const [regsPop, regsEdif, regsAloj, regsVendas, regsRend, regsRendas] = await Promise.all([
    fetchIndicador(IND_POPULACAO),
    fetchIndicador(IND_EDIFICIOS),
    fetchIndicador(IND_ALOJAMENTOS),
    fetchIndicador(IND_VENDAS_M2),
    fetchIndicador(IND_RENDIMENTO),
    fetchIndicador(IND_RENDAS, 'S7A2024', 'lvl@5'),
  ]);

  /* 2. Encontrar a freguesia por nome (+ município opcional para desambiguar) */
  const info = encontrarFreguesia(regsPop, nome, resultado.municipio);
  if (!info) {
    resultado.avisos.push(`Freguesia "${nome}" não encontrada na API INE (indicador ${IND_POPULACAO})`);
    return resultado;
  }

  resultado.geocod    = info.geocod;
  resultado.populacao = info.populacao;
  resultado.ine_dados.populacao = info.populacao;

  /* 3. Extrair restantes dados INE com o geocod real
   *    Indicadores de freguesia usam geocod directo (DICOFRE 6 dígitos)
   *    Indicadores de município usam os primeiros 4 dígitos do geocod */
  const edificios    = extrairTotal(regsEdif,  info.geocod);
  const alojamentos  = extrairTotal(regsAloj,  info.geocod);
  const vendasM2     = extrairVendasM2(regsVendas, info.geocod, resultado.municipio || '');
  const rendimento   = extrairRendimento(regsRend, info.geocod);
  const rendasMediana = extrairValorMunicipio(regsRendas, info.geocod, resultado.municipio || '');

  resultado.ine_dados = {
    populacao:          info.populacao,
    edificios,
    alojamentos,
    vendas_m2:          vendasM2,
    rendimento_mediano: rendimento,
    rendas_mediana_m2:  rendasMediana,
    geocod_municipio:   codigoMunicipio(info.geocod),
  };

  if (!edificios)      resultado.avisos.push('Edifícios não disponíveis para este geocod');
  if (!vendasM2)       resultado.avisos.push('Valor mediano de vendas não disponível para esta freguesia');
  if (!rendimento)     resultado.avisos.push('Rendimento mediano não disponível para esta freguesia');
  if (!rendasMediana)  resultado.avisos.push('Rendas medianas não disponíveis para este município (cobertura INE parcial)');

  /* 4. Calcular scores com os dados disponíveis */
  const { scores, densidadeScore, mercadoScore, economicoScore } =
    calcularScores(info.populacao, edificios, alojamentos, vendasM2, rendimento);

  resultado.scores_calculados = { densidadeScore, mercadoScore, economicoScore };

  /* 5. Montar os campos a actualizar no Airtable */
  const fields = {
    Codigo_INE: info.geocod,
    Populacao:  info.populacao,
  };

  // Dados de mercado a nível de município
  if (rendasMediana !== null) {
    fields.Rendas_Mediana     = parseFloat(rendasMediana.toFixed(2));
  }
  if (vendasM2 !== null) {
    fields.Preco_Avaliacao_m2 = parseFloat(vendasM2.toFixed(0));
  }

  // Score_Geral: só actualiza se tiver proxies suficientes
  // (Transportes, Saúde, Educação e Segurança requerem IMT/ACSS/DGEEC/DGAI — não disponíveis aqui)
  if (mercadoScore !== null && economicoScore !== null) {
    fields.Score_Geral = parseFloat(((mercadoScore + economicoScore + (densidadeScore || 5.0)) / 3).toFixed(1));
    resultado.scores_calculados.Score_Geral_calculado = fields.Score_Geral;
  }

  resultado.airtable.campos_actualizados = Object.keys(fields);

  /* 6. Encontrar ou criar registo no Airtable */
  const registo = await encontrarRegistoAirtable(token, nome);
  if (registo) {
    await actualizarAirtable(token, registo.id, fields);
    resultado.airtable.acção   = 'actualizado';
    resultado.airtable.record_id = registo.id;
  } else {
    const novoRegisto = await criarRegistoAirtable(token, {
      Nome:      info.geodsg,
      Município: '', // não disponível directamente na API
      ...fields,
    });
    resultado.airtable.acção    = 'criado';
    resultado.airtable.record_id = novoRegisto.records?.[0]?.id;
    resultado.avisos.push('Registo não existia no Airtable — criado automaticamente');
  }

  return resultado;
}

/* ─── Entry point ─────────────────────────────────────────────────────────── */

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const cors   = corsHeaders(origin);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    if (request.method !== 'GET') {
      return json({ erro: 'Método não permitido' }, 405, cors);
    }

    const url      = new URL(request.url);
    const pathname = url.pathname;

    /* GET /healthcheck */
    if (pathname === '/healthcheck' || pathname === '/health') {
      return json({
        status:  'ok',
        worker:  'ine-api',
        indicadores: {
          freguesia: { populacao: IND_POPULACAO, edificios: IND_EDIFICIOS, alojamentos: IND_ALOJAMENTOS },
          municipio:  { vendas_m2: IND_VENDAS_M2, rendimento: IND_RENDIMENTO, rendas: IND_RENDAS },
        },
        geocodigos: 'DICOFRE 6 dígitos (freguesia) e 4 dígitos (município)',
        airtable_base: AIRTABLE_BASE_ID,
        airtable_tab:  AIRTABLE_TABLE_ID,
      }, 200, cors);
    }

    /* GET /sync?freguesia=NOME */
    if (pathname === '/sync' || pathname === '/') {
      const nome = url.searchParams.get('freguesia');

      if (!nome || nome.trim().length < 2) {
        return json({ erro: 'Parâmetro ?freguesia= obrigatório (mínimo 2 caracteres)' }, 400, cors);
      }

      if (!env.AIRTABLE_TOKEN) {
        return json({ erro: 'AIRTABLE_TOKEN não configurado no Worker' }, 500, cors);
      }

      try {
        const municipio = url.searchParams.get('municipio') || null;
        const resultado = await handleSync(nome.trim(), env.AIRTABLE_TOKEN, municipio);
        const status    = resultado.geocod ? 200 : 404;
        return json({ sucesso: !!resultado.geocod, ...resultado }, status, cors);
      } catch (erro) {
        return json({ sucesso: false, erro: erro.message }, 500, cors);
      }
    }

    return json({ erro: 'Endpoint não encontrado. Use /sync?freguesia=NOME ou /healthcheck' }, 404, cors);
  },
};
