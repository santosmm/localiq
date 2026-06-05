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

function escapar(str) {
  return str.replace(/"/g, '');
}

function mapearRegisto(f) {
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
    rendas_mediana:     f.Rendas_Mediana     || null,
  };
}

async function consultarFreguesia(nome, municipio, token) {
  /* Se municipio fornecido, filtra por nome + município; caso contrário devolve até 5 matches */
  let formula;
  if (municipio) {
    formula = `AND(LOWER({Nome})=LOWER("${escapar(nome)}"),LOWER({Município})=LOWER("${escapar(municipio)}"))`;
  } else {
    formula = `LOWER({Nome})=LOWER("${escapar(nome)}")`;
  }

  const url = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}`
            + `?filterByFormula=${encodeURIComponent(formula)}&maxRecords=5`;

  const resposta = await fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  if (!resposta.ok) {
    throw new Error(`Airtable ${resposta.status}`);
  }

  const json     = await resposta.json();
  const registos = json.records || [];

  if (registos.length === 0) return { tipo: 'nenhum' };

  /* Resultado único — devolve directamente */
  if (registos.length === 1) {
    return { tipo: 'unico', dados: mapearRegisto(registos[0].fields) };
  }

  /* Múltiplos resultados — pede para desambiguar com município */
  return {
    tipo: 'multiplos',
    opcoes: registos.map(r => ({
      nome:      r.fields.Nome      || '',
      municipio: r.fields['Município'] || '',
    })),
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

    const url       = new URL(request.url);
    const freguesia = url.searchParams.get('freguesia');
    const municipio = url.searchParams.get('municipio');

    if (!freguesia || freguesia.trim().length < 2) {
      return respostaJson({ erro: 'Parâmetro ?freguesia= obrigatório' }, 400, cors);
    }

    try {
      const resultado = await consultarFreguesia(freguesia.trim(), municipio?.trim() || '', env.AIRTABLE_TOKEN);

      if (resultado.tipo === 'nenhum') {
        return respostaJson({ encontrado: false }, 200, cors);
      }

      if (resultado.tipo === 'multiplos') {
        return respostaJson({ encontrado: false, multiplos: true, opcoes: resultado.opcoes }, 200, cors);
      }

      return respostaJson({ encontrado: true, dados: resultado.dados }, 200, cors);
    } catch (erro) {
      return respostaJson({ erro: 'Erro ao consultar dados' }, 500, cors);
    }
  },
};
