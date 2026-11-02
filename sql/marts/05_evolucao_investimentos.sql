CREATE OR REPLACE TEMP TABLE _mart05_pdd_cnpj_ano AS
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
    CASE
        WHEN COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'invalid') > 0
            THEN 'invalid'
        WHEN COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'valid') = 0
         AND COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'null') > 0
            THEN 'null'
        WHEN COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'null') > 0
            THEN 'partial'
        ELSE 'valid'
    END AS status_total_planejado,
    SUM(VlrTotalRealizado)
        FILTER (WHERE VlrTotalRealizado_status = 'valid')
        AS total_realizado,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'valid')
        AS qtd_realizados_validos,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'null')
        AS qtd_realizados_nulos,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'invalid')
        AS qtd_realizados_invalidos,
    CASE
        WHEN COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'invalid') > 0
            THEN 'invalid'
        WHEN COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'valid') = 0
         AND COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'null') > 0
            THEN 'null'
        WHEN COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'null') > 0
            THEN 'partial'
        ELSE 'valid'
    END AS status_total_realizado
FROM refined.pdd
WHERE AnoReferencia BETWEEN 2022 AND 2025
GROUP BY NumCPFCNPJ, AnoReferencia;

CREATE OR REPLACE TABLE marts.evolucao_investimentos_distribuidora AS
WITH serie_com_coorte AS (
    SELECT
        p.*,
        EXISTS (
            SELECT 1
            FROM marts.cohorte_top10_2025 AS t
            WHERE t.cnpj = p.cnpj
        ) AS top10_2025
    FROM _mart05_pdd_cnpj_ano AS p
),
serie_anterior AS (
    SELECT
        *,
        LAG(ano_referencia) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS ano_anterior,
        LAG(total_planejado) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS total_planejado_ano_anterior,
        LAG(status_total_planejado) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS status_planejado_ano_anterior,
        LAG(total_realizado) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS total_realizado_ano_anterior,
        LAG(status_total_realizado) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS status_realizado_ano_anterior
    FROM serie_com_coorte
),
status_variacoes AS (
    SELECT
        *,
        CASE
            WHEN ano_anterior IS NULL THEN 'ano_anterior_ausente'
            WHEN ano_anterior <> ano_referencia - 1
                THEN 'ano_intermediario_ausente'
            WHEN status_total_planejado <> 'valid'
                THEN 'valor_atual_' || status_total_planejado
            WHEN status_planejado_ano_anterior <> 'valid'
                THEN 'valor_anterior_' || status_planejado_ano_anterior
            ELSE 'valid'
        END AS status_variacao_planejado_absoluta,
        CASE
            WHEN ano_anterior IS NULL THEN 'ano_anterior_ausente'
            WHEN ano_anterior <> ano_referencia - 1
                THEN 'ano_intermediario_ausente'
            WHEN status_total_realizado <> 'valid'
                THEN 'valor_atual_' || status_total_realizado
            WHEN status_realizado_ano_anterior <> 'valid'
                THEN 'valor_anterior_' || status_realizado_ano_anterior
            ELSE 'valid'
        END AS status_variacao_realizado_absoluta
    FROM serie_anterior
),
com_status_percentual AS (
    SELECT
        *,
        CASE
            WHEN status_variacao_planejado_absoluta <> 'valid'
                THEN status_variacao_planejado_absoluta
            WHEN total_planejado_ano_anterior = 0 THEN 'base_zero'
            ELSE 'valid'
        END AS status_variacao_planejado_percentual,
        CASE
            WHEN status_variacao_realizado_absoluta <> 'valid'
                THEN status_variacao_realizado_absoluta
            WHEN total_realizado_ano_anterior = 0 THEN 'base_zero'
            ELSE 'valid'
        END AS status_variacao_realizado_percentual
    FROM status_variacoes
)
SELECT
    cnpj,
    ano_referencia,
    top10_2025,
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
    ano_anterior,
    total_planejado_ano_anterior,
    CASE
        WHEN status_variacao_planejado_absoluta = 'valid'
        THEN total_planejado - total_planejado_ano_anterior
        ELSE NULL
    END AS variacao_planejado_absoluta,
    status_variacao_planejado_absoluta,
    CASE
        WHEN status_variacao_planejado_percentual = 'valid'
        THEN ROUND(
            100.0 * (total_planejado - total_planejado_ano_anterior)
                / total_planejado_ano_anterior,
            2
        )::DECIMAL(18, 2)
        ELSE NULL
    END AS variacao_planejado_percentual,
    status_variacao_planejado_percentual,
    total_realizado_ano_anterior,
    CASE
        WHEN status_variacao_realizado_absoluta = 'valid'
        THEN total_realizado - total_realizado_ano_anterior
        ELSE NULL
    END AS variacao_realizado_absoluta,
    status_variacao_realizado_absoluta,
    CASE
        WHEN status_variacao_realizado_percentual = 'valid'
        THEN ROUND(
            100.0 * (total_realizado - total_realizado_ano_anterior)
                / total_realizado_ano_anterior,
            2
        )::DECIMAL(18, 2)
        ELSE NULL
    END AS variacao_realizado_percentual,
    status_variacao_realizado_percentual
FROM com_status_percentual
WHERE ano_referencia BETWEEN 2023 AND 2025
ORDER BY ano_referencia, cnpj;

CREATE OR REPLACE TABLE marts.evolucao_investimentos_agregada AS
WITH pdd_por_ano_escopo AS (
    SELECT
        ano_referencia,
        'nacional' AS escopo,
        SUM(qtd_registros_pdd) AS qtd_registros_pdd,
        COUNT(*) AS qtd_cnpjs,
        SUM(total_planejado) AS total_planejado,
        SUM(qtd_planejados_validos) AS qtd_planejados_validos,
        SUM(qtd_planejados_nulos) AS qtd_planejados_nulos,
        SUM(qtd_planejados_invalidos) AS qtd_planejados_invalidos,
        CASE
            WHEN SUM(qtd_planejados_invalidos) > 0 THEN 'invalid'
            WHEN SUM(qtd_planejados_validos) = 0
             AND SUM(qtd_planejados_nulos) > 0 THEN 'null'
            WHEN SUM(qtd_planejados_nulos) > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_planejado,
        SUM(total_realizado) AS total_realizado,
        SUM(qtd_realizados_validos) AS qtd_realizados_validos,
        SUM(qtd_realizados_nulos) AS qtd_realizados_nulos,
        SUM(qtd_realizados_invalidos) AS qtd_realizados_invalidos,
        CASE
            WHEN SUM(qtd_realizados_invalidos) > 0 THEN 'invalid'
            WHEN SUM(qtd_realizados_validos) = 0
             AND SUM(qtd_realizados_nulos) > 0 THEN 'null'
            WHEN SUM(qtd_realizados_nulos) > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_realizado
    FROM _mart05_pdd_cnpj_ano
    GROUP BY ano_referencia

    UNION ALL

    SELECT
        p.ano_referencia,
        'top10' AS escopo,
        SUM(p.qtd_registros_pdd) AS qtd_registros_pdd,
        COUNT(*) AS qtd_cnpjs,
        SUM(p.total_planejado) AS total_planejado,
        SUM(p.qtd_planejados_validos) AS qtd_planejados_validos,
        SUM(p.qtd_planejados_nulos) AS qtd_planejados_nulos,
        SUM(p.qtd_planejados_invalidos) AS qtd_planejados_invalidos,
        CASE
            WHEN SUM(p.qtd_planejados_invalidos) > 0 THEN 'invalid'
            WHEN SUM(p.qtd_planejados_validos) = 0
             AND SUM(p.qtd_planejados_nulos) > 0 THEN 'null'
            WHEN SUM(p.qtd_planejados_nulos) > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_planejado,
        SUM(p.total_realizado) AS total_realizado,
        SUM(p.qtd_realizados_validos) AS qtd_realizados_validos,
        SUM(p.qtd_realizados_nulos) AS qtd_realizados_nulos,
        SUM(p.qtd_realizados_invalidos) AS qtd_realizados_invalidos,
        CASE
            WHEN SUM(p.qtd_realizados_invalidos) > 0 THEN 'invalid'
            WHEN SUM(p.qtd_realizados_validos) = 0
             AND SUM(p.qtd_realizados_nulos) > 0 THEN 'null'
            WHEN SUM(p.qtd_realizados_nulos) > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_realizado
    FROM _mart05_pdd_cnpj_ano AS p
    INNER JOIN marts.cohorte_top10_2025 AS t ON p.cnpj = t.cnpj
    GROUP BY p.ano_referencia
),
serie_anterior AS (
    SELECT
        *,
        LAG(ano_referencia) OVER (
            PARTITION BY escopo ORDER BY ano_referencia
        ) AS ano_anterior,
        LAG(total_planejado) OVER (
            PARTITION BY escopo ORDER BY ano_referencia
        ) AS total_planejado_ano_anterior,
        LAG(status_total_planejado) OVER (
            PARTITION BY escopo ORDER BY ano_referencia
        ) AS status_planejado_ano_anterior,
        LAG(total_realizado) OVER (
            PARTITION BY escopo ORDER BY ano_referencia
        ) AS total_realizado_ano_anterior,
        LAG(status_total_realizado) OVER (
            PARTITION BY escopo ORDER BY ano_referencia
        ) AS status_realizado_ano_anterior
    FROM pdd_por_ano_escopo
),
status_variacoes AS (
    SELECT
        *,
        CASE
            WHEN ano_anterior IS NULL THEN 'ano_anterior_ausente'
            WHEN ano_anterior <> ano_referencia - 1
                THEN 'ano_intermediario_ausente'
            WHEN status_total_planejado <> 'valid'
                THEN 'valor_atual_' || status_total_planejado
            WHEN status_planejado_ano_anterior <> 'valid'
                THEN 'valor_anterior_' || status_planejado_ano_anterior
            ELSE 'valid'
        END AS status_variacao_planejado_absoluta,
        CASE
            WHEN ano_anterior IS NULL THEN 'ano_anterior_ausente'
            WHEN ano_anterior <> ano_referencia - 1
                THEN 'ano_intermediario_ausente'
            WHEN status_total_realizado <> 'valid'
                THEN 'valor_atual_' || status_total_realizado
            WHEN status_realizado_ano_anterior <> 'valid'
                THEN 'valor_anterior_' || status_realizado_ano_anterior
            ELSE 'valid'
        END AS status_variacao_realizado_absoluta
    FROM serie_anterior
),
com_status_percentual AS (
    SELECT
        *,
        CASE
            WHEN status_variacao_planejado_absoluta <> 'valid'
                THEN status_variacao_planejado_absoluta
            WHEN total_planejado_ano_anterior = 0 THEN 'base_zero'
            ELSE 'valid'
        END AS status_variacao_planejado_percentual,
        CASE
            WHEN status_variacao_realizado_absoluta <> 'valid'
                THEN status_variacao_realizado_absoluta
            WHEN total_realizado_ano_anterior = 0 THEN 'base_zero'
            ELSE 'valid'
        END AS status_variacao_realizado_percentual
    FROM status_variacoes
)
SELECT
    ano_referencia,
    escopo,
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
    ano_anterior,
    total_planejado_ano_anterior,
    CASE
        WHEN status_variacao_planejado_absoluta = 'valid'
        THEN total_planejado - total_planejado_ano_anterior
        ELSE NULL
    END AS variacao_planejado_absoluta,
    status_variacao_planejado_absoluta,
    CASE
        WHEN status_variacao_planejado_percentual = 'valid'
        THEN ROUND(
            100.0 * (total_planejado - total_planejado_ano_anterior)
                / total_planejado_ano_anterior,
            2
        )::DECIMAL(18, 2)
        ELSE NULL
    END AS variacao_planejado_percentual,
    status_variacao_planejado_percentual,
    total_realizado_ano_anterior,
    CASE
        WHEN status_variacao_realizado_absoluta = 'valid'
        THEN total_realizado - total_realizado_ano_anterior
        ELSE NULL
    END AS variacao_realizado_absoluta,
    status_variacao_realizado_absoluta,
    CASE
        WHEN status_variacao_realizado_percentual = 'valid'
        THEN ROUND(
            100.0 * (total_realizado - total_realizado_ano_anterior)
                / total_realizado_ano_anterior,
            2
        )::DECIMAL(18, 2)
        ELSE NULL
    END AS variacao_realizado_percentual,
    status_variacao_realizado_percentual
FROM com_status_percentual
WHERE ano_referencia BETWEEN 2023 AND 2025
ORDER BY ano_referencia, escopo;

DROP TABLE _mart05_pdd_cnpj_ano;
