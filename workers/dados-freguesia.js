const AIRTABLE_BASE_ID  = 'appzKGnGUD6pafKKn';
const AIRTABLE_TABLE_ID = 'tbl2mvTKYsrb1h6fc';

const ORIGENS_PERMITIDAS = [
  'https://melhorzona.netlify.app',
  'https://melhorzona.pt',
  'https://www.melhorzona.pt',
  'http://localhost:8745',
  'http://localhost:8080',
  'http://127.0.0.1:8745',
];

function cabecalhosCors(origin) {
  const origemPermitida = ORIGENS_PERMITIDAS.includes(origin) ? origin : ORIGENS_PERMITIDAS[0];
  return {
    'Access-Control-Allow-Origin': origemPermitida,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'public, max-age=3600',
  };
}

function respostaJson(dados, status, cors) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

async function consultarFreguesia(nome, token) {
  /* Pesquisa case-insensitive pelo campo Nome */
  const formula    = `LOWER({Nome})=LOWER("${nome.replace(/"/g, '')}")`;
  const url        = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}`
                   + `?filterByFormula=${encodeURIComponent(formula)}&maxRecords=1`;

  const resposta = await fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  if (!resposta.ok) {
    throw new Error(`Airtable ${resposta.status}`);
  }

  const json     = await resposta.json();
  const registos = json.records || [];

  if (registos.length === 0) return null;

  const f = registos[0].fields;
  return {
    nome:               f.Nome               || '',
    municipio:          f['Município']        || '',
    codigo_ine:         f.Codigo_INE         || '',
    populacao:          f.Populacao          || null,
    score_geral:        f.Score_Geral        || null,
    transportes_score:  f.Transportes_Score  || null,
    saude_score:        f.Saude_Score        || null,
    educacao_score:     f.Educacao_Score     || null,
    seguranca_score:    f.Seguranca_Score    || null,
  };
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const cors   = cabecalhosCors(origin);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    if (request.method !== 'GET') {
      return respostaJson({ erro: 'Método não permitido' }, 405, cors);
    }

    const url      = new URL(request.url);
    const freguesia = url.searchParams.get('freguesia');

    if (!freguesia || freguesia.trim().length < 2) {
      return respostaJson({ erro: 'Parâmetro ?freguesia= obrigatório' }, 400, cors);
    }

    try {
      const dados = await consultarFreguesia(freguesia.trim(), env.AIRTABLE_TOKEN);

      if (!dados) {
        return respostaJson({ encontrado: false }, 200, cors);
      }

      return respostaJson({ encontrado: true, dados }, 200, cors);
    } catch (erro) {
      return respostaJson({ erro: 'Erro ao consultar dados' }, 500, cors);
    }
  },
};
