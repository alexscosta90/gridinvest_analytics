from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from pipeline import refined

COLUNAS_PDD = [
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


def preparar_banco(caminho: Path, linhas: list[tuple[str, ...]]) -> None:
    """Cria uma origem RAW fictícia no banco temporário do teste."""
    con = duckdb.connect(str(caminho))
    definicao = ", ".join(f'"{coluna}" VARCHAR' for coluna in COLUNAS_PDD)
    con.execute("CREATE SCHEMA raw")
    con.execute(f"CREATE TABLE raw.pdd ({definicao})")
    placeholders = ", ".join("?" for _ in COLUNAS_PDD)
    con.executemany(f"INSERT INTO raw.pdd VALUES ({placeholders})", linhas)
    con.close()


def conectar_teste(caminho: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        refined,
        "conectar",
        lambda: duckdb.connect(str(caminho)),
    )


def linha_pdd(
    *,
    id_: str = "1",
    cnpj: str = "02341467000120",
    ano: str = "2024",
    realizado: str = "1234,56",
    planejado: str = "9876,54",
    data: str = "2026-06-26 13:43:48.523000000",
    tipo: str = "Expansão",
    classe: str = "Planejamento Setorial",
) -> tuple[str, ...]:
    return (
        id_,
        data,
        "Agente Exemplo",
        cnpj,
        "Concessionária",
        "SP",
        "Sudeste",
        ano,
        tipo,
        classe,
        realizado,
        planejado,
    )


def test_transformar_pdd_converte_tipos_e_preserva_origem(tmp_path, monkeypatch):
    banco = tmp_path / "pdd.duckdb"
    preparar_banco(
        banco,
        [
            linha_pdd(),
            linha_pdd(
                id_="2",
                cnpj="04368898000106",
                ano="2025",
                realizado="",
                planejado="valor-invalido",
                tipo="Melhoria",
                classe="",
            ),
        ],
    )
    conectar_teste(banco, monkeypatch)

    resultado = refined.transformar_pdd()

    assert resultado == {
        "linhas_origem": 2,
        "linhas_destino": 2,
        "datas_invalidas": 0,
        "anos_invalidos": 0,
        "valores_realizados_invalidos": 0,
        "valores_planejados_invalidos": 1,
    }
    with duckdb.connect(str(banco)) as con:
        registros = con.execute(
            """
            SELECT NumCPFCNPJ, AnoReferencia, VlrTotalRealizado,
                   VlrTotalPlanejado, VlrTotalPlanejado_raw,
                   VlrTotalPlanejado_status, DscTipoObra, DscTipoObraClasse
            FROM refined.pdd ORDER BY _id
            """
        ).fetchall()
        tipos = dict(
            con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'refined' AND table_name = 'pdd'
                """
            ).fetchall()
        )
        raw_total = con.execute("SELECT COUNT(*) FROM raw.pdd").fetchone()[0]

    assert registros == [
        (
            "02341467000120",
            2024,
            Decimal("1234.56"),
            Decimal("9876.54"),
            "9876,54",
            "valid",
            "Expansão",
            "Planejamento Setorial",
        ),
        (
            "04368898000106",
            2025,
            None,
            None,
            "valor-invalido",
            "invalid",
            "Melhoria",
            "",
        ),
    ]
    assert tipos["NumCPFCNPJ"] == "VARCHAR"
    assert tipos["AnoReferencia"] == "SMALLINT"
    assert tipos["DatGeracaoConjuntoDados"] == "TIMESTAMP"
    assert tipos["VlrTotalRealizado"] == "DECIMAL(18,2)"
    assert tipos["VlrTotalPlanejado"] == "DECIMAL(18,2)"
    assert raw_total == 2


def test_transformar_pdd_nulos_e_data_invalida_sao_sinalizados(
    tmp_path, monkeypatch
):
    banco = tmp_path / "pdd.duckdb"
    preparar_banco(
        banco,
        [
            linha_pdd(
                data="data-ruim",
                ano="ano-ruim",
                realizado="1.234,56",
                planejado="",
            )
        ],
    )
    conectar_teste(banco, monkeypatch)

    resultado = refined.transformar_pdd()

    assert resultado["datas_invalidas"] == 1
    assert resultado["anos_invalidos"] == 1
    with duckdb.connect(str(banco)) as con:
        registro = con.execute(
            """
            SELECT DatGeracaoConjuntoDados, DatGeracaoConjuntoDados_raw,
                   DatGeracaoConjuntoDados_status, AnoReferencia,
                   AnoReferencia_raw, AnoReferencia_status,
                   VlrTotalRealizado, VlrTotalPlanejado,
                   VlrTotalPlanejado_status
            FROM refined.pdd
            """
        ).fetchone()

    assert registro == (
        None,
        "data-ruim",
        "invalid",
        None,
        "ano-ruim",
        "invalid",
        Decimal("1234.56"),
        None,
        "null",
    )


def test_transformar_pdd_pode_ser_reexecutada_sem_duplicar(tmp_path, monkeypatch):
    banco = tmp_path / "pdd.duckdb"
    preparar_banco(banco, [linha_pdd(), linha_pdd(id_="2")])
    conectar_teste(banco, monkeypatch)

    refined.transformar_pdd()
    refined.transformar_pdd()

    with duckdb.connect(str(banco)) as con:
        total = con.execute("SELECT COUNT(*) FROM refined.pdd").fetchone()[0]
    assert total == 2


def test_falha_de_chave_preserva_tabela_refined_anterior(tmp_path, monkeypatch):
    banco = tmp_path / "pdd.duckdb"
    preparar_banco(banco, [linha_pdd(), linha_pdd(id_="1", ano="2025")])
    conectar_teste(banco, monkeypatch)
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA refined")
        con.execute("CREATE TABLE refined.pdd AS SELECT 'anterior' AS marcador")

    with pytest.raises(ValueError, match="_id.*única"):
        refined.transformar_pdd()

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute("SELECT marcador FROM refined.pdd").fetchall()
        raw_total = con.execute("SELECT COUNT(*) FROM raw.pdd").fetchone()[0]

    assert anterior == [("anterior",)]
    assert raw_total == 2
