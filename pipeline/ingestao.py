import csv

from pipeline.db import BASE_DIR, conectar

ARQUIVO_PDD = BASE_DIR / "raw" / "pdd-distribuicao-aneel.csv"

COLUNAS_ESPERADAS = [
    "_id",
    "DatGeracaoConjuntoDados",
    "SigAgente",
    "NumCPFCNPJ",
    "DscTipoOutorga",
    "SigUF",
    "DscRegiao",
    "AnoReferencia",
    "DscTipoObra",
    "DscTipoObraClasse",
    "VlrTotalRealizado",
    "VlrTotalPlanejado",
]


def validar_linha(linha: list[str], numero_linha: int) -> None:
    """Confere se a linha possui a quantidade esperada de campos."""
    quantidade_esperada = len(COLUNAS_ESPERADAS)

    if len(linha) != quantidade_esperada:
        raise ValueError(
            f"Linha {numero_linha}: "
            f"esperadas {quantidade_esperada} colunas, "
            f"encontradas {len(linha)}."
        )


def ingerir_pdd() -> None:
    """Carrega o CSV original do PDD para a camada RAW."""

    if not ARQUIVO_PDD.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {ARQUIVO_PDD}")

    with ARQUIVO_PDD.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=",")
        colunas = next(leitor)

        if colunas != COLUNAS_ESPERADAS:
            raise ValueError("As colunas não correspondem ao esperado.")

        with conectar() as con:
            con.execute("BEGIN TRANSACTION")

            try:
                con.execute("CREATE SCHEMA IF NOT EXISTS raw")

                definicao = ", ".join(
                    f'"{coluna}" VARCHAR' for coluna in COLUNAS_ESPERADAS
                )

                con.execute(f"CREATE OR REPLACE TABLE raw.pdd ({definicao})")

                total_csv = 0
                lote = []

                sql_insert = (
                    "INSERT INTO raw.pdd VALUES ("
                    + ", ".join(["?"] * len(colunas))
                    + ")"
                )

                for numero_linha, linha in enumerate(leitor, start=2):
                    validar_linha(linha, numero_linha)

                    lote.append(linha)
                    total_csv += 1

                    if len(lote) >= 1000:
                        con.executemany(sql_insert, lote)
                        lote.clear()

                if lote:
                    con.executemany(sql_insert, lote)

                total_banco = con.execute("SELECT COUNT(*) FROM raw.pdd").fetchone()[0]

                if total_csv != total_banco:
                    raise ValueError(f"CSV={total_csv}, banco={total_banco}")

                con.execute("COMMIT")

            except Exception:
                con.execute("ROLLBACK")
                raise

    print("Ingestão do PDD concluída!")
    print(f"Registros no CSV: {total_csv}")
    print(f"Registros no DuckDB: {total_banco}")
    print(f"Colunas: {len(colunas)}")


if __name__ == "__main__":
    ingerir_pdd()
