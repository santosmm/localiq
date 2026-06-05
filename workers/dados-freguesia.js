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

function mapearRegisto(r) {
  return {
    nome:                r.nome                ?? '',
    municipio:           r.municipio           ?? '',
    codigo_ine:          r.codigo_ine          ?? '',
    populacao:           r.populacao           ?? null,
    score_geral:         r.score_geral         ?? null,
    transportes_score:   r.transportes_score   ?? null,
    transportes_valor:   r.transportes_valor   ?? null,
    ar_score:            r.ar_score            ?? null,
    ar_valor:            r.ar_valor            ?? null,
    demografia_score:    r.demografia_score    ?? null,
    demografia_valor:    r.demografia_valor    ?? null,
    ensino_score:        r.ensino_score        ?? null,
    ensino_valor:        r.ensino_valor        ?? null,
    saude_score:         r.saude_score         ?? null,
    saude_valor:         r.saude_valor         ?? null,
    arrendamento_score:  r.arrendamento_score  ?? null,
    arrendamento_valor:  r.arrendamento_valor  ?? null,
    rendas_mediana:      r.rendas_mediana      ?? null,
    preco_avaliacao_m2:  r.preco_avaliacao_m2  ?? null,
    resumo_ia:           r.resumo_ia           ?? null,
  };
}

async function consultarFreguesia(nome, municipio, supabaseUrl, supabaseKey) {
  let url = `${supabaseUrl}/rest/v1/freguesias?select=*&nome=ilike.${encodeURIComponent(nome)}*&limit=5`;
  if (municipio) {
    url += `&municipio=ilike.${encodeURIComponent(municipio)}`;
  }

  const resposta = await fetch(url, {
    headers: {
      'apikey':        supabaseKey,
      'Authorization': `Bearer ${supabaseKey}`,
    },
  });

  if (!resposta.ok) {
    throw new Error(`Supabase ${resposta.status}`);
  }

  const registos = await resposta.json();

  if (!registos.length) return { tipo: 'nenhum' };

  if (registos.length === 1) {
    return { tipo: 'unico', dados: mapearRegisto(registos[0]) };
  }

  return {
    tipo: 'multiplos',
    opcoes: registos.map(r => ({ nome: r.nome || '', municipio: r.municipio || '' })),
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
      const resultado = await consultarFreguesia(
        freguesia.trim(),
        municipio?.trim() || '',
        env.SUPABASE_URL,
        env.SUPABASE_KEY,
      );

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
