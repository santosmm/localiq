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

## Ficheiros existentes
- index.html — landing page com formulário de lista espera
- relatorio.html — página de relatório por freguesia
  (dados de exemplo, paywall suave nos 3 últimos indicadores)
- assets/css/ — estilos
- assets/js/ — scripts
- assets/images/ — imagens
- workers/lista-espera.js — Cloudflare Worker para formulário
- workers/wrangler.toml — configuração Cloudflare
- data/ — scripts de processamento dados INE (vazio)

## Airtable
- Base: Melhor Zona (appzKGnGUD6pafKKn)
- Tabela: Lista de Espera (tblB9N9UdJDgIHE7B)
- Campos: Email, Data, Fonte, Notas
- Já tem inscritos reais — não apagar registos sem confirmar

## Fluxo actual do utilizador
1. Chega à landing page (index.html)
2. Deixa email no formulário → vai para Airtable via Worker
3. [A CONSTRUIR] Pesquisa freguesia → vai para relatorio.html
4. Vê 3 indicadores gratuitos
5. Clica "Desbloquear por 4,99€" → [A LIGAR] Stripe

## Próximos passos (Sprint 1 em curso)
- [x] Ligar barra de pesquisa da home ao relatorio.html
- [x] Ler parâmetro ?freguesia= no URL do relatório
- [x] Pills de freguesias populares na home
- [ ] Construir comparar.html (comparação entre 2 freguesias)
- [ ] Integrar Stripe para pagamento de 4,99€
- [ ] Carregar dados reais do INE/IPMA no Airtable

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
