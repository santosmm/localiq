const AIRTABLE_BASE_ID = 'appzKGnGUD6pafKKn';
const AIRTABLE_TABLE_ID = 'tblB9N9UdJDgIHE7B';
const AIRTABLE_API_URL = `https://api.airtable.com/v0/${AIRTABLE_BASE_ID}/${AIRTABLE_TABLE_ID}`;

const ORIGENS_PERMITIDAS = [
  'https://melhorzona.netlify.app',
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

async function guardarNoAirtable(email, fonte, notas, token) {
  const campos = {
    Email: email.trim(),
    Data:  new Date().toISOString(),
    Fonte: fonte || 'desconhecida',
  };
  if (notas) campos.Notas = notas;

  const resposta = await fetch(AIRTABLE_API_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ records: [{ fields: campos }] }),
  });

  if (!resposta.ok) {
    const erro = await resposta.text();
    throw new Error(`Airtable devolveu ${resposta.status}: ${erro}`);
  }

  return resposta.json();
}

async function enviarEmailConfirmacao(email, apiKey) {
  const resposta = await fetch('https://api.brevo.com/v3/smtp/email', {
    method: 'POST',
    headers: {
      'api-key': apiKey,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      sender: { name: 'Melhor Zona', email: 'noreply@melhorzona.pt' },
      to: [{ email }],
      subject: 'Estás na lista de espera — Melhor Zona',
      htmlContent: `
        <div style="font-family:Inter,sans-serif;max-width:520px;margin:0 auto;color:#0d2137">
          <div style="background:#1B4F72;padding:32px 28px;border-radius:12px 12px 0 0">
            <p style="font-size:1.3rem;font-weight:700;color:#fff;margin:0">Melhor Zona<span style="color:rgba(255,255,255,0.45);font-weight:400">.pt</span></p>
          </div>
          <div style="background:#fff;padding:32px 28px;border:1px solid #dde3eb;border-top:none;border-radius:0 0 12px 12px">
            <h1 style="font-size:1.4rem;font-weight:700;margin:0 0 12px">Estás na lista! 🎉</h1>
            <p style="color:#4a5568;line-height:1.7;margin:0 0 20px">
              Recebemos a tua inscrição. Quando o Melhor Zona abrir ao público,
              és dos primeiros a saber — e terás acesso antecipado gratuito.
            </p>
            <p style="color:#4a5568;line-height:1.7;margin:0 0 28px">
              Entretanto, podes já explorar relatórios de qualidade de vida
              por freguesia em <a href="https://melhorzona.pt" style="color:#2E86C1">melhorzona.pt</a>.
            </p>
            <p style="font-size:0.8rem;color:#9aa5b4;margin:0">
              Recebeste este email porque inscreveste o endereço ${email} na lista de espera do Melhor Zona.
            </p>
          </div>
        </div>
      `,
    }),
  });

  if (!resposta.ok) {
    const erro = await resposta.text();
    throw new Error(`Brevo ${resposta.status}: ${erro}`);
  }
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const cors = cabecalhosCors(origin);

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

    const { email, fonte: fonteBody, notas } = corpo;

    if (!emailValido(email)) {
      return new Response(
        JSON.stringify({ success: false, error: 'Email inválido' }),
        { status: 400, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    try {
      const fonteFinal = fonteBody || origin;
      await guardarNoAirtable(email, fonteFinal, notas, env.AIRTABLE_TOKEN);
    } catch (erro) {
      return new Response(
        JSON.stringify({ success: false, error: 'Erro ao guardar. Tenta novamente.' }),
        { status: 500, headers: { ...cors, 'Content-Type': 'application/json' } }
      );
    }

    /* Email de confirmação — falha silenciosa para não bloquear o signup */
    if (env.BREVO_API_KEY) {
      try {
        await enviarEmailConfirmacao(email.trim(), env.BREVO_API_KEY);
      } catch (e) {
        console.error('Brevo falhou:', e.message);
      }
    }

    return new Response(
      JSON.stringify({ success: true }),
      { status: 200, headers: { ...cors, 'Content-Type': 'application/json' } }
    );
  },
};
