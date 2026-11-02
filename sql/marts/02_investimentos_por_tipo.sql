CREATE OR REPLACE TABLE marts.investimentos_por_tipo AS
WITH pdd_cnpj_ano_tipo AS (
    SELECT
        NumCPFCNPJ AS cnpj,
        AnoReferencia AS ano_referencia,
        DscTipoObra AS tipo_obra,
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
    GROUP BY NumCPFCNPJ, AnoReferencia, DscTipoObra
),
por_escopo AS (
    SELECT
        ano_referencia,
        'nacional' AS escopo,
        tipo_obra,
        COUNT(*) AS qtd_cnpjs,
        SUM(qtd_registros_pdd) AS qtd_registros_pdd,
        SUM(total_planejado) AS total_planejado,
        SUM(qtd_planejados_validos) AS qtd_planejados_validos,
        SUM(qtd_planejados_nulos) AS qtd_planejados_nulos,
        SUM(qtd_planejados_invalidos) AS qtd_planejados_invalidos,
        SUM(total_realizado) AS total_realizado,
        SUM(qtd_realizados_validos) AS qtd_realizados_validos,
        SUM(qtd_realizados_nulos) AS qtd_realizados_nulos,
        SUM(qtd_realizados_invalidos) AS qtd_realizados_invalidos
    FROM pdd_cnpj_ano_tipo
    GROUP BY ano_referencia, tipo_obra

    UNION ALL

    SELECT
        p.ano_referencia,
        'top10' AS escopo,
        p.tipo_obra,
        COUNT(*) AS qtd_cnpjs,
        SUM(p.qtd_registros_pdd) AS qtd_registros_pdd,
        SUM(p.total_planejado) AS total_planejado,
        SUM(p.qtd_planejados_validos) AS qtd_planejados_validos,
        SUM(p.qtd_planejados_nulos) AS qtd_planejados_nulos,
        SUM(p.qtd_planejados_invalidos) AS qtd_planejados_invalidos,
        SUM(p.total_realizado) AS total_realizado,
        SUM(p.qtd_realizados_validos) AS qtd_realizados_validos,
        SUM(p.qtd_realizados_nulos) AS qtd_realizados_nulos,
        SUM(p.qtd_realizados_invalidos) AS qtd_realizados_invalidos
    FROM pdd_cnpj_ano_tipo AS p
    INNER JOIN marts.cohorte_top10_2025 AS t
        ON p.cnpj = t.cnpj
    GROUP BY p.ano_referencia, p.tipo_obra
)
SELECT
    ano_referencia,
    escopo,
    tipo_obra,
    CASE
        WHEN tipo_obra IS NULL OR TRIM(tipo_obra) = '' THEN 'sem_tipo'
        WHEN LOWER(TRIM(tipo_obra)) = LOWER('Expansão') THEN 'expansao'
        WHEN LOWER(TRIM(tipo_obra)) = LOWER('Melhoria') THEN 'melhoria'
        WHEN LOWER(TRIM(tipo_obra)) = LOWER('Renovação') THEN 'renovacao'
        ELSE 'outras'
    END AS categoria_tipo_obra,
    qtd_cnpjs,
    qtd_registros_pdd,
    total_planejado,
    qtd_planejados_validos,
    qtd_planejados_nulos,
    qtd_planejados_invalidos,
    CASE
        WHEN qtd_planejados_invalidos > 0 THEN 'invalid'
        WHEN qtd_planejados_validos = 0 AND qtd_planejados_nulos > 0 THEN 'null'
        WHEN qtd_planejados_nulos > 0 THEN 'partial'
        ELSE 'valid'
    END AS status_total_planejado,
    total_realizado,
    qtd_realizados_validos,
    qtd_realizados_nulos,
    qtd_realizados_invalidos,
    CASE
        WHEN qtd_realizados_invalidos > 0 THEN 'invalid'
        WHEN qtd_realizados_validos = 0 AND qtd_realizados_nulos > 0 THEN 'null'
        WHEN qtd_realizados_nulos > 0 THEN 'partial'
        ELSE 'valid'
    END AS status_total_realizado
FROM por_escopo
ORDER BY ano_referencia, escopo, tipo_obra;
