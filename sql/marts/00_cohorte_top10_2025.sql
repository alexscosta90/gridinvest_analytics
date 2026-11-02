CREATE TABLE marts.cohorte_top10_2025 AS
WITH ucs_dezembro AS (
    SELECT
        NumCNPJ AS cnpj,
        CAST(SUM(QtdUCAtiva) AS BIGINT) AS uc_dez_2025
    FROM refined.indger_comerciais
    WHERE DatReferenciaInformada = DATE '2025-12-01'
    GROUP BY NumCNPJ
    HAVING COUNT(QtdUCAtiva) > 0
),
ordenadas AS (
    SELECT
        CAST(
            ROW_NUMBER() OVER (ORDER BY uc_dez_2025 DESC, cnpj ASC)
            AS INTEGER
        ) AS posicao,
        cnpj,
        uc_dez_2025
    FROM ucs_dezembro
)
SELECT posicao, cnpj, uc_dez_2025
FROM ordenadas
WHERE posicao <= 10
ORDER BY posicao;

