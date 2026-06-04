/**
 * Worker: INE API → Airtable
 *
 * Endpoint principal:
 *   GET /sync?freguesia=NOME   — sincroniza uma freguesia com dados reais do INE
 *   GET /healthcheck           — devolve status do Worker
 *
 * Indicadores usados (todos Censos 2021, nível de freguesia, geocod DICOFRE 6 dígitos):
 *   0014584 — População residente por sexo
 *   0014620 — Edifícios
 *   0014626 — Alojamentos familiares clássicos de residência habitual
 *   0012227 — Valor mediano das vendas de alojamentos (€/m²) — proxy mercado imobiliário
 *   0012749 — Rendimento mediano bruto por sujeito passivo (€) — proxy nível económico
 *
 * Scores que o INE NÃO fornece ao nível de freguesia (precisam de outras fontes):
 *   Transportes → IMT / GTFS
 *   Saúde → ACSS (SNS)
 *   Educação → DGEEC
 *   Segurança → DGAI / MAI
 */

const AIRTABLE_BASE_ID  = 'appzKGnGUD6pafKKn';
const AIRTABLE_TABLE_ID = 'tbl2mvTKYsrb1h6fc';
const INE_BASE          = 'https://www.ine.pt/ine/json_indicador/pindica.jsp';

const IND_POPULACAO    = '0014584'; // pop. residente por sexo (HM = total)
const IND_EDIFICIOS    = '0014620'; // edifícios — proxy urbanização
const IND_ALOJAMENTOS  = '0014626'; // alojamentos de residência habitual
const IND_VENDAS_M2    = '0012227'; // valor mediano vendas €/m² (trimestral)
const IND_RENDIMENTO   = '0012749'; // rendimento mediano IRS por s.p. (anual)

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
 * Chama a API INE e devolve o array de registos do primeiro período disponível.
 * Devolve [] em caso de erro.
 */
async function fetchIndicador(varcd) {
  const url = `${INE_BASE}?op=2&varcd=${varcd}&lang=PT`;
  try {
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'MelhorZona/1.0 (melhorzona.pt)' },
    });
    if (!resp.ok) return [];
    const lista = await resp.json();
    const item  = Array.isArray(lista) ? lista[0] : lista;
    const dados = item?.Dados || {};
    const anos  = Object.keys(dados);
    return anos.length ? dados[anos[0]] : [];
  } catch {
    return [];
  }
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
 * Extrai o total de edifícios para um geocod específico (dim_3='T' ou primeiro dim).
 */
function extrairTotal(registos, geocod) {
  const total = registos.find(r => r.geocod === geocod && (r.dim_3 === 'T' || !r.dim_3));
  if (total) return parseInt(total.valor, 10) || null;
  // Fallback: somar todos os registos com este geocod
  const todos = registos.filter(r => r.geocod === geocod);
  if (!todos.length) return null;
  return todos.reduce((s, r) => s + (parseInt(r.valor, 10) || 0), 0);
}

/**
 * Extrai o valor mediano de vendas €/m² para um geocod.
 * O indicador 0012227 usa geocods diferentes (ex: "11A131202" para Bonfim no Porto).
 * Tenta correspondência parcial com o geodsg.
 */
function extrairVendasM2(registos, geocod, geodsg) {
  const nomeBusca = normalizarNome(geodsg);
  // Tentar match directo pelo geocod
  let reg = registos.find(r => r.geocod === geocod);
  if (!reg) {
    // Tentar pelo nome
    reg = registos.find(r => normalizarNome(r.geodsg || '').includes(nomeBusca));
  }
  return reg ? (parseFloat(reg.valor) || null) : null;
}

/**
 * Extrai rendimento mediano para um geocod.
 */
function extrairRendimento(registos, geocod) {
  const reg = registos.find(r => r.geocod === geocod);
  return reg ? (parseFloat(reg.valor) || null) : null;
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

  /* 1. Carregar dados INE em paralelo */
  const [regsPop, regsEdif, regsAloj, regsVendas, regsRend] = await Promise.all([
    fetchIndicador(IND_POPULACAO),
    fetchIndicador(IND_EDIFICIOS),
    fetchIndicador(IND_ALOJAMENTOS),
    fetchIndicador(IND_VENDAS_M2),
    fetchIndicador(IND_RENDIMENTO),
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

  /* 3. Extrair restantes dados INE com o geocod real */
  const edificios   = extrairTotal(regsEdif,  info.geocod);
  const alojamentos = extrairTotal(regsAloj,  info.geocod);
  const vendasM2    = extrairVendasM2(regsVendas, info.geocod, info.geodsg);
  const rendimento  = extrairRendimento(regsRend, info.geocod);

  resultado.ine_dados = {
    populacao:    info.populacao,
    edificios,
    alojamentos,
    vendas_m2:   vendasM2,
    rendimento_mediano: rendimento,
  };

  if (!edificios)   resultado.avisos.push('Edifícios não disponíveis para este geocod');
  if (!vendasM2)    resultado.avisos.push('Valor mediano de vendas não disponível para esta freguesia');
  if (!rendimento)  resultado.avisos.push('Rendimento mediano não disponível para esta freguesia');

  /* 4. Calcular scores com os dados disponíveis */
  const { scores, densidadeScore, mercadoScore, economicoScore } =
    calcularScores(info.populacao, edificios, alojamentos, vendasM2, rendimento);

  resultado.scores_calculados = { densidadeScore, mercadoScore, economicoScore };

  /* 5. Montar os campos a actualizar no Airtable */
  const fields = {
    Codigo_INE: info.geocod,
    Populacao:  info.populacao,
  };

  // Só actualiza scores se tiver dados reais para calculá-los
  // Nota: Transportes, Saúde, Educação e Segurança precisam de fontes externas (IMT, ACSS, DGEEC, DGAI)
  // Enquanto não estão disponíveis, não sobrescreve os valores existentes
  if (mercadoScore !== null && economicoScore !== null) {
    // Score_Geral derivado das melhores proxies disponíveis
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
        status:       'ok',
        worker:       'ine-api',
        indicadores:  [IND_POPULACAO, IND_EDIFICIOS, IND_ALOJAMENTOS, IND_VENDAS_M2, IND_RENDIMENTO],
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
