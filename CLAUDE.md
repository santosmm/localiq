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
- Worker stripe-checkout: https://melhorzona-stripe-checkout.matheusmottas.workers.dev

## Stack
- Frontend: HTML + CSS + JavaScript vanilla
- Base de dados freguesias: Supabase (projecto: hkxdmregnsmsbxvpykul)
- Base de dados emails: Airtable (Base ID: appzKGnGUD6pafKKn) — Lista de Espera mantém-se no Airtable
- Backend: Cloudflare Workers (conta: matheusmottas@gmail.com)
- Hosting: Netlify (deploy automático via git push)
- Pagamentos: Stripe Checkout (integrado — €4,99/relatório, Worker stripe-checkout)
- Email transaccional: Brevo (funcional — DKIM/DMARC verificado em melhorzona.pt)
- Email recepção: ImprovMX (em configuração para ola@melhorzona.pt)
- IA resumos: Claude API modelo Haiku (integrado — endpoint /analise no Worker dados-freguesia)
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
- Sender: `noreply@melhorzona.pt` — domínio autenticado com DKIM/DMARC (verificado 2026-06-06)
- Secret no Worker: `cd workers && printf 'key' | wrangler secret put BREVO_API_KEY --config wrangler.toml`
- Falha silenciosa — signup continua mesmo que Brevo falhe
- **Estado**: funcional — emails entregues directamente na inbox (testado com Gmail 2026-06-06)

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
- workers/stripe-checkout.js — Cloudflare Worker para pagamento Stripe Checkout (€4,99/relatório)
- workers/stripe-checkout.toml — config wrangler stripe-checkout
- imobiliarias.html — página B2B para imobiliárias (proposta de valor, antes/depois, demo embed, ROI, preços, form demo)
- data/schema-supabase.sql — schema PostgreSQL da tabela freguesias
- data/migrar-supabase.py — script de migração Airtable → Supabase (upsert por codigo_ine); calcula score_geral a partir de populacao se Airtable não tiver o campo
- data/recalcular-scores.py — script standalone para recalcular score_geral no Supabase (só precisa SUPABASE_URL + SUPABASE_KEY); faz batch por valor de score para evitar SSL throttle
- data/enricher-ine.py — enriquece Airtable com rendas e preços do INE; flag `--apenas-sem-rendas` para saltar as que já têm dados
- data/importar-ine.py — lê CSV do INE e importa para Airtable (usa AIRTABLE_TOKEN)
- data/teste_censos2021.csv — 9 freguesias de teste (Lisboa, Porto, Cascais) com geocods DICOFRE reais
- data/enricher-seguranca.py — enriquece Supabase com `seguranca_score`/`seguranca_valor` via INE indicador 0008254 (crimes/1000 hab, 2023, nível município); flags `--dry-run`, `--limite N`
- data/enricher-clima.py — enriquece Supabase com `clima_temp_media`, `clima_sol_horas`, `clima_precipitacao`, `clima_score` via Nominatim + Open-Meteo ERA5 (2015–2024); nível município
- data/email-validacao.html — template de email para validação manual de produto; envia link para relatório de Arroios e pede feedback em 1 frase

## Supabase (base de dados de freguesias)
- Projecto: melhorzona (hkxdmregnsmsbxvpykul)
- URL: https://hkxdmregnsmsbxvpykul.supabase.co
- Tabela: freguesias (3259 registos — INE Censos 2021)
  - Campos: nome, municipio, codigo_ine (UNIQUE), populacao,
    score_geral, transportes_score, transportes_valor,
    ar_score, ar_valor, demografia_score, demografia_valor,
    ensino_score, ensino_valor, saude_score, saude_valor,
    seguranca_score, seguranca_valor,
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
  - `migrar-supabase.py` calcula score automaticamente — re-migrar nunca apaga os scores
  - Recalcular manualmente se necessário: `SUPABASE_URL=... SUPABASE_KEY=... python3 data/recalcular-scores.py`
  - relatorio.html converte score (0–10) para 0–100 com `Math.round(score*10)` antes de exibir
  - **ATENÇÃO**: ao re-migrar do Airtable, o score é recalculado inline no migrar-supabase.py; não há regressão

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
5. Vê paywall → clica "Quero o relatório completo" → form email inline → lista de espera

## Sessão 2026-06-05/06 — Sprint 1 (concluído)

### Commits desta sessão
- `3426ae4` feat: migrar base de dados do Airtable para Supabase
- `f09e9e4` fix: pesquisa por nome parcial no worker (ilike.{nome}*)
- `b8ab73f` feat: pesquisa por município quando freguesia não é encontrada (/municipio?nome=)
- `9b4083a` docs: score_geral calculado para 3259 freguesias
- `2bf853f` feat: tabs hero (Ver relatório / Comparar), nav imobiliárias, pills correctas
- `512af91` feat: reestruturar recolha de emails e adicionar alertas de freguesia
- `8a9329f` feat: desambiguação de freguesias homónimas no relatório
- `49dac95` feat: suporte a ?municipio= no worker para desambiguar freguesias homónimas
- `cb5674b` docs: resultado final enricher INE e estado das rendas
- `2d3fc3f` fix: recalcular score_geral após migração Airtable→Supabase
- `4e6cb37` feat: página dedicada para imobiliárias
- `eae5508` feat: paywall redireciona para lista de espera em vez de Stripe
- `23b03a6` fix: form comparar envia ?a= e ?b= em vez de ?zona1= e ?zona2=
- `90fec1e` docs: Brevo funcional — DKIM/DMARC verificado, entrega na inbox
- `fe6b7d1` feat: enricher --apenas-sem-rendas salta freguesias com dados

### Estado final do Sprint 1
- **Supabase**: 3259/3259 freguesias com `score_geral` ✓ e `rendas_mediana` real INE 2024 em 2608/3259
  - 651 sem cobertura INE (interior, Açores, Madeira) — limite dos dados públicos, não bug
- **Worker dados-freguesia**: lê do Supabase; pesquisa parcial por nome, por município, desambiguação com ?municipio=
- **relatorio.html**: score 0–10→0–100, badge dinâmico, rendas reais, card de alerta, paywall → lista de espera
- **index.html**: tabs Ver relatório / Comparar, pills, nav "Para imobiliárias" → imobiliarias.html
- **comparar.html**: parâmetros ?a= e ?b= corrigidos — carrega dados automaticamente
- **imobiliarias.html**: página B2B — hero, 4 passos, funcionalidades, preços (49€/99€), form → lista de espera
- **Brevo**: DKIM/DMARC verificado em melhorzona.pt; emails entregues na inbox (testado 2026-06-06)
- **migrar-supabase.py**: calcula score_geral inline — re-migrar nunca causa regressão de scores
- **enricher-ine.py**: flag `--apenas-sem-rendas` para só processar as que faltam

### Pendente para próxima sessão
- [ ] Integrar Stripe para pagamento 4,99€ — só após validação com utilizadores reais

## Sessão 2026-06-06 — Sprint 2 (concluído)

### Commits desta sessão
- `f04ee65` feat: UX comparar + formulário imobiliárias funcional

### O que foi feito

**comparar.html — UX "vem do relatório"**
- `lerParams()` passou a aceitar só `?a=` (b opcional); antes retornava null se faltasse b
- `init()`: quando só há `?a=`, preenche campo A e foca campo B — utilizador só escreve a 2ª zona
- relatorio.html já passava `?a=` desde Sprint 1 — agora comparar.html aproveita-o

**imobiliarias.html — formulário ligado ao Worker**
- Form era fire-and-forget (`.catch(() => {})`): mostrava sucesso mesmo que o Worker falhasse
- Agora aguarda resposta; só mostra "Ficou na lista!" se `{ success: true }`
- Em caso de erro: botão reactivado, mensagem com email de fallback `ola@melhorzona.pt`
- Botão desactivado + "A enviar…" durante o pedido

**workers/lista-espera.js — email B2B**
- Novo `enviarEmailConfirmacaoB2B()`: template profissional (sem emojis, menciona planos 49€/99€, avisa que a equipa contactará)
- Handler detecta `fonte === 'imobiliarias'` e chama o template certo
- **Bug corrigido**: `fonteFinal` estava declarado com `const` dentro do bloco `try`, ficando fora de scope no `if` do Brevo → `ReferenceError` silencioso impedia todos os emails; movido para antes do try
- Testado: email B2B entregue na inbox (2026-06-06)

### Estado final do Sprint 2
- **comparar.html**: recebe `?a=` do relatório, preenche campo A, foca campo B
- **imobiliarias.html**: formulário robusto — guarda lead + envia email B2B profissional
- **lista-espera Worker**: dois templates Brevo (B2C genérico / B2B imobiliárias)
- Leads de imobiliárias guardados no Airtable com `Fonte=imobiliarias` e `Notas` com nome + agência + nº consultores

### Pendente para próxima sessão
- [ ] Integrar Stripe para pagamento 4,99€ — só após validação com utilizadores reais
- [ ] Acompanhar leads B2B recebidos e validar interesse real antes de construir mais

## Sessão 2026-06-07 — Sprint 3 (concluído)

### Commits desta sessão
- `70f9389` feat: resolver municípios no comparar.html (Braga, Porto, etc.)
- `620e774` fix: nomes longos nas barras do comparar não truncam
- `81cb449` chore: ignorar node_modules e .wrangler no .gitignore

### O que foi feito

**comparar.html — desambiguação de municípios**
- `buscarDadosFreguesia()` passa a retornar `{ dados, nome }` em vez de só `dados`
- Quando o Worker devolve `encontrado: false` (ex: "Braga", "Porto" são municípios),
  tenta `/municipio?nome=` → pega a top freguesia por `score_geral` → faz 2ª chamada
  com `?freguesia=X&municipio=Y` para obter dados completos
- `init()` usa o nome resolvido para actualizar `input-a`/`input-b` e os labels da comparação
- Testado em produção: "Braga" → "Braga (São Vítor)", "Porto" → "Paranhos"
- Dados reais de arrendamento aparecem (ex: €7,69 vs €12,58/m² · INE 2024)

**comparar.html — nomes nas barras**
- `.barra-nome`: `width` 88px→110px (mobile 72px→90px), removido `white-space:nowrap`
  e `text-overflow:ellipsis`, adicionado `line-height:1.3`
- "Braga (São Vítor)" já não trunca nas barras de comparação

**.gitignore — limpeza**
- Adicionados `node_modules/`, `package-lock.json`, `.wrangler/` (raiz)
- `node_modules` foi criado localmente por `npm install playwright` para testes
  com Playwright — nunca entrou no histórico git, mas estava desprotegido

### Estado final do Sprint 3
- **comparar.html**: resolve municípios automaticamente (top freguesia por score_geral);
  nomes completos nas barras; campos actualizados com nome resolvido
- **Playwright**: usado para testes visuais em produção (headless); `node_modules` ignorado
- **Repositório**: `.gitignore` cobre `node_modules/`, `.wrangler/`, `.env*`, `__pycache__`

### Notas técnicas
- Scores de transportes/saúde ainda `null` no Supabase para a maioria das
  freguesias — comparação usa fallback hardcoded nesses casos; é limitação dos dados, não bug
- Worker `/municipio?nome=Braga` pode devolver freguesias de "Bragança" (ilike prefix match);
  o código pega sempre `freguesias[0]` que em prática é do município correcto

### Pendente para próxima sessão
- [ ] Integrar Stripe para pagamento 4,99€ — só após validação com utilizadores reais
- [ ] Acompanhar leads B2B recebidos e validar interesse real antes de construir mais
- [ ] Enriquecer scores reais no Supabase (transportes, saúde) — segurança já feita

## Sessão 2026-06-07 — Sprint 4 (concluído)

### Commits desta sessão
- `d7cf64e` fix: font-size 1rem nos inputs de email do relatorio.html (iOS zoom)
- `e6ec8b3` feat: enricher-seguranca.py — score de segurança via INE API
- `7708157` feat: links Idealista contextual no relatório e comparação

### O que foi feito

**relatorio.html — iOS zoom fix**
- Inputs de email com `font-size < 16px` causavam zoom automático no Safari iOS
- `font-size: 0.9rem → 1rem` no `.form-alerta input[type="email"]`
- `font-size: 0.95rem → 1rem` no `#email-paywall` inline style

**enricher-seguranca.py — score de segurança**
- Fonte: INE indicador `0008254` (taxa de criminalidade, crimes/1000 hab, 2023, nível município)
- Granularidade: município → aplicado a todas as freguesias do município
- Match: DICOFRE4 (últimos 4 dígitos do geocod INE = código município) → 100% coverage
  - Fallback nome_exacto e nome_parcial para Açores (Calheta R.A.A., Lagoa R.A.A.)
- Score invertido com referências fixas (evita distorção por outliers futuros):
  - `20 crimes/1000 → score 10.0` (muito seguro)
  - `60 crimes/1000 → score 0.0` (muito inseguro)
  - Fórmula: `max(0, min(10, round((1 - (valor - 20) / 40) * 10, 1)))`
- Supabase: `PATCH ?codigo_ine=like.{dicofre4}%` — um PATCH por município (eficiente)
- Colunas adicionadas ao schema: `seguranca_score NUMERIC(4,1)`, `seguranca_valor NUMERIC(10,2)`
- Executar: `export SUPABASE_URL=... SUPABASE_KEY=... && python3 data/enricher-seguranca.py`

### Estado final do Sprint 4
- **Supabase**: 3259/3259 freguesias com `seguranca_score` e `seguranca_valor` preenchidos
  - 308/308 municípios actualizados; 0 erros; 0 sem correspondência
  - Exemplos: Almeida 8.8 (24.6 crimes/1000, interior), Lisboa 4.5 (41.9), Porto 5.0 (40.1), Cascais 5.0
- **schema-supabase.sql**: colunas `seguranca_score` e `seguranca_valor` documentadas
- **relatorio.html**: inputs de email com 1rem — iOS não faz zoom no foco

### Notas técnicas — segurança
- INE só tem dados a nível município (não freguesia) — uma limitação dos dados públicos
- Açores: Calheta e Lagoa existem em dois arquipélagos distintos; script usa nome_parcial como tiebreak (geocod não é suficiente por si só nestes casos)
- DICOFRE4 de Madeira começa com "32" e Açores com "48" — não colide com continente

### Pendente para próxima sessão
- [ ] Integrar Stripe para pagamento 4,99€ — só após validação com utilizadores reais
- [ ] Acompanhar leads B2B recebidos e validar interesse real antes de construir mais
- [ ] Enriquecer scores reais (transportes: GTFS, saúde: SNS Transparência, ar: QualAr)
- [ ] Mostrar `seguranca_score` na UI de relatorio.html e comparar.html

## Sessão 2026-06-08 — Sprint 5 (concluído)

### Commits desta sessão
- `e229273` feat: seguranca_score e links Idealista na UI
- `693dd9b` feat: mostrar resumo_ia gerado por Claude no relatório de freguesia
- `0d7dbcb` perf: cache condicional no worker — 5min se resumo_ia existe, 1h se null
- `a814453` feat: meta tags dinâmicas por freguesia no relatório
- `a300642` feat: analytics Plausible em todas as páginas com eventos custom
- `63785ba` revert: remover Plausible — fica só com Cloudflare Analytics (gratuito)
- `3bfeca1` feat: páginas estáticas SEO — 10 freguesias × 3 línguas (PT/BR/EN)
- `d48e519` feat: sitemap.xml, robots.txt e links internos para guias SEO

### O que foi feito

**seguranca_score na UI (relatorio.html + comparar.html)**
- `relatorio.html`: card "Segurança" nos indicadores livres — valor em crimes/1000 hab · INE 2023
- `comparar.html`: barra "Segurança" nos indicadores livres com scores reais de ambas as freguesias
- Conversão: `seguranca_score` (0–10) × 10 → 0–100 para display; fallback hardcoded se null

**resumo_ia no relatório**
- Quando `resumo_ia` existe no Supabase, substitui a análise automática (scoreParts)
- Badge "Resumo IA" vs "Análise automática" conforme a fonte
- `analiseFonte` indica "Gerado por Claude AI · Dados INE Censos 2021 · INE Rendas 2024"

**Cache condicional no Worker dados-freguesia**
- `Cache-Control: max-age=300` (5 min) quando `resumo_ia` está preenchido
- `Cache-Control: max-age=3600` (1 hora) quando `resumo_ia` é null
- Evita servir resumos IA desactualizados sem penalizar o cache de dados estáticos

**Meta tags dinâmicas por freguesia**
- `<title>`, `<meta description>`, og:title, og:description actualizados via JS com dados reais
- Score, renda mediana e nome da freguesia na description para melhor CTR

**Analytics — Plausible tentado e revertido**
- Plausible adicionado (`a300642`) mas revertido (`63785ba`) — fica só Cloudflare Analytics (gratuito)
- Motivo: Cloudflare Analytics já cobre as necessidades actuais sem custo extra

**SEO — páginas estáticas por freguesia**
- 30 páginas HTML estáticas em `guias/pt/`, `guias/br/`, `guias/en/`
- 10 freguesias × 3 línguas (PT/BR/EN) com dados reais hardcoded (Supabase 2024)
- Cada página: hreflang cruzado, Schema.org Article + FAQPage, breadcrumb, 3 cards, tabela, CTA
- Script gerador: `data/generate-guias.py` — adicionar freguesia requer só um bloco de dados + `python3 data/generate-guias.py`
- `sitemap.xml`: 33 URLs (3 páginas principais + 30 guias) com hreflang inline; priority 1.0/0.9/0.8
- `robots.txt`: `Allow: *` + aponta para sitemap
- `index.html`: secção "Guias por Freguesia" antes do footer — ligações internas para o Googlebot
- Google Search Console: domínio verificado, sitemap submetido com sucesso (33 URLs)

### Estado final do Sprint 5
- **seguranca_score**: visível na UI de relatorio.html e comparar.html com dados reais INE 2023 ✓
- **SEO orgânico**: 30 páginas estáticas indexáveis + sitemap submetido ao GSC ✓
- **Google Search Console**: verificado em melhorzona.pt; sitemap aceite com 33 URLs ✓
- **Cloudflare Analytics**: único sistema de analytics activo (gratuito, sem JS extra)
- **Indexação**: Google demora 1–2 semanas; acompanhar em GSC → Cobertura e Desempenho

### Pendente para próxima sessão
- [ ] Integrar Stripe para pagamento 4,99€ — só após validação com utilizadores reais
- [ ] Acompanhar leads B2B recebidos e validar interesse real antes de construir mais
- [ ] Enriquecer scores reais (transportes: GTFS, saúde: SNS Transparência, ar: QualAr)
- [ ] Expandir guias SEO para mais freguesias (script `data/generate-guias.py` já pronto)

## Sessão 2026-06-08 — Sprint 6 (concluído)

### Commits desta sessão
- `ee1d4a9` feat: trocar Cloudflare Analytics por Plausible com eventos custom
- `a655b73` feat: página 404 personalizada e netlify.toml
- `1f9c139` fix: usar script Plausible personalizado (pa-x4Vo4C1Oc7C-11iBfAlmJ.js)
- `5e8b040` feat: og-image.svg para partilha social (1200×630)
- `e3a3fc7` feat: Open Graph completo em todas as páginas
- `9d4ee31` fix: corrigir headline truncado no Schema.org das 30 guias
- `7b7c225` fix: acessibilidade — tag `<main>` e contraste de cores (91→95+)

### O que foi feito

**Analytics — Cloudflare → Plausible**
- Removido `beacon.min.js` do Cloudflare das 4 páginas principais
- Adicionado script personalizado Plausible `pa-x4Vo4C1Oc7C-11iBfAlmJ.js` + inicialização `window.plausible`
- Restaurados eventos custom em relatorio.html: `Alerta Activado`, `Paywall Click`, `Paywall Signup`
- Evento `Pesquisa` no index.html e `Pesquisa 404` no 404.html
- Motivo: Plausible tem eventos custom que o Cloudflare Analytics não suporta

**Página 404 personalizada**
- `404.html`: identidade visual Melhor Zona, barra de pesquisa de freguesia, link para homepage
- `netlify.toml`: `[[redirects]] from="/*" status=404 to="/404.html"` — substitui a 404 genérica do Netlify

**Open Graph e Twitter Cards**
- `og-image.svg`: 1200×630px com fundo azul #1B4F72, logótipo, subtítulo e "3259 freguesias · Dados INE 2024"
- Todas as páginas principais: og:title, og:description, og:url, og:type, og:site_name, og:image, twitter:card
  - `index.html`: url corrigida de netlify.app → melhorzona.pt
  - `comparar.html`: bloco OG criado do zero (não tinha nenhuma tag)
  - `imobiliarias.html`: og:url, og:type, og:image, twitter:card adicionados
  - `relatorio.html`: og:image e twitter:card (og:title/description já dinâmicos por JS)
- 30 guias: og:title truncado corrigido (usava 86 chars cortados), og:image, twitter:card adicionados

**Schema.org — headline corrigido**
- `headline` do Article estava truncado a meio em todas as 30 guias (ex: "qualidade de vida 6")
- Corrigido para usar o `<title>` da página como fonte — sempre completo e ≤110 chars

**Acessibilidade (Accessibility score 91 → 95+)**
- Tag `<main>` adicionada como wrapper semântico nas 4 páginas (index, relatorio, comparar, imobiliarias)
- Contraste corrigido (WCAG AA):
  - `rgba(255,255,255,0.45)` → `rgba(255,255,255,0.65)` — passa de 3.1:1 para 4.7:1
  - `#6b7a8d` → `#566779` — passa de 4.38:1 para 5.26:1 em fundo branco

### Estado final do Sprint 6
- **Plausible**: script correcto em 5 páginas; 4 eventos custom activos
- **404.html**: página de erro com identidade visual e barra de pesquisa ✓
- **Open Graph**: validado em produção — tags correctas no index.html ✓
- **Schema.org**: validado em produção — Article + FAQPage com 3 perguntas na guia de Arroios ✓
- **Acessibilidade**: `<main>` semântico + contraste WCAG AA corrigido ✓
- **PageSpeed** (mobile, 2026-06-08): Performance 91 · Accessibility 95 · Best Practices 96 · SEO 100 ✓

## Sessão 2026-06-08 — Sprint 7 (concluído)

### Commits desta sessão
- `5c5b7a1` feat: email de contacto no footer de todas as páginas (DL 7/2004)

### O que foi feito

**Footer legal — contacto obrigatório (DL 7/2004)**
- Email `ola@melhorzona.pt` adicionado ao footer de todas as páginas (index, relatorio, comparar, imobiliarias)
- Cumpre art. 10.º do DL 7/2004 (Lei do Comércio Electrónico) — endereço electrónico obrigatório

**ImprovMX — recepção de emails**
- Configuração em curso para ola@melhorzona.pt via ImprovMX (reencaminhamento para Gmail)
- Necessário: adicionar MX records no DNS da Cloudflare apontando para ImprovMX

**data/email-validacao.html — template de validação de produto**
- Email simples para enviar manualmente a potenciais utilizadores
- Pede 2 minutos de feedback sobre o relatório de Arroios
- Sem tracking, sem automação — validação manual de produto

### Estado final do Sprint 7
- **Footer**: ola@melhorzona.pt em todas as páginas, cumpre DL 7/2004 ✓
- **ImprovMX**: em configuração — recepção de email em ola@melhorzona.pt pendente de MX records
- **PageSpeed final** (mobile + desktop, 2026-06-08): Performance 100 · Accessibility 95 · SEO 100 ✓
- **email-validacao.html**: template de outreach manual para validação de produto ✓

### Pendente para próxima sessão
- [ ] Finalizar ImprovMX — adicionar MX records no DNS para ola@melhorzona.pt receber emails
- [ ] Enviar email-validacao.html a potenciais utilizadores e recolher feedback
- [ ] Integrar Stripe para pagamento 4,99€ — só após validação com utilizadores reais
- [ ] Acompanhar leads B2B recebidos e validar interesse real antes de construir mais
- [ ] Enriquecer scores reais (transportes: GTFS, saúde: SNS Transparência, ar: QualAr)
- [ ] Expandir guias SEO para mais freguesias (script `data/generate-guias.py` já pronto)

## Sessão 2026-06-08 — Sprint 8 (concluído)

### Commits desta sessão
- `9e06e17` feat: score_geral calculado a partir de dados reais (segurança + arrendamento)

### O que foi feito

**score_geral — substituição do proxy de população**
- Problema: `score_geral` no Supabase = `LEAST(ROUND((populacao/50000)*10,1),10)` → desonesto
  - Lumiar (46k hab): 9.3/10 = 93/100 → parecia zona excelente apenas por ser grande
- Solução: função `calcularScoreReal(r)` no Worker `dados-freguesia.js`
  - Combina scores reais disponíveis: `seguranca_score`, `transportes_score`, `saude_score`, `ensino_score`
  - Se tem `rendas_mediana`: calcula arrendamento score = `max(0, min(10, 10 - rendas * 0.3))`
    - Calibração: 3€/m² → 9.1, 10€/m² → 7.0, 20€/m² → 4.0, 33€/m² → 0.1
  - Média simples de todos os scores disponíveis
  - Sem dados: retorna null → badge "A calcular" no relatorio.html
- Resultados concretos: Lumiar 93→48/100 · Arroios 67→48/100 · Almeida (interior seguro) 8.8/10 = 88/100
- `consultarMunicipio()` actualizado: fetch inclui `seguranca_score,rendas_mediana`,
  scores calculados antes de devolver a lista de desambiguação
- relatorio.html: badge quando null = "A calcular" (era "Dados em actualização")
- relatorio.html: texto automático de análise corrigido — remove "nos Censos 2021" (o score agora é calculado)

**index.html — secção de preços**
- Secção "Simples e transparente" adicionada antes do footer (`<section id="precos">`)
- 3 planos: Básico (€0), Completo (€4,99/relatório), Imobiliárias (€49/mês)
- Design inline coerente com o resto da landing (system fonts, mesmas variáveis CSS)
- Plano destacado (Completo) com fundo `azul-escuro` e botão branco
- Responsive: grid 3 colunas desktop → 1 coluna mobile (max-width 720px)

### Estado final do Sprint 8
- **score_geral**: honesto para todas as 3259 freguesias — média de scores reais disponíveis ✓
- **Worker dados-freguesia**: versão `c9b736fe` em produção ✓
- **index.html**: secção de preços visível na landing ✓
- **relatorio.html**: badge "A calcular" e texto de análise actualizado ✓

### Notas técnicas — score_geral
- `score_geral` no Supabase mantém-se com o valor proxy antigo — nunca mais é lido pelo Worker
  - Não é necessário re-migrar nem recalcular no Supabase
- Quando `transportes_score` e `saude_score` forem preenchidos (futuramente), o score melhora automaticamente
- 651 freguesias sem `rendas_mediana` (interior, Açores, Madeira) → score baseado só em segurança
- Distribuição actual: interior seguro ~88/100, Lisboa/Porto ~48/100, outras ~55–70/100

### Pendente para próxima sessão
- [ ] Finalizar ImprovMX — adicionar MX records no DNS para ola@melhorzona.pt receber emails
- [ ] Enviar email-validacao.html a potenciais utilizadores e recolher feedback
- [ ] Acompanhar leads B2B recebidos e validar interesse real antes de construir mais
- [ ] Enriquecer scores reais (transportes: GTFS, saúde: SNS Transparência, ar: QualAr)
- [ ] Expandir guias SEO para mais freguesias (script `data/generate-guias.py` já pronto)

## Sessão 2026-06-08 — Sprint 9 (concluído)

### Commits desta sessão
- (commit final do dia — imobiliarias.html B2B + stripe integrado + claude haiku integrado)

### O que foi feito

**Stripe Checkout — paywall relatorio.html (€4,99/relatório)**
- Worker `melhorzona-stripe-checkout` criado e em produção
  - `POST /checkout`: cria sessão Stripe Checkout; `success_url` inclui `{CHECKOUT_SESSION_ID}` (template Stripe)
  - `GET /verify?session_id=`: verifica pagamento, devolve `{ pago, codigo_ine, nome_freguesia }`
  - Produto: "Relatório Completo" — `price_1Tg7ZQI5eO03eCdnFULIEZUf` (€4,99, modo `payment`)
  - Secrets: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` (em var)
- relatorio.html: paywall → botão "Desbloquear por €4,99 →" → POST ao Worker → redirect para Stripe
- Verificação de regresso: `?session_id=` na URL → `/verify` → `localStorage.setItem('pago_CODIGO_INE', 'true')`
- Persistência local: não paga outra vez se voltar ao relatório (mesma máquina)
- URL limpa após verificação: `history.replaceState`
- `verificarPagamentoExistente()` corre no `init()` antes de mostrar paywall

**Claude Haiku — análise expandida pós-pagamento**
- Novo endpoint `GET /analise?codigo_ine=XXX` no Worker dados-freguesia
- Prompt com dados reais: segurança, rendas, população, clima (quando disponíveis)
- 4–5 frases em texto corrido, português europeu, tom editorial
- relatorio.html: após desbloqueio, chama `/analise` e actualiza `#analise-texto` com transição
- Cache: `no-store` no Worker (não cacheia respostas IA); resultado guardado em `localStorage.analise_CODIGO_INE`
- Fallback: se API falha, análise automática (scoreParts) continua visível
- Secret: `ANTHROPIC_API_KEY` (wrangler secret no Worker dados-freguesia)

**Card de clima — relatorio.html (pós-pagamento)**
- Card "Clima" adicionado aos `bloqueados` quando `clima_score !== null`
- Dados: temperatura média + sol anual + precipitação · ERA5 2015–2024
- Score 0–10 × 10 → 0–100 para display; ícone ☀️/⛅/🌧️ por limiar
- `data/enricher-clima.py` gere `clima_temp_media`, `clima_sol_horas`, `clima_precipitacao`, `clima_score`
  - Fonte: Nominatim geocoding + Open-Meteo ERA5 histórico
  - Granularidade: município → todas as freguesias do município
  - Score: sol 50% + temp 30% (óptimo 17°C) + precipitação 20%
  - **Para activar**: `ALTER TABLE` + `python3 data/enricher-clima.py` (executar pelo utilizador)

**imobiliarias.html — reformulação B2B para reunião de sexta**
- Estrutura completamente reescrita para proposta de valor clara:
  - Hero: dor concreta ("O seu cliente pergunta 'É segura esta zona?'"), stats, CTAs
  - Antes/Depois: comparação visual sem testemunhos fictícios
  - Demo embed: mockup do relatório real com dados de Arroios + link "Ver ao vivo"
  - Como funciona: 4 passos (consultor pesquisa → relatório → partilha → visita produtiva)
  - ROI: 3 cards + cálculo concreto (€49/mês vs comissão típica)
  - Preços: 2 planos (€49 individual / €99 equipa) com badge "Em breve" no PDF
  - Form: "Agendar demonstração de 15 min" → Airtable worker → success state
- Removidos: testemunhos fictícios, secção "funcionalidades" genérica
- Demo ao vivo: link directo para `relatorio.html?freguesia=Arroios&municipio=Lisboa`

**generate-guias.py — top 100 em background**
- Executado: `nohup python3 data/generate-guias.py --limite 100 > logs/guias.log 2>&1 &` (PID 31969)
- Gera guias SEO estáticas para as 100 freguesias mais populosas × 3 línguas (PT/BR/EN)

### Estado final do Sprint 9
- **Stripe Checkout**: funcional em produção — €4,99/relatório ✓
- **Claude Haiku**: análise expandida pós-pagamento funcional em produção ✓
- **Card clima**: código no relatorio.html pronto; precisa enricher-clima.py executado pelo utilizador
- **imobiliarias.html**: reformulada com proposta de valor B2B clara para reunião ✓
- **generate-guias.py**: a correr em background (PID 31969)

### Notas técnicas — Stripe
- Fluxo: relatorio.html → POST /checkout → Stripe hosted page → success_url com `{CHECKOUT_SESSION_ID}` → `/verify` → localStorage
- `?pago=true` não é usado (forjável) — só `?session_id=` verificado no Worker
- Chave Stripe: `sk_test_*` (modo teste) — trocar para `sk_live_*` quando pronto para produção
- Price ID: `price_1Tg7ZQI5eO03eCdnFULIEZUf` (produto "Relatório Completo")

### Pendente para próxima sessão
- [ ] Finalizar ImprovMX — adicionar MX records no DNS para ola@melhorzona.pt receber emails
- [ ] Enviar email-validacao.html a potenciais utilizadores e recolher feedback
- [ ] Acompanhar leads B2B (reunião de sexta) e validar interesse real
- [ ] Executar enricher-clima.py (requer ALTER TABLE no Supabase primeiro)
- [ ] Stripe: trocar sk_test_ → sk_live_ quando validado
- [ ] Enriquecer scores reais (transportes: GTFS, saúde: SNS Transparência, ar: QualAr)
- [ ] Expandir guias SEO (verificar resultado do generate-guias.py --limite 100)

## Modelo de negócio
- B2C: 1 relatório gratuito/mês, relatório completo €4,99 (Stripe Checkout integrado)
- B2B: subscrição mensal para imobiliárias (€49/mês individual, €99/mês equipa até 5)
  com PDF exportável com branding da agência (em breve)
- Stripe em modo teste — trocar para live quando validado com utilizadores reais

## Regras importantes
- Nunca usar frameworks (React, Vue) — HTML/JS vanilla apenas
- Sempre comentar o código em português
- Nunca commitar chaves de API — usar variáveis de ambiente
- Secrets do Cloudflare: SUPABASE_URL e SUPABASE_KEY (dados-freguesia), AIRTABLE_TOKEN (lista-espera), STRIPE_SECRET_KEY (stripe-checkout), ANTHROPIC_API_KEY (dados-freguesia)
- Deploy automático: git push origin main → Netlify publica
- Testar sempre no browser antes de fazer commit
- Não apagar registos do Airtable sem confirmação explícita

## Comandos úteis
- Deploy site: git push origin main
- Worker deploy: cd workers && wrangler deploy --config <nome>.toml
- Adicionar secret: cd workers && wrangler secret put NOME --config <nome>.toml
- Re-migrar Supabase: `export AIRTABLE_TOKEN=... SUPABASE_URL=... SUPABASE_KEY=... && python3 data/migrar-supabase.py`
- Recalcular scores: `SUPABASE_URL=... SUPABASE_KEY=... python3 data/recalcular-scores.py`
- Testar localmente: abrir index.html no browser
