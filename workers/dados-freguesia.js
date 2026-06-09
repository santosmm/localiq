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
    clima_temp_media:    r.clima_temp_media    ?? null,
    clima_sol_horas:     r.clima_sol_horas     ?? null,
    clima_precipitacao:  r.clima_precipitacao  ?? null,
    clima_score:         r.clima_score         ?? null,
  };
}

/* Gera análise expandida com Claude Haiku para relatório pago */
async function gerarAnaliseIa(codigoIne, env) {
  /* Busca dados completos da freguesia no Supabase */
  const sbUrl = `${env.SUPABASE_URL}/rest/v1/freguesias?select=*&codigo_ine=eq.${encodeURIComponent(codigoIne)}&limit=1`;
  const sbRes = await fetch(sbUrl, {
    headers: {
      'apikey':        env.SUPABASE_KEY,
      'Authorization': `Bearer ${env.SUPABASE_KEY}`,
    },
  });
  if (!sbRes.ok) throw new Error(`Supabase ${sbRes.status}`);
  const registos = await sbRes.json();
  if (!registos.length) return { erro: 'Freguesia não encontrada' };

  const r = registos[0];

  /* Perfil urbano/suburbano/rural pela população */
  const pop    = r.populacao ?? 0;
  const perfil = pop > 50000 ? 'urbana' : pop > 10000 ? 'suburbana' : pop > 2000 ? 'semi-urbana' : 'rural';

  /* Monta lista de dados disponíveis para o prompt */
  const dadosStr = [
    r.score_geral     != null ? `score geral ${r.score_geral}/10 (índice Melhor Zona)` : null,
    r.seguranca_valor != null
      ? `segurança: ${parseFloat(r.seguranca_valor).toFixed(1)} crimes/1000 hab (média nacional ~35 — quanto menor, mais seguro)`
      : null,
    r.rendas_mediana  != null
      ? `rendas: €${parseFloat(r.rendas_mediana).toFixed(2)}/m² de mediana (média nacional ~€10/m²; Lisboa ~€17/m²)`
      : null,
    pop > 0 ? `${pop.toLocaleString('pt-PT')} habitantes — zona ${perfil}` : null,
    r.clima_temp_media   != null ? `temperatura média ${parseFloat(r.clima_temp_media).toFixed(1)}°C` : null,
    r.clima_sol_horas    != null ? `${Math.round(r.clima_sol_horas)} horas de sol por ano` : null,
    r.clima_precipitacao != null ? `${Math.round(r.clima_precipitacao)} mm de precipitação anual` : null,
  ].filter(Boolean).join('\n- ');

  const prompt = `Gera uma análise de 4 a 5 frases sobre a qualidade de vida em ${r.nome}, ${r.municipio}, Portugal.

Dados reais disponíveis:
- ${dadosStr}

Inclui obrigatoriamente:
1. Uma apresentação da zona e o que a caracteriza (zona ${perfil}).
2. O contexto de segurança${r.seguranca_valor != null ? ` (${parseFloat(r.seguranca_valor).toFixed(1)} crimes/1000 hab)` : ''} em relação à média nacional (~35).
3. O mercado de arrendamento${r.rendas_mediana != null ? ` (€${parseFloat(r.rendas_mediana).toFixed(2)}/m²)` : ''} face à média nacional (~€10/m²) e ao contexto regional.
4. Para quem é ideal esta zona — famílias, jovens profissionais ou reformados — deduzido dos dados reais.

Responde apenas com as 4 a 5 frases em texto corrido, sem bullets nem títulos. Português europeu, tom editorial sóbrio.`;

  const claudeRes = await fetch('https://api.anthropic.com/v1/messages', {
    method:  'POST',
    headers: {
      'Content-Type':      'application/json',
      'x-api-key':         env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model:      'claude-haiku-4-5-20251001',
      max_tokens: 450,
      messages:   [{ role: 'user', content: prompt }],
    }),
  });

  const claudeJson = await claudeRes.json();
  const texto = claudeJson.content?.[0]?.text?.trim() ?? '';

  if (!texto) throw new Error('Claude devolveu resposta vazia');

  return {
    analise: texto,
    fonte:   'Gerado por Claude Haiku · Dados INE Censos 2021 · INE Rendas 2024',
  };
}

/* Gera análise estruturada para PDF (página 3) — retorna JSON com título, pontos fortes/atenção, etc. */
async function gerarAnalisePdf(codigoIne, env) {
  const sbUrl = `${env.SUPABASE_URL}/rest/v1/freguesias`
    + `?select=nome,municipio,populacao,rendas_mediana,seguranca_valor,seguranca_score,clima_temp_media,clima_sol_horas`
    + `&codigo_ine=eq.${encodeURIComponent(codigoIne)}&limit=1`;

  const sbRes = await fetch(sbUrl, {
    headers: { 'apikey': env.SUPABASE_KEY, 'Authorization': `Bearer ${env.SUPABASE_KEY}` },
  });
  if (!sbRes.ok) throw new Error(`Supabase ${sbRes.status}`);
  const registos = await sbRes.json();
  if (!registos.length) return { erro: 'Freguesia não encontrada' };

  const r   = registos[0];
  const pop = r.populacao ?? 0;
  const dados = [
    r.rendas_mediana  != null ? `rendas medianas ${parseFloat(r.rendas_mediana).toFixed(2)}€/m² (nacional ~€10/m²)` : null,
    r.seguranca_valor != null ? `${parseFloat(r.seguranca_valor).toFixed(1)} crimes/1000 hab (nacional ~35)` : null,
    pop > 0 ? `${pop.toLocaleString('pt-PT')} habitantes` : null,
    r.clima_temp_media != null ? `temperatura média ${parseFloat(r.clima_temp_media).toFixed(1)}°C` : null,
    r.clima_sol_horas  != null ? `${Math.round(r.clima_sol_horas)} horas de sol por ano` : null,
  ].filter(Boolean).join(', ');

  const prompt = `Para a freguesia ${r.nome} em ${r.municipio}, Portugal, com os seguintes dados: ${dados}.

Responde APENAS com JSON válido (sem texto extra, sem blocos markdown), com estas chaves exactas:
{"titulo":"(título editorial curto, máx 10 palavras, português de Portugal)","caracterizacao":"(2 frases a caracterizar a zona, tom sóbrio, português europeu)","pontos_fortes":["(máx 7 palavras)","(máx 7 palavras)","(máx 7 palavras)"],"pontos_atencao":["(máx 7 palavras)","(máx 7 palavras)","(máx 7 palavras)"],"para_quem":"(uma frase, máx 15 palavras, sobre para quem é esta zona)"}`;

  const claudeRes = await fetch('https://api.anthropic.com/v1/messages', {
    method:  'POST',
    headers: {
      'Content-Type':      'application/json',
      'x-api-key':         env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model:      'claude-haiku-4-5-20251001',
      max_tokens: 600,
      messages:   [{ role: 'user', content: prompt }],
    }),
  });

  const claudeJson = await claudeRes.json();
  const texto      = claudeJson.content?.[0]?.text?.trim() ?? '';
  if (!texto) throw new Error('Claude devolveu resposta vazia');

  const match = texto.match(/\{[\s\S]*\}/);
  if (!match) throw new Error('Claude não devolveu JSON válido');

  return { nome: r.nome, municipio: r.municipio, ...JSON.parse(match[0]) };
}

async function consultarMunicipio(nome, supabaseUrl, supabaseKey) {
  const url = `${supabaseUrl}/rest/v1/freguesias`
            + `?select=nome,municipio,score_geral,seguranca_score,rendas_mediana,populacao`
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
    nome:           r.nome           ?? '',
    municipio:      r.municipio      ?? '',
    /* score_geral do Supabase (proxy de população) — difere por freguesia,
       ao contrário de calcularScoreReal que é igual para todas do mesmo município */
    score_geral:    r.score_geral    ?? null,
    rendas_mediana: r.rendas_mediana ?? null,
    populacao:      r.populacao      ?? null,
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

    /* Endpoint /analise?codigo_ine=XXX — análise expandida com Claude Haiku (relatório pago) */
    if (pathname === '/analise') {
      const codigoIne = url.searchParams.get('codigo_ine');
      if (!codigoIne) return respostaJson({ erro: 'codigo_ine obrigatório' }, 400, cors);
      try {
        const resultado = await gerarAnaliseIa(codigoIne, env);
        return new Response(JSON.stringify(resultado), {
          status:  resultado.erro ? 404 : 200,
          headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
        });
      } catch (_) {
        return respostaJson({ erro: 'Erro ao gerar análise' }, 500, cors);
      }
    }

    /* Endpoint /analise-pdf?codigo_ine=XXX — análise estruturada para geração de PDF (página 3) */
    if (pathname === '/analise-pdf') {
      const codigoIne = url.searchParams.get('codigo_ine');
      if (!codigoIne) return respostaJson({ erro: 'codigo_ine obrigatório' }, 400, cors);
      try {
        const resultado = await gerarAnalisePdf(codigoIne, env);
        return new Response(JSON.stringify(resultado), {
          status:  resultado.erro ? 404 : 200,
          headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
        });
      } catch (_) {
        return respostaJson({ erro: 'Erro ao gerar análise PDF' }, 500, cors);
      }
    }

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
