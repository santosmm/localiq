# Melhor Zona.pt — Comparador de Qualidade de Vida por Freguesia

## O que é
Aplicação web que ajuda pessoas que não conhecem Portugal — sobretudo brasileiros em processo de mudança para Portugal (segmento de 1,5M+ residentes) — a comparar qualidade de vida entre freguesias, usando dados públicos (INE, DGAI). Modelo freemium B2C + canal B2B para imobiliárias.

**Reposicionamento (jun 2026):** o alvo deixou de ser "toda a gente" e passou a ser quem está de fora e não conhece o país. O relatório fala em linguagem humana e concreta, não em scores abstratos.

## URLs em produção
- Site: https://melhorzona.pt
- GitHub: https://github.com/santosmm/localiq
- Worker dados: https://melhorzona-dados-freguesia.matheusmottas.workers.dev
- Worker emails: https://melhorzona-lista-espera.matheusmottas.workers.dev

## Stack
- Frontend: HTML + CSS + JavaScript vanilla (nunca frameworks)
- Base de dados: Supabase (projeto: hkxdmregnsmsbxvpykul, tabela: freguesias, 3.259 registos) — fonte primária, incluindo lista de espera
- Airtable: legado (base appzKGnGUD6pafKKn); lista de espera migrada para Supabase
- Backend: Cloudflare Workers
- Hosting: Netlify (deploy automático via git push)
- Pagamentos: Stripe — INTEGRADO, EM MODO TESTE (ver secção Stripe)
- Email: Brevo — configurado e autenticado (SPF/DKIM/DMARC); ImprovMX encaminha para ola@melhorzona.pt
- Analytics: Microsoft Clarity (Project ID x4cr5fxzap) em todas as páginas; Plausible com trial a terminar (~8 jul) — decisão: por defeito cancelar e consolidar em Clarity + Google Search Console
- IA: API Anthropic (Claude Haiku) gera o texto da página 3 do PDF

## Identidade visual
- Cor principal: azul azulejo #1B4F72
- Azul médio: #2E86C1 / Azul claro: #D6E8F5
- Tipografia títulos: Playfair Display / corpo: Inter
- Tom: editorial português, sóbrio, baseado em dados

## Ficheiros principais
- index.html — landing com hero em tabs ("Ver relatório" / "Comparar duas zonas"), sem formulário no hero
- relatorio.html — relatório por freguesia (redesenhado jun 2026), paywall suave, card de alerta, exportação PDF
- comparar.html — comparação entre 2 freguesias com veredicto dinâmico; pré-preenche Zona A ao vir de um relatório
- guias/ — 300 páginas SEO estáticas (PT/BR/EN) com Schema.org e Open Graph; sitemap de 303 URLs submetido ao GSC (9 jun 2026)
- workers/dados-freguesia.js — Worker que lê do Supabase
- workers/lista-espera.js — Worker que guarda emails
- workers/ine-api.js — integração direta API INE
- workers/ (Stripe) — Worker de checkout com endpoints /pagar-unitario e /pagar-mensal
- data/enricher-ine.py — enriquecimento de rendas INE 2024
- data/migrar-supabase.py — sync completo para o Supabase
- data/generate-guias.py — gerador das páginas SEO (lê freguesias do Supabase)

## Estado atual dos dados
- 3.259 freguesias no Supabase (Nome, Município, Codigo_INE, Populacao)
- Rendas_Mediana: dados reais INE 2024 para ~2.608 freguesias; ~651 sem dados INE (fallback honesto, nunca inventar valor)
- Segurança: scores reais para todas as freguesias via dados DGAI (crime)
- Score_Geral: média de sub-scores reais — decisão de produto: NUNCA usar população como proxy
- Fontes citadas no produto: "INE Censos 2021 · INE Rendas 2024 · DGAI 2023"

## Arquitetura de emails
- Hero da landing: SEM formulário — só pesquisa/tabs
- Relatório: card "Recebe alertas de [freguesia]" entre indicadores livres e bloqueados
- Emails guardados com campo Fonte = "alerta-[nome-freguesia]" (agora em Supabase)

## PDF (relatório pago)
- 4 páginas estilo revista, gerado client-side com html2pdf.js
- Página 3: texto gerado por Claude Haiku — atribuição de IA invisível ao utilizador final: nada de "Claude", "Haiku" ou rótulos de análise editorial
- BUG ABERTO 1: freguesias alternativas na página 4 mostram a renda de outra freguesia (ex.: Arroios) em vez dos dados próprios
- BUG ABERTO 2: rótulo "Análise Editorial" ainda aparece na página 3 — remover

## Stripe
- Dois produtos: pagamento único 4,99€ (/pagar-unitario) e subscrição mensal 9,99€ (/pagar-mensal), via Cloudflare Worker
- EM MODO TESTE — ativação live depende da verificação de negócio no dashboard do Stripe
- Funcionalidades não construídas atrás do paywall mostram "em breve" (nunca remover)

## Modelo de negócio
- B2C: relatório gratuito com indicadores base; relatório completo (PDF 4 págs) por 4,99€
- B2C recorrente: subscrição 9,99€/mês
- B2B: subscrição para imobiliárias (49-99€/mês); licenças enterprise para redes/franchises (800-1.500€/mês)
- Afiliados (planeado): links Imovirtual/Idealista via CJ Affiliate

## Estado de aquisição (jul 2026 — leitura honesta)
- Tráfego real ≈ zero: 6 visitantes / 7 pageviews entre 10 jun e 3 jul, 100% direct, zero visitas orgânicas às /guias/
- Cidades registadas (Vancouver, Amesterdão, Milão) + 7s de duração → provavelmente bots
- SEO ainda não posicionado (normal em domínio novo <2 meses) — falta VERIFICAR INDEXAÇÃO no GSC
- Nenhum canal ativo ligado: próximo passo é Meta Ads €5/dia (segmento brasileiro) + outreach B2B

## SESSÃO 3 JUL 2026 — ONDE FICÁMOS (retomar aqui)
1. Copy SEO das guias foi revista e validada inline (títulos 60-66c, descrições 124-154c, scores baixos removidos do snippet, custo T2, gancho de intenção)
2. PENDENTE: regenerar as ~300 páginas com `python3 data/generate-guias.py --supabase ...` — precisa de SUPABASE_URL + SUPABASE_KEY como env vars
3. DECISÃO EM ABERTO: testar primeiro se a chave `anon` chega para a geração (só leitura) em vez da `service_role` — princípio do privilégio mínimo
4. REGRA: a chave NUNCA é colada no chat nem escrita inline no comando — usar `export SUPABASE_KEY="$(pbpaste)"` num terminal fora da sessão
5. Depois da regeneração: Claude Code valida output → git diff → commit + push
6. A seguir (por ordem): verificar indexação das 303 URLs no GSC → bugs do PDF → Stripe live → Meta Ads → decidir Plausible (trial acaba ~8 jul)
7. Pergunta em aberto de estratégia: resultado da reunião B2B de 9 jun ainda não foi partilhado nesta conversa

## Segurança e credenciais
- Nunca commitar chaves de API — usar variáveis de ambiente (Workers: secrets via wrangler)
- Nunca colar chaves em chats/prompts — histórico: tokens Airtable, Brevo e Anthropic foram expostos em sessões passadas e tiveram de ser rodados
- Ao rodar uma chave, atualizar imediatamente os secrets nos Workers correspondentes
- Preferir sempre a chave mais fraca que faz o trabalho (anon > service_role quando só há leitura)

## Regras de desenvolvimento
- Nunca usar frameworks (React, Vue) — HTML/JS vanilla apenas
- Comentários sempre em português
- Testar sempre antes de fazer commit
- Deploy automático: git push origin main → Netlify publica

## Regra de comunicação
Sempre que propuseres uma ação técnica — comando, configuração, registo DNS, alteração de código — explica primeiro o PORQUÊ em linguagem simples:
- O que este passo faz
- O que acontece se não for feito
- Qual o risco ou consequência
Só depois mostra o COMO (o comando ou valor concreto).
