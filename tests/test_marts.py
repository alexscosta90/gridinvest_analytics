from decimal import Decimal

import duckdb
import pytest

from pipeline import marts

TOP10_CNPJ = "06981180000116"


def preparar_banco(caminho, linhas):
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA refined")
    con.execute(
        """
        CREATE TABLE refined.pdd (
            NumCPFCNPJ VARCHAR,
            AnoReferencia SMALLINT,
            VlrTotalPlanejado DECIMAL(18, 2),
            VlrTotalPlanejado_status VARCHAR,
            VlrTotalRealizado DECIMAL(18, 2),
            VlrTotalRealizado_status VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO refined.pdd VALUES (?, ?, ?, ?, ?, ?)",
        linhas,
    )
    con.close()


def conectar_teste(caminho, monkeypatch):
    monkeypatch.setattr(
        marts,
        "conectar",
        lambda: duckdb.connect(str(caminho)),
    )


def linhas_completas():
    return [
        (TOP10_CNPJ, 2023, Decimal("100.00"), "valid", Decimal("80.00"), "valid"),
        (TOP10_CNPJ, 2023, Decimal("20.00"), "valid", Decimal("10.00"), "valid"),
        ("99999999000199", 2023, Decimal("7.00"), "valid", Decimal("5.00"), "valid"),
        ("99999999000199", 2023, None, "invalid", None, "null"),
        (TOP10_CNPJ, 2024, Decimal("40.00"), "valid", Decimal("30.00"), "valid"),
        ("99999999000199", 2024, Decimal("10.00"), "valid", Decimal("8.00"), "valid"),
        (TOP10_CNPJ, 2025, Decimal("60.00"), "valid", Decimal("50.00"), "valid"),
        ("99999999000199", 2025, Decimal("9.00"), "valid", Decimal("8.00"), "valid"),
    ]


def test_mart01_agrega_por_ano_e_escopo_sem_perder_o_nacional(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart_test.duckdb"
    preparar_banco(banco, linhas_completas())
    conectar_teste(banco, monkeypatch)

    resultado = marts.executar_mart_01()

    assert resultado == {"linhas": 6}
    with duckdb.connect(str(banco)) as con:
        linhas = con.execute(
            """
            SELECT ano_referencia, escopo, qtd_registros_pdd, qtd_cnpjs,
                   total_planejado, qtd_planejados_invalidos,
                   status_total_planejado, total_realizado,
                   qtd_realizados_nulos, status_total_realizado,
                   ano_realizado_completo
            FROM marts.investimentos_anuais
            ORDER BY ano_referencia, escopo
            """
        ).fetchall()
        tipos = dict(
            con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'marts'
                  AND table_name = 'investimentos_anuais'
                """
            ).fetchall()
        )

    assert linhas == [
        (
            2023,
            "nacional",
            4,
            2,
            Decimal("127.00"),
            1,
            "invalid",
            Decimal("95.00"),
            1,
            "partial",
            True,
        ),
        (
            2023,
            "top10",
            2,
            1,
            Decimal("120.00"),
            0,
            "valid",
            Decimal("90.00"),
            0,
            "valid",
            True,
        ),
        (
            2024,
            "nacional",
            2,
            2,
            Decimal("50.00"),
            0,
            "valid",
            Decimal("38.00"),
            0,
            "valid",
            True,
        ),
        (
            2024,
            "top10",
            1,
            1,
            Decimal("40.00"),
            0,
            "valid",
            Decimal("30.00"),
            0,
            "valid",
            True,
        ),
        (
            2025,
            "nacional",
            2,
            2,
            Decimal("69.00"),
            0,
            "valid",
            Decimal("58.00"),
            0,
            "valid",
            True,
        ),
        (
            2025,
            "top10",
            1,
            1,
            Decimal("60.00"),
            0,
            "valid",
            Decimal("50.00"),
            0,
            "valid",
            True,
        ),
    ]
    assert tipos["total_planejado"].startswith("DECIMAL")
    assert tipos["total_realizado"].startswith("DECIMAL")


def test_mart01_e_idempotente(tmp_path, monkeypatch):
    banco = tmp_path / "mart_test.duckdb"
    preparar_banco(banco, linhas_completas())
    conectar_teste(banco, monkeypatch)

    marts.executar_mart_01()
    marts.executar_mart_01()

    with duckdb.connect(str(banco)) as con:
        total = con.execute(
            "SELECT COUNT(*) FROM marts.investimentos_anuais"
        ).fetchone()[0]
    assert total == 6


def test_falha_de_validacao_preserva_mart_anterior(tmp_path, monkeypatch):
    banco = tmp_path / "mart_test.duckdb"
    preparar_banco(
        banco,
        [
            (TOP10_CNPJ, 2023, Decimal("100.00"), "valid", Decimal("80.00"), "valid"),
            ("99999999000199", 2023, Decimal("7.00"), "valid", Decimal("5.00"), "valid"),
            (TOP10_CNPJ, 2024, Decimal("40.00"), "valid", Decimal("30.00"), "valid"),
            ("99999999000199", 2024, Decimal("10.00"), "valid", Decimal("8.00"), "valid"),
        ],
    )
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.investimentos_anuais "
            "AS SELECT 'anterior' AS marcador"
        )
    conectar_teste(banco, monkeypatch)

    with pytest.raises(ValueError, match="2023–2025"):
        marts.executar_mart_01()

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute(
            "SELECT marcador FROM marts.investimentos_anuais"
        ).fetchall()
    assert anterior == [("anterior",)]
