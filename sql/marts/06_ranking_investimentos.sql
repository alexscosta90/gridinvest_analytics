CREATE OR REPLACE TEMP TABLE _mart06_pdd_cnpj_ano AS
WITH pdd_agregado AS (
    SELECT
        NumCPFCNPJ AS cnpj,
        AnoReferencia AS ano_referencia,
        COUNT(*) AS qtd_registros_pdd,
        SUM(VlrTotalPlanejado)
            FILTER (WHERE VlrTotalPlanejado_status = 'valid')
            AS total_planejado,
        COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'valid')
            AS qtd_planejados_validos,
        COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'null')
            AS qtd_planejados_nulos,
        COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'invalid')
            AS qtd_planejados_invalidos,
        SUM(VlrTotalRealizado)
            FILTER (WHERE VlrTotalRealizado_status = 'valid')
            AS total_realizado,
        COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'valid')
            AS qtd_realizados_validos,
        COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'null')
            AS qtd_realizados_nulos,
        COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'invalid')
            AS qtd_realizados_invalidos
    FROM refined.pdd
    WHERE AnoReferencia BETWEEN 2023 AND 2025
    GROUP BY NumCPFCNPJ, AnoReferencia
), aliases_pdd AS (
    SELECT
        NumCPFCNPJ AS cnpj,
        AnoReferencia AS ano_referencia,
        STRING_AGG(DISTINCT NULLIF(TRIM(SigAgente), ''), ' | ' ORDER BY NULLIF(TRIM(SigAgente), '')) AS rotulo_pdd
    FROM refined.pdd
    WHERE AnoReferencia BETWEEN 2023 AND 2025
      AND NULLIF(TRIM(SigAgente), '') IS NOT NULL
    GROUP BY NumCPFCNPJ, AnoReferencia
), aliases_indger AS (
    SELECT
        NumCNPJ AS cnpj,
        STRING_AGG(DISTINCT NULLIF(TRIM(NomAgente), ''), ' | ' ORDER BY NULLIF(TRIM(NomAgente), '')) AS rotulo_indger
    FROM refined.indger_comerciais
    WHERE DatReferenciaInformada = DATE '2025-12-01'
      AND NULLIF(TRIM(NomAgente), '') IS NOT NULL
    GROUP BY NumCNPJ
)
SELECT
    p.*,
    CASE
        WHEN p.qtd_planejados_invalidos > 0 THEN 'invalid'
        WHEN p.qtd_planejados_validos = 0 AND p.qtd_planejados_nulos > 0 THEN 'null'
        WHEN p.qtd_planejados_nulos > 0 THEN 'partial'
        ELSE 'valid'
    END AS status_total_planejado,
    CASE
        WHEN p.qtd_realizados_invalidos > 0 THEN 'invalid'
        WHEN p.qtd_realizados_validos = 0 AND p.qtd_realizados_nulos > 0 THEN 'null'
        WHEN p.qtd_realizados_nulos > 0 THEN 'partial'
        ELSE 'valid'
    END AS status_total_realizado,
    ap.rotulo_pdd,
    ai.rotulo_indger,
    EXISTS (
        SELECT 1 FROM marts.cohorte_top10_2025 AS c WHERE c.cnpj = p.cnpj
    ) AS top10_2025
FROM pdd_agregado AS p
LEFT JOIN aliases_pdd AS ap
    ON p.cnpj = ap.cnpj AND p.ano_referencia = ap.ano_referencia
LEFT JOIN aliases_indger AS ai
    ON p.cnpj = ai.cnpj;

CREATE OR REPLACE TEMP TABLE _mart06_por_escopo AS
SELECT a.*, 'nacional' AS escopo
FROM _mart06_pdd_cnpj_ano AS a

UNION ALL

SELECT a.*, 'top10' AS escopo
FROM _mart06_pdd_cnpj_ano AS a
INNER JOIN marts.cohorte_top10_2025 AS c ON a.cnpj = c.cnpj;

CREATE OR REPLACE TEMP TABLE _mart06_medidas AS
SELECT
    ano_referencia,
    cnpj,
    escopo,
    'planejado' AS medida,
    total_planejado AS valor_investimento,
    status_total_planejado AS status_valor,
    qtd_registros_pdd,
    qtd_planejados_validos AS qtd_valores_validos,
    qtd_planejados_nulos AS qtd_valores_nulos,
    qtd_planejados_invalidos AS qtd_valores_invalidos,
    rotulo_pdd,
    rotulo_indger,
    top10_2025
FROM _mart06_por_escopo

UNION ALL

SELECT
    ano_referencia,
    cnpj,
    escopo,
    'realizado' AS medida,
    total_realizado AS valor_investimento,
    status_total_realizado AS status_valor,
    qtd_registros_pdd,
    qtd_realizados_validos AS qtd_valores_validos,
    qtd_realizados_nulos AS qtd_valores_nulos,
    qtd_realizados_invalidos AS qtd_valores_invalidos,
    rotulo_pdd,
    rotulo_indger,
    top10_2025
FROM _mart06_por_escopo;

CREATE OR REPLACE TABLE marts.ranking_investimentos AS
WITH rankeados AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY ano_referencia, escopo, medida
            ORDER BY valor_investimento DESC, cnpj ASC
        ) AS posicao
    FROM _mart06_medidas
    WHERE status_valor = 'valid'
)
SELECT
    m.ano_referencia,
    m.cnpj,
    m.escopo,
    m.medida,
    m.valor_investimento,
    m.status_valor,
    m.qtd_registros_pdd,
    m.qtd_valores_validos,
    m.qtd_valores_nulos,
    m.qtd_valores_invalidos,
    m.rotulo_pdd,
    m.rotulo_indger,
    m.top10_2025,
    r.posicao
FROM _mart06_medidas AS m
LEFT JOIN rankeados AS r
    ON m.ano_referencia = r.ano_referencia
   AND m.cnpj IS NOT DISTINCT FROM r.cnpj
   AND m.escopo = r.escopo
   AND m.medida = r.medida
ORDER BY m.ano_referencia, m.escopo, m.medida, r.posicao NULLS LAST, m.cnpj;

DROP TABLE _mart06_medidas;
DROP TABLE _mart06_por_escopo;
DROP TABLE _mart06_pdd_cnpj_ano;
