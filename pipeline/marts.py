"""Execução transacional de artefatos da camada MARTS."""

from collections.abc import Callable
from pathlib import Path

import duckdb

from pipeline.db import BASE_DIR, conectar

COORTE_TOP10_SQL = BASE_DIR / "sql" / "marts" / "00_cohorte_top10_2025.sql"
MART_01_SQL = BASE_DIR / "sql" / "marts" / "01_investimentos_anuais.sql"
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


if __name__ == "__main__":
    resultado = executar_mart_01()
    print(f"MART 01 concluído: {resultado['linhas']} linhas.")

