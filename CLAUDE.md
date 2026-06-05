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
- Worker lista-espera: https://melhorzona-lista-espera.matheusmottas.workers.dev
- Worker dados-freguesia: https://melhorzona-dados-freguesia.matheusmottas.workers.dev

## Stack
- Frontend: HTML + CSS + JavaScript vanilla
- Base de dados freguesias: Supabase (projecto: hkxdmregnsmsbxvpykul)
- Base de dados emails: Airtable (Base ID: appzKGnGUD6pafKKn) — Lista de Espera mantém-se no Airtable
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
- workers/lista-espera.js — Cloudflare Worker para formulário (usa Airtable)
- workers/wrangler.toml — config wrangler lista-espera
- workers/dados-freguesia.js — Cloudflare Worker para dados de freguesia (usa Supabase)
- workers/dados-freguesia.toml — config wrangler dados-freguesia
- workers/ine-api.js — Cloudflare Worker de integração com a API INE
- workers/ine-api.toml — config wrangler ine-api
- data/schema-supabase.sql — schema PostgreSQL da tabela freguesias
- data/migrar-supabase.py — script de migração Airtable → Supabase (upsert por codigo_ine)
- data/importar-ine.py — lê CSV do INE e importa para Airtable (usa AIRTABLE_TOKEN)
- data/teste_censos2021.csv — 9 freguesias de teste (Lisboa, Porto, Cascais) com geocods DICOFRE reais

## Supabase (base de dados de freguesias)
- Projecto: melhorzona (hkxdmregnsmsbxvpykul)
- URL: https://hkxdmregnsmsbxvpykul.supabase.co
- Tabela: freguesias (3259 registos — INE Censos 2021)
  - Campos: nome, municipio, codigo_ine (UNIQUE), populacao,
    score_geral, transportes_score, transportes_valor,
    ar_score, ar_valor, demografia_score, demografia_valor,
    ensino_score, ensino_valor, saude_score, saude_valor,
    arrendamento_score, arrendamento_valor,
    rendas_mediana, preco_avaliacao_m2, resumo_ia
- RLS activo: leitura pública, escrita só com service_role
- Secrets no Worker dados-freguesia: SUPABASE_URL, SUPABASE_KEY
- Re-migrar: `export AIRTABLE_TOKEN=... SUPABASE_URL=... SUPABASE_KEY=... && python3 data/migrar-supabase.py`
- Pesquisa por freguesia: `GET ?freguesia=Cascais` — usa `ilike.{nome}*` (começa por); "Cascais" encontra "Cascais e Estoril"
- Pesquisa por município: `GET /municipio?nome=Lisboa` — devolve top 10 freguesias do município por `score_geral DESC`
  - Usado pelo relatorio.html como fallback quando `encontrado: false` (ex: user pesquisa "Lisboa")
  - Mostra "Quiseste dizer uma destas freguesias de Lisboa?" com scores clicáveis
  - Caso "Porto": ainda cai na desambiguação de freguesias que começam por "Porto" (pré-existente)
- Municípios usam `ilike.{municipio}` (exacto) — vêm de desambiguação, não de input livre
- **score_geral preenchido** para todas as 3259 freguesias (proxy temporário: `LEAST(ROUND((populacao/50000)*10,1),10)`)
  - Recalcular se scores reais forem importados: SQL `UPDATE freguesias SET score_geral = LEAST(ROUND((populacao::float/50000)*10,1),10)`
  - relatorio.html converte score (0–10) para 0–100 com `Math.round(score*10)` antes de exibir

## Airtable (emails — mantém-se)
- Base: Melhor Zona (appzKGnGUD6pafKKn)
- Tabela: Lista de Espera (tblB9N9UdJDgIHE7B)
  - Campos: Email, Data, Fonte, Notas
  - Já tem inscritos reais — não apagar registos sem confirmar
- Tabela: Freguesias (tbl2mvTKYsrb1h6fc) — fonte de dados para migração; já não usada pelo Worker

## Fluxo actual do utilizador
1. Chega à landing page (index.html)
2. Pesquisa freguesia → vai para relatorio.html
3. Vê 3 indicadores gratuitos
4. Vê card de alerta → pode subscrever actualizações por email
5. Clica "Desbloquear por 4,99€" → [A LIGAR] Stripe

## Sessão 2026-06-05 — Sprint 1 (concluído)

### Commits desta sessão
- `3426ae4` feat: migrar base de dados do Airtable para Supabase
- `f09e9e4` fix: pesquisa por nome parcial no worker (ilike.{nome}*)
- `b8ab73f` feat: pesquisa por município quando freguesia não é encontrada (/municipio?nome=)
- `9b4083a` docs: score_geral calculado para 3259 freguesias
- `2bf853f` feat: tabs hero (Ver relatório / Comparar), nav imobiliárias, pills correctas

### Estado actual
- **Supabase**: 3259 freguesias com `populacao`, `rendas_mediana` (parcial) e `score_geral` (proxy pop.)
- **Worker dados-freguesia**: lê do Supabase; pesquisa por nome parcial e por município
- **relatorio.html**: mostra score_geral, badge dinâmico, card de alerta, paywall
- **index.html**: tabs Ver relatório / Comparar, pills reais, "Para imobiliárias" no nav
- **Enricher INE** (`data/enricher-ine.py`): a correr em background (PID 44589 em 2026-06-05)
  - Quando terminar: `python3 data/migrar-supabase.py` para sincronizar rendas reais no Supabase

### Pendente para próxima sessão
- [ ] Confirmar que enricher INE terminou e sincronizar Supabase
- [ ] Configurar `BREVO_API_KEY` no Worker lista-espera (emails de confirmação)
- [ ] Integrar Stripe para pagamento 4,99€
- [ ] Criar página dedicada "Para imobiliárias" (actualmente âncora #beneficios)

## Próximos passos (Sprint 1 em curso)
- [x] Ligar barra de pesquisa da home ao relatorio.html
- [x] Ler parâmetro ?freguesia= no URL do relatório
- [x] Pills de freguesias populares na home
- [x] Construir comparar.html (comparação entre 2 freguesias — veredicto dinâmico, 3 perfis, insight surpresa, paywall contextual)
- [ ] Integrar Stripe para pagamento de 4,99€
- [x] Carregar dados reais do INE/IPMA no Airtable (10 freguesias de teste via data/importar-ine.py)
- [x] Worker dados-freguesia.js — GET ?freguesia= → consulta Supabase → JSON
- [x] relatorio.html liga ao Worker; fallback para dados de exemplo com badge amarelo
- [x] Reestruturar recolha de emails: remover forms da landing; card de alerta no relatório
- [x] lista-espera worker: aceitar fonte+notas no body; integração Brevo (aguarda BREVO_API_KEY)
- [x] Migrar base de dados de freguesias do Airtable para Supabase (3259 registos)

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
- Secrets do Cloudflare: SUPABASE_URL e SUPABASE_KEY (dados-freguesia), AIRTABLE_TOKEN (lista-espera)
- Deploy automático: git push origin main → Netlify publica
- Testar sempre no browser antes de fazer commit
- Não apagar registos do Airtable sem confirmação explícita

## Comandos úteis
- Deploy site: git push origin main
- Worker deploy: cd workers && wrangler deploy --config <nome>.toml
- Adicionar secret: cd workers && wrangler secret put NOME --config <nome>.toml
- Re-migrar Supabase: python3 data/migrar-supabase.py (com env vars definidas)
- Testar localmente: abrir index.html no browser
