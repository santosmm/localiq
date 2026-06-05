# Melhor Zona.pt — Comparador de Qualidade de Vida por Freguesia

## O que é este projecto
Aplicação web que permite a famílias portuguesas comparar
a qualidade de vida entre freguesias usando dados públicos
do INE, ACSS, IPMA e DGEEC. Modelo freemium com canal B2B
para imobiliárias.

## URLs em produção
- Site: https://melhorzona.pt
- Netlify: https://melhorzona.netlify.app
- GitHub: https://github.com/santosmm/localiq
- Worker: https://melhorzona-lista-espera.matheusmottas.workers.dev

## Stack
- Frontend: HTML + CSS + JavaScript vanilla
- Base de dados: Airtable (Base ID: appzKGnGUD6pafKKn)
- Backend: Cloudflare Workers (conta: matheusmottas@gmail.com)
- Hosting: Netlify (deploy automático via git push)
- Pagamentos: Stripe (ainda não integrado)
- Email: Brevo (ainda não configurado)
- IA resumos: Claude API modelo Haiku (ainda não integrado)
- Controlo versões: GitHub

## Identidade visual
- Cor principal: azul azulejo #1B4F72
- Azul médio: #2E86C1
- Azul claro: #D6E8F5
- Tipografia títulos: Playfair Display (Google Fonts)
- Tipografia corpo: Inter (Google Fonts)
- Tom: editorial português, sóbrio, baseado em dados
- Linguagem: sempre portuguesa e local (freguesia, concelho,
  SNS, ACSS, CP, QualAr)

## Arquitectura de recolha de emails
- **index.html**: sem formulário de email. Hero tem só barra de pesquisa de freguesia.
  CTA Final tem botão de scroll "Descobre a tua melhor zona →" que ancora em `#pesquisa`.
- **relatorio.html**: card de alerta entre indicadores livres e bloqueados.
  Envia para o Worker `lista-espera` com `fonte: "alerta-<nome>"` e `notas: "Freguesia: <nome>"`.
- **lista-espera worker**: aceita `fonte` e `notas` no body JSON (override do origin-based fonte).
  Envia confirmação via Brevo (requer secret `BREVO_API_KEY` — ver secção Brevo abaixo).

## Brevo (email transaccional)
- API: `https://api.brevo.com/v3/smtp/email`
- Sender: `noreply@melhorzona.pt` (necessita verificação no painel Brevo)
- Secret no Worker: `cd workers && wrangler secret put BREVO_API_KEY --config lista-espera.toml`
- Falha silenciosa — signup continua mesmo que Brevo falhe

## Ficheiros existentes
- index.html — landing page; hero com barra de pesquisa; sem formulários de email
- relatorio.html — página de relatório por freguesia
  (dados de exemplo, paywall suave nos 3 últimos indicadores; card de alerta entre livres e bloqueados)
- assets/css/ — estilos
- assets/js/ — scripts
- assets/images/ — imagens
- workers/lista-espera.js — Cloudflare Worker para formulário
- workers/wrangler.toml — config wrangler lista-espera
- workers/dados-freguesia.js — Cloudflare Worker para dados de freguesia
- workers/dados-freguesia.toml — config wrangler dados-freguesia
- workers/ine-api.js — Cloudflare Worker de integração com a API INE
- workers/ine-api.toml — config wrangler ine-api
- data/ — scripts de processamento dados INE
  - importar-ine.py — lê CSV do INE e importa para Airtable (usa AIRTABLE_TOKEN)
  - teste_censos2021.csv — 9 freguesias de teste (Lisboa, Porto, Cascais) com geocods DICOFRE reais

## Airtable
- Base: Melhor Zona (appzKGnGUD6pafKKn)
- Tabela: Lista de Espera (tblB9N9UdJDgIHE7B)
  - Campos: Email, Data, Fonte, Notas
  - Já tem inscritos reais — não apagar registos sem confirmar
- Tabela: Freguesias (tbl2mvTKYsrb1h6fc)
  - Campos: Nome, Município, Codigo_INE, Score_Geral, Transportes_Score, Saude_Score, Educacao_Score, Seguranca_Score, Populacao
  - Scores com 1 casa decimal (0–10); Populacao inteiro
  - Geocods DICOFRE reais (INE Censos 2021); 9 registos de teste:
    - Arroios (110656, Lisboa, 33302 hab.)
    - Avenidas Novas (110657, Lisboa, 23261 hab.)
    - Misericórdia (110661, Lisboa, 9658 hab.)
    - Parque das Nações (110662, Lisboa, 22382 hab.)
    - Santa Maria Maior (110665, Lisboa, 10051 hab.)
    - Bonfim (131202, Porto, 22978 hab.)
    - Cedofeita (131217, Porto, 37430 hab.)
    - Paranhos (131210, Porto, 45883 hab.)
    - Cascais e Estoril (110508, Cascais, 64192 hab.)

## Fluxo actual do utilizador
1. Chega à landing page (index.html)
2. Pesquisa freguesia → vai para relatorio.html
3. Vê 3 indicadores gratuitos
4. Vê card de alerta → pode subscrever actualizações por email
5. Clica "Desbloquear por 4,99€" → [A LIGAR] Stripe

## Próximos passos (Sprint 1 em curso)
- [x] Ligar barra de pesquisa da home ao relatorio.html
- [x] Ler parâmetro ?freguesia= no URL do relatório
- [x] Pills de freguesias populares na home
- [x] Construir comparar.html (comparação entre 2 freguesias — veredicto dinâmico, 3 perfis, insight surpresa, paywall contextual)
- [ ] Integrar Stripe para pagamento de 4,99€
- [x] Carregar dados reais do INE/IPMA no Airtable (10 freguesias de teste via data/importar-ine.py)
- [x] Worker dados-freguesia.js — GET ?freguesia= → consulta Airtable → JSON (https://melhorzona-dados-freguesia.matheusmottas.workers.dev)
- [x] relatorio.html liga ao Worker; fallback para dados de exemplo com badge amarelo
- [x] Reestruturar recolha de emails: remover forms da landing; card de alerta no relatório
- [x] lista-espera worker: aceitar fonte+notas no body; integração Brevo (aguarda BREVO_API_KEY)

## Modelo de negócio
- B2C: 1 relatório gratuito/mês, relatório completo 4,99€
  (preço a validar com utilizadores reais)
- B2B: subscrição mensal para imobiliárias (49-99€/mês)
  com PDF exportável com branding da agência
- Preços ainda não validados — não implementar Stripe
  antes de ter feedback de utilizadores reais

## Regras importantes
- Nunca usar frameworks (React, Vue) — HTML/JS vanilla apenas
- Sempre comentar o código em português
- Nunca commitar chaves de API — usar variáveis de ambiente
- AIRTABLE_TOKEN está no Cloudflare como secret encriptado
- Deploy automático: git push origin main → Netlify publica
- Testar sempre no browser antes de fazer commit
- Não apagar registos do Airtable sem confirmação explícita

## Comandos úteis
- Deploy: git push origin main
- Worker deploy: cd workers && wrangler deploy
- Adicionar secret: cd workers && wrangler secret put NOME
- Testar localmente: abrir index.html no browser
