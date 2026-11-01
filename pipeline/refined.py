"""Transformações da camada REFINED."""


from pipeline.db import conectar
from pipeline.ingestao_indger import COLUNAS_INDGER


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


def transformar_indger() -> dict[str, int]:
    """Cria ou substitui refined.indger_comerciais atomicamente.

    Todas as linhas da RAW são preservadas. Os quatro campos tipados mantêm
    o valor original em colunas ``_raw`` e recebem status ``valid``, ``null``
    ou ``invalid``. Chaves repetidas e códigos IBGE ``0`` são sinalizados.
    """
    conversoes = {
        "DatReferenciaInformada": "DATE",
        "DatGeracaoConjuntoDados": "DATE",
        "DthCarga": "TIMESTAMP",
        "QtdUCAtiva": "BIGINT",
    }
    projecoes = []

    for coluna in COLUNAS_INDGER:
        identificador = f'"{coluna}"'
        if coluna not in conversoes:
            projecoes.append(identificador)
            continue

        tipo = conversoes[coluna]
        valor_limpo = f"NULLIF(TRIM({identificador}), '')"
        valor_convertido = f"TRY_CAST({valor_limpo} AS {tipo})"
        status = (
            "CASE "
            f"WHEN {identificador} IS NULL OR TRIM({identificador}) = '' "
            "THEN 'null' "
            f"WHEN {valor_convertido} IS NULL THEN 'invalid' "
            "ELSE 'valid' END "
            f"AS \"{coluna}_status\""
        )
        projecoes.extend(
            [
                f"{valor_convertido} AS {identificador}",
                f"{identificador} AS \"{coluna}_raw\"",
                status,
            ]
        )

    chave = '"NumCNPJ", "CodMunicipioIBGE", "DatReferenciaInformada"'
    flag_ibge = (
        "CASE WHEN TRIM(\"CodMunicipioIBGE\") = '0' "
        "THEN TRUE ELSE FALSE END AS \"CodMunicipioIBGE_revisar\""
    )
    projecoes.extend(
        [
            flag_ibge,
            f'(COUNT(*) OVER (PARTITION BY {chave}) > 1) AS "duplicidade_chave"',
        ]
    )
    consulta_staging = (
        "CREATE TEMP TABLE _indger_staging AS SELECT\n    "
        + ",\n    ".join(projecoes)
        + "\nFROM raw.indger_comerciais"
    )

    with conectar() as con:
        con.execute("BEGIN TRANSACTION")

        try:
            total_origem = con.execute(
                "SELECT COUNT(*) FROM raw.indger_comerciais"
            ).fetchone()[0]
            con.execute(consulta_staging)
            total_staging = con.execute(
                "SELECT COUNT(*) FROM _indger_staging"
            ).fetchone()[0]

            if total_origem != total_staging:
                raise ValueError(
                    "Contagem divergente: "
                    f"raw.indger_comerciais={total_origem}, "
                    f"staging={total_staging}."
                )

            con.execute("CREATE SCHEMA IF NOT EXISTS refined")
            con.execute(
                """
                CREATE OR REPLACE TABLE refined.indger_comerciais AS
                SELECT * FROM _indger_staging
                """
            )
            total_destino = con.execute(
                "SELECT COUNT(*) FROM refined.indger_comerciais"
            ).fetchone()[0]
            if total_destino != total_origem:
                raise ValueError(
                    "Contagem divergente após transformação: "
                    f"raw.indger_comerciais={total_origem}, "
                    f"refined.indger_comerciais={total_destino}."
                )

            diagnostico = con.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE DatReferenciaInformada_status = 'invalid'
                    ),
                    COUNT(*) FILTER (
                        WHERE DatGeracaoConjuntoDados_status = 'invalid'
                    ),
                    COUNT(*) FILTER (WHERE DthCarga_status = 'invalid'),
                    COUNT(*) FILTER (WHERE QtdUCAtiva_status = 'invalid'),
                    COUNT(*) FILTER (WHERE CodMunicipioIBGE_revisar),
                    COUNT(*) FILTER (WHERE duplicidade_chave)
                FROM refined.indger_comerciais
                """
            ).fetchone()
            grupos_repetidos = con.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT NumCNPJ, CodMunicipioIBGE, DatReferenciaInformada_raw
                    FROM refined.indger_comerciais
                    GROUP BY NumCNPJ, CodMunicipioIBGE, DatReferenciaInformada_raw
                    HAVING COUNT(*) > 1
                ) grupos
                """
            ).fetchone()[0]
            con.execute("COMMIT")

            return {
                "linhas_origem": total_origem,
                "linhas_destino": total_destino,
                "referencias_invalidas": diagnostico[0],
                "datas_geracao_invalidas": diagnostico[1],
                "cargas_invalidas": diagnostico[2],
                "uc_ativas_invalidas": diagnostico[3],
                "ibge_zero_para_revisao": diagnostico[4],
                "linhas_com_chave_repetida": diagnostico[5],
                "grupos_chave_repetida": grupos_repetidos,
            }
        except Exception:
            con.execute("ROLLBACK")
            raise


if __name__ == "__main__":
    resultado = transformar_pdd()
    print("Transformação de refined.pdd concluída.")
    for nome, valor in resultado.items():
        print(f"{nome}: {valor}")
