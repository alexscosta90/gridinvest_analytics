"""Transformações da camada REFINED."""


from pipeline.db import conectar


def transformar_pdd() -> dict[str, int]:
    """Cria ou substitui refined.pdd a partir de raw.pdd atomicamente.

    Valores que não puderem ser convertidos ficam nulos na coluna tipada,
    com o original preservado em uma coluna ``_raw`` e seu status marcado
    como ``invalid``. Valores vazios são marcados como ``null``.
    """
    with conectar() as con:
        con.execute("BEGIN TRANSACTION")

        try:
            con.execute(
                """
                CREATE TEMP TABLE _pdd_staging AS
                SELECT
                    _id,
                    DatGeracaoConjuntoDados,
                    TRY_CAST(NULLIF(TRIM(DatGeracaoConjuntoDados), '') AS TIMESTAMP)
                        AS DatGeracaoConjuntoDados_typed,
                    SigAgente,
                    NumCPFCNPJ,
                    DscTipoOutorga,
                    SigUF,
                    DscRegiao,
                    AnoReferencia,
                    TRY_CAST(NULLIF(TRIM(AnoReferencia), '') AS SMALLINT)
                        AS AnoReferencia_typed,
                    DscTipoObra,
                    DscTipoObraClasse,
                    VlrTotalRealizado,
                    TRY_CAST(
                        NULLIF(
                            REPLACE(REPLACE(TRIM(VlrTotalRealizado), '.', ''), ',', '.'),
                            ''
                        ) AS DECIMAL(18, 2)
                    ) AS VlrTotalRealizado_typed,
                    VlrTotalPlanejado,
                    TRY_CAST(
                        NULLIF(
                            REPLACE(REPLACE(TRIM(VlrTotalPlanejado), '.', ''), ',', '.'),
                            ''
                        ) AS DECIMAL(18, 2)
                    ) AS VlrTotalPlanejado_typed
                FROM raw.pdd
                """
            )

            total_origem = con.execute("SELECT COUNT(*) FROM raw.pdd").fetchone()[0]
            total_staging = con.execute(
                "SELECT COUNT(*) FROM _pdd_staging"
            ).fetchone()[0]
            invalidos_id = con.execute(
                """
                SELECT COUNT(*)
                FROM _pdd_staging
                WHERE _id IS NULL OR TRIM(_id) = ''
                """
            ).fetchone()[0]
            ids_distintos = con.execute(
                "SELECT COUNT(DISTINCT _id) FROM _pdd_staging"
            ).fetchone()[0]

            if total_origem != total_staging:
                raise ValueError(
                    f"Contagem divergente: raw.pdd={total_origem}, "
                    f"staging={total_staging}."
                )
            if invalidos_id or ids_distintos != total_staging:
                raise ValueError(
                    "A chave _id de raw.pdd deve ser preenchida e única; "
                    f"linhas={total_staging}, IDs distintos={ids_distintos}, "
                    f"IDs vazios/nulos={invalidos_id}."
                )

            con.execute("CREATE SCHEMA IF NOT EXISTS refined")
            con.execute(
                """
                CREATE OR REPLACE TABLE refined.pdd AS
                SELECT
                    _id,
                    DatGeracaoConjuntoDados_typed AS DatGeracaoConjuntoDados,
                    DatGeracaoConjuntoDados AS DatGeracaoConjuntoDados_raw,
                    CASE
                        WHEN DatGeracaoConjuntoDados IS NULL
                          OR TRIM(DatGeracaoConjuntoDados) = '' THEN 'null'
                        WHEN DatGeracaoConjuntoDados_typed IS NULL THEN 'invalid'
                        ELSE 'valid'
                    END AS DatGeracaoConjuntoDados_status,
                    SigAgente,
                    NumCPFCNPJ,
                    DscTipoOutorga,
                    SigUF,
                    DscRegiao,
                    AnoReferencia_typed AS AnoReferencia,
                    AnoReferencia AS AnoReferencia_raw,
                    CASE
                        WHEN AnoReferencia IS NULL OR TRIM(AnoReferencia) = ''
                            THEN 'null'
                        WHEN AnoReferencia_typed IS NULL THEN 'invalid'
                        ELSE 'valid'
                    END AS AnoReferencia_status,
                    DscTipoObra,
                    DscTipoObraClasse,
                    VlrTotalRealizado_typed AS VlrTotalRealizado,
                    VlrTotalRealizado AS VlrTotalRealizado_raw,
                    CASE
                        WHEN VlrTotalRealizado IS NULL
                          OR TRIM(VlrTotalRealizado) = '' THEN 'null'
                        WHEN VlrTotalRealizado_typed IS NULL THEN 'invalid'
                        ELSE 'valid'
                    END AS VlrTotalRealizado_status,
                    VlrTotalPlanejado_typed AS VlrTotalPlanejado,
                    VlrTotalPlanejado AS VlrTotalPlanejado_raw,
                    CASE
                        WHEN VlrTotalPlanejado IS NULL
                          OR TRIM(VlrTotalPlanejado) = '' THEN 'null'
                        WHEN VlrTotalPlanejado_typed IS NULL THEN 'invalid'
                        ELSE 'valid'
                    END AS VlrTotalPlanejado_status
                FROM _pdd_staging
                """
            )

            total_destino = con.execute(
                "SELECT COUNT(*) FROM refined.pdd"
            ).fetchone()[0]
            if total_destino != total_origem:
                raise ValueError(
                    f"Contagem divergente após transformação: "
                    f"raw.pdd={total_origem}, refined.pdd={total_destino}."
                )

            invalidos = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE DatGeracaoConjuntoDados_status = 'invalid'),
                    COUNT(*) FILTER (WHERE AnoReferencia_status = 'invalid'),
                    COUNT(*) FILTER (WHERE VlrTotalRealizado_status = 'invalid'),
                    COUNT(*) FILTER (WHERE VlrTotalPlanejado_status = 'invalid')
                FROM refined.pdd
                """
            ).fetchone()
            con.execute("COMMIT")

            return {
                "linhas_origem": total_origem,
                "linhas_destino": total_destino,
                "datas_invalidas": invalidos[0],
                "anos_invalidos": invalidos[1],
                "valores_realizados_invalidos": invalidos[2],
                "valores_planejados_invalidos": invalidos[3],
            }
        except Exception:
            con.execute("ROLLBACK")
            raise


if __name__ == "__main__":
    resultado = transformar_pdd()
    print("Transformação de refined.pdd concluída.")
    for nome, valor in resultado.items():
        print(f"{nome}: {valor}")
