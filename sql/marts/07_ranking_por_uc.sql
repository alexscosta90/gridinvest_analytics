CREATE OR REPLACE TEMP TABLE _mart07_uc_cnpj_ano AS
WITH agregados AS (
    SELECT
        NumCNPJ AS cnpj,
        YEAR(DatReferenciaInformada)::SMALLINT AS ano_referencia,
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
    FROM refined.indger_comerciais
    WHERE MONTH(DatReferenciaInformada) = 12
      AND YEAR(DatReferenciaInformada) BETWEEN 2023 AND 2025
    GROUP BY NumCNPJ, YEAR(DatReferenciaInformada)
), status AS (
    SELECT
        *,
        CASE
            WHEN qtd_uc_invalidas > 0 THEN 'invalid'
            WHEN qtd_uc_nulas > 0 AND qtd_uc_validas > 0 THEN 'partial'
            WHEN qtd_uc_nulas > 0 THEN 'null'
            WHEN qtd_uc_validas = 0 THEN 'invalid'
            WHEN soma_uc_validas = 0 THEN 'zero'
            ELSE 'valid'
        END AS status_cobertura
    FROM agregados
)
SELECT
    cnpj,
    ano_referencia,
    qtd_municipios_dezembro,
    qtd_uc_validas,
    qtd_uc_nulas,
    qtd_uc_invalidas,
    CASE
        WHEN status_cobertura IN ('valid', 'zero')
        THEN soma_uc_validas::BIGINT
        ELSE NULL::BIGINT
    END AS qtd_uc_dezembro,
    status_cobertura
FROM status;

CREATE OR REPLACE TEMP TABLE _mart07_rotulos AS
SELECT
    NumCNPJ AS cnpj,
    YEAR(DatReferenciaInformada)::SMALLINT AS ano_referencia,
    STRING_AGG(
        DISTINCT NULLIF(TRIM(NomAgente), ''),
        ' | ' ORDER BY NULLIF(TRIM(NomAgente), '')
    ) AS rotulo_indger
FROM refined.indger_comerciais
WHERE MONTH(DatReferenciaInformada) = 12
  AND YEAR(DatReferenciaInformada) BETWEEN 2023 AND 2025
  AND NULLIF(TRIM(NomAgente), '') IS NOT NULL
GROUP BY NumCNPJ, YEAR(DatReferenciaInformada);

CREATE OR REPLACE TABLE marts.ranking_por_uc_nacional AS
WITH nacional_com_coorte AS (
    SELECT
        u.*,
        r.rotulo_indger,
        c.posicao AS posicao_coorte_2025,
        c.cnpj IS NOT NULL AS top10_2025
    FROM _mart07_uc_cnpj_ano AS u
    LEFT JOIN _mart07_rotulos AS r
      ON u.cnpj IS NOT DISTINCT FROM r.cnpj
     AND u.ano_referencia = r.ano_referencia
    LEFT JOIN marts.cohorte_top10_2025 AS c ON u.cnpj = c.cnpj
), ranqueado AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY ano_referencia
            ORDER BY qtd_uc_dezembro DESC, cnpj ASC
        ) AS posicao_nacional
    FROM nacional_com_coorte
    WHERE status_cobertura IN ('valid', 'zero') AND cnpj IS NOT NULL
)
SELECT
    n.ano_referencia,
    n.cnpj,
    n.rotulo_indger,
    n.qtd_municipios_dezembro,
    n.qtd_uc_validas,
    n.qtd_uc_nulas,
    n.qtd_uc_invalidas,
    n.qtd_uc_dezembro,
    n.status_cobertura,
    n.posicao_coorte_2025,
    n.top10_2025,
    r.posicao_nacional
FROM nacional_com_coorte AS n
LEFT JOIN ranqueado AS r
  ON n.ano_referencia = r.ano_referencia
 AND n.cnpj IS NOT DISTINCT FROM r.cnpj
ORDER BY n.ano_referencia, r.posicao_nacional NULLS LAST, n.cnpj;

CREATE OR REPLACE TEMP TABLE _mart07_coorte_anos AS
SELECT
    c.posicao AS posicao_coorte_2025,
    c.cnpj,
    a.ano_referencia
FROM marts.cohorte_top10_2025 AS c
CROSS JOIN (
    SELECT 2023::SMALLINT AS ano_referencia
    UNION ALL SELECT 2024::SMALLINT
    UNION ALL SELECT 2025::SMALLINT
) AS a;

CREATE OR REPLACE TEMP TABLE _mart07_top10_base AS
SELECT
    a.ano_referencia,
    a.cnpj,
    r.rotulo_indger,
    COALESCE(u.qtd_municipios_dezembro, 0)::BIGINT
        AS qtd_municipios_dezembro,
    COALESCE(u.qtd_uc_validas, 0)::BIGINT AS qtd_uc_validas,
    COALESCE(u.qtd_uc_nulas, 0)::BIGINT AS qtd_uc_nulas,
    COALESCE(u.qtd_uc_invalidas, 0)::BIGINT AS qtd_uc_invalidas,
    u.qtd_uc_dezembro,
    a.posicao_coorte_2025,
    COALESCE(u.status_cobertura, 'sem_referencia') AS status_cobertura
FROM _mart07_coorte_anos AS a
LEFT JOIN _mart07_uc_cnpj_ano AS u
  ON a.cnpj = u.cnpj AND a.ano_referencia = u.ano_referencia
LEFT JOIN _mart07_rotulos AS r
  ON a.cnpj = r.cnpj AND a.ano_referencia = r.ano_referencia;

CREATE OR REPLACE TABLE marts.ranking_por_uc_top10 AS
WITH serie_anterior AS (
    SELECT
        *,
        LAG(ano_referencia) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS ano_anterior,
        LAG(qtd_uc_dezembro) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS qtd_uc_ano_anterior,
        LAG(status_cobertura) OVER (
            PARTITION BY cnpj ORDER BY ano_referencia
        ) AS status_ano_anterior
    FROM _mart07_top10_base
), variacoes AS (
    SELECT
        *,
        CASE
            WHEN ano_anterior IS NULL THEN 'ano_anterior_ausente'
            WHEN ano_anterior <> ano_referencia - 1
                THEN 'ano_intermediario_ausente'
            WHEN status_cobertura NOT IN ('valid', 'zero')
                THEN 'uc_atual_' || status_cobertura
            WHEN status_ano_anterior NOT IN ('valid', 'zero')
                THEN 'uc_anterior_' || status_ano_anterior
            ELSE 'valid'
        END AS status_variacao_absoluta
    FROM serie_anterior
), rankeado AS (
    SELECT
        cnpj,
        ano_referencia,
        ROW_NUMBER() OVER (
            PARTITION BY ano_referencia
            ORDER BY qtd_uc_dezembro DESC, cnpj ASC
        ) AS posicao_anual
    FROM _mart07_top10_base
    WHERE status_cobertura IN ('valid', 'zero')
), com_variacoes AS (
    SELECT
        *,
        CASE
            WHEN status_variacao_absoluta <> 'valid'
                THEN status_variacao_absoluta
            WHEN qtd_uc_ano_anterior = 0 THEN 'base_zero'
            ELSE 'valid'
        END AS status_variacao_percentual
    FROM variacoes
)
SELECT
    v.ano_referencia,
    v.cnpj,
    v.rotulo_indger,
    v.qtd_municipios_dezembro,
    v.qtd_uc_validas,
    v.qtd_uc_nulas,
    v.qtd_uc_invalidas,
    v.qtd_uc_dezembro,
    v.status_cobertura,
    r.posicao_anual,
    v.posicao_coorte_2025,
    v.ano_anterior,
    v.qtd_uc_ano_anterior,
    CASE
        WHEN v.status_variacao_absoluta = 'valid'
        THEN v.qtd_uc_dezembro - v.qtd_uc_ano_anterior
        ELSE NULL::BIGINT
    END AS variacao_absoluta_uc,
    v.status_variacao_absoluta,
    CASE
        WHEN v.status_variacao_percentual = 'valid'
        THEN ROUND(
            100.0 * (v.qtd_uc_dezembro - v.qtd_uc_ano_anterior)
                / v.qtd_uc_ano_anterior,
            2
        )::DECIMAL(18, 2)
        ELSE NULL::DECIMAL(18, 2)
    END AS variacao_percentual_uc,
    v.status_variacao_percentual
FROM com_variacoes AS v
LEFT JOIN rankeado AS r
  ON v.ano_referencia = r.ano_referencia AND v.cnpj = r.cnpj
ORDER BY v.ano_referencia, r.posicao_anual NULLS LAST, v.cnpj;

DROP TABLE _mart07_top10_base;
DROP TABLE _mart07_coorte_anos;
DROP TABLE _mart07_rotulos;
DROP TABLE _mart07_uc_cnpj_ano;
