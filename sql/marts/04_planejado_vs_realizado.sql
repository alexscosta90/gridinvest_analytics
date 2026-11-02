CREATE OR REPLACE TEMP TABLE _mart04_pdd_cnpj_ano AS
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
),
aliases_distintos AS (
    SELECT DISTINCT
        NumCPFCNPJ AS cnpj,
        AnoReferencia AS ano_referencia,
        NULLIF(TRIM(SigAgente), '') AS alias_pdd
    FROM refined.pdd
    WHERE AnoReferencia BETWEEN 2023 AND 2025
      AND NULLIF(TRIM(SigAgente), '') IS NOT NULL
),
aliases AS (
    SELECT
        cnpj,
        ano_referencia,
        STRING_AGG(alias_pdd, ' | ' ORDER BY alias_pdd) AS rotulo_pdd
    FROM aliases_distintos
    GROUP BY cnpj, ano_referencia
)
SELECT
    p.*,
    a.rotulo_pdd,
    EXISTS (
        SELECT 1
        FROM marts.cohorte_top10_2025 AS t
        WHERE t.cnpj = p.cnpj
    ) AS top10_2025
FROM pdd_agregado AS p
LEFT JOIN aliases AS a
    ON p.cnpj = a.cnpj AND p.ano_referencia = a.ano_referencia;

CREATE OR REPLACE TABLE marts.planejado_vs_realizado_distribuidora AS
WITH status_financeiro AS (
    SELECT
        *,
        CASE
            WHEN qtd_planejados_invalidos > 0 THEN 'invalid'
            WHEN qtd_planejados_validos = 0 AND qtd_planejados_nulos > 0
                THEN 'null'
            WHEN qtd_planejados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_planejado,
        CASE
            WHEN qtd_realizados_invalidos > 0 THEN 'invalid'
            WHEN qtd_realizados_validos = 0 AND qtd_realizados_nulos > 0
                THEN 'null'
            WHEN qtd_realizados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_realizado
    FROM _mart04_pdd_cnpj_ano
),
status_indicadores AS (
    SELECT
        *,
        CASE
            WHEN status_total_planejado <> 'valid' THEN
                'planejado_' || status_total_planejado
            WHEN total_planejado = 0 THEN 'planejado_zero'
            WHEN total_planejado < 0 THEN 'planejado_nao_positivo'
            WHEN status_total_realizado <> 'valid' THEN
                'realizado_' || status_total_realizado
            ELSE 'valid'
        END AS status_percentuais,
        CASE
            WHEN status_total_planejado = 'valid'
             AND status_total_realizado = 'valid' THEN 'valid'
            WHEN status_total_planejado = 'invalid'
              OR status_total_realizado = 'invalid' THEN 'invalid'
            WHEN status_total_planejado = 'null'
              OR status_total_realizado = 'null' THEN 'null'
            ELSE 'partial'
        END AS status_diferenca
    FROM status_financeiro
)
SELECT
    cnpj,
    rotulo_pdd,
    ano_referencia,
    qtd_registros_pdd,
    total_planejado,
    qtd_planejados_validos,
    qtd_planejados_nulos,
    qtd_planejados_invalidos,
    status_total_planejado,
    total_realizado,
    qtd_realizados_validos,
    qtd_realizados_nulos,
    qtd_realizados_invalidos,
    status_total_realizado,
    CASE
        WHEN status_diferenca = 'valid'
        THEN total_realizado - total_planejado
        ELSE NULL
    END AS diferenca_absoluta,
    status_diferenca,
    CASE
        WHEN status_percentuais = 'valid'
        THEN ROUND(100.0 * total_realizado / total_planejado, 2)
            ::DECIMAL(18, 2)
        ELSE NULL
    END AS percentual_execucao,
    status_percentuais AS status_percentual_execucao,
    CASE
        WHEN status_percentuais = 'valid'
        THEN ROUND(
            100.0 * (total_realizado - total_planejado) / total_planejado,
            2
        )::DECIMAL(18, 2)
        ELSE NULL
    END AS diferenca_percentual,
    status_percentuais AS status_diferenca_percentual,
    top10_2025,
    TRUE AS ano_realizado_completo
FROM status_indicadores
ORDER BY ano_referencia, cnpj;

CREATE OR REPLACE TABLE marts.planejado_vs_realizado_nacional AS
WITH agregado AS (
    SELECT
        ano_referencia,
        SUM(qtd_registros_pdd) AS qtd_registros_pdd,
        COUNT(*) AS qtd_cnpjs,
        SUM(total_planejado) AS total_planejado,
        SUM(qtd_planejados_validos) AS qtd_planejados_validos,
        SUM(qtd_planejados_nulos) AS qtd_planejados_nulos,
        SUM(qtd_planejados_invalidos) AS qtd_planejados_invalidos,
        SUM(total_realizado) AS total_realizado,
        SUM(qtd_realizados_validos) AS qtd_realizados_validos,
        SUM(qtd_realizados_nulos) AS qtd_realizados_nulos,
        SUM(qtd_realizados_invalidos) AS qtd_realizados_invalidos
    FROM _mart04_pdd_cnpj_ano
    GROUP BY ano_referencia
),
status_financeiro AS (
    SELECT
        *,
        CASE
            WHEN qtd_planejados_invalidos > 0 THEN 'invalid'
            WHEN qtd_planejados_validos = 0 AND qtd_planejados_nulos > 0
                THEN 'null'
            WHEN qtd_planejados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_planejado,
        CASE
            WHEN qtd_realizados_invalidos > 0 THEN 'invalid'
            WHEN qtd_realizados_validos = 0 AND qtd_realizados_nulos > 0
                THEN 'null'
            WHEN qtd_realizados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_realizado
    FROM agregado
),
status_indicadores AS (
    SELECT
        *,
        CASE
            WHEN status_total_planejado <> 'valid' THEN
                'planejado_' || status_total_planejado
            WHEN total_planejado = 0 THEN 'planejado_zero'
            WHEN total_planejado < 0 THEN 'planejado_nao_positivo'
            WHEN status_total_realizado <> 'valid' THEN
                'realizado_' || status_total_realizado
            ELSE 'valid'
        END AS status_percentuais,
        CASE
            WHEN status_total_planejado = 'valid'
             AND status_total_realizado = 'valid' THEN 'valid'
            WHEN status_total_planejado = 'invalid'
              OR status_total_realizado = 'invalid' THEN 'invalid'
            WHEN status_total_planejado = 'null'
              OR status_total_realizado = 'null' THEN 'null'
            ELSE 'partial'
        END AS status_diferenca
    FROM status_financeiro
)
SELECT
    ano_referencia,
    qtd_registros_pdd,
    qtd_cnpjs,
    total_planejado,
    qtd_planejados_validos,
    qtd_planejados_nulos,
    qtd_planejados_invalidos,
    status_total_planejado,
    total_realizado,
    qtd_realizados_validos,
    qtd_realizados_nulos,
    qtd_realizados_invalidos,
    status_total_realizado,
    CASE
        WHEN status_diferenca = 'valid'
        THEN total_realizado - total_planejado
        ELSE NULL
    END AS diferenca_absoluta,
    status_diferenca,
    CASE
        WHEN status_percentuais = 'valid'
        THEN ROUND(100.0 * total_realizado / total_planejado, 2)
            ::DECIMAL(18, 2)
        ELSE NULL
    END AS percentual_execucao,
    status_percentuais AS status_percentual_execucao,
    CASE
        WHEN status_percentuais = 'valid'
        THEN ROUND(
            100.0 * (total_realizado - total_planejado) / total_planejado,
            2
        )::DECIMAL(18, 2)
        ELSE NULL
    END AS diferenca_percentual,
    status_percentuais AS status_diferenca_percentual,
    TRUE AS ano_realizado_completo
FROM status_indicadores
ORDER BY ano_referencia;

DROP TABLE _mart04_pdd_cnpj_ano;
