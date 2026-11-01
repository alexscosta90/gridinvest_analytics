"""Execução de artefatos da camada MARTS."""

from pipeline.db import BASE_DIR, conectar

MART_01_SQL = BASE_DIR / "sql" / "marts" / "01_investimentos_anuais.sql"
ANOS_MART_01 = {2023, 2024, 2025}
ESCOPOS_MART_01 = {"nacional", "top10"}


def executar_mart_01() -> dict[str, int]:
    """Executa o MART 01 dentro de uma transação e valida seu grão."""
    if not MART_01_SQL.is_file():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {MART_01_SQL}")

    consulta = MART_01_SQL.read_text(encoding="utf-8")

    with conectar() as con:
        con.execute("BEGIN TRANSACTION")

        try:
            con.execute("CREATE SCHEMA IF NOT EXISTS marts")
            con.execute(consulta)

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
                    "nacional e top10; "
                    f"chaves encontradas={sorted(chaves_encontradas)}."
                )
            if len(chaves) != len(chaves_encontradas):
                raise ValueError(
                    "O MART 01 contém mais de uma linha por ano e escopo."
                )

            total_linhas = con.execute(
                "SELECT COUNT(*) FROM marts.investimentos_anuais"
            ).fetchone()[0]
            con.execute("COMMIT")

            return {"linhas": total_linhas}
        except Exception:
            con.execute("ROLLBACK")
            raise


if __name__ == "__main__":
    resultado = executar_mart_01()
    print(f"MART 01 concluído: {resultado['linhas']} linhas.")

