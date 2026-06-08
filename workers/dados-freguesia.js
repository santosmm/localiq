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
  };
}

function respostaJson(dados, status, cors, temResumoIa = false) {
  const maxAge = temResumoIa ? 300 : 3600;
  return new Response(JSON.stringify(dados), {
    status,
    headers: {
      ...cors,
      'Content-Type': 'application/json',
      'Cache-Control': `public, max-age=${maxAge}`,
    },
  });
}

/* Calcula score geral a partir dos dados reais — nunca usa população como proxy */
function calcularScoreReal(r) {
  var scores = [];
  if (r.seguranca_score   != null) scores.push(r.seguranca_score);
  if (r.transportes_score != null) scores.push(r.transportes_score);
  if (r.saude_score       != null) scores.push(r.saude_score);
  if (r.ensino_score      != null) scores.push(r.ensino_score);
  if (r.rendas_mediana    != null) {
    /* Invertido: rendas baixas = mais acessível = melhor score */
    /* Calibração: 3€/m² → 9.1, 10€/m² → 7.0, 20€/m² → 4.0, 33€/m² → 0.1 */
    var arScore = Math.max(0, Math.min(10, parseFloat((10 - r.rendas_mediana * 0.3).toFixed(1))));
    scores.push(arScore);
  } else if (r.arrendamento_score != null) {
    scores.push(r.arrendamento_score);
  }
  if (scores.length === 0) return null;
  var media = scores.reduce(function(a, b) { return a + b; }, 0) / scores.length;
  return parseFloat(media.toFixed(1));
}

function mapearRegisto(r) {
  return {
    nome:                r.nome                ?? '',
    municipio:           r.municipio           ?? '',
    codigo_ine:          r.codigo_ine          ?? '',
    populacao:           r.populacao           ?? null,
    score_geral:         calcularScoreReal(r),
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
    seguranca_score:     r.seguranca_score     ?? null,
    seguranca_valor:     r.seguranca_valor     ?? null,
    arrendamento_score:  r.arrendamento_score  ?? null,
    arrendamento_valor:  r.arrendamento_valor  ?? null,
    rendas_mediana:      r.rendas_mediana      ?? null,
    preco_avaliacao_m2:  r.preco_avaliacao_m2  ?? null,
    resumo_ia:           r.resumo_ia           ?? null,
  };
}

async function consultarMunicipio(nome, supabaseUrl, supabaseKey) {
  const url = `${supabaseUrl}/rest/v1/freguesias`
            + `?select=nome,municipio,score_geral,seguranca_score,rendas_mediana`
            + `&municipio=ilike.${encodeURIComponent(nome)}*`
            + `&order=score_geral.desc.nullslast`
            + `&limit=10`;

  const resposta = await fetch(url, {
    headers: {
      'apikey':        supabaseKey,
      'Authorization': `Bearer ${supabaseKey}`,
    },
  });

  if (!resposta.ok) throw new Error(`Supabase ${resposta.status}`);

  const registos = await resposta.json();
  return registos.map(r => ({
    nome:        r.nome      ?? '',
    municipio:   r.municipio ?? '',
    score_geral: calcularScoreReal(r),
  }));
}

async function consultarFreguesia(nome, municipio, supabaseUrl, supabaseKey) {
  let url = `${supabaseUrl}/rest/v1/freguesias?select=*&nome=ilike.${encodeURIComponent(nome)}*&order=populacao.desc.nullslast&limit=5`;
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
    const pathname  = url.pathname;
    const freguesia = url.searchParams.get('freguesia');
    const municipio = url.searchParams.get('municipio');

    /* Endpoint /municipio?nome=Lisboa — top 10 freguesias do município */
    if (pathname === '/municipio') {
      const nome = url.searchParams.get('nome');
      if (!nome || nome.trim().length < 2) {
        return respostaJson({ erro: 'Parâmetro ?nome= obrigatório' }, 400, cors);
      }
      try {
        const freguesias = await consultarMunicipio(nome.trim(), env.SUPABASE_URL, env.SUPABASE_KEY);
        if (!freguesias.length) return respostaJson({ encontrado: false }, 200, cors);
        return respostaJson({ encontrado: true, municipio: nome.trim(), freguesias }, 200, cors);
      } catch (erro) {
        return respostaJson({ erro: 'Erro ao consultar município' }, 500, cors);
      }
    }

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

      const temResumoIa = !!resultado.dados.resumo_ia;
      return respostaJson({ encontrado: true, dados: resultado.dados }, 200, cors, temResumoIa);
    } catch (erro) {
      return respostaJson({ erro: 'Erro ao consultar dados' }, 500, cors);
    }
  },
};
