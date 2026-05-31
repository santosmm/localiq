# Comparador de Habitação Portugal (Localiq)

## O que é este projeto
Aplicação web que permite a famílias portuguesas comparar 
a qualidade de vida entre freguesias usando dados públicos 
do INE, ACSS, IPMA e DGEEC. Modelo freemium com canal B2B 
para imobiliárias.

## Stack
- Frontend: HTML + CSS + JavaScript vanilla
- Base de dados: Airtable (API REST)
- Backend: Cloudflare Workers (funções serverless)
- Hosting: Netlify
- Pagamentos: Stripe
- Email: Brevo
- IA (resumos): Claude API modelo Haiku
- Controlo versões: GitHub

## Estrutura de ficheiros
/index.html          → landing page + pesquisa
/relatorio.html      → página de relatório por freguesia
/comparar.html       → comparação lado a lado
/assets/             → CSS, JS, imagens
/workers/            → funções Cloudflare Workers
/data/               → scripts de processamento dados INE
/CLAUDE.md           → este ficheiro

## Dados públicos usados
- INE Censos 2021: demografia por freguesia
- INE Arrendamento: preço mediano €/m² por tipologia
- ACSS: cobertura médico de família por ACES
- QualAr/APA: índice qualidade do ar por município
- DGEEC: taxa de sucesso escolar por agrupamento
- GTFS dados.gov: cobertura transportes públicos

## Regras importantes
- Nunca usar frameworks (React, Vue) — HTML/JS vanilla apenas
- Sempre comentar o código em português
- Cada função faz uma coisa só
- Nunca commitar chaves de API — usar variáveis de ambiente
- Testar sempre no browser antes de fazer commit

## Comandos úteis
- Deploy: git push origin main (Netlify faz deploy automático)
- Testar localmente: abrir index.html no browser
