"""Execução transacional de artefatos da camada MARTS."""

from collections.abc import Callable
from pathlib import Path

import duckdb

from pipeline.db import BASE_DIR, conectar

COORTE_TOP10_SQL = BASE_DIR / "sql" / "marts" / "00_cohorte_top10_2025.sql"
MART_01_SQL = BASE_DIR / "sql" / "marts" / "01_investimentos_anuais.sql"
MART_02_SQL = BASE_DIR / "sql" / "marts" / "02_investimentos_por_tipo.sql"
MART_03_SQL = BASE_DIR / "sql" / "marts" / "03_investimento_por_uc.sql"
MART_04_SQL = BASE_DIR / "sql" / "marts" / "04_planejado_vs_realizado.sql"
ANOS_MART_01 = {2023, 2024, 2025}
ESCOPOS_MART_01 = {"nacional", "top10"}


def _validar_coorte_top10(con: duckdb.DuckDBPyConnection) -> None:
    """Confirma que a coorte persistida tem dez posições e CNPJs únicos."""
    linhas = con.execute(
        """
        SELECT posicao, cnpj, uc_dez_2025
        FROM marts.cohorte_top10_2025
        ORDER BY posicao
        """
    ).fetchall()

    if len(linhas) != 10:
        raise ValueError(
            f"A coorte fixa do top 10 deve conter 10 linhas; encontradas={len(linhas)}."
        )

    posicoes = [linha[0] for linha in linhas]
    cnpjs = [linha[1] for linha in linhas]
    if posicoes != list(range(1, 11)) or len(set(cnpjs)) != 10:
        raise ValueError(
            "A coorte fixa do top 10 deve ter posições 1–10 e CNPJs únicos."
        )
    if any(cnpj is None or uc is None for _, cnpj, uc in linhas):
        raise ValueError("A coorte contém CNPJ ou total de UCs nulo.")


def _garantir_coorte_top10(con: duckdb.DuckDBPyConnection) -> None:
    """Cria a coorte uma única vez, após validar a chave municipal."""
    existe = con.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'marts'
          AND table_name = 'cohorte_top10_2025'
        """
    ).fetchone()[0]

    if existe:
        _validar_coorte_top10(con)
        return

    grupos_duplicados, linhas_duplicadas = con.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(quantidade), 0)
        FROM (
            SELECT COUNT(*) AS quantidade
            FROM refined.indger_comerciais
            WHERE DatReferenciaInformada = DATE '2025-12-01'
            GROUP BY NumCNPJ, CodMunicipioIBGE, DatReferenciaInformada
            HAVING COUNT(*) > 1
        ) duplicidades
        """
    ).fetchone()

    if grupos_duplicados:
        raise ValueError(
            "Coorte não criada: chave municipal duplicada em dezembro de 2025; "
            f"grupos={grupos_duplicados}, linhas envolvidas={linhas_duplicadas}."
        )

    consulta = COORTE_TOP10_SQL.read_text(encoding="utf-8")
    con.execute(consulta)
    _validar_coorte_top10(con)


def executar_sql_mart(
    caminho_sql: Path,
    validacao: Callable[[duckdb.DuckDBPyConnection], dict[str, int]] | None = None,
    *,
    validacao_previa: Callable[[duckdb.DuckDBPyConnection], None] | None = None,
) -> dict[str, int]:
    """Executa um MART e sua validação dentro da mesma transação."""
    if not caminho_sql.is_file():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {caminho_sql}")

    consulta = caminho_sql.read_text(encoding="utf-8")

    with conectar() as con:
        con.execute("BEGIN TRANSACTION")

        try:
            con.execute("CREATE SCHEMA IF NOT EXISTS marts")
            if validacao_previa is not None:
                validacao_previa(con)
            _garantir_coorte_top10(con)
            con.execute(consulta)

            resultado = validacao(con) if validacao is not None else {}
            con.execute("COMMIT")
            return resultado
        except Exception:
            con.execute("ROLLBACK")
            raise


def _validar_mart_01(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    chaves = con.execute(
        """
        SELECT ano_referencia, escopo
        FROM marts.investimentos_anuais
        """
    ).fetchall()
    chaves_encontradas = {(ano, escopo) for ano, escopo in chaves}
    chaves_esperadas = {
        (ano, escopo)
        for ano in ANOS_MART_01
        for escopo in ESCOPOS_MART_01
    }

    if chaves_encontradas != chaves_esperadas:
        raise ValueError(
            "O MART 01 deve conter cada ano de 2023–2025 nos escopos "
            f"nacional e top10; chaves encontradas={sorted(chaves_encontradas)}."
        )
    if len(chaves) != len(chaves_encontradas):
        raise ValueError("O MART 01 deve ter uma linha por ano e escopo.")

    return {"linhas": len(chaves)}


def executar_mart_01() -> dict[str, int]:
    """Executa o MART 01 usando o executor e a coorte compartilhados."""
    return executar_sql_mart(MART_01_SQL, _validar_mart_01)


def _validar_mart_02(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    linhas = con.execute(
        "SELECT ano_referencia, escopo, tipo_obra "
        "FROM marts.investimentos_por_tipo"
    ).fetchall()
    if not linhas:
        raise ValueError("O MART 02 não produziu linhas.")

    duplicadas = con.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT ano_referencia, escopo, tipo_obra
            FROM marts.investimentos_por_tipo
            GROUP BY ano_referencia, escopo, tipo_obra
            HAVING COUNT(*) > 1
        ) AS chaves_duplicadas
        """
    ).fetchone()[0]
    if duplicadas:
        raise ValueError("O MART 02 contém duplicidades em ano/escopo/tipo.")

    anos = {linha[0] for linha in linhas}
    escopos = {linha[1] for linha in linhas}
    if anos != ANOS_MART_01 or escopos != ESCOPOS_MART_01:
        raise ValueError(
            "O MART 02 deve cobrir os anos 2023–2025 e os escopos "
            f"nacional/top10; anos={sorted(anos)}, escopos={sorted(escopos)}."
        )

    divergencias = con.execute(
        """
        WITH agregado AS (
            SELECT
                ano_referencia,
                escopo,
                SUM(qtd_registros_pdd) AS qtd_registros_pdd,
                SUM(qtd_planejados_validos) AS qtd_planejados_validos,
                SUM(qtd_planejados_nulos) AS qtd_planejados_nulos,
                SUM(qtd_planejados_invalidos) AS qtd_planejados_invalidos,
                SUM(total_planejado) AS total_planejado,
                SUM(qtd_realizados_validos) AS qtd_realizados_validos,
                SUM(qtd_realizados_nulos) AS qtd_realizados_nulos,
                SUM(qtd_realizados_invalidos) AS qtd_realizados_invalidos,
                SUM(total_realizado) AS total_realizado
            FROM marts.investimentos_por_tipo
            GROUP BY ano_referencia, escopo
        )
        SELECT COUNT(*)
        FROM agregado AS a
        FULL OUTER JOIN marts.investimentos_anuais AS b
            USING (ano_referencia, escopo)
        WHERE a.ano_referencia IS NULL OR b.ano_referencia IS NULL
           OR a.qtd_registros_pdd IS DISTINCT FROM b.qtd_registros_pdd
           OR a.qtd_planejados_validos
                IS DISTINCT FROM b.qtd_planejados_validos
           OR a.qtd_planejados_nulos IS DISTINCT FROM b.qtd_planejados_nulos
           OR a.qtd_planejados_invalidos
                IS DISTINCT FROM b.qtd_planejados_invalidos
           OR a.total_planejado IS DISTINCT FROM b.total_planejado
           OR a.qtd_realizados_validos
                IS DISTINCT FROM b.qtd_realizados_validos
           OR a.qtd_realizados_nulos IS DISTINCT FROM b.qtd_realizados_nulos
           OR a.qtd_realizados_invalidos
                IS DISTINCT FROM b.qtd_realizados_invalidos
           OR a.total_realizado IS DISTINCT FROM b.total_realizado
        """
    ).fetchone()[0]
    if divergencias:
        raise ValueError(
            "As somas e os status do MART 02 não reconciliam com o MART 01 "
            f"em {divergencias} combinações de ano/escopo."
        )
    return {"linhas": len(linhas)}


def executar_mart_02() -> dict[str, int]:
    """Executa o MART 02 na transação e coorte compartilhadas."""
    return executar_sql_mart(MART_02_SQL, _validar_mart_02)


def _validar_chaves_uc_mart_03(con: duckdb.DuckDBPyConnection) -> None:
    """Bloqueia soma municipal se a chave INDGER repetir em dezembro."""
    duplicidades = con.execute(
        """
        SELECT
            YEAR(DatReferenciaInformada) AS ano_referencia,
            NumCNPJ,
            CodMunicipioIBGE,
            DatReferenciaInformada,
            COUNT(*) AS quantidade
        FROM refined.indger_comerciais
        WHERE MONTH(DatReferenciaInformada) = 12
          AND YEAR(DatReferenciaInformada) BETWEEN 2023 AND 2025
        GROUP BY NumCNPJ, CodMunicipioIBGE, DatReferenciaInformada
        HAVING COUNT(*) > 1
        ORDER BY ano_referencia, NumCNPJ, CodMunicipioIBGE
        """
    ).fetchall()
    if duplicidades:
        raise ValueError(
            "Agregação de UCs bloqueada: chave CNPJ + município + dezembro "
            f"duplicada em {len(duplicidades)} grupo(s); exemplos="
            f"{duplicidades[:5]}"
        )


def _validar_mart_03(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    chaves = con.execute(
        "SELECT ano_referencia, escopo, cnpj "
        "FROM marts.investimento_por_uc"
    ).fetchall()
    if not chaves:
        raise ValueError("O MART 03 não produziu linhas.")

    duplicadas = con.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT ano_referencia, escopo, cnpj
            FROM marts.investimento_por_uc
            GROUP BY ano_referencia, escopo, cnpj
            HAVING COUNT(*) > 1
        ) AS chaves_duplicadas
        """
    ).fetchone()[0]
    if duplicadas:
        raise ValueError("O MART 03 contém chaves CNPJ/ano/escopo duplicadas.")

    anos = {linha[0] for linha in chaves}
    escopos = {linha[1] for linha in chaves}
    if anos != ANOS_MART_01 or escopos != ESCOPOS_MART_01:
        raise ValueError(
            "O MART 03 deve cobrir 2023–2025 nos escopos nacional/top10; "
            f"anos={sorted(anos)}, escopos={sorted(escopos)}."
        )

    tipos = dict(
        con.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'marts' AND table_name = 'investimento_por_uc'
            """
        ).fetchall()
    )
    if tipos.get("cnpj") != "VARCHAR":
        raise ValueError("O CNPJ do MART 03 deve permanecer como VARCHAR.")
    for coluna in ("total_planejado", "total_realizado"):
        if not tipos.get(coluna, "").startswith("DECIMAL"):
            raise ValueError(f"{coluna} deve manter tipo DECIMAL no MART 03.")
    for coluna in (
        "investimento_planejado_por_uc",
        "investimento_realizado_por_uc",
    ):
        if tipos.get(coluna) != "DECIMAL(18,2)":
            raise ValueError(f"{coluna} deve ser DECIMAL(18,2).")

    divergencias = con.execute(
        """
        WITH pdd_cnpj_ano AS (
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
        esperado AS (
            SELECT *, 'nacional' AS escopo FROM pdd_cnpj_ano
            UNION ALL
            SELECT p.*, 'top10' AS escopo
            FROM pdd_cnpj_ano AS p
            INNER JOIN marts.cohorte_top10_2025 AS t ON p.cnpj = t.cnpj
        )
        SELECT COUNT(*)
        FROM esperado AS e
        FULL OUTER JOIN marts.investimento_por_uc AS m
          ON e.cnpj IS NOT DISTINCT FROM m.cnpj
         AND e.ano_referencia = m.ano_referencia
         AND e.escopo = m.escopo
        WHERE e.ano_referencia IS NULL OR m.ano_referencia IS NULL
           OR e.qtd_registros_pdd IS DISTINCT FROM m.qtd_registros_pdd
           OR e.total_planejado IS DISTINCT FROM m.total_planejado
           OR e.qtd_planejados_validos
                IS DISTINCT FROM m.qtd_planejados_validos
           OR e.qtd_planejados_nulos IS DISTINCT FROM m.qtd_planejados_nulos
           OR e.qtd_planejados_invalidos
                IS DISTINCT FROM m.qtd_planejados_invalidos
           OR e.total_realizado IS DISTINCT FROM m.total_realizado
           OR e.qtd_realizados_validos
                IS DISTINCT FROM m.qtd_realizados_validos
           OR e.qtd_realizados_nulos IS DISTINCT FROM m.qtd_realizados_nulos
           OR e.qtd_realizados_invalidos
                IS DISTINCT FROM m.qtd_realizados_invalidos
        """
    ).fetchone()[0]
    if divergencias:
        raise ValueError(
            "Os investimentos do MART 03 não reconciliam linha a linha com "
            f"refined.pdd ({divergencias} divergências); possível multiplicação "
            "ou perda durante o JOIN."
        )

    indisponiveis = con.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE investimento_planejado_por_uc IS NULL
            ),
            COUNT(*) FILTER (
                WHERE investimento_realizado_por_uc IS NULL
            )
        FROM marts.investimento_por_uc
        """
    ).fetchone()
    return {
        "linhas": len(chaves),
        "planejado_por_uc_indisponivel": indisponiveis[0],
        "realizado_por_uc_indisponivel": indisponiveis[1],
    }


def executar_mart_03() -> dict[str, int]:
    """Executa R$/UC após validar as chaves municipais de dezembro."""
    return executar_sql_mart(
        MART_03_SQL,
        _validar_mart_03,
        validacao_previa=_validar_chaves_uc_mart_03,
    )


def _validar_mart_04(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    linhas_distribuidora = con.execute(
        "SELECT cnpj, ano_referencia FROM marts.planejado_vs_realizado_distribuidora"
    ).fetchall()
    linhas_nacionais = con.execute(
        "SELECT ano_referencia FROM marts.planejado_vs_realizado_nacional"
    ).fetchall()
    if not linhas_distribuidora:
        raise ValueError("A saída por distribuidora do MART 04 não produziu linhas.")

    chaves_distintas = set(linhas_distribuidora)
    anos_nacionais = [linha[0] for linha in linhas_nacionais]
    if len(chaves_distintas) != len(linhas_distribuidora):
        raise ValueError("MART 04 contém CNPJ/ano duplicado na saída por distribuidora.")
    if set(anos_nacionais) != ANOS_MART_01 or len(anos_nacionais) != 3:
        raise ValueError("A saída nacional do MART 04 deve ter uma linha por ano 2023–2025.")
    if {ano for _, ano in linhas_distribuidora} != ANOS_MART_01:
        raise ValueError("A saída por distribuidora do MART 04 deve cobrir 2023–2025.")

    tipos = dict(
        con.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'marts'
              AND table_name = 'planejado_vs_realizado_distribuidora'
            """
        ).fetchall()
    )
    if tipos.get("cnpj") != "VARCHAR":
        raise ValueError("O CNPJ do MART 04 deve permanecer como VARCHAR.")
    for coluna in (
        "total_planejado",
        "total_realizado",
        "diferenca_absoluta",
    ):
        if not tipos.get(coluna, "").startswith("DECIMAL"):
            raise ValueError(f"{coluna} deve manter tipo DECIMAL no MART 04.")
    for coluna in ("percentual_execucao", "diferenca_percentual"):
        if tipos.get(coluna) != "DECIMAL(18,2)":
            raise ValueError(f"{coluna} deve ser DECIMAL(18,2) no MART 04.")

    divergencias_coorte = con.execute(
        """
        SELECT COUNT(*)
        FROM marts.planejado_vs_realizado_distribuidora AS d
        WHERE d.top10_2025 IS DISTINCT FROM EXISTS (
            SELECT 1 FROM marts.cohorte_top10_2025 AS t WHERE t.cnpj = d.cnpj
        )
        """
    ).fetchone()[0]
    if divergencias_coorte:
        raise ValueError("A flag top10_2025 diverge da coorte persistida.")

    divergencias_pdd = con.execute(
        """
        WITH esperado AS (
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
        )
        SELECT COUNT(*)
        FROM esperado AS e
        FULL OUTER JOIN marts.planejado_vs_realizado_distribuidora AS d
          ON e.cnpj IS NOT DISTINCT FROM d.cnpj
         AND e.ano_referencia = d.ano_referencia
        WHERE e.ano_referencia IS NULL OR d.ano_referencia IS NULL
           OR e.qtd_registros_pdd IS DISTINCT FROM d.qtd_registros_pdd
           OR e.total_planejado IS DISTINCT FROM d.total_planejado
           OR e.qtd_planejados_validos
                IS DISTINCT FROM d.qtd_planejados_validos
           OR e.qtd_planejados_nulos IS DISTINCT FROM d.qtd_planejados_nulos
           OR e.qtd_planejados_invalidos
                IS DISTINCT FROM d.qtd_planejados_invalidos
           OR e.total_realizado IS DISTINCT FROM d.total_realizado
           OR e.qtd_realizados_validos
                IS DISTINCT FROM d.qtd_realizados_validos
           OR e.qtd_realizados_nulos IS DISTINCT FROM d.qtd_realizados_nulos
           OR e.qtd_realizados_invalidos
                IS DISTINCT FROM d.qtd_realizados_invalidos
        """
    ).fetchone()[0]
    if divergencias_pdd:
        raise ValueError(
            "A saída por distribuidora do MART 04 não reconcilia com refined.pdd; "
            f"divergências={divergencias_pdd}."
        )

    divergencias_nacionais = con.execute(
        """
        SELECT COUNT(*)
        FROM marts.planejado_vs_realizado_nacional AS n
        FULL OUTER JOIN (
            SELECT * FROM marts.investimentos_anuais WHERE escopo = 'nacional'
        ) AS a
            ON n.ano_referencia = a.ano_referencia
        WHERE n.ano_referencia IS NULL OR a.ano_referencia IS NULL
           OR n.qtd_registros_pdd IS DISTINCT FROM a.qtd_registros_pdd
           OR n.qtd_cnpjs IS DISTINCT FROM a.qtd_cnpjs
           OR n.total_planejado IS DISTINCT FROM a.total_planejado
           OR n.qtd_planejados_validos
                IS DISTINCT FROM a.qtd_planejados_validos
           OR n.qtd_planejados_nulos IS DISTINCT FROM a.qtd_planejados_nulos
           OR n.qtd_planejados_invalidos
                IS DISTINCT FROM a.qtd_planejados_invalidos
           OR n.status_total_planejado
                IS DISTINCT FROM a.status_total_planejado
           OR n.total_realizado IS DISTINCT FROM a.total_realizado
           OR n.qtd_realizados_validos
                IS DISTINCT FROM a.qtd_realizados_validos
           OR n.qtd_realizados_nulos IS DISTINCT FROM a.qtd_realizados_nulos
           OR n.qtd_realizados_invalidos
                IS DISTINCT FROM a.qtd_realizados_invalidos
           OR n.status_total_realizado
                IS DISTINCT FROM a.status_total_realizado
        """
    ).fetchone()[0]
    if divergencias_nacionais:
        raise ValueError(
            "A saída nacional do MART 04 não reconcilia com o MART 01; "
            f"divergências={divergencias_nacionais}."
        )

    return {
        "linhas_distribuidoras": len(linhas_distribuidora),
        "linhas_nacionais": len(linhas_nacionais),
    }


def executar_mart_04() -> dict[str, int]:
    """Executa as saídas separadas do MART 04 na transação compartilhada."""
    return executar_sql_mart(MART_04_SQL, _validar_mart_04)


if __name__ == "__main__":
    resultado = executar_mart_01()
    print(f"MART 01 concluído: {resultado['linhas']} linhas.")

