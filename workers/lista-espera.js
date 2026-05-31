const AIRTABLE_BASE_ID = 'appzKGnGUD6pafKKn';
const AIRTABLE_TABLE_ID = 'tblB9N9UdJDgIHE7B';
const AIRTABLE_API_URL = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}`;

const ORIGENS_PERMITIDAS = [
  'https://melhorzona.pt',
  'https://www.melhorzona.pt',
];

function cabecalhosCors(origin) {
  const origemPermitida = ORIGENS_PERMITIDAS.includes(origin) ? origin : ORIGENS_PERMITIDAS[0];
  return {
    'Access-Control-Allow-Origin': origemPermitida,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

function emailValido(email) {
  return typeof email === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

async function guardarNoAirtable(email, fonte, token) {
  const resposta = await fetch(AIRTABLE_API_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      records: [{
        fields: {
          Email: email.trim(),
          Data: new Date().toISOString(),
          Fonte: fonte || 'desconhecida',
        },
      }],
    }),
  });

  if (!resposta.ok) {
    const erro = await resposta.text();
    throw new Error(`Airtable devolveu ${resposta.status}: ${erro}`);
  }

  return resposta.json();
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const cors = cabecalhosCors(origin);

    // Responde ao preflight CORS
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    if (request.method !== 'POST') {
      return new Response(
        JSON.stringify({ success: false, error: 'Método não permitido' }),
        { status: 405, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    let corpo;
    try {
      corpo = await request.json();
    } catch {
      return new Response(
        JSON.stringify({ success: false, error: 'JSON inválido' }),
        { status: 400, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    const { email } = corpo;

    if (!emailValido(email)) {
      return new Response(
        JSON.stringify({ success: false, error: 'Email inválido' }),
        { status: 400, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    try {
      await guardarNoAirtable(email, origin, env.AIRTABLE_TOKEN);
      return new Response(
        JSON.stringify({ success: true }),
        { status: 200, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    } catch (erro) {
      return new Response(
        JSON.stringify({ success: false, error: 'Erro ao guardar. Tenta novamente.' }),
        { status: 500, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }
  },
};
