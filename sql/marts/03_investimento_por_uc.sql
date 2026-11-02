CREATE OR REPLACE TABLE marts.investimento_por_uc AS
WITH aliases_pdd_distintos AS (
    SELECT DISTINCT
        NumCPFCNPJ AS cnpj,
        AnoReferencia AS ano_referencia,
        NULLIF(TRIM(SigAgente), '') AS alias_pdd
    FROM refined.pdd
    WHERE AnoReferencia BETWEEN 2023 AND 2025
      AND NULLIF(TRIM(SigAgente), '') IS NOT NULL
),
pdd_aliases AS (
    SELECT
        cnpj,
        ano_referencia,
        STRING_AGG(alias_pdd, ' | ' ORDER BY alias_pdd) AS aliases_pdd
    FROM aliases_pdd_distintos
    GROUP BY cnpj, ano_referencia
),
indger_rotulos_distintos AS (
    SELECT DISTINCT
        NumCNPJ AS cnpj,
        YEAR(DatReferenciaInformada)::SMALLINT AS ano_referencia,
        NULLIF(TRIM(NomAgente), '') AS rotulo_indger
    FROM refined.indger_comerciais
    WHERE MONTH(DatReferenciaInformada) = 12
      AND YEAR(DatReferenciaInformada) BETWEEN 2023 AND 2025
      AND NULLIF(TRIM(NomAgente), '') IS NOT NULL
),
indger_rotulos AS (
    SELECT
        cnpj,
        ano_referencia,
        STRING_AGG(rotulo_indger, ' | ' ORDER BY rotulo_indger)
            AS rotulo_indger
    FROM indger_rotulos_distintos
    GROUP BY cnpj, ano_referencia
),
pdd_por_cnpj_ano AS (
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
uc_municipais_dezembro AS (
    SELECT
        NumCNPJ AS cnpj,
        YEAR(DatReferenciaInformada)::SMALLINT AS ano_referencia,
        CodMunicipioIBGE,
        QtdUCAtiva,
        QtdUCAtiva_status
    FROM refined.indger_comerciais
    WHERE MONTH(DatReferenciaInformada) = 12
      AND YEAR(DatReferenciaInformada) BETWEEN 2023 AND 2025
),
ucs_por_cnpj_ano AS (
    SELECT
        cnpj,
        ano_referencia,
        COUNT(*) AS qtd_municipios_dezembro,
        COUNT(*) FILTER (
            WHERE QtdUCAtiva_status = 'valid' AND QtdUCAtiva IS NOT NULL
        ) AS qtd_uc_validas,
        COUNT(*) FILTER (
            WHERE QtdUCAtiva_status = 'null'
               OR (QtdUCAtiva_status = 'valid' AND QtdUCAtiva IS NULL)
        ) AS qtd_uc_nulas,
        COUNT(*) FILTER (
            WHERE QtdUCAtiva_status = 'invalid'
               OR QtdUCAtiva_status IS NULL
               OR QtdUCAtiva_status NOT IN ('valid', 'null', 'invalid')
        ) AS qtd_uc_invalidas,
        SUM(QtdUCAtiva) FILTER (
            WHERE QtdUCAtiva_status = 'valid' AND QtdUCAtiva IS NOT NULL
        ) AS soma_uc_validas
    FROM uc_municipais_dezembro
    GROUP BY cnpj, ano_referencia
),
ucs_cnpj_ano AS (
    SELECT
        cnpj,
        ano_referencia,
        qtd_municipios_dezembro,
        qtd_uc_validas,
        qtd_uc_nulas,
        qtd_uc_invalidas,
        CASE
            WHEN qtd_uc_validas = qtd_municipios_dezembro
             AND qtd_uc_nulas = 0
             AND qtd_uc_invalidas = 0 THEN soma_uc_validas
            ELSE NULL
        END AS qtd_uc_dezembro,
        CASE
            WHEN qtd_uc_invalidas > 0 THEN 'invalid'
            WHEN qtd_uc_nulas > 0 AND qtd_uc_validas > 0 THEN 'partial'
            WHEN qtd_uc_nulas > 0 THEN 'null'
            WHEN qtd_uc_validas = 0 THEN 'invalid'
            WHEN soma_uc_validas = 0 THEN 'zero'
            ELSE 'valid'
        END AS status_cobertura
    FROM ucs_por_cnpj_ano
),
pdd_por_escopo AS (
    SELECT p.*, 'nacional' AS escopo
    FROM pdd_por_cnpj_ano AS p

    UNION ALL

    SELECT p.*, 'top10' AS escopo
    FROM pdd_por_cnpj_ano AS p
    INNER JOIN marts.cohorte_top10_2025 AS t
        ON p.cnpj = t.cnpj
),
base_unida AS (
    SELECT
        p.ano_referencia,
        p.escopo,
        p.cnpj,
        r.rotulo_indger,
        a.aliases_pdd,
        p.qtd_registros_pdd,
        p.total_planejado,
        p.qtd_planejados_validos,
        p.qtd_planejados_nulos,
        p.qtd_planejados_invalidos,
        CASE
            WHEN p.qtd_planejados_invalidos > 0 THEN 'invalid'
            WHEN p.qtd_planejados_validos = 0 AND p.qtd_planejados_nulos > 0
                THEN 'null'
            WHEN p.qtd_planejados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_planejado,
        p.total_realizado,
        p.qtd_realizados_validos,
        p.qtd_realizados_nulos,
        p.qtd_realizados_invalidos,
        CASE
            WHEN p.qtd_realizados_invalidos > 0 THEN 'invalid'
            WHEN p.qtd_realizados_validos = 0 AND p.qtd_realizados_nulos > 0
                THEN 'null'
            WHEN p.qtd_realizados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_total_realizado,
        u.qtd_municipios_dezembro,
        COALESCE(u.qtd_uc_validas, 0) AS qtd_uc_validas,
        COALESCE(u.qtd_uc_nulas, 0) AS qtd_uc_nulas,
        COALESCE(u.qtd_uc_invalidas, 0) AS qtd_uc_invalidas,
        u.qtd_uc_dezembro,
        COALESCE(u.status_cobertura, 'sem_referencia') AS status_cobertura
    FROM pdd_por_escopo AS p
    LEFT JOIN ucs_cnpj_ano AS u
        ON p.cnpj = u.cnpj AND p.ano_referencia = u.ano_referencia
    LEFT JOIN indger_rotulos AS r
        ON p.cnpj = r.cnpj AND p.ano_referencia = r.ano_referencia
    LEFT JOIN pdd_aliases AS a
        ON p.cnpj = a.cnpj AND p.ano_referencia = a.ano_referencia
),
com_indicadores AS (
    SELECT
        *,
        CASE
            WHEN status_total_planejado <> 'valid' THEN
                'investimento_' || status_total_planejado
            WHEN status_cobertura = 'zero' THEN 'denominador_zero'
            WHEN status_cobertura <> 'valid' THEN 'uc_' || status_cobertura
            ELSE 'valid'
        END AS status_planejado_por_uc,
        CASE
            WHEN status_total_realizado <> 'valid' THEN
                'investimento_' || status_total_realizado
            WHEN status_cobertura = 'zero' THEN 'denominador_zero'
            WHEN status_cobertura <> 'valid' THEN 'uc_' || status_cobertura
            ELSE 'valid'
        END AS status_realizado_por_uc
    FROM base_unida
)
SELECT
    ano_referencia,
    escopo,
    cnpj,
    rotulo_indger,
    aliases_pdd,
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
    qtd_municipios_dezembro,
    qtd_uc_validas,
    qtd_uc_nulas,
    qtd_uc_invalidas,
    qtd_uc_dezembro,
    status_cobertura,
    CASE
        WHEN status_planejado_por_uc = 'valid'
         AND qtd_uc_dezembro > 0
        THEN ROUND(total_planejado / qtd_uc_dezembro, 2)::DECIMAL(18, 2)
        ELSE NULL
    END AS investimento_planejado_por_uc,
    status_planejado_por_uc,
    CASE
        WHEN status_realizado_por_uc = 'valid'
         AND qtd_uc_dezembro > 0
        THEN ROUND(total_realizado / qtd_uc_dezembro, 2)::DECIMAL(18, 2)
        ELSE NULL
    END AS investimento_realizado_por_uc,
    status_realizado_por_uc
FROM com_indicadores
ORDER BY ano_referencia, escopo, cnpj;
