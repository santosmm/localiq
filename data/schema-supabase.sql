-- Schema Supabase — tabela freguesias
-- Executar no SQL Editor: https://supabase.com/dashboard/project/hkxdmregnsmsbxvpykul/sql/new

CREATE TABLE IF NOT EXISTS freguesias (
  id                   SERIAL         PRIMARY KEY,

  -- Identificação
  nome                 TEXT           NOT NULL,
  municipio            TEXT           NOT NULL,
  codigo_ine           TEXT           UNIQUE,
  populacao            INTEGER,

  -- Score agregado
  score_geral          NUMERIC(4,1),

  -- Transportes
  transportes_score    NUMERIC(4,1),
  transportes_valor    NUMERIC(10,2),

  -- Qualidade do ar
  ar_score             NUMERIC(4,1),
  ar_valor             NUMERIC(10,2),

  -- Demografia
  demografia_score     NUMERIC(4,1),
  demografia_valor     NUMERIC(10,2),

  -- Ensino
  ensino_score         NUMERIC(4,1),
  ensino_valor         NUMERIC(10,2),

  -- Saúde
  saude_score          NUMERIC(4,1),
  saude_valor          NUMERIC(10,2),

  -- Segurança
  seguranca_score      NUMERIC(4,1),
  seguranca_valor      NUMERIC(10,2),

  -- Arrendamento
  arrendamento_score   NUMERIC(4,1),
  arrendamento_valor   NUMERIC(10,2),

  -- Imobiliário
  rendas_mediana       NUMERIC(10,2),
  preco_avaliacao_m2   NUMERIC(10,2),

  -- Clima (ERA5, média 2015-2024)
  clima_temp_media     NUMERIC(5,2),
  clima_sol_horas      NUMERIC(8,1),
  clima_precipitacao   NUMERIC(8,1),
  clima_score          NUMERIC(4,1),

  -- IA
  resumo_ia            TEXT,

  -- Metadados
  criado_em            TIMESTAMPTZ    DEFAULT NOW(),
  atualizado_em        TIMESTAMPTZ    DEFAULT NOW()
);

-- Índices para pesquisa rápida por nome/município
CREATE INDEX IF NOT EXISTS idx_freguesias_nome
  ON freguesias (LOWER(nome));

CREATE INDEX IF NOT EXISTS idx_freguesias_municipio
  ON freguesias (LOWER(municipio));

CREATE INDEX IF NOT EXISTS idx_freguesias_nome_mun
  ON freguesias (LOWER(nome), LOWER(municipio));

-- Trigger para atualizar atualizado_em automaticamente
CREATE OR REPLACE FUNCTION atualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.atualizado_em = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_freguesias_updated
  BEFORE UPDATE ON freguesias
  FOR EACH ROW EXECUTE FUNCTION atualizar_timestamp();

-- Row Level Security: leitura pública, escrita só com service_role
ALTER TABLE freguesias ENABLE ROW LEVEL SECURITY;

CREATE POLICY "leitura_publica"
  ON freguesias
  FOR SELECT
  USING (true);
