"""Execução transacional de artefatos da camada MARTS."""

from collections.abc import Callable
from pathlib import Path

import duckdb

from pipeline.db import BASE_DIR, conectar

COORTE_TOP10_SQL = BASE_DIR / "sql" / "marts" / "00_cohorte_top10_2025.sql"
MART_01_SQL = BASE_DIR / "sql" / "marts" / "01_investimentos_anuais.sql"
MART_02_SQL = BASE_DIR / "sql" / "marts" / "02_investimentos_por_tipo.sql"
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
) -> dict[str, int]:
    """Executa um MART e sua validação dentro da mesma transação."""
    if not caminho_sql.is_file():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {caminho_sql}")

    consulta = caminho_sql.read_text(encoding="utf-8")

    with conectar() as con:
        con.execute("BEGIN TRANSACTION")

        try:
            con.execute("CREATE SCHEMA IF NOT EXISTS marts")
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


if __name__ == "__main__":
    resultado = executar_mart_01()
    print(f"MART 01 concluído: {resultado['linhas']} linhas.")

