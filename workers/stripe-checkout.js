const ORIGENS_PERMITIDAS = [
  'https://melhorzona.netlify.app',
  'https://melhorzona.pt',
  'https://www.melhorzona.pt',
  'http://localhost:8745',
  'http://localhost:8080',
  'http://127.0.0.1:8745',
];

const STRIPE_API = 'https://api.stripe.com/v1';
const SITE       = 'https://melhorzona.pt';

function cabecalhosCors(origin) {
  const origemPermitida = ORIGENS_PERMITIDAS.includes(origin) ? origin : ORIGENS_PERMITIDAS[0];
  return {
    'Access-Control-Allow-Origin':  origemPermitida,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function respostaJson(dados, status, cors) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

async function chamarStripe(path, method, params, stripeKey) {
  const url  = `${STRIPE_API}/${path}`;
  const opts = {
    method,
    headers: {
      'Authorization': `Bearer ${stripeKey}`,
      'Content-Type':  'application/x-www-form-urlencoded',
    },
  };
  if (params) opts.body = new URLSearchParams(params).toString();
  const res = await fetch(url, opts);
  return res.json();
}

/* Cria sessão Stripe Checkout — modo 'payment' ou 'subscription' */
async function criarSessao(body, env, modo) {
  const { codigo_ine, nome_freguesia, municipio, freguesia_param, municipio_param } = body;

  const tipo   = modo === 'subscription' ? 'mensal' : 'unitario';
  const qFreg  = encodeURIComponent(freguesia_param || nome_freguesia || '');
  const qMun   = municipio_param ? '&municipio=' + encodeURIComponent(municipio_param)   : '';
  const qIne   = codigo_ine      ? '&codigo_ine='  + encodeURIComponent(codigo_ine)      : '';

  /* {CHECKOUT_SESSION_ID} é substituído pelo Stripe com o ID real da sessão */
  const successUrl = `${SITE}/obrigado.html?session_id={CHECKOUT_SESSION_ID}&tipo=${tipo}&freguesia=${qFreg}${qMun}${qIne}`;
  const cancelUrl  = `${SITE}/relatorio.html?freguesia=${qFreg}${qMun}`;

  const priceId = modo === 'subscription'
    ? env.STRIPE_PRICE_ID_MENSAL
    : env.STRIPE_PRICE_ID_UNITARIO;

  if (!priceId) {
    return { erro: `STRIPE_PRICE_ID_${modo === 'subscription' ? 'MENSAL' : 'UNITARIO'} não configurado` };
  }

  const sessao = await chamarStripe('checkout/sessions', 'POST', {
    'line_items[0][price]':     priceId,
    'line_items[0][quantity]':  '1',
    'mode':                     modo,
    'success_url':              successUrl,
    'cancel_url':               cancelUrl,
    'metadata[codigo_ine]':     codigo_ine     || '',
    'metadata[nome_freguesia]': nome_freguesia || '',
    'metadata[municipio]':      municipio      || '',
  }, env.STRIPE_SECRET_KEY);

  if (!sessao.url) {
    return { erro: 'Erro ao criar sessão de pagamento', detalhe: sessao.error?.message || '' };
  }

  return { url: sessao.url };
}

/* Verifica sessão Stripe — funciona para pagamentos únicos e subscrições */
async function verificarPagamento(sessionId, env) {
  const sessao = await chamarStripe(
    `checkout/sessions/${encodeURIComponent(sessionId)}`,
    'GET', null, env.STRIPE_SECRET_KEY,
  );

  if (sessao.error) return { pago: false, erro: 'Sessão inválida' };

  const pago = sessao.status === 'complete';
  const tipo = sessao.mode  === 'subscription' ? 'mensal' : 'unitario';

  return {
    pago,
    tipo,
    codigo_ine:     sessao.metadata?.codigo_ine     || null,
    nome_freguesia: sessao.metadata?.nome_freguesia || null,
  };
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const cors   = cabecalhosCors(origin);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    const url      = new URL(request.url);
    const pathname = url.pathname;

    /* POST /pagar-unitario — relatório único €4,99 (mode: payment) */
    if (pathname === '/pagar-unitario' && request.method === 'POST') {
      try {
        const body      = await request.json();
        const resultado = await criarSessao(body, env, 'payment');
        return respostaJson(resultado, resultado.erro ? 500 : 200, cors);
      } catch (_) {
        return respostaJson({ erro: 'Erro interno' }, 500, cors);
      }
    }

    /* POST /pagar-mensal — acesso mensal €9,99/mês (mode: subscription) */
    if (pathname === '/pagar-mensal' && request.method === 'POST') {
      try {
        const body      = await request.json();
        const resultado = await criarSessao(body, env, 'subscription');
        return respostaJson(resultado, resultado.erro ? 500 : 200, cors);
      } catch (_) {
        return respostaJson({ erro: 'Erro interno' }, 500, cors);
      }
    }

    /* GET /verify?session_id=cs_xxx — verifica pagamento (unitário ou mensal) */
    if (pathname === '/verify' && request.method === 'GET') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId) return respostaJson({ erro: 'session_id obrigatório' }, 400, cors);
      try {
        const resultado = await verificarPagamento(sessionId, env);
        return respostaJson(resultado, 200, cors);
      } catch (_) {
        return respostaJson({ erro: 'Erro ao verificar pagamento' }, 500, cors);
      }
    }

    /* POST /checkout — endpoint legado; mantido para compatibilidade (mode: payment) */
    if (pathname === '/checkout' && request.method === 'POST') {
      try {
        const body      = await request.json();
        const resultado = await criarSessao(body, env, 'payment');
        return respostaJson(resultado, resultado.erro ? 500 : 200, cors);
      } catch (_) {
        return respostaJson({ erro: 'Erro interno' }, 500, cors);
      }
    }

    return respostaJson({ erro: 'Rota não encontrada' }, 404, cors);
  },
};
