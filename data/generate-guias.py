#!/usr/bin/env python3
"""
Gerador de guias estáticos de freguesia — PT · BR · EN
Executar da raiz do projecto: python3 data/generate-guias.py
Gera /guias/pt/*.html, /guias/br/*.html, /guias/en/*.html (30 ficheiros)
"""
import os, urllib.parse, urllib.request, json, re, argparse, unicodedata

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────────────────────
# AUXILIARES
# ─────────────────────────────────────────────────────────────────────────────

def calc_arr(renda):
    return max(0, min(100, round((20 - renda) / 15 * 100)))

def arr_badge(score, lang):
    t = {'pt': ('Acessível','Médio','Caro'),
         'br': ('Acessível','Moderado','Caro'),
         'en': ('Affordable','Moderate','Expensive')}[lang]
    if score >= 60: return 'bom',   t[0]
    if score >= 40: return 'medio', t[1]
    return 'fraco', t[2]

def seg_badge(score, lang):
    t = {'pt': ('Muito seguro','Médio','Atenção'),
         'br': ('Muito seguro','Regular','Atenção'),
         'en': ('Very safe','Average','Caution')}[lang]
    if score >= 60: return 'bom',   t[0]
    if score >= 40: return 'medio', t[1]
    return 'fraco', t[2]

def score_badge(score, lang):
    if score >= 88: return 'bom',   {'pt':'Excelente',     'br':'Excelente',     'en':'Excellent'}[lang]
    if score >= 65: return 'bom',   {'pt':'Muito bom',     'br':'Muito bom',     'en':'Very good'}[lang]
    if score >= 50: return 'medio', {'pt':'Bom',           'br':'Bom',           'en':'Good'}[lang]
    return 'medio',                 {'pt':'Em actualização','br':'Em actualização','en':'Updating'}[lang]

def n(v):
    """float → string sem trailing zeros desnecessários (ex: 41.9, 10.2)"""
    return f'{v:g}'

def r(v, lang):
    """Formata renda: PT/BR usa vírgula, EN usa ponto"""
    s = f'{v:.2f}'
    return s if lang == 'en' else s.replace('.', ',')

def sv(v, lang):
    """Formata seg_val: PT/BR vírgula, EN ponto"""
    s = f'{v:.1f}'
    return s if lang == 'en' else s.replace('.', ',')

def pop(v, lang):
    s = f'{v:,}'
    return s if lang == 'en' else s.replace(',', ' ')

def t2(renda, lang):
    t = round(renda * 70)
    s = f'{t:,}'
    if lang == 'en': return f'€{s}'
    return f'{s.replace(",", chr(160))} €'

def esc(s):
    """Escapa aspas para JSON dentro de atributos HTML"""
    return s.replace('"', '&quot;')

def uq(s):
    return urllib.parse.quote(s, safe='')

def slugify(s):
    """Converte nome de freguesia para slug URL"""
    s = unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode()
    s = s.lower()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    return re.sub(r'[\s_-]+', '-', s).strip('-')

def calcular_score(row):
    """Equivalente ao calcularScoreReal() do Worker dados-freguesia.js"""
    scores = []
    if row.get('seguranca_score')   is not None: scores.append(float(row['seguranca_score']))
    if row.get('transportes_score') is not None: scores.append(float(row['transportes_score']))
    if row.get('saude_score')       is not None: scores.append(float(row['saude_score']))
    if row.get('ensino_score')      is not None: scores.append(float(row['ensino_score']))
    if row.get('rendas_mediana') is not None:
        ar = max(0.0, min(10.0, 10.0 - float(row['rendas_mediana']) * 0.3))
        scores.append(ar)
    elif row.get('arrendamento_score') is not None:
        scores.append(float(row['arrendamento_score']))
    if not scores:
        return 50
    return min(100, round(sum(scores) / len(scores) * 10))

def auto_content(p):
    """Gera conteúdo editorial automático para freguesias sem texto curado"""
    nome      = p['nome']
    municipio = p['municipio']
    pop_v     = p['pop']
    renda     = p['renda']
    seg       = p['seg']
    seg_val   = p['seg_val']
    score     = p['score']
    estimada  = p.get('renda_estimada', False)

    pop_pt = pop(pop_v, 'pt')
    pop_en = pop(pop_v, 'en')
    rv_pt  = f'{renda:.2f}'.replace('.', ',')
    rv_en  = f'{renda:.2f}'
    sv_pt  = f'{seg_val:.1f}'.replace('.', ',')
    sv_en  = f'{seg_val:.1f}'

    if pop_v > 50000:   badge='Zona urbana';        p_pt='zona urbana';        p_br='bairro urbano';      p_en='urban area'
    elif pop_v > 15000: badge='Zona consolidada';   p_pt='zona consolidada';   p_br='bairro consolidado'; p_en='established neighbourhood'
    elif pop_v > 5000:  badge='Zona suburbana';     p_pt='zona suburbana';     p_br='bairro suburbano';   p_en='suburban area'
    elif pop_v > 1000:  badge='Zona semi-urbana';   p_pt='zona semi-urbana';   p_br='área semi-urbana';   p_en='semi-urban area'
    else:               badge='Zona rural';         p_pt='zona rural';         p_br='área rural';         p_en='rural area'

    if estimada:
        rent_pt = f'Dados de arrendamento em {nome} em actualização. Referência nacional: €10,50/m² (INE 2024).'
        rent_br = f'Dados de aluguel em {nome} em atualização. Média nacional portuguesa: €10,50/m² (INE 2024).'
        rent_en = f'Rental data for {nome} is being compiled. National reference: €10.50/m² (INE 2024).'
    else:
        diff = renda - 10.50
        if diff > 3:
            rent_pt = f'Com rendas de {rv_pt} €/m², {nome} está acima da média nacional (€10,50/m²), reflexo da procura elevada.'
            rent_br = f'Com {rv_pt} €/m², o aluguel em {nome} está acima da média nacional portuguesa de €10,50/m².'
            rent_en = f'At €{rv_en}/m², rents in {nome} are above the Portuguese national average of €10.50/m².'
        elif diff > 0:
            rent_pt = f'As rendas em {nome} ({rv_pt} €/m²) estão ligeiramente acima da média nacional de €10,50/m².'
            rent_br = f'O aluguel em {nome} ({rv_pt} €/m²) está levemente acima da média nacional portuguesa.'
            rent_en = f'Rents in {nome} (€{rv_en}/m²) are slightly above the Portuguese national average of €10.50/m².'
        elif diff > -2:
            rent_pt = f'As rendas em {nome} ({rv_pt} €/m²) estão próximas da média nacional de €10,50/m².'
            rent_br = f'O aluguel em {nome} ({rv_pt} €/m²) está próximo da média nacional portuguesa de €10,50/m².'
            rent_en = f'Rents in {nome} (€{rv_en}/m²) are close to the Portuguese national average of €10.50/m².'
        else:
            rent_pt = f'Com {rv_pt} €/m², {nome} oferece rendas abaixo da média nacional (€10,50/m²) — uma opção mais acessível em {municipio}.'
            rent_br = f'Com {rv_pt} €/m², {nome} está abaixo da média nacional (€10,50/m²) — uma das opções mais acessíveis desta região.'
            rent_en = f'At €{rv_en}/m², {nome} is below the national average (€10.50/m²) — a more affordable option in {municipio}.'

    if seg_val < 25:
        safe_pt = f'O município de {municipio} regista criminalidade baixa: {sv_pt} crimes/1 000 hab (INE 2023), bem abaixo da média nacional (~35).'
        safe_br = f'{municipio} tem taxa de criminalidade baixa: {sv_pt} crimes/1.000 hab (INE 2023), abaixo da média nacional portuguesa.'
        safe_en = f'{municipio} has a low crime rate: {sv_en} crimes per 1,000 residents (INE 2023), well below the national average of ~35.'
    elif seg_val < 40:
        safe_pt = f'O município de {municipio} tem {sv_pt} crimes/1 000 hab (INE 2023), abaixo da média nacional de ~35.'
        safe_br = f'{municipio} registou {sv_pt} crimes/1.000 hab (INE 2023), abaixo da média nacional portuguesa.'
        safe_en = f'{municipio} recorded {sv_en} crimes per 1,000 inhabitants (INE 2023), below the national average of ~35.'
    elif seg_val < 55:
        safe_pt = f'O município de {municipio} tem {sv_pt} crimes/1 000 hab (INE 2023), próximo da média nacional de ~35.'
        safe_br = f'{municipio} tem {sv_pt} crimes/1.000 hab (INE 2023), próximo da média nacional portuguesa.'
        safe_en = f'{municipio} has {sv_en} crimes per 1,000 residents (INE 2023), close to the national average of ~35.'
    else:
        safe_pt = f'O município de {municipio} tem criminalidade acima da média nacional: {sv_pt} crimes/1 000 hab (INE 2023, média ~35).'
        safe_br = f'{municipio} tem {sv_pt} crimes/1.000 hab (INE 2023), acima da média nacional portuguesa de ~35.'
        safe_en = f'{municipio} has a higher crime rate of {sv_en} crimes per 1,000 residents (INE 2023), above the national average of ~35.'

    life_pt = f'Com {pop_pt} residentes, {nome} é uma {p_pt} de {municipio}. O Índice de Qualidade de Vida Melhor Zona é de {score}/100, calculado com dados INE.'
    life_br = f'Com {pop_pt} residentes, {nome} é um {p_br} de {municipio}. O Índice de Qualidade de Vida Melhor Zona é de {score}/100, baseado em dados públicos INE.'
    life_en = f'With {pop_en} residents, {nome} is a {p_en} in {municipio}. The Melhor Zona quality of life score is {score}/100, based on real INE data.'

    if score >= 65:
        adv_pt = 'Uma excelente opção para famílias e profissionais que procuram qualidade de vida acima da média.'
        adv_br = 'Excelente opção para quem busca qualidade de vida acima da média em Portugal.'
        adv_en = 'An excellent choice for families and professionals seeking above-average quality of life.'
    elif score >= 45:
        adv_pt = 'Uma escolha sólida com boa relação qualidade/custo dentro do município.'
        adv_br = 'Uma boa opção com equilíbrio entre custo e qualidade de vida.'
        adv_en = 'A solid option with a good quality-to-cost ratio within the municipality.'
    else:
        adv_pt = f'Recomendamos comparar com outras zonas de {municipio} antes de decidir.'
        adv_br = f'Recomendamos comparar com outras áreas de {municipio} antes de decidir.'
        adv_en = f'We recommend comparing with other areas of {municipio} before deciding.'

    return dict(
        pt=dict(
            meta=f'{nome}, {municipio}: renda mediana {rv_pt} €/m², segurança {seg}/100, qualidade de vida {score}/100. Dados INE 2024.',
            badge=badge,
            ctx_rent=rent_pt, ctx_safe=safe_pt, ctx_life=life_pt,
            faq3_q=f'Vale a pena viver em {nome}, {municipio}?',
            faq3_a=f'{nome} tem score de {score}/100, rendas de {rv_pt} €/m² e segurança de {seg}/100. {adv_pt}',
        ),
        br=dict(
            meta=f'Morar em {nome}, {municipio}: aluguel {rv_pt} €/m², segurança {seg}/100, qualidade {score}/100. Dados INE para brasileiros.',
            badge=badge,
            intro=f'Se está a pensar em morar em {municipio}, {nome} é uma opção com qualidade de vida de {score}/100.',
            ctx_rent=rent_br, ctx_safe=safe_br, ctx_life=life_br,
            faq3_q=f'{nome} em {municipio} é boa opção para morar?',
            faq3_a=f'{nome} tem score de {score}/100, aluguel {rv_pt} €/m² e segurança {seg}/100. {adv_br}',
        ),
        en=dict(
            meta=f'Living in {nome}, {municipio}: rent €{rv_en}/m², safety {seg}/100, quality of life {score}/100. Real INE 2024 data.',
            badge=badge,
            ctx_rent=rent_en, ctx_safe=safe_en, ctx_life=life_en,
            faq3_q=f'Is {nome} a good place to live in {municipio}?',
            faq3_a=f'{nome} scores {score}/100 overall, median rent €{rv_en}/m², safety {seg}/100. {adv_en}',
        ),
    )

def fetch_supabase(supabase_url, supabase_key, limit=100):
    """Busca top N freguesias por população no Supabase"""
    cols = 'nome,municipio,populacao,codigo_ine,seguranca_score,seguranca_valor,rendas_mediana,arrendamento_score'
    url  = (f'{supabase_url}/rest/v1/freguesias'
            f'?select={cols}&order=populacao.desc.nullslast&limit={limit}')
    req = urllib.request.Request(url, headers={
        'apikey':        supabase_key,
        'Authorization': f'Bearer {supabase_key}',
    })
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode())

def build_parish_from_row(row, manual=None):
    """Constrói dict de paróquia a partir de linha do Supabase"""
    nome      = row.get('nome')      or ''
    municipio = row.get('municipio') or ''
    pop_v     = int(row.get('populacao') or 0)
    seg_raw   = row.get('seguranca_score')
    segv_raw  = row.get('seguranca_valor')
    renda_raw = row.get('rendas_mediana')

    seg             = round(float(seg_raw)  * 10) if seg_raw  is not None else 50
    seg_val         = float(segv_raw)              if segv_raw is not None else 35.0
    renda           = float(renda_raw)             if renda_raw is not None else 10.50
    renda_estimada  = renda_raw is None

    score = calcular_score(row)

    p = dict(
        slug=slugify(nome), nome=nome, municipio=municipio,
        pop=pop_v, score=score, seg=seg, seg_val=seg_val,
        renda=renda, renda_estimada=renda_estimada,
        qf=nome, qm=municipio,
    )
    content = manual or auto_content(p)
    p['pt'] = content['pt']
    p['br'] = content['br']
    p['en'] = content['en']
    return p

# ─────────────────────────────────────────────────────────────────────────────
# DADOS DAS 10 FREGUESIAS
# ─────────────────────────────────────────────────────────────────────────────

PARISHES = [
  dict(
    slug='arroios', nome='Arroios', municipio='Lisboa',
    pop=33302, score=67, seg=45, seg_val=41.9, renda=15.93,
    qf='Arroios', qm='Lisboa',
    pt=dict(
      meta='Arroios, Lisboa: renda mediana 15,93 €/m², segurança 45/100, qualidade de vida 67/100. Dados reais INE 2024 para quem quer arrendar em Arroios.',
      badge='Zona urbana consolidada',
      ctx_rent='Arroios reflecte a pressão do mercado imobiliário de Lisboa — uma das poucas freguesias centrais com identidade de bairro preservada e população residente expressiva.',
      ctx_safe='A criminalidade em Lisboa concentra-se sobretudo em zonas turísticas e de elevado trânsito nocturno. A Mouraria e o Intendente, parte de Arroios, beneficiaram de requalificação urbana na última década.',
      ctx_life='Bem servida de metro (linhas Verde e Amarela, estações Arroios, Anjos e Intendente), tem acesso fácil ao Baixa-Chiado. Destaca-se pela diversidade cultural, restauração acessível e mercados de bairro.',
      faq3_q='Vale a pena viver em Arroios?',
      faq3_a='Arroios tem um score de qualidade de vida de 67/100. A localização central, as boas ligações de metro e a vida de bairro são os principais trunfos. O custo de arrendamento elevado (acima de 15 €/m²) é o principal ponto negativo.',
    ),
    br=dict(
      meta='Pensando em morar em Arroios, Lisboa? Aluguel médio de 15,93 €/m² (em torno de €1.115/mês num T2), segurança 45/100. Dados reais INE para brasileiros que vão para Portugal.',
      badge='Bairro consolidado',
      intro='Se está a pensar mudar para Portugal, Arroios é uma das zonas mais procuradas por brasileiros em Lisboa pela centralidade e acesso a transportes.',
      ctx_rent='Para quem vem de São Paulo ou Rio de Janeiro, o preço é alto pelo padrão português mas razoável para morar no centro de uma capital europeia com metro na porta.',
      ctx_safe='Para quem vem do Brasil, a sensação de segurança em Arroios tende a ser muito melhor do que em cidades brasileiras de grande porte, mesmo com pontuação de 45/100.',
      ctx_life='Arroios tem uma das maiores comunidades brasileiras de Lisboa, com restaurantes, salões de beleza e lojas com produtos familiares na zona do Intendente e da Mouraria.',
      faq3_q='Arroios é um bom bairro para brasileiro morar em Lisboa?',
      faq3_a='Sim. Arroios tem comunidade brasileira expressiva, metrô na porta (linhas Verde e Amarela) e restauração mais acessível do que Chiado ou Príncipe Real. Pontuação geral de 67/100.',
    ),
    en=dict(
      meta='Thinking of living in Arroios, Lisbon? Median rent €15.93/m² (~€1,115/month for a 2-bed), safety 45/100, quality of life 67/100. Real INE data for expats moving to Lisbon.',
      badge='Established neighbourhood',
      ctx_rent='Arroios typically runs 15–20% below Chiado or Príncipe Real while offering a similar central location and direct metro access on the Green and Yellow lines.',
      ctx_safe='Violent crime is rare; the main concern is opportunistic theft near tourist areas around Rossio and Martim Moniz. Day-to-day residential life is calm.',
      ctx_life='One of Lisbon\'s most multicultural neighbourhoods, with a wide range of affordable restaurants, independent shops and a well-established expat community. 15 minutes\' walk to Baixa-Chiado.',
      faq3_q='Is Arroios a good neighbourhood for expats in Lisbon?',
      faq3_a='Yes. Arroios is multicultural, central, well served by metro (Green and Yellow lines) and more affordable than Chiado or Príncipe Real. Quality of life score: 67/100.',
    ),
  ),
  dict(
    slug='cascais-e-estoril', nome='Cascais e Estoril', municipio='Cascais',
    pop=64192, score=100, seg=50, seg_val=39.9, renda=15.31,
    qf='Cascais e Estoril', qm='Cascais',
    pt=dict(
      meta='Cascais e Estoril: renda mediana 15,31 €/m², segurança 50/100, qualidade de vida 100/100. Dados INE 2024. Tudo o que precisa saber antes de arrendar em Cascais.',
      badge='Zona premium costeira',
      ctx_rent='Cascais e Estoril é um dos municípios mais valorizados do país, com forte procura nacional e internacional. A Linha de Cascais garante ligação a Lisboa em 40 minutos.',
      ctx_safe='Cascais é consistentemente apontada como uma das cidades mais seguras de Portugal, com forte presença residencial estável e baixa criminalidade urbana.',
      ctx_life='A Linha de Cascais (comboio) liga o centro de Lisboa em cerca de 40 minutos. Praias, campos de golfe, o Casino Estoril e uma comunidade cosmopolita de expatriados fazem desta zona uma das mais procuradas do país.',
      faq3_q='Vale a pena viver em Cascais e Estoril?',
      faq3_a='Cascais e Estoril tem o score máximo de 100/100 na plataforma Melhor Zona. É uma escolha excelente para quem quer qualidade de vida elevada junto ao mar com acesso fácil a Lisboa. O custo é alto mas justificado pela oferta.',
    ),
    br=dict(
      meta='Pensando em morar em Cascais e Estoril? Aluguel médio de 15,31 €/m² (~€1.072/mês num T2), segurança 50/100. Dados reais INE. Guia para brasileiros em Portugal.',
      badge='Zona premium costeira',
      intro='Cascais e Estoril é uma das escolhas favoritas de brasileiros que procuram qualidade de vida superior, praia e fácil acesso de trem a Lisboa.',
      ctx_rent='O aluguel é elevado mas comparável a bairros nobres de São Paulo, com a vantagem de incluir praia, segurança e acesso rápido de trem ao centro de Lisboa.',
      ctx_safe='É considerada uma das cidades mais seguras de Portugal, com índice de criminalidade muito baixo e ambiente tranquilo — ideal para famílias e para quem vem com crianças.',
      ctx_life='Tem uma comunidade internacional expressiva, escolas internacionais nas proximidades e uma vida social activa tanto no verão como no inverno. O trem para Lisboa custa cerca de €2.',
      faq3_q='Cascais e Estoril é boa opção para brasileiro morar em Portugal?',
      faq3_a='Sim, é uma das melhores. Praias excelentes, segurança alta, trem para Lisboa e comunidade internacional. O aluguel é caro mas a qualidade de vida justifica. Score máximo: 100/100.',
    ),
    en=dict(
      meta='Living in Cascais and Estoril, Portugal: median rent €15.31/m² (~€1,072/month for a 2-bed), safety 50/100, quality of life 100/100. Real INE 2024 data for expats.',
      badge='Premium coastal area',
      ctx_rent='Cascais has long attracted international residents. The premium reflects the coastal lifestyle, quality infrastructure and the 40-minute train connection to central Lisbon.',
      ctx_safe='Cascais is consistently rated one of Portugal\'s safest municipalities — a key factor for families and expats considering relocation from abroad.',
      ctx_life='A cosmopolitan town with Atlantic beaches, golf courses, the famous Estoril Casino and a well-established expat community. The Cascais Line train makes Lisbon easily reachable for work.',
      faq3_q='Is Cascais and Estoril a good place to live as an expat?',
      faq3_a='Yes — one of Portugal\'s best. Cascais scores 100/100 overall. It combines beaches, safety, international community and a 40-minute train link to Lisbon. Rents are high but the quality of life is exceptional.',
    ),
  ),
  dict(
    slug='lumiar', nome='Lumiar', municipio='Lisboa',
    pop=46334, score=93, seg=45, seg_val=41.9, renda=15.93,
    qf='Lumiar', qm='Lisboa',
    pt=dict(
      meta='Lumiar, Lisboa: renda mediana 15,93 €/m², segurança 45/100, qualidade de vida 93/100. Dados INE 2024. Zona residencial do norte de Lisboa para famílias.',
      badge='Zona residencial consolidada',
      ctx_rent='Lumiar é uma das opções mais residenciais do norte de Lisboa, com rendas iguais às do centro mas numa zona mais tranquila, com apartamentos tipicamente maiores.',
      ctx_safe='Partilha os dados de criminalidade do município de Lisboa. Sendo uma zona predominantemente residencial, tem menor exposição a crimes de oportunidade ligados ao turismo.',
      ctx_life='Próxima da Universidade Lusófona e do Hospital de Santa Maria. Bem servida de metro e autocarros, com comércio local desenvolvido e bom acesso ao Aeroporto de Lisboa.',
      faq3_q='Vale a pena viver em Lumiar?',
      faq3_a='Lumiar tem 93/100 de qualidade de vida. É ideal para famílias que querem Lisboa com mais tranquilidade e apartamentos maiores. As rendas são equivalentes ao centro mas o ambiente é mais residencial.',
    ),
    br=dict(
      meta='Pensando em morar em Lumiar, Lisboa? Aluguel médio de 15,93 €/m² (~€1.115/mês num T2), segurança 45/100, qualidade de vida 93/100. Guia para brasileiros.',
      badge='Zona residencial consolidada',
      intro='Lumiar é uma escolha popular para famílias brasileiras que querem Lisboa mas preferem uma zona mais residencial e tranquila do que o centro histórico.',
      ctx_rent='O preço é semelhante ao das zonas centrais, mas Lumiar oferece apartamentos maiores, mais silêncio e melhor qualidade de vida para quem tem filhos ou trabalha em casa.',
      ctx_safe='Zona residencial com baixa movimentação turística. A percepção de segurança no dia a dia é boa, com ruas tranquilas e vizinhança estável.',
      ctx_life='Boa ligação ao centro de Lisboa por metro. Tem supermercados, parques, escolas públicas de qualidade e é uma das zonas mais próximas do aeroporto de Lisboa.',
      faq3_q='Lumiar é boa opção para família brasileira em Lisboa?',
      faq3_a='Sim. Score de 93/100, zona residencial tranquila, metro para o centro e próximo do aeroporto. Bom para famílias com crianças que preferem apartamentos maiores a preço equivalente ao centro.',
    ),
    en=dict(
      meta='Living in Lumiar, Lisbon: median rent €15.93/m² (~€1,115/month for a 2-bed), safety 45/100, quality of life 93/100. Real INE 2024 data for expats moving to north Lisbon.',
      badge='Established residential area',
      ctx_rent='Lumiar offers comparable rents to central Lisbon with more residential character and typically larger apartments — a trade-off that suits families and professionals working from home.',
      ctx_safe='As a residential district with less tourist traffic than central Lisbon, day-to-day safety perception tends to be better than in the historic centre.',
      ctx_life='Well connected by metro to the city centre and close to Lisbon Airport. Home to Universidade Lusófona and Hospital de Santa Maria — a practical choice for healthcare workers.',
      faq3_q='Is Lumiar a good area for expats in Lisbon?',
      faq3_a='Yes. Lumiar scores 93/100 overall. It\'s ideal for families or professionals who want Lisbon with a quieter pace, larger apartments and easy metro access to the city centre.',
    ),
  ),
  dict(
    slug='belem', nome='Belém', municipio='Lisboa',
    pop=16546, score=33, seg=45, seg_val=41.9, renda=15.93,
    qf='Belém', qm='Lisboa',
    pt=dict(
      meta='Belém, Lisboa: renda mediana 15,93 €/m², segurança 45/100. Torre de Belém, Mosteiro dos Jerónimos e MAAT. Dados INE 2024 para quem quer arrendar em Belém.',
      badge='Zona histórica e cultural',
      ctx_rent='Belém é uma das freguesias mais icónicas e mais pequenas de Lisboa, com apenas 16 546 residentes. A procura supera largamente a oferta, mantendo as rendas ao nível das zonas centrais.',
      ctx_safe='Os dados de criminalidade reflectem o município de Lisboa. Belém tem uma componente turística muito activa durante o dia, mas é essencialmente uma zona residencial tranquila à noite.',
      ctx_life='Sede da Torre de Belém, do Mosteiro dos Jerónimos, do MAAT e dos famosos Pastéis de Belém. A freguesia fica junto ao Tejo e tem eléctrico e autocarros para o centro de Lisboa.',
      faq3_q='Vale a pena viver em Belém, Lisboa?',
      faq3_a='Belém é única pela localização histórica junto ao Tejo e pela proximidade a monumentos Património da Humanidade. O score de 33/100 reflecte a pequena dimensão da freguesia (16 546 hab.), não a qualidade — os dados completos estão em actualização.',
    ),
    br=dict(
      meta='Pensando em morar em Belém, Lisboa? Renda mediana 15,93 €/m², o bairro dos Pastéis de Belém, da Torre e do Mosteiro dos Jerónimos. Dados INE 2024.',
      badge='Zona histórica e cultural',
      intro='Belém é o bairro de Lisboa onde ficam os maiores cartões-postais da cidade — morar aqui coloca você a 5 minutos dos Pastéis de Belém e do Tejo.',
      ctx_rent='O aluguel é caro para uma zona pequena e muito turística. Mas a localização junto ao rio, os monumentos e o ambiente tranquilo durante a semana fazem de Belém uma escolha especial.',
      ctx_safe='Zona turística mas com comunidade local estável. O ambiente é calmo durante a semana e mais movimentado ao fim de semana pelo turismo.',
      ctx_life='Tem eléctrico, autocarro e estação de comboio (Belém). Boa opção para quem quer qualidade de vida junto ao rio, fora da intensidade do centro histórico.',
      faq3_q='Belém é boa opção para morar em Lisboa?',
      faq3_a='Belém é única pela localização histórica e o ambiente ribeirinho. O score de 33/100 é provisório — baseado no tamanho da freguesia, não na qualidade de vida real. Para quem pode pagar, é uma das zonas mais especiais de Lisboa.',
    ),
    en=dict(
      meta='Living in Belém, Lisbon: median rent €15.93/m², home to the Tower of Belém, Jerónimos Monastery and MAAT. Real INE 2024 data for expats considering Belém.',
      badge='Historic & cultural area',
      ctx_rent='Belém is Lisbon\'s most iconic riverside neighbourhood and rents reflect that desirability. Supply is limited in this small parish of just 16,546 residents, keeping prices at central Lisbon levels.',
      ctx_safe='A predominantly residential area with significant tourist traffic during the day. After hours it becomes quiet and local, with a stable community of long-term residents.',
      ctx_life='Home to the Tower of Belém, Jerónimos Monastery, the MAAT contemporary art museum and the famous Pastéis de Belém bakery. Tram and bus links connect to central Lisbon.',
      faq3_q='Is Belém a good place to live in Lisbon?',
      faq3_a='Belém is unique for its UNESCO heritage setting on the Tagus riverfront. The overall score of 33/100 is a provisional proxy based on population size, not quality of life — full data is being compiled. For those who can afford it, it\'s one of Lisbon\'s most special areas.',
    ),
  ),
  dict(
    slug='sintra', nome='Sintra', municipio='Sintra',
    pop=29896, score=60, seg=41, seg_val=43.8, renda=10.20,
    qf='Sintra', qm='Sintra',
    pt=dict(
      meta='Sintra: renda mediana 10,20 €/m², segurança 41/100, qualidade de vida 60/100. Dados INE 2024. Patrimônio UNESCO a 40 minutos de Lisboa de comboio.',
      badge='Vila histórica e acessível',
      ctx_rent='Sintra destaca-se como uma das zonas mais acessíveis desta lista, com renda mediana de 10,20 €/m². A ligação ferroviária directa a Lisboa compensa a distância de cerca de 30 km.',
      ctx_safe='O município de Sintra tem uma taxa de criminalidade ligeiramente acima da média nacional, reflectindo o elevado fluxo turístico. A vida residencial quotidiana é tranquila e segura.',
      ctx_life='Classificada como Paisagem Cultural por UNESCO, a vila histórica tem palácios, quintas e natureza a poucos passos de casa. O comboio para Lisboa Rossio demora cerca de 40 minutos.',
      faq3_q='Vale a pena viver em Sintra?',
      faq3_a='Sintra tem 60/100 de qualidade de vida e é uma das opções mais acessíveis desta lista a 10,20 €/m². Ideal para quem quer qualidade de vida, natureza e Património UNESCO sem abdicar da proximidade a Lisboa.',
    ),
    br=dict(
      meta='Pensando em morar em Sintra? Aluguel médio de 10,20 €/m² (~€714/mês num T2), segurança 41/100. Patrimônio UNESCO a 40 minutos de Lisboa de trem. Guia para brasileiros.',
      badge='Vila histórica e acessível',
      intro='Sintra é o destino favorito dos brasileiros que visitam Lisboa — e morar aqui dá para perceber porque tantos acabam ficando de vez.',
      ctx_rent='O aluguel em Sintra é muito mais acessível do que em Lisboa. Um T2 fica em torno de €714/mês, o que abre possibilidades para quem está a construir a vida em Portugal.',
      ctx_safe='Cidade turística com criminalidade ligeiramente acima da média portuguesa, mas muito tranquila para os residentes. O ambiente quotidiano é seguro e relaxado.',
      ctx_life='Trem directo para Lisboa Rossio em 40 minutos. Sintra tem mercados, restaurantes e uma comunidade crescente de famílias que trocaram Lisboa pelo campo com natureza e palácio à porta.',
      faq3_q='Sintra é boa opção para brasileiro morar perto de Lisboa?',
      faq3_a='Sim. Sintra tem aluguel acessível (€714/mês num T2), Patrimônio UNESCO, natureza e trem para Lisboa em 40 minutos. Score de 60/100. Ótima opção para famílias ou quem trabalha remotamente.',
    ),
    en=dict(
      meta='Living in Sintra, Portugal: median rent €10.20/m² (~€714/month for a 2-bed), safety 41/100, quality of life 60/100. UNESCO World Heritage town, 40 minutes from Lisbon by train.',
      badge='Historic & affordable town',
      ctx_rent='At €10.20/m², Sintra is one of the most affordable options on this list. The direct train to Lisbon Rossio takes around 40 minutes, making it viable for daily commuters.',
      ctx_safe='Slightly elevated crime rate driven largely by tourist activity. Day-to-day residential life is calm and safe by European standards.',
      ctx_life='A UNESCO World Cultural Landscape with palaces, forested hills and a charming historic centre. Increasingly chosen by remote workers and families priced out of Lisbon.',
      faq3_q='Is Sintra a good place to live near Lisbon?',
      faq3_a='Yes, especially for families and remote workers. Sintra scores 60/100 with rents at €10.20/m² (a T2 ~€714/month) and a 40-minute train to central Lisbon. UNESCO heritage and nature on the doorstep.',
    ),
  ),
  dict(
    slug='paranhos', nome='Paranhos', municipio='Porto',
    pop=45883, score=92, seg=50, seg_val=40.1, renda=12.58,
    qf='Paranhos', qm='Porto',
    pt=dict(
      meta='Paranhos, Porto: renda mediana 12,58 €/m², segurança 50/100, qualidade de vida 92/100. Dados INE 2024. Zona residencial do Porto com Universidade e metro.',
      badge='Zona universitária e residencial',
      ctx_rent='Paranhos é mais acessível do que Bonfim, Cedofeita ou Lordelo do Ouro, as zonas mais valorizadas do Porto. É uma opção equilibrada para quem quer a cidade sem pagar o máximo.',
      ctx_safe='O Porto tem uma taxa de criminalidade ligeiramente abaixo de Lisboa. Paranhos, sendo uma zona predominantemente residencial e universitária, tem uma percepção de segurança acima da média da cidade.',
      ctx_life='Vários campi da Universidade do Porto estão em Paranhos, criando um ambiente jovem e académico. O metro (linhas D e B/E) liga rapidamente ao centro e ao aeroporto Francisco Sá Carneiro.',
      faq3_q='Vale a pena viver em Paranhos, Porto?',
      faq3_a='Paranhos tem 92/100 de qualidade de vida. Oferece boa relação preço-qualidade no Porto: zona residencial tranquila, metro para o centro e ambiente académico. Mais económico do que Bonfim ou Cedofeita.',
    ),
    br=dict(
      meta='Pensando em morar em Paranhos, Porto? Aluguel médio de 12,58 €/m² (~€881/mês num T2), segurança 50/100, qualidade de vida 92/100. Guia para brasileiros no Porto.',
      badge='Zona universitária e residencial',
      intro='Paranhos é uma das zonas preferidas por brasileiros no Porto — mais acessível do que o Bonfim histórico e com boa infraestrutura académica e de transportes.',
      ctx_rent='Para quem vem do Brasil, Paranhos oferece excelente custo-benefício: metrô, universidade, hospitais e aluguel abaixo da média do Porto central.',
      ctx_safe='O Porto é ligeiramente mais seguro do que Lisboa pelos indicadores do INE. Paranhos tem ambiente universitário e residencial que contribui para uma boa sensação de segurança no dia a dia.',
      ctx_life='A comunidade brasileira no Porto tem crescido muito e Paranhos é uma das zonas de maior concentração. Tem metrô, farmácias, supermercados e restaurantes acessíveis a poucos minutos.',
      faq3_q='Paranhos é boa opção para brasileiro morar no Porto?',
      faq3_a='Sim. Score 92/100, aluguel mais acessível do que Bonfim ou Cedofeita, metrô para o centro e comunidade brasileira presente. Ótima relação custo-benefício no Porto.',
    ),
    en=dict(
      meta='Living in Paranhos, Porto: median rent €12.58/m² (~€881/month for a 2-bed), safety 50/100, quality of life 92/100. Real INE 2024 data for expats moving to Porto.',
      badge='University & residential area',
      ctx_rent='Paranhos offers better value than Porto\'s most sought-after parishes (Bonfim, Cedofeita, Lordelo do Ouro) while remaining well connected to the city centre by metro.',
      ctx_safe='Porto\'s overall crime rate is lower than Lisbon\'s. Paranhos, as a residential and university district, has a notably calm day-to-day atmosphere.',
      ctx_life='Home to several University of Porto campuses, Paranhos has a young, academic character. Metro lines D and B/E provide direct links to the city centre and Francisco Sá Carneiro Airport.',
      faq3_q='Is Paranhos a good neighbourhood for expats in Porto?',
      faq3_a='Yes. Paranhos scores 92/100 overall and offers great value compared to Bonfim or Cedofeita. University atmosphere, metro access and rents around €881/month for a 2-bed flat.',
    ),
  ),
  dict(
    slug='braga-sao-vitor', nome='Braga (São Vítor)', municipio='Braga',
    pop=32876, score=66, seg=41, seg_val=43.8, renda=7.69,
    qf='Braga (São Vítor)', qm='Braga',
    pt=dict(
      meta='Braga (São Vítor): renda mediana 7,69 €/m², segurança 41/100, qualidade de vida 66/100. Dados INE 2024. Centro histórico de Braga com as rendas mais acessíveis desta lista.',
      badge='Centro histórico acessível',
      ctx_rent='Com 7,69 €/m², São Vítor tem as rendas mais baixas de toda esta lista e fica no coração histórico de Braga, a poucas centenas de metros da Sé Catedral.',
      ctx_safe='O município de Braga tem criminalidade abaixo das grandes cidades portuguesas. O valor de 43,8 crimes/1 000 hab reflecte uma cidade universitária activa, não violência urbana.',
      ctx_life='Braga é uma das cidades que mais cresce em Portugal, com um forte sector tecnológico e população jovem. São Vítor fica no coração da cidade histórica, com tudo acessível a pé.',
      faq3_q='Vale a pena viver em Braga (São Vítor)?',
      faq3_a='Braga (São Vítor) tem 66/100 de qualidade de vida com as rendas mais acessíveis desta lista (7,69 €/m²). Ideal para quem quer viver no centro histórico de uma cidade universitária a crescer, sem os custos de Lisboa ou Porto.',
    ),
    br=dict(
      meta='Pensando em morar em Braga (São Vítor)? Aluguel médio de 7,69 €/m² (~€538/mês num T2) — o mais barato desta lista. Centro histórico, universidade e tech. Guia para brasileiros.',
      badge='Centro histórico acessível',
      intro='Braga (São Vítor) é onde a relação custo-benefício é mais favorável para quem chega do Brasil — custo europeu baixo, universidade, tecnologia e qualidade de vida real.',
      ctx_rent='Com aluguel em torno de €538/mês num T2, Braga (São Vítor) é a opção mais acessível desta lista. Equivale a pagar um quarto em república de SP por um apartamento inteiro na Europa.',
      ctx_safe='Cidade universitária com ambiente seguro pelo padrão europeu. A taxa de criminalidade é uma das mais baixas das cidades desta lista — muito melhor do que qualquer capital brasileira.',
      ctx_life='Braga tem campus da Universidade do Minho, parque de ciência e tecnologia, e um centro histórico muito animado. TGV até Lisboa em menos de 2 horas. Muito procurada por brasileiros na área de TI.',
      faq3_q='Braga (São Vítor) é boa opção para brasileiro morar em Portugal?',
      faq3_a='Sim, especialmente para quem trabalha em tecnologia ou estuda. É a opção mais barata desta lista (€538/mês num T2) com qualidade de vida europeia real, universidade e uma comunidade brasileira crescente.',
    ),
    en=dict(
      meta='Living in Braga (São Vítor), Portugal: median rent €7.69/m² (~€538/month for a 2-bed) — the most affordable on this list. Historic centre, university city, growing tech scene.',
      badge='Affordable historic centre',
      ctx_rent='At €7.69/m², São Vítor is the best-value option on this list — central Braga with its medieval cathedral and university, at rents far below Lisbon or Porto.',
      ctx_safe='Braga\'s crime rate is among the lowest of Portugal\'s major cities. The university character of the city contributes to a generally safe and lively atmosphere.',
      ctx_life='Braga is one of Portugal\'s fastest-growing cities, driven by tech companies and the University of Minho. São Vítor sits at the heart of the historic centre, walkable to everything.',
      faq3_q='Is Braga (São Vítor) a good place to live in Portugal?',
      faq3_a='Yes, especially for tech professionals and students. At €7.69/m² (a 2-bed ~€538/month), it\'s the most affordable option on this list with genuine European quality of life and a growing international community.',
    ),
  ),
  dict(
    slug='oeiras', nome='Oeiras', municipio='Oeiras',
    pop=58094, score=100, seg=51, seg_val=39.8, renda=13.80,
    qf='Oeiras', qm='Oeiras',
    pt=dict(
      meta='Oeiras: renda mediana 13,80 €/m², segurança 51/100, qualidade de vida 100/100. Taguspark, praias e acesso a Lisboa. Dados INE 2024 para arrendar em Oeiras.',
      badge='Hub tecnológico e residencial',
      ctx_rent='Oeiras é um hub tecnológico com sede de empresas como Dell, Cisco e Oracle no Taguspark. As rendas são mais acessíveis do que Lisboa cidade com qualidade de vida superior.',
      ctx_safe='Oeiras tem consistentemente uma das taxas de criminalidade mais baixas da Área Metropolitana de Lisboa — uma das opções mais seguras desta lista.',
      ctx_life='Além do Taguspark, tem praias próprias (Oeiras, Paço de Arcos), acesso à A5 para Lisboa e comboio na Linha de Cascais. Muito procurada por profissionais de tecnologia e famílias.',
      faq3_q='Vale a pena viver em Oeiras?',
      faq3_a='Oeiras tem o score máximo de 100/100 e é uma das zonas mais seguras da Área Metropolitana de Lisboa. Ideal para profissionais de tecnologia (Taguspark) e famílias que querem qualidade de vida com menos trânsito do que Lisboa.',
    ),
    br=dict(
      meta='Pensando em morar em Oeiras? Aluguel médio de 13,80 €/m² (~€966/mês num T2), segurança 51/100, qualidade de vida 100/100. Hub tech, praias e ligação a Lisboa. Guia para brasileiros.',
      badge='Hub tecnológico e residencial',
      intro='Oeiras é a escolha de muitos brasileiros que trabalham em tecnologia na região de Lisboa — o Taguspark reúne multinacionais e o custo de vida é mais baixo do que na capital.',
      ctx_rent='O aluguel é mais acessível do que em Lisboa, com apartamentos de maior qualidade. Para quem trabalha no Taguspark, elimina deslocações longas e oferece melhor qualidade de vida.',
      ctx_safe='Uma das zonas mais seguras da Área Metropolitana de Lisboa, com ambiente familiar e residencial muito diferente da intensidade do centro de Lisboa.',
      ctx_life='Tem acesso ao comboio (Linha de Cascais), praias, centros comerciais e uma comunidade de expatriados crescente. Escola internacional próxima para famílias com filhos.',
      faq3_q='Oeiras é boa opção para brasileiro trabalhar em tecnologia em Portugal?',
      faq3_a='Sim, é a melhor opção para quem trabalha no Taguspark. Score máximo de 100/100, grande segurança, praias, e aluguel mais baixo do que Lisboa central. Uma das preferidas de brasileiros em TI.',
    ),
    en=dict(
      meta='Living in Oeiras, Portugal: median rent €13.80/m² (~€966/month for a 2-bed), safety 51/100, quality of life 100/100. Taguspark tech hub, beaches and Lisbon access.',
      badge='Tech hub & residential area',
      ctx_rent='Oeiras offers a compelling value proposition: lower rents than central Lisbon with access to the Taguspark tech cluster where Dell, Cisco, Oracle and dozens of others have offices.',
      ctx_safe='Consistently one of the safest municipalities in the Lisbon Metropolitan Area — an important consideration for families and professionals relocating from abroad.',
      ctx_life='The parish combines Taguspark, Atlantic beaches, the Cascais Line train to Lisbon and well-developed suburban infrastructure. One of the most popular choices for tech professionals and families.',
      faq3_q='Is Oeiras a good place to live near Lisbon for tech professionals?',
      faq3_a='Yes — one of the best options. Oeiras scores 100/100 overall, is one of the safest areas near Lisbon, and sits adjacent to Taguspark. Rents (~€966/month for a 2-bed) are lower than central Lisbon.',
    ),
  ),
  dict(
    slug='almada', nome='Almada', municipio='Almada',
    pop=48608, score=97, seg=49, seg_val=40.2, renda=11.76,
    qf='Almada', qm='Almada',
    pt=dict(
      meta='Almada: renda mediana 11,76 €/m², segurança 49/100, qualidade de vida 97/100. Margem Sul do Tejo, 10 min de barco de Lisboa. Dados INE 2024.',
      badge='Alternativa acessível a Lisboa',
      ctx_rent='Almada é a alternativa mais económica a Lisboa na margem sul do Tejo. A renda mediana de 11,76 €/m² é significativamente inferior à da capital, mantendo a proximidade ao centro.',
      ctx_safe='O município de Almada tem criminalidade ligeiramente abaixo da média de Lisboa. É uma zona residencial mista com menos concentração de turismo do que a capital.',
      ctx_life='O cacilheiro (ferry) faz a travessia para o Terreiro do Paço em 10 minutos. Cristo Rei, a Almada Velha e a zona ribeirinha tornam esta uma alternativa genuína e cada vez mais valorizada a Lisboa.',
      faq3_q='Vale a pena viver em Almada em vez de Lisboa?',
      faq3_a='Almada tem 97/100 de qualidade de vida. Com rendas a 11,76 €/m², é significativamente mais acessível do que Lisboa e o ferry para o Terreiro do Paço demora apenas 10 minutos. Uma excelente alternativa para quem trabalha em Lisboa.',
    ),
    br=dict(
      meta='Pensando em morar em Almada? Aluguel médio de 11,76 €/m² (~€823/mês num T2), segurança 49/100. Margem Sul do Tejo a 10 min de barco de Lisboa. Guia para brasileiros.',
      badge='Alternativa acessível a Lisboa',
      intro='Almada é a alternativa ideal para brasileiros que querem Lisboa mas não querem ou não conseguem pagar os aluguéis da capital — a travessia de barco leva apenas 10 minutos.',
      ctx_rent='O aluguel em Almada é consideravelmente mais baixo do que em Lisboa, e o cacilheiro é mais rápido do que muitas ligações de metrô dentro da própria capital.',
      ctx_safe='Ambiente mais residencial do que Lisboa, com menor pressão turística. A sensação de segurança no dia a dia é boa, com bairros tranquilos e bem estruturados.',
      ctx_life='Além do ferry, tem o Cristo Rei (um claro cartão de visita para brasileiros), o centro comercial Almada Forum e a Almada Velha com vista para Lisboa. Bairro cada vez mais valorizado.',
      faq3_q='Almada é boa opção para brasileiro morar perto de Lisboa?',
      faq3_a='Sim. Score de 97/100, aluguel muito mais acessível do que Lisboa (~€823/mês num T2) e 10 minutos de barco do Terreiro do Paço. Uma das melhores relações custo-benefício da Área Metropolitana.',
    ),
    en=dict(
      meta='Living in Almada, Portugal: median rent €11.76/m² (~€823/month for a 2-bed), safety 49/100, quality of life 97/100. South bank of the Tagus, 10 minutes by ferry from Lisbon.',
      badge='Affordable Lisbon alternative',
      ctx_rent='Almada is Lisbon\'s south-bank alternative. Rents run significantly lower than the capital while the Cacilheiros ferry (10 minutes) makes the crossing faster than many metro journeys within Lisbon itself.',
      ctx_safe='A residential municipality with less tourist pressure than Lisbon. Crime rates are slightly below the capital, making it a comfortable choice for families and professionals.',
      ctx_life='Cacilheiros ferry to Terreiro do Paço in 10 minutes, Cristo Rei viewpoint, the historic Almada old town and the Almada Forum shopping centre round out a well-equipped south-bank suburb.',
      faq3_q='Is Almada a good alternative to living in Lisbon?',
      faq3_a='Yes — one of the best. Almada scores 97/100 with rents at €11.76/m² (~€823/month for a 2-bed). The 10-minute ferry to central Lisbon makes the commute faster than many routes within the city itself.',
    ),
  ),
  dict(
    slug='setubal', nome='Setúbal', municipio='Setúbal',
    pop=52627, score=100, seg=49, seg_val=40.2, renda=9.65,
    qf='Setúbal (São Sebastião)', qm='Setúbal',
    pt=dict(
      meta='Setúbal: renda mediana 9,65 €/m², segurança 49/100, qualidade de vida 100/100. Porta de entrada para a Serra da Arrábida. Dados INE 2024.',
      badge='Cidade costeira acessível',
      ctx_rent='Com 9,65 €/m², Setúbal é uma das opções mais acessíveis desta lista. Trata-se de uma cidade costeira com vida própria, a cerca de 50 km de Lisboa pela A2.',
      ctx_safe='Setúbal tem uma taxa de criminalidade alinhada com a média nacional. É uma cidade de escala média onde a vida quotidiana é tranquila, sem a pressão urbana de Lisboa ou Porto.',
      ctx_life='Setúbal é a porta de entrada para o Parque Natural da Serra da Arrábida, com praias de água cristalina a menos de 20 minutos. Tem universidade, porto activo e vida cultural própria.',
      faq3_q='Vale a pena viver em Setúbal?',
      faq3_a='Setúbal tem o score máximo de 100/100 com rendas a 9,65 €/m². Ideal para quem quer qualidade de vida junto ao mar a um custo acessível, com a Serra da Arrábida à porta e ligação a Lisboa pela A2.',
    ),
    br=dict(
      meta='Pensando em morar em Setúbal? Aluguel médio de 9,65 €/m² (~€676/mês num T2). Serra da Arrábida, praias, qualidade de vida. Guia para brasileiros em Portugal.',
      badge='Cidade costeira acessível',
      intro='Setúbal é a escolha perfeita para brasileiros que querem Portugal com qualidade de vida, mar e custo acessível — sem depender de Lisboa para tudo.',
      ctx_rent='O aluguel é muito acessível para o que a cidade oferece. Um T2 em Setúbal fica em torno de €676/mês — uma fracção do que custaria num bairro equivalente em Lisboa ou Porto.',
      ctx_safe='Cidade de porte médio com ambiente calmo e seguro pelo padrão europeu. Muito diferente da intensidade de Lisboa ou Porto, é uma boa opção para quem prioriza tranquilidade.',
      ctx_life='A Serra da Arrábida com as suas praias de água verde é o grande trunfo de Setúbal — uma das áreas naturais mais bonitas da Europa. Tem universidade, hospital e boas ligações a Lisboa.',
      faq3_q='Setúbal é boa opção para brasileiro morar em Portugal?',
      faq3_a='Sim, especialmente para quem valoriza natureza, mar e custo de vida baixo. Score máximo de 100/100 com aluguel de €676/mês num T2. A Arrábida é uma das melhores praias da Europa.',
    ),
    en=dict(
      meta='Living in Setúbal, Portugal: median rent €9.65/m² (~€676/month for a 2-bed), safety 49/100, quality of life 100/100. Gateway to Arrábida Natural Park, 50 km from Lisbon.',
      badge='Affordable coastal city',
      ctx_rent='At €9.65/m², Setúbal is one of the most affordable cities on this list. Located 50 km south of Lisbon on the A2 motorway, it offers a genuine coastal city lifestyle at low cost.',
      ctx_safe='A mid-sized city with a calm daily pace and crime rates in line with the national average. Far removed from the pressures of Lisbon or Porto.',
      ctx_life='Setúbal is the gateway to the Arrábida Natural Park — turquoise-water beaches less than 20 minutes away. The city has its own university, active port and cultural scene.',
      faq3_q='Is Setúbal a good place to live in Portugal?',
      faq3_a='Yes, especially for those who value nature, sea and low cost of living. Setúbal scores 100/100 with rents at €9.65/m² (~€676/month for a 2-bed). The Arrábida beaches are among Europe\'s finest.',
    ),
  ),
]

# Dict para lookup rápido de conteúdo curado por slug (usado quando --supabase)
PARISHES_MANUAIS = {p['slug']: p for p in PARISHES}

# ─────────────────────────────────────────────────────────────────────────────
# CSS (partilhado entre todas as páginas)
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --azul: #1B4F72; --azul-medio: #2E86C1; --azul-claro: #D6E8F5;
      --azul-escuro: #0d2137; --branco: #ffffff; --cinza-fundo: #f2f6fa;
      --cinza-borda: #dde3eb; --cinza-texto: #6b7a8d;
      --verde: #1e8449; --verde-claro: #d5f5e3;
      --amarelo: #9a7d0a; --amarelo-claro: #fef9e7;
      --vermelho: #c0392b; --vermelho-claro: #fadbd8;
      --titulo: 'Playfair Display', Georgia, serif;
      --corpo: 'Inter', system-ui, sans-serif;
      --raio: 12px; --sombra: 0 4px 20px rgba(13,33,55,0.09);
    }
    html { scroll-behavior: smooth; }
    body { font-family: var(--corpo); color: var(--azul-escuro); background: var(--cinza-fundo); -webkit-font-smoothing: antialiased; line-height: 1.6; }
    .container { max-width: 780px; margin: 0 auto; padding: 0 20px; }
    nav { background: var(--azul-escuro); padding: 16px 0; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 12px rgba(0,0,0,0.2); }
    .nav-inner { max-width: 1100px; margin: 0 auto; padding: 0 20px; display: flex; align-items: center; justify-content: space-between; }
    .nav-logo { display: flex; align-items: center; gap: 8px; text-decoration: none; }
    .nav-logo-icone { width: 32px; height: 32px; background: var(--azul-medio); border-radius: 7px; display: flex; align-items: center; justify-content: center; }
    .nav-logo-icone svg { width: 18px; height: 18px; fill: var(--branco); }
    .nav-logo-nome { font-size: 1.1rem; font-weight: 700; color: var(--branco); }
    .nav-logo-nome span { color: rgba(255,255,255,0.45); font-weight: 400; }
    .btn-nav { color: rgba(255,255,255,0.75); text-decoration: none; font-size: 0.875rem; font-weight: 500; padding: 7px 14px; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; transition: background 0.2s; }
    .btn-nav:hover { background: rgba(255,255,255,0.1); color: var(--branco); }
    .breadcrumb { padding: 12px 0; font-size: 0.8rem; color: var(--cinza-texto); }
    .breadcrumb a { color: var(--azul-medio); text-decoration: none; }
    .breadcrumb a:hover { text-decoration: underline; }
    .breadcrumb span { margin: 0 6px; }
    .hero { background-color: var(--azul); background-image: repeating-linear-gradient(-45deg, transparent 0px, transparent 18px, rgba(255,255,255,0.04) 18px, rgba(255,255,255,0.04) 19px); padding: 52px 20px 44px; text-align: center; }
    .hero-titulo { font-family: var(--titulo); font-size: clamp(1.8rem, 5vw, 2.8rem); font-weight: 800; color: var(--branco); line-height: 1.15; letter-spacing: -0.5px; margin-bottom: 8px; }
    .hero-subtitulo { font-size: 1rem; color: rgba(255,255,255,0.65); margin-bottom: 24px; }
    .hero-score-wrap { display: inline-flex; align-items: center; gap: 14px; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.22); border-radius: 14px; padding: 16px 28px; margin-bottom: 22px; }
    .hero-score-numero { font-family: var(--titulo); font-size: 3.2rem; font-weight: 800; color: var(--branco); line-height: 1; }
    .hero-score-label-top { font-size: 0.7rem; color: rgba(255,255,255,0.5); text-transform: uppercase; letter-spacing: 0.8px; }
    .hero-score-label-badge { font-size: 0.95rem; font-weight: 700; color: var(--branco); }
    .hero-meta { font-size: 0.8rem; color: rgba(255,255,255,0.45); margin-bottom: 22px; }
    .hero-cta { display: inline-flex; align-items: center; gap: 8px; background: var(--branco); color: var(--azul); text-decoration: none; font-weight: 700; font-size: 0.95rem; padding: 13px 28px; border-radius: 10px; transition: background 0.2s, transform 0.15s; box-shadow: 0 4px 14px rgba(0,0,0,0.18); }
    .hero-cta:hover { background: var(--azul-claro); transform: translateY(-1px); }
    .secao { padding: 40px 0 20px; }
    .secao h2 { font-family: var(--titulo); font-size: 1.5rem; font-weight: 700; color: var(--azul-escuro); margin-bottom: 6px; }
    .secao-intro { font-size: 0.875rem; color: var(--cinza-texto); margin-bottom: 20px; }
    .cards-grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
    @media (min-width: 560px) { .cards-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (min-width: 740px) { .cards-grid { grid-template-columns: repeat(3, 1fr); } }
    .card { background: var(--branco); border: 1px solid var(--cinza-borda); border-radius: var(--raio); padding: 22px; box-shadow: var(--sombra); }
    .card-icone { width: 44px; height: 44px; background: var(--azul-claro); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.35rem; margin-bottom: 14px; }
    .card-nome { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--cinza-texto); margin-bottom: 6px; }
    .card-score { font-family: var(--titulo); font-size: 2.4rem; font-weight: 800; color: var(--azul); line-height: 1; margin-bottom: 10px; }
    .card-score span { font-family: var(--corpo); font-size: 0.9rem; color: var(--cinza-texto); font-weight: 400; }
    .barra-fundo { height: 6px; background: var(--cinza-borda); border-radius: 3px; overflow: hidden; margin-bottom: 8px; }
    .barra-progresso { height: 100%; border-radius: 3px; }
    .barra-progresso.bom   { background: var(--verde); }
    .barra-progresso.medio { background: var(--amarelo); }
    .barra-progresso.fraco { background: var(--vermelho); }
    .card-valor { font-size: 0.82rem; color: var(--cinza-texto); margin-bottom: 12px; }
    .card-nota { font-size: 0.75rem; color: var(--cinza-texto); margin-bottom: 12px; font-style: italic; }
    .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.77rem; font-weight: 700; }
    .badge-bom   { background: var(--verde-claro);   color: var(--verde);   }
    .badge-medio { background: var(--amarelo-claro); color: var(--amarelo); }
    .badge-fraco { background: var(--vermelho-claro);color: var(--vermelho);}
    .prosa { background: var(--branco); border: 1px solid var(--cinza-borda); border-radius: var(--raio); padding: 28px 32px; box-shadow: var(--sombra); margin-top: 20px; }
    .prosa h3 { font-family: var(--titulo); font-size: 1.15rem; font-weight: 700; color: var(--azul-escuro); margin-bottom: 10px; margin-top: 24px; }
    .prosa h3:first-child { margin-top: 0; }
    .prosa p { font-size: 0.95rem; color: #2c3e50; line-height: 1.8; margin-bottom: 12px; }
    .prosa p:last-child { margin-bottom: 0; }
    .tabela-dados { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    .tabela-dados th { background: var(--azul-claro); color: var(--azul); font-weight: 700; padding: 10px 14px; text-align: left; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .tabela-dados td { padding: 10px 14px; border-bottom: 1px solid var(--cinza-borda); }
    .tabela-dados tr:last-child td { border-bottom: none; }
    .tabela-dados tr:nth-child(even) td { background: #f8fafc; }
    .cta-relatorio { background-color: var(--azul); background-image: repeating-linear-gradient(-45deg, transparent 0px, transparent 18px, rgba(255,255,255,0.04) 18px, rgba(255,255,255,0.04) 19px); border-radius: var(--raio); padding: 36px 32px; text-align: center; margin: 32px 0; }
    .cta-relatorio h2 { font-family: var(--titulo); font-size: 1.5rem; font-weight: 800; color: var(--branco); margin-bottom: 10px; }
    .cta-relatorio p { font-size: 0.9rem; color: rgba(255,255,255,0.7); margin-bottom: 20px; }
    .btn-principal { display: inline-flex; align-items: center; gap: 8px; background: var(--branco); color: var(--azul); text-decoration: none; font-weight: 700; font-size: 0.95rem; padding: 13px 28px; border-radius: 10px; margin: 4px; box-shadow: 0 4px 14px rgba(0,0,0,0.18); transition: background 0.2s, transform 0.15s; }
    .btn-principal:hover { background: var(--azul-claro); transform: translateY(-1px); }
    .btn-secundario { display: inline-flex; align-items: center; gap: 8px; background: transparent; color: rgba(255,255,255,0.85); text-decoration: none; font-weight: 600; font-size: 0.9rem; padding: 12px 24px; border: 1px solid rgba(255,255,255,0.3); border-radius: 10px; margin: 4px; transition: background 0.2s; }
    .btn-secundario:hover { background: rgba(255,255,255,0.1); }
    .linguas { background: var(--branco); border: 1px solid var(--cinza-borda); border-radius: var(--raio); padding: 16px 20px; margin: 16px 0 0; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 0.85rem; }
    .linguas span { color: var(--cinza-texto); }
    .lingua-link { color: var(--azul-medio); text-decoration: none; font-weight: 600; padding: 4px 10px; border: 1px solid var(--azul-claro); border-radius: 6px; transition: background 0.2s; }
    .lingua-link:hover { background: var(--azul-claro); }
    .lingua-link.activa { background: var(--azul); color: var(--branco); border-color: var(--azul); }
    .outras-freguesias { background: var(--branco); border: 1px solid var(--cinza-borda); border-radius: var(--raio); padding: 24px 28px; box-shadow: var(--sombra); margin-bottom: 40px; }
    .outras-freguesias h3 { font-family: var(--titulo); font-size: 1.1rem; font-weight: 700; color: var(--azul-escuro); margin-bottom: 14px; }
    .links-lista { display: flex; flex-wrap: wrap; gap: 8px; }
    .link-item { display: inline-block; padding: 6px 14px; background: var(--azul-claro); color: var(--azul); text-decoration: none; border-radius: 20px; font-size: 0.82rem; font-weight: 600; transition: background 0.2s, color 0.2s; }
    .link-item:hover { background: var(--azul); color: var(--branco); }
    footer { background: var(--azul-escuro); color: rgba(255,255,255,0.5); text-align: center; padding: 32px 20px; font-size: 0.82rem; line-height: 1.8; }
    footer a { color: rgba(255,255,255,0.6); }
    footer a:hover { color: var(--branco); }
    .footer-fonte { font-size: 0.75rem; color: rgba(255,255,255,0.35); margin-top: 8px; }
    @media (max-width: 520px) {
      .prosa { padding: 20px 18px; }
      .cta-relatorio { padding: 28px 20px; }
      .hero { padding: 40px 16px 36px; }
    }
"""

# ─────────────────────────────────────────────────────────────────────────────
# TEXTOS POR LÍNGUA (títulos de secção, nav, etc.)
# ─────────────────────────────────────────────────────────────────────────────

UI = {
    'pt': dict(
        html_lang='pt-PT', og_locale='pt_PT',
        nav_back='← Pesquisar', nav_label='Melhor Zona — página inicial',
        breadcrumb_base='Guias de Freguesia',
        hero_meta='Análise com dados públicos · INE Censos 2021 · INE 2024',
        hero_cta='Ver relatório interactivo completo →',
        score_label='Qualidade de vida',
        lang_switch='Esta página em:',
        sec_ind_title='Indicadores de qualidade de vida',
        sec_ind_sub='Dados de fontes públicas oficiais. Pontuação de 0 a 100 — quanto maior, melhor.',
        card_arr='Arrendamento', card_seg='Segurança', card_geral='Qualidade Global',
        card_arr_val=lambda p: f'{r(p["renda"],"pt")} €/m² · renda mediana · INE 2024',
        card_seg_val=lambda p: f'{sv(p["seg_val"],"pt")} crimes/1 000 hab · {p["municipio"]} · INE 2023',
        card_geral_val=lambda p: f'{pop(p["pop"],"pt")} residentes · INE Censos 2021',
        card_arr_nota='calculado a partir da renda mediana INE 2024',
        sec_ed_title=lambda p: f'{p["nome"]} em detalhe',
        h3_rent=lambda p: f'Quanto custa arrendar em {p["nome"]}?',
        h3_safe=lambda p: f'Segurança em {p["nome"]}',
        h3_life='Vida na zona',
        p_rent_tmpl=lambda p, arr: f'A renda mediana em {p["nome"]} é de <strong>{r(p["renda"],"pt")} €/m²</strong> (INE 2024). Para um T2 típico com 70 m², isso representa uma renda mensal de aproximadamente <strong>{t2(p["renda"],"pt")}/mês</strong>.',
        p_safe_tmpl=lambda p: f'O município de {p["municipio"]} registou <strong>{sv(p["seg_val"],"pt")} crimes por 1 000 habitantes</strong> em 2023 (INE), o que coloca {p["nome"]} numa pontuação de segurança de <strong>{p["seg"]}/100</strong>.',
        p_life_tmpl=lambda p: f'Com <strong>{pop(p["pop"],"pt")} residentes</strong> registados nos Censos 2021,',
        sec_tab_title=lambda p: f'Resumo dos dados de {p["nome"]}',
        sec_tab_sub='Fontes públicas oficiais. Actualizado em junho de 2026.',
        th=['Indicador','Valor','Pontuação','Fonte'],
        tr_arr=lambda p, arr: [f'Renda mediana', f'{r(p["renda"],"pt")} €/m²', f'{arr}/100', 'INE 2024'],
        tr_t2=lambda p: ['T2 estimado (70 m²)', f'~{t2(p["renda"],"pt")}/mês', '—', 'Calculado'],
        tr_seg=lambda p: ['Segurança (criminalidade)', f'{sv(p["seg_val"],"pt")} crimes/1 000 hab', f'{p["seg"]}/100', 'DGAI 2023'],
        tr_geral=lambda p: ['Qualidade de vida global', '—', f'{p["score"]}/100', 'Calculado'],
        tr_pop=lambda p: ['População residente', f'{pop(p["pop"],"pt")} hab', '—', 'INE Censos 2021'],
        tr_pending='Dados em actualização — disponíveis no relatório interactivo',
        cta_title=lambda p: f'Relatório completo de {p["nome"]}',
        cta_sub='Transportes, qualidade do ar, escolas e saúde — tudo num só lugar, actualizado.',
        cta_btn='Abrir relatório interactivo',
        cta_btn2='Comparar com outra zona',
        other_title='Outras freguesias populares em Portugal',
        footer_copy='Qualidade de vida por freguesia em Portugal',
        footer_data='Dados: INE Censos 2021 · INE Rendas 2024 · DGAI 2023',
        privacy='Privacidade',
        faq1_q=lambda p: f'Quanto custa arrendar em {p["nome"]}?',
        faq1_a=lambda p, arr: f'A renda mediana em {p["nome"]} é de {r(p["renda"],"pt")} €/m² (INE 2024). Para um T2 típico de 70 m², isso representa uma renda mensal de aproximadamente {t2(p["renda"],"pt")}/mês.',
        faq2_q=lambda p: f'É seguro viver em {p["nome"]}?',
        faq2_a=lambda p: f'{p["nome"]} tem uma pontuação de segurança de {p["seg"]}/100, com base nos {sv(p["seg_val"],"pt")} crimes registados por 1 000 habitantes no município de {p["municipio"]} (INE 2023).',
        schema_lang='pt-PT',
        lang_flag_pt='🇵🇹', lang_flag_br='🇧🇷', lang_flag_en='🇬🇧',
        lang_label_pt='Português PT', lang_label_br='Português BR', lang_label_en='English',
    ),
    'br': dict(
        html_lang='pt-BR', og_locale='pt_BR',
        nav_back='← Pesquisar', nav_label='Melhor Zona — página inicial',
        breadcrumb_base='Guias de Bairro',
        hero_meta='Dados públicos oficiais · INE Censos 2021 · INE 2024',
        hero_cta='Ver relatório completo →',
        score_label='Qualidade de vida',
        lang_switch='Esta página em:',
        sec_ind_title='Indicadores do bairro',
        sec_ind_sub='Dados reais de fontes públicas portuguesas. Pontuação de 0 a 100 — quanto maior, melhor.',
        card_arr='Aluguel', card_seg='Segurança', card_geral='Qualidade Geral',
        card_arr_val=lambda p: f'{r(p["renda"],"br")} €/m² · mediana · INE 2024',
        card_seg_val=lambda p: f'{sv(p["seg_val"],"br")} crimes/1.000 hab · {p["municipio"]} · INE 2023',
        card_geral_val=lambda p: f'{pop(p["pop"],"br")} residentes · INE Censos 2021',
        card_arr_nota='calculado a partir do aluguel mediano INE 2024',
        sec_ed_title=lambda p: f'O que você precisa saber sobre {p["nome"]}',
        h3_rent=lambda p: f'Quanto custa alugar em {p["nome"]}?',
        h3_safe=lambda p: f'{p["nome"]} é seguro?',
        h3_life='Como é morar no bairro',
        p_rent_tmpl=lambda p, arr: f'O aluguel médio em {p["nome"]} é de <strong>{r(p["renda"],"br")} €/m²</strong> (INE 2024). Um apartamento T2 — equivalente a um 2 quartos no Brasil — com 70 m² fica em torno de <strong>{t2(p["renda"],"en")}/mês</strong>.',
        p_safe_tmpl=lambda p: f'{p["municipio"]} registrou <strong>{sv(p["seg_val"],"br")} crimes por 1.000 habitantes</strong> em 2023 (INE). {p["nome"]} tem uma pontuação de segurança de <strong>{p["seg"]}/100</strong>.',
        p_life_tmpl=lambda p: f'{p["nome"]} tem <strong>{pop(p["pop"],"br")} residentes</strong> (Censos 2021).',
        sec_tab_title=lambda p: f'Resumo dos dados de {p["nome"]}',
        sec_tab_sub='Fonte: INE (Instituto Nacional de Estatística de Portugal). Atualizado em junho de 2026.',
        th=['Indicador','Valor','Pontuação','Fonte'],
        tr_arr=lambda p, arr: ['Aluguel médio (mediana)', f'{r(p["renda"],"br")} €/m²', f'{arr}/100', 'INE 2024'],
        tr_t2=lambda p: ['T2 estimado (70 m²)', f'~{t2(p["renda"],"en")}/mês', '—', 'Calculado'],
        tr_seg=lambda p: ['Segurança (criminalidade)', f'{sv(p["seg_val"],"br")} crimes/1.000 hab', f'{p["seg"]}/100', 'DGAI 2023'],
        tr_geral=lambda p: ['Qualidade de vida global', '—', f'{p["score"]}/100', 'Calculado'],
        tr_pop=lambda p: ['População residente', f'{pop(p["pop"],"br")} hab', '—', 'INE Censos 2021'],
        tr_pending='Dados em atualização — disponíveis no relatório interativo',
        cta_title=lambda p: f'Relatório completo de {p["nome"]}',
        cta_sub='Transporte, qualidade do ar, escolas e saúde — todos os dados num só lugar.',
        cta_btn='Ver relatório interativo',
        cta_btn2='Comparar com outro bairro',
        other_title='Outros bairros populares em Portugal',
        footer_copy='Qualidade de vida por freguesia em Portugal',
        footer_data='Dados: INE Censos 2021 · INE Rendas 2024 · DGAI 2023',
        privacy='Privacidade',
        faq1_q=lambda p: f'Quanto custa alugar em {p["nome"]}, {p["municipio"]}?',
        faq1_a=lambda p, arr: f'O aluguel médio em {p["nome"]} é de {r(p["renda"],"br")} €/m² (INE 2024). Um T2 (2 quartos) de 70 m² fica em torno de {t2(p["renda"],"en")}/mês.',
        faq2_q=lambda p: f'{p["nome"]} é seguro para morar?',
        faq2_a=lambda p: f'{p["nome"]} tem pontuação de segurança de {p["seg"]}/100, com base em {sv(p["seg_val"],"br")} crimes por 1.000 habitantes no município de {p["municipio"]} (INE 2023).',
        schema_lang='pt-BR',
        lang_flag_pt='🇵🇹', lang_flag_br='🇧🇷', lang_flag_en='🇬🇧',
        lang_label_pt='Português PT', lang_label_br='Português BR', lang_label_en='English',
    ),
    'en': dict(
        html_lang='en', og_locale='en_GB',
        nav_back='← Search', nav_label='Melhor Zona — home',
        breadcrumb_base='Neighbourhood Guides',
        hero_meta='Official public data · INE Census 2021 · INE 2024',
        hero_cta='View full interactive report →',
        score_label='Quality of life',
        lang_switch='This page in:',
        sec_ind_title='Key indicators',
        sec_ind_sub='All figures from official Portuguese public sources. Score out of 100 — higher is better.',
        card_arr='Rent', card_seg='Safety', card_geral='Overall Score',
        card_arr_val=lambda p: f'€{r(p["renda"],"en")}/m² median rent · INE 2024',
        card_seg_val=lambda p: f'{sv(p["seg_val"],"en")} crimes per 1,000 residents · INE 2023',
        card_geral_val=lambda p: f'{pop(p["pop"],"en")} residents · INE Census 2021',
        card_arr_nota='calculated from INE 2024 median rent',
        sec_ed_title=lambda p: f'The {p["nome"]} neighbourhood guide',
        h3_rent=lambda p: f'How much does it cost to rent in {p["nome"]}?',
        h3_safe=lambda p: f'Is {p["nome"]} safe?',
        h3_life='What is the neighbourhood like?',
        p_rent_tmpl=lambda p, arr: f'The median rent in {p["nome"]} is <strong>€{r(p["renda"],"en")}/m²</strong> (INE 2024). A typical 2-bedroom apartment (T2 in Portuguese) of around 70 m² costs approximately <strong>{t2(p["renda"],"en")}/month</strong>.',
        p_safe_tmpl=lambda p: f'{p["municipio"]} recorded <strong>{sv(p["seg_val"],"en")} crimes per 1,000 inhabitants</strong> in 2023 (INE), giving {p["nome"]} a safety score of <strong>{p["seg"]}/100</strong>.',
        p_life_tmpl=lambda p: f'With <strong>{pop(p["pop"],"en")} residents</strong> (INE Census 2021),',
        sec_tab_title=lambda p: f'{p["nome"]} at a glance',
        sec_tab_sub='All data from official Portuguese public sources. Updated June 2026.',
        th=['Indicator','Value','Score','Source'],
        tr_arr=lambda p, arr: ['Median rent', f'€{r(p["renda"],"en")}/m²', f'{arr}/100', 'INE 2024'],
        tr_t2=lambda p: ['Estimated 2-bed (70 m²)', f'~{t2(p["renda"],"en")}/month', '—', 'Calculated'],
        tr_seg=lambda p: ['Safety (crime rate)', f'{sv(p["seg_val"],"en")} crimes/1,000 residents', f'{p["seg"]}/100', 'DGAI 2023'],
        tr_geral=lambda p: ['Overall quality of life', '—', f'{p["score"]}/100', 'Calculado'],
        tr_pop=lambda p: ['Resident population', pop(p['pop'],'en'), '—', 'INE Census 2021'],
        tr_pending='Data being compiled — available in the interactive report',
        cta_title=lambda p: f'Full {p["nome"]} report',
        cta_sub='Transport links, air quality, schools and healthcare — all in one place.',
        cta_btn='Open interactive report',
        cta_btn2='Compare with another area',
        other_title='Other popular neighbourhoods in Portugal',
        footer_copy='Quality of life by neighbourhood in Portugal',
        footer_data='Data: INE Census 2021 · INE Rents 2024 · DGAI 2023',
        privacy='Privacy',
        faq1_q=lambda p: f'How much does it cost to rent in {p["nome"]}, {p["municipio"]}?',
        faq1_a=lambda p, arr: f'The median rent in {p["nome"]} is €{r(p["renda"],"en")}/m² (INE 2024). A typical 2-bedroom flat (T2) of around 70 m² costs approximately {t2(p["renda"],"en")}/month.',
        faq2_q=lambda p: f'Is {p["nome"]} safe to live in?',
        faq2_a=lambda p: f'{p["nome"]} has a safety score of {p["seg"]} out of 100, based on {sv(p["seg_val"],"en")} crimes per 1,000 inhabitants in {p["municipio"]} municipality (INE 2023).',
        schema_lang='en',
        lang_flag_pt='🇵🇹', lang_flag_br='🇧🇷', lang_flag_en='🇬🇧',
        lang_label_pt='Português PT', lang_label_br='Português BR', lang_label_en='English',
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# GERADOR HTML
# ─────────────────────────────────────────────────────────────────────────────

def other_links_html(current_slug, lang, all_parishes=None):
    """Mostra as 9 primeiras freguesias da lista excluindo a actual"""
    if all_parishes is None:
        all_parishes = PARISHES
    links = ''
    count = 0
    for p in all_parishes:
        if p['slug'] == current_slug:
            continue
        if count >= 9:
            break
        links += f'<a href="https://melhorzona.pt/guias/{lang}/{p["slug"]}.html" class="link-item">{p["nome"]}</a>\n        '
        count += 1
    return links.strip()

def generate(p, lang, all_parishes=None):
    c  = p[lang]          # conteúdo editorial desta língua
    ui = UI[lang]         # textos de interface
    arr = calc_arr(p['renda'])
    arr_cls, arr_lbl = arr_badge(arr, lang)
    seg_cls, seg_lbl = seg_badge(p['seg'], lang)
    sco_cls, sco_lbl = score_badge(p['score'], lang)

    # Título SEO limpo
    title_tmpls = {
        'pt': f"Viver em {p['nome']}, {p['municipio']}: Rendas e Qualidade de Vida 2026 · Melhor Zona",
        'br': f"Morar em {p['nome']}, {p['municipio']}: Tudo que Você Precisa Saber · Melhor Zona",
        'en': f"Living in {p['nome']}, {p['municipio']}: Rents, Safety &amp; Quality of Life 2026 · Melhor Zona",
    }
    page_title = title_tmpls[lang]

    # Schema FAQ
    faq1_q = esc(ui['faq1_q'](p))
    faq1_a = esc(ui['faq1_a'](p, arr))
    faq2_q = esc(ui['faq2_q'](p))
    faq2_a = esc(ui['faq2_a'](p))
    faq3_q = esc(c['faq3_q'])
    faq3_a = esc(c['faq3_a'])

    # Parágrafos editoriais
    p_rent = ui['p_rent_tmpl'](p, arr) + ' ' + c['ctx_rent']
    p_safe = ui['p_safe_tmpl'](p) + ' ' + c['ctx_safe']
    p_life = ui['p_life_tmpl'](p) + ' ' + c['ctx_life']

    # Para BR: parágrafo de intro antes da secção de arrendamento
    intro_para = ''
    if lang == 'br' and c.get('intro'):
        intro_para = f'<p>{c["intro"]}</p>\n        '

    # Tabela
    def tr(cells):
        tds = ''.join(f'<td>{x}</td>' for x in cells)
        return f'<tr>{tds}</tr>'

    table_rows = '\n            '.join([
        tr(ui['tr_arr'](p, arr)),
        tr(ui['tr_t2'](p)),
        tr(ui['tr_seg'](p)),
        tr(ui['tr_geral'](p)),
        tr(ui['tr_pop'](p)),
        f'<tr><td>{ui["tr_pending"]}</td><td colspan="3" style="color:var(--cinza-texto);font-style:italic">{ui["tr_pending"]}</td></tr>',
    ])
    # Remove a linha duplicada de pending
    th_row = ''.join(f'<th>{h}</th>' for h in ui['th'])

    relatorio_url = f'https://melhorzona.pt/relatorio.html?freguesia={uq(p["qf"])}&municipio={uq(p["qm"])}'
    comparar_url  = f'https://melhorzona.pt/comparar.html?a={uq(p["qf"])}'

    html = f"""<!DOCTYPE html>
<html lang="{ui['html_lang']}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <meta name="description" content="{esc(c['meta'])}">
  <link rel="canonical" href="https://melhorzona.pt/guias/{lang}/{p['slug']}.html">
  <link rel="alternate" hreflang="pt-PT" href="https://melhorzona.pt/guias/pt/{p['slug']}.html">
  <link rel="alternate" hreflang="pt-BR" href="https://melhorzona.pt/guias/br/{p['slug']}.html">
  <link rel="alternate" hreflang="en"    href="https://melhorzona.pt/guias/en/{p['slug']}.html">
  <link rel="alternate" hreflang="x-default" href="https://melhorzona.pt/guias/pt/{p['slug']}.html">
  <meta property="og:title"       content="{esc(c['meta'][:80])}">
  <meta property="og:description" content="{esc(c['meta'])}">
  <meta property="og:url"         content="https://melhorzona.pt/guias/{lang}/{p['slug']}.html">
  <meta property="og:type"        content="article">
  <meta property="og:site_name"   content="Melhor Zona">
  <meta property="og:locale"      content="{ui['og_locale']}">
  <meta name="theme-color"        content="#1B4F72">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{esc(c['meta'][:110])}",
    "url": "https://melhorzona.pt/guias/{lang}/{p['slug']}.html",
    "inLanguage": "{ui['schema_lang']}",
    "datePublished": "2026-06-08",
    "dateModified": "2026-06-08",
    "author": {{"@type":"Organization","name":"Melhor Zona","url":"https://melhorzona.pt"}},
    "publisher": {{"@type":"Organization","name":"Melhor Zona","url":"https://melhorzona.pt","logo":{{"@type":"ImageObject","url":"https://melhorzona.pt/assets/images/icon-192.png"}}}},
    "about": {{"@type":"Place","name":"{esc(p['nome'])}","containedInPlace":{{"@type":"City","name":"{esc(p['municipio'])}"}}}}
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {{"@type":"Question","name":"{faq1_q}","acceptedAnswer":{{"@type":"Answer","text":"{faq1_a}"}}}},
      {{"@type":"Question","name":"{faq2_q}","acceptedAnswer":{{"@type":"Answer","text":"{faq2_a}"}}}},
      {{"@type":"Question","name":"{faq3_q}","acceptedAnswer":{{"@type":"Answer","text":"{faq3_a}"}}}}
    ]
  }}
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>

  <nav>
    <div class="nav-inner">
      <a href="https://melhorzona.pt" class="nav-logo" aria-label="{ui['nav_label']}">
        <div class="nav-logo-icone">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
        </div>
        <span class="nav-logo-nome">Melhor Zona<span>.pt</span></span>
      </a>
      <a href="https://melhorzona.pt" class="btn-nav">{ui['nav_back']}</a>
    </div>
  </nav>

  <div class="container">
    <nav class="breadcrumb" aria-label="breadcrumb">
      <a href="https://melhorzona.pt">Melhor Zona</a>
      <span>›</span>
      <a href="https://melhorzona.pt/guias/{lang}/">{ui['breadcrumb_base']}</a>
      <span>›</span>
      <span>{p['nome']}</span>
    </nav>
  </div>

  <section class="hero" aria-labelledby="titulo-principal">
    <h1 class="hero-titulo" id="titulo-principal">{p['nome']}</h1>
    <p class="hero-subtitulo">{p['municipio']} · {ui['hero_meta']}</p>
    <div class="hero-score-wrap" aria-label="{ui['score_label']}: {p['score']} / 100">
      <div class="hero-score-numero" aria-hidden="true">{p['score']}</div>
      <div>
        <div class="hero-score-label-top">{ui['score_label']}</div>
        <div class="hero-score-label-badge">{c['badge']}</div>
      </div>
    </div>
    <p class="hero-meta">{ui['hero_meta']}</p>
    <a href="{relatorio_url}" class="hero-cta">{ui['hero_cta']}</a>
  </section>

  <main class="container">

    <div class="linguas" role="navigation" aria-label="languages">
      <span>{ui['lang_switch']}</span>
      <a href="https://melhorzona.pt/guias/pt/{p['slug']}.html" class="lingua-link{'  activa' if lang=='pt' else ''}"{'  aria-current="page"' if lang=='pt' else ''}>{ui['lang_flag_pt']} {ui['lang_label_pt']}</a>
      <a href="https://melhorzona.pt/guias/br/{p['slug']}.html" class="lingua-link{'  activa' if lang=='br' else ''}"{'  aria-current="page"' if lang=='br' else ''}>{ui['lang_flag_br']} {ui['lang_label_br']}</a>
      <a href="https://melhorzona.pt/guias/en/{p['slug']}.html" class="lingua-link{'  activa' if lang=='en' else ''}"{'  aria-current="page"' if lang=='en' else ''}>{ui['lang_flag_en']} {ui['lang_label_en']}</a>
    </div>

    <section class="secao" aria-labelledby="tit-ind">
      <h2 id="tit-ind">{ui['sec_ind_title']}</h2>
      <p class="secao-intro">{ui['sec_ind_sub']}</p>
      <div class="cards-grid">

        <div class="card">
          <div class="card-icone" aria-hidden="true">🏠</div>
          <div class="card-nome">{ui['card_arr']}</div>
          <div class="card-score">{arr}<span>/100</span></div>
          <div class="barra-fundo" role="progressbar" aria-valuenow="{arr}" aria-valuemin="0" aria-valuemax="100">
            <div class="barra-progresso {arr_cls}" style="width:{arr}%"></div>
          </div>
          <div class="card-valor">{ui['card_arr_val'](p)}</div>
          <div class="card-nota">{ui['card_arr_nota']}</div>
          <span class="badge badge-{arr_cls}">{arr_lbl}</span>
        </div>

        <div class="card">
          <div class="card-icone" aria-hidden="true">🛡️</div>
          <div class="card-nome">{ui['card_seg']}</div>
          <div class="card-score">{p['seg']}<span>/100</span></div>
          <div class="barra-fundo" role="progressbar" aria-valuenow="{p['seg']}" aria-valuemin="0" aria-valuemax="100">
            <div class="barra-progresso {seg_cls}" style="width:{p['seg']}%"></div>
          </div>
          <div class="card-valor">{ui['card_seg_val'](p)}</div>
          <span class="badge badge-{seg_cls}">{seg_lbl}</span>
        </div>

        <div class="card">
          <div class="card-icone" aria-hidden="true">⭐</div>
          <div class="card-nome">{ui['card_geral']}</div>
          <div class="card-score">{p['score']}<span>/100</span></div>
          <div class="barra-fundo" role="progressbar" aria-valuenow="{p['score']}" aria-valuemin="0" aria-valuemax="100">
            <div class="barra-progresso {sco_cls}" style="width:{p['score']}%"></div>
          </div>
          <div class="card-valor">{ui['card_geral_val'](p)}</div>
          <span class="badge badge-{sco_cls}">{sco_lbl}</span>
        </div>

      </div>
    </section>

    <section class="secao" aria-labelledby="tit-ed">
      <h2 id="tit-ed">{ui['sec_ed_title'](p)}</h2>
      <div class="prosa">
        {intro_para}<h3>{ui['h3_rent'](p)}</h3>
        <p>{p_rent}</p>
        <h3>{ui['h3_safe'](p)}</h3>
        <p>{p_safe}</p>
        <h3>{ui['h3_life']}</h3>
        <p>{p_life}</p>
      </div>
    </section>

    <section class="secao" aria-labelledby="tit-tab">
      <h2 id="tit-tab">{ui['sec_tab_title'](p)}</h2>
      <p class="secao-intro">{ui['sec_tab_sub']}</p>
      <div class="prosa" style="padding:0;overflow:hidden;">
        <table class="tabela-dados" aria-label="{esc(p['nome'])}">
          <thead><tr>{th_row}</tr></thead>
          <tbody>
            {tr(ui['tr_arr'](p, arr))}
            {tr(ui['tr_t2'](p))}
            {tr(ui['tr_seg'](p))}
            {tr(ui['tr_geral'](p))}
            {tr(ui['tr_pop'](p))}
            <tr><td colspan="4" style="color:var(--cinza-texto);font-style:italic;font-size:0.82rem">{ui['tr_pending']}</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="cta-relatorio" role="complementary">
      <h2>{ui['cta_title'](p)}</h2>
      <p>{ui['cta_sub']}</p>
      <a href="{relatorio_url}" class="btn-principal">{ui['cta_btn']}</a>
      <a href="{comparar_url}" class="btn-secundario">{ui['cta_btn2']}</a>
    </div>

    <aside class="outras-freguesias" aria-label="{ui['other_title']}">
      <h3>{ui['other_title']}</h3>
      <div class="links-lista">
        {other_links_html(p['slug'], lang, all_parishes)}
      </div>
    </aside>

  </main>

  <footer>
    <p><a href="https://melhorzona.pt">Melhor Zona</a> · {ui['footer_copy']}</p>
    <p class="footer-fonte">
      {ui['footer_data']} ·
      <a href="https://melhorzona.pt/privacidade.html">{ui['privacy']}</a>
    </p>
  </footer>

</body>
</html>"""
    return html

# ─────────────────────────────────────────────────────────────────────────────
# SITEMAP
# ─────────────────────────────────────────────────────────────────────────────

def actualizar_sitemap(parishes):
    """Regenera sitemap.xml com todas as guias geradas"""
    sitemap_path = os.path.join(BASE, 'sitemap.xml')
    hoje = '2026-06-08'

    principais = f"""  <!-- Páginas principais -->
  <url>
    <loc>https://melhorzona.pt/</loc>
    <lastmod>{hoje}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://melhorzona.pt/imobiliarias.html</loc>
    <lastmod>{hoje}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://melhorzona.pt/privacidade.html</loc>
    <lastmod>{hoje}</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
  </url>"""

    guias_xml = '\n  <!-- Guias de freguesia -->'
    for p in parishes:
        sl = p['slug']
        for lang, prio in [('pt','0.9'),('br','0.8'),('en','0.8')]:
            guias_xml += f"""
  <url>
    <loc>https://melhorzona.pt/guias/{lang}/{sl}.html</loc>
    <lastmod>{hoje}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{prio}</priority>
    <xhtml:link rel="alternate" hreflang="pt-PT" href="https://melhorzona.pt/guias/pt/{sl}.html"/>
    <xhtml:link rel="alternate" hreflang="pt-BR" href="https://melhorzona.pt/guias/br/{sl}.html"/>
    <xhtml:link rel="alternate" hreflang="en"    href="https://melhorzona.pt/guias/en/{sl}.html"/>
  </url>"""

    conteudo = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">

{principais}
{guias_xml}

</urlset>
"""
    with open(sitemap_path, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    print(f'  sitemap.xml actualizado — {3 + len(parishes) * 3} URLs')

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Gera guias estáticos de freguesia (PT · BR · EN)')
    parser.add_argument('--supabase', action='store_true',
        help='Busca top --limite freguesias por população (requer SUPABASE_URL + SUPABASE_KEY)')
    parser.add_argument('--limite', type=int, default=100,
        help='Número de freguesias a gerar com --supabase (padrão: 100)')
    args = parser.parse_args()

    if args.supabase:
        supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        supabase_key = os.environ.get('SUPABASE_KEY', '')
        if not supabase_url or not supabase_key:
            print('Erro: SUPABASE_URL e SUPABASE_KEY são obrigatórios com --supabase')
            print('  export SUPABASE_URL=https://hkxdmregnsmsbxvpykul.supabase.co')
            print('  export SUPABASE_KEY=seu_service_role_key')
            print('  python3 data/generate-guias.py --supabase')
            return
        print(f'A buscar top {args.limite} freguesias no Supabase...')
        rows = fetch_supabase(supabase_url, supabase_key, limit=args.limite)
        print(f'  {len(rows)} freguesias encontradas')
        parishes = []
        for row in rows:
            slug   = slugify(row.get('nome') or '')
            manual = PARISHES_MANUAIS.get(slug)
            parishes.append(build_parish_from_row(row, manual))
    else:
        parishes = PARISHES

    total = 0
    for lang in ['pt', 'br', 'en']:
        d = os.path.join(BASE, 'guias', lang)
        os.makedirs(d, exist_ok=True)
        for p in parishes:
            html = generate(p, lang, parishes)
            path = os.path.join(d, f"{p['slug']}.html")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f'  ✓  guias/{lang}/{p["slug"]}.html')
            total += 1

    actualizar_sitemap(parishes)
    print(f'\n{total} ficheiros gerados.')

if __name__ == '__main__':
    main()
