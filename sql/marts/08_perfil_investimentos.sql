CREATE OR REPLACE TEMP TABLE _mart08_pdd_cnpj_ano AS
SELECT
    NumCPFCNPJ AS cnpj,
    AnoReferencia AS ano_referencia,
    COUNT(*) AS qtd_registros_pdd,
    SUM(VlrTotalPlanejado)
        FILTER (WHERE VlrTotalPlanejado_status = 'valid')
        AS total_planejado_cnpj_ano,
    COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'valid')
        AS qtd_planejados_validos,
    COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'null')
        AS qtd_planejados_nulos,
    COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'invalid')
        AS qtd_planejados_invalidos,
    SUM(VlrTotalRealizado)
        FILTER (WHERE VlrTotalRealizado_status = 'valid')
        AS total_realizado_cnpj_ano,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'valid')
        AS qtd_realizados_validos,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'null')
        AS qtd_realizados_nulos,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'invalid')
        AS qtd_realizados_invalidos
FROM refined.pdd
WHERE AnoReferencia BETWEEN 2023 AND 2025
GROUP BY NumCPFCNPJ, AnoReferencia;

CREATE OR REPLACE TEMP TABLE _mart08_pdd_cnpj_ano_tipo_classe AS
SELECT
    NumCPFCNPJ AS cnpj,
    AnoReferencia AS ano_referencia,
    DscTipoObra AS tipo_obra,
    DscTipoObraClasse AS classe_obra,
    COUNT(*) AS qtd_registros_pdd,
    SUM(VlrTotalPlanejado)
        FILTER (WHERE VlrTotalPlanejado_status = 'valid') AS total_planejado,
    COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'valid')
        AS qtd_planejados_validos,
    COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'null')
        AS qtd_planejados_nulos,
    COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'invalid')
        AS qtd_planejados_invalidos,
    SUM(VlrTotalRealizado)
        FILTER (WHERE VlrTotalRealizado_status = 'valid') AS total_realizado,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'valid')
        AS qtd_realizados_validos,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'null')
        AS qtd_realizados_nulos,
    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'invalid')
        AS qtd_realizados_invalidos
FROM refined.pdd
WHERE AnoReferencia BETWEEN 2023 AND 2025
GROUP BY NumCPFCNPJ, AnoReferencia, DscTipoObra, DscTipoObraClasse;

CREATE OR REPLACE TEMP TABLE _mart08_rotulos_pdd AS
SELECT
    NumCPFCNPJ AS cnpj,
    AnoReferencia AS ano_referencia,
    STRING_AGG(
        DISTINCT NULLIF(TRIM(SigAgente), ''),
        ' | ' ORDER BY NULLIF(TRIM(SigAgente), '')
    ) AS rotulo_pdd
FROM refined.pdd
WHERE AnoReferencia BETWEEN 2023 AND 2025
  AND NULLIF(TRIM(SigAgente), '') IS NOT NULL
GROUP BY NumCPFCNPJ, AnoReferencia;

CREATE OR REPLACE TABLE marts.perfil_investimentos AS
WITH denominadores_com_status AS (
    SELECT
        *,
        CASE
            WHEN qtd_planejados_invalidos > 0 THEN 'invalid'
            WHEN qtd_planejados_validos = 0 AND qtd_planejados_nulos > 0
                THEN 'null'
            WHEN qtd_planejados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_denominador_planejado,
        CASE
            WHEN qtd_realizados_invalidos > 0 THEN 'invalid'
            WHEN qtd_realizados_validos = 0 AND qtd_realizados_nulos > 0
                THEN 'null'
            WHEN qtd_realizados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_denominador_realizado
    FROM _mart08_pdd_cnpj_ano
), denominadores_por_escopo AS (
    SELECT d.*, 'nacional' AS escopo
    FROM denominadores_com_status AS d

    UNION ALL

    SELECT d.*, 'top10' AS escopo
    FROM denominadores_com_status AS d
    INNER JOIN marts.cohorte_top10_2025 AS c ON d.cnpj = c.cnpj
), detalhes_com_status AS (
    SELECT
        d.*,
        CASE
            WHEN qtd_planejados_invalidos > 0 THEN 'invalid'
            WHEN qtd_planejados_validos = 0 AND qtd_planejados_nulos > 0
                THEN 'null'
            WHEN qtd_planejados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_investimento_planejado,
        CASE
            WHEN qtd_realizados_invalidos > 0 THEN 'invalid'
            WHEN qtd_realizados_validos = 0 AND qtd_realizados_nulos > 0
                THEN 'null'
            WHEN qtd_realizados_nulos > 0 THEN 'partial'
            ELSE 'valid'
        END AS status_investimento_realizado
    FROM _mart08_pdd_cnpj_ano_tipo_classe AS d
), detalhes_por_escopo AS (
    SELECT d.*, 'nacional' AS escopo
    FROM detalhes_com_status AS d

    UNION ALL

    SELECT d.*, 'top10' AS escopo
    FROM detalhes_com_status AS d
    INNER JOIN marts.cohorte_top10_2025 AS c ON d.cnpj = c.cnpj
), rotulos_por_escopo AS (
    SELECT r.*, 'nacional' AS escopo
    FROM _mart08_rotulos_pdd AS r

    UNION ALL

    SELECT r.*, 'top10' AS escopo
    FROM _mart08_rotulos_pdd AS r
    INNER JOIN marts.cohorte_top10_2025 AS c ON r.cnpj = c.cnpj
), com_denominadores AS (
    SELECT
        d.*,
        n.total_planejado_cnpj_ano,
        n.status_denominador_planejado,
        n.total_realizado_cnpj_ano,
        n.status_denominador_realizado,
        r.rotulo_pdd
    FROM detalhes_por_escopo AS d
    INNER JOIN denominadores_por_escopo AS n
      ON d.cnpj IS NOT DISTINCT FROM n.cnpj
     AND d.ano_referencia = n.ano_referencia
     AND d.escopo = n.escopo
    LEFT JOIN rotulos_por_escopo AS r
      ON d.cnpj IS NOT DISTINCT FROM r.cnpj
     AND d.ano_referencia = r.ano_referencia
     AND d.escopo = r.escopo
), status_participacoes AS (
    SELECT
        *,
        CASE
            WHEN status_denominador_planejado <> 'valid'
                THEN 'denominador_' || status_denominador_planejado
            WHEN total_planejado_cnpj_ano = 0 THEN 'denominador_zero'
            WHEN status_investimento_planejado <> 'valid'
                THEN 'valor_' || status_investimento_planejado
            ELSE 'valid'
        END AS status_participacao_planejado,
        CASE
            WHEN status_denominador_realizado <> 'valid'
                THEN 'denominador_' || status_denominador_realizado
            WHEN total_realizado_cnpj_ano = 0 THEN 'denominador_zero'
            WHEN status_investimento_realizado <> 'valid'
                THEN 'valor_' || status_investimento_realizado
            ELSE 'valid'
        END AS status_participacao_realizado
    FROM com_denominadores
)
SELECT
    escopo,
    cnpj,
    rotulo_pdd,
    ano_referencia,
    tipo_obra,
    CASE
        WHEN tipo_obra IS NULL THEN 'nula'
        WHEN TRIM(tipo_obra) = '' THEN 'vazia'
        ELSE 'preenchida'
    END AS status_tipo_obra,
    classe_obra,
    CASE
        WHEN classe_obra IS NULL THEN 'nula'
        WHEN TRIM(classe_obra) = '' THEN 'vazia'
        ELSE 'preenchida'
    END AS status_classe_obra,
    qtd_registros_pdd,
    total_planejado,
    qtd_planejados_validos,
    qtd_planejados_nulos,
    qtd_planejados_invalidos,
    status_investimento_planejado,
    total_realizado,
    qtd_realizados_validos,
    qtd_realizados_nulos,
    qtd_realizados_invalidos,
    status_investimento_realizado,
    CASE
        WHEN status_participacao_planejado = 'valid'
        THEN ROUND(
            100.0 * total_planejado / total_planejado_cnpj_ano,
            2
        )::DECIMAL(18, 2)
        ELSE NULL::DECIMAL(18, 2)
    END AS participacao_planejado_percentual,
    status_participacao_planejado,
    CASE
        WHEN status_participacao_realizado = 'valid'
        THEN ROUND(
            100.0 * total_realizado / total_realizado_cnpj_ano,
            2
        )::DECIMAL(18, 2)
        ELSE NULL::DECIMAL(18, 2)
    END AS participacao_realizado_percentual,
    status_participacao_realizado
FROM status_participacoes
ORDER BY escopo, ano_referencia, cnpj, tipo_obra, classe_obra;

DROP TABLE _mart08_rotulos_pdd;
DROP TABLE _mart08_pdd_cnpj_ano_tipo_classe;
DROP TABLE _mart08_pdd_cnpj_ano;
