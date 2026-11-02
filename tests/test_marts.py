from datetime import date
from decimal import Decimal

import duckdb
import pytest

from pipeline import marts

COORTE_CNPJS = [
    "06981180000116",
    "61695227000193",
    "15139629000194",
    "04368898000106",
    "33050196000188",
    "60444437000146",
    "07047251000170",
    "10835932000108",
    "08336783000190",
    "01543032000104",
]
TOP10_CNPJ = COORTE_CNPJS[0]
OUTRO_CNPJ = "99999999000199"


def linhas_indger_dezembro():
    return [
        (
            cnpj,
            f"{posicao:07d}",
            date(2025, 12, 1),
            50000 - posicao * 1000,
            "valid",
        )
        for posicao, cnpj in enumerate(COORTE_CNPJS, start=1)
    ]


def preparar_banco(caminho, linhas_pdd, linhas_indger=None):
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA refined")
    con.execute(
        """
        CREATE TABLE refined.pdd (
            NumCPFCNPJ VARCHAR,
            AnoReferencia SMALLINT,
            DscTipoObra VARCHAR,
            VlrTotalPlanejado DECIMAL(18, 2),
            VlrTotalPlanejado_status VARCHAR,
            VlrTotalRealizado DECIMAL(18, 2),
            VlrTotalRealizado_status VARCHAR
        )
        """
    )
    con.execute("ALTER TABLE refined.pdd ADD COLUMN SigAgente VARCHAR")
    con.executemany(
        "INSERT INTO refined.pdd VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(*linha, f"Agente {linha[0]}") for linha in linhas_pdd],
    )
    con.execute(
        """
        CREATE TABLE refined.indger_comerciais (
            NumCNPJ VARCHAR,
            CodMunicipioIBGE VARCHAR,
            DatReferenciaInformada DATE,
            QtdUCAtiva BIGINT,
            QtdUCAtiva_status VARCHAR
        )
        """
    )
    con.execute("ALTER TABLE refined.indger_comerciais ADD COLUMN NomAgente VARCHAR")
    linhas_indger = linhas_indger if linhas_indger is not None else linhas_indger_dezembro()
    con.executemany(
        "INSERT INTO refined.indger_comerciais VALUES (?, ?, ?, ?, ?, ?)",
        [(*linha, f"Distribuidora {linha[0]}") for linha in linhas_indger],
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
        (TOP10_CNPJ, 2023, "Expansão", Decimal("100.00"), "valid", Decimal("80.00"), "valid"),
        (TOP10_CNPJ, 2023, "Melhoria", Decimal("20.00"), "valid", Decimal("10.00"), "valid"),
        (TOP10_CNPJ, 2023, "Expansão", Decimal("0.00"), "valid", Decimal("0.00"), "valid"),
        (OUTRO_CNPJ, 2023, "Melhoria", Decimal("7.00"), "valid", Decimal("5.00"), "valid"),
        (OUTRO_CNPJ, 2023, None, None, "invalid", None, "null"),
        (TOP10_CNPJ, 2024, "Expansão", Decimal("40.00"), "valid", Decimal("30.00"), "valid"),
        (OUTRO_CNPJ, 2024, "Melhoria", Decimal("10.00"), "valid", Decimal("8.00"), "valid"),
        (TOP10_CNPJ, 2025, "Expansão", Decimal("60.00"), "valid", Decimal("50.00"), "valid"),
        (OUTRO_CNPJ, 2025, "Melhoria", Decimal("9.00"), "valid", Decimal("8.00"), "valid"),
    ]


def linhas_mart02():
    return [
        (TOP10_CNPJ, 2023, "Expansão", Decimal("0.00"), "valid", Decimal("0.00"), "valid"),
        (TOP10_CNPJ, 2023, "Melhoria", Decimal("10.00"), "valid", None, "null"),
        (OUTRO_CNPJ, 2023, "Tipo novo", Decimal("5.00"), "valid", Decimal("3.00"), "valid"),
        (OUTRO_CNPJ, 2023, "", None, "null", None, "invalid"),
        (TOP10_CNPJ, 2024, "Renovação", Decimal("40.00"), "valid", Decimal("35.00"), "valid"),
        (OUTRO_CNPJ, 2024, "Expansão", Decimal("7.00"), "valid", Decimal("5.00"), "valid"),
        (TOP10_CNPJ, 2025, "", Decimal("2.00"), "valid", Decimal("1.00"), "valid"),
        (OUTRO_CNPJ, 2025, None, None, "invalid", None, "null"),
    ]


def linhas_mart03():
    return [
        (TOP10_CNPJ, 2023, "Expansão", Decimal("0.50"), "valid", Decimal("0.50"), "valid"),
        (TOP10_CNPJ, 2023, "Expansão", Decimal("0.50"), "valid", Decimal("0.50"), "valid"),
        (COORTE_CNPJS[1], 2023, "Melhoria", Decimal("2.00"), "valid", Decimal("6.00"), "valid"),
        (COORTE_CNPJS[2], 2023, "Renovação", Decimal("3.00"), "valid", Decimal("1.00"), "valid"),
        (OUTRO_CNPJ, 2023, "Expansão", Decimal("7.00"), "valid", Decimal("4.00"), "valid"),
        (OUTRO_CNPJ, 2023, None, None, "invalid", None, "invalid"),
        (TOP10_CNPJ, 2024, "Expansão", Decimal("5.00"), "valid", Decimal("2.00"), "valid"),
        (OUTRO_CNPJ, 2024, "Melhoria", Decimal("3.00"), "valid", Decimal("1.00"), "valid"),
        (TOP10_CNPJ, 2025, "Renovação", Decimal("3.00"), "valid", Decimal("1.00"), "valid"),
    ]


def linhas_mart04():
    return [
        (COORTE_CNPJS[0], 2023, "Expansão", Decimal("100.00"), "valid", Decimal("120.00"), "valid"),
        (COORTE_CNPJS[1], 2023, "Melhoria", Decimal("100.00"), "valid", Decimal("80.00"), "valid"),
        (COORTE_CNPJS[2], 2023, "Renovação", Decimal("0.00"), "valid", Decimal("10.00"), "valid"),
        (COORTE_CNPJS[3], 2023, "Expansão", None, "null", Decimal("5.00"), "valid"),
        (COORTE_CNPJS[4], 2023, "Melhoria", None, "invalid", Decimal("4.00"), "valid"),
        (COORTE_CNPJS[5], 2023, "Renovação", Decimal("100.00"), "valid", Decimal("0.00"), "valid"),
        (COORTE_CNPJS[0], 2024, "Expansão", Decimal("200.00"), "valid", Decimal("100.00"), "valid"),
        (COORTE_CNPJS[1], 2024, "Melhoria", Decimal("50.00"), "valid", Decimal("75.00"), "valid"),
        (COORTE_CNPJS[5], 2024, "Renovação", Decimal("100.00"), "valid", Decimal("0.00"), "valid"),
        (COORTE_CNPJS[0], 2025, "Expansão", Decimal("100.00"), "valid", Decimal("100.00"), "valid"),
        (COORTE_CNPJS[1], 2025, "Melhoria", Decimal("100.00"), "valid", Decimal("150.00"), "valid"),
    ]


def linhas_mart05():
    return [
        (COORTE_CNPJS[0], 2022, "Expansão", Decimal("100.00"), "valid", Decimal("100.00"), "valid"),
        (COORTE_CNPJS[0], 2023, "Expansão", Decimal("150.00"), "valid", Decimal("120.00"), "valid"),
        (COORTE_CNPJS[0], 2024, "Expansão", Decimal("150.00"), "valid", Decimal("120.00"), "valid"),
        (COORTE_CNPJS[0], 2025, "Expansão", Decimal("120.00"), "valid", Decimal("150.00"), "valid"),
        (COORTE_CNPJS[1], 2023, "Expansão", Decimal("50.00"), "valid", Decimal("40.00"), "valid"),
        (COORTE_CNPJS[1], 2025, "Expansão", Decimal("60.00"), "valid", Decimal("50.00"), "valid"),
        (COORTE_CNPJS[2], 2022, "Expansão", Decimal("0.00"), "valid", Decimal("0.00"), "valid"),
        (COORTE_CNPJS[2], 2023, "Expansão", Decimal("20.00"), "valid", Decimal("10.00"), "valid"),
        (COORTE_CNPJS[3], 2022, "Expansão", None, "null", None, "invalid"),
        (COORTE_CNPJS[3], 2023, "Expansão", Decimal("10.00"), "valid", Decimal("5.00"), "valid"),
        (COORTE_CNPJS[4], 2022, "Expansão", None, "invalid", None, "null"),
        (COORTE_CNPJS[4], 2023, "Expansão", Decimal("10.00"), "valid", Decimal("5.00"), "valid"),
        (OUTRO_CNPJ, 2023, "Expansão", Decimal("10.00"), "valid", Decimal("12.00"), "valid"),
        (OUTRO_CNPJ, 2024, "Expansão", Decimal("15.00"), "valid", Decimal("15.00"), "valid"),
        (OUTRO_CNPJ, 2025, "Expansão", Decimal("20.00"), "valid", Decimal("18.00"), "valid"),
    ]


def linhas_mart06():
    linhas = [
        (COORTE_CNPJS[0], 2023, "Expansão", Decimal("100.00"), "valid", Decimal("10.00"), "valid"),
        (COORTE_CNPJS[1], 2023, "Melhoria", Decimal("100.00"), "valid", Decimal("80.00"), "valid"),
        (COORTE_CNPJS[2], 2023, "Renovação", Decimal("0.00"), "valid", Decimal("0.00"), "valid"),
        (COORTE_CNPJS[3], 2023, "Expansão", None, "null", Decimal("90.00"), "valid"),
        (COORTE_CNPJS[4], 2023, "Melhoria", None, "invalid", None, "null"),
        (COORTE_CNPJS[4], 2023, "Melhoria", Decimal("500.00"), "valid", Decimal("1.00"), "valid"),
        (OUTRO_CNPJ, 2023, "Expansão", Decimal("200.00"), "valid", Decimal("150.00"), "valid"),
        (COORTE_CNPJS[0], 2024, "Expansão", Decimal("50.00"), "valid", Decimal("70.00"), "valid"),
        (OUTRO_CNPJ, 2024, "Melhoria", Decimal("50.00"), "valid", Decimal("20.00"), "valid"),
        (COORTE_CNPJS[0], 2025, "Renovação", Decimal("100.00"), "valid", Decimal("300.00"), "valid"),
        (COORTE_CNPJS[1], 2025, "Melhoria", Decimal("200.00"), "valid", Decimal("100.00"), "valid"),
        (OUTRO_CNPJ, 2025, "Expansão", Decimal("250.00"), "valid", Decimal("150.00"), "valid"),
    ]
    pares_existentes = {(linha[0], linha[1]) for linha in linhas}
    linhas.extend(
        (
            cnpj,
            ano,
            "Expansão",
            Decimal("0.00"),
            "valid",
            Decimal("0.00"),
            "valid",
        )
        for ano in (2023, 2024, 2025)
        for cnpj in COORTE_CNPJS
        if (cnpj, ano) not in pares_existentes
    )
    return linhas


def linhas_indger_mart07():
    linhas = []
    for ano in (2023, 2024, 2025):
        for indice, cnpj in enumerate(COORTE_CNPJS):
            if indice == 0:
                total_uc = {2023: 0, 2024: 100, 2025: 120}[ano]
            elif ano == 2024 and indice in (1, 2):
                total_uc = 925
            else:
                total_uc = 1000 - indice * 50 + (ano - 2023) * 10
            primeira_parcela = total_uc // 2
            for municipio, quantidade in enumerate(
                (primeira_parcela, total_uc - primeira_parcela)
            ):
                linhas.append(
                    (
                        cnpj,
                        f"{ano}{indice:02d}{municipio:02d}",
                        date(ano, 12, 1),
                        quantidade,
                        "valid",
                    )
                )
    for ano, total_uc in ((2023, 2000), (2024, 1100), (2025, 50)):
        linhas.append(
            (OUTRO_CNPJ, f"{ano}9999", date(ano, 12, 1), total_uc, "valid")
        )
    return linhas


def linhas_pdd_mart07():
    return [
        (
            cnpj,
            ano,
            "Expansão",
            Decimal(1000 + indice),
            "valid",
            Decimal(500 + indice),
            "valid",
        )
        for ano in (2023, 2024, 2025)
        for indice, cnpj in enumerate(COORTE_CNPJS)
    ]


def linhas_indger_mart03():
    linhas = [
        (
            cnpj,
            f"{posicao:07d}",
            date(2025, 12, 1),
            100 - posicao,
            "valid",
        )
        for posicao, cnpj in enumerate(COORTE_CNPJS, start=1)
    ]
    linhas[0] = (TOP10_CNPJ, "0000001", date(2025, 12, 1), 100, "valid")
    linhas.extend(
        [
            (TOP10_CNPJ, "1000001", date(2023, 12, 1), 1, "valid"),
            (TOP10_CNPJ, "1000002", date(2023, 12, 1), 2, "valid"),
            (TOP10_CNPJ, "1000001", date(2023, 11, 1), 1000, "valid"),
            (COORTE_CNPJS[1], "2000001", date(2023, 12, 1), 0, "valid"),
            (COORTE_CNPJS[2], "3000001", date(2023, 12, 1), None, "null"),
            (TOP10_CNPJ, "1000001", date(2024, 12, 1), 2, "valid"),
            (OUTRO_CNPJ, "9000001", date(2023, 11, 1), 500, "valid"),
        ]
    )
    return linhas


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
                   total_planejado, qtd_planejados_validos,
                   qtd_planejados_invalidos, status_total_planejado,
                   total_realizado, qtd_realizados_validos,
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
        coorte = con.execute(
            """
            SELECT posicao, cnpj, uc_dez_2025
            FROM marts.cohorte_top10_2025
            ORDER BY posicao
            """
        ).fetchall()

    assert linhas == [
        (
            2023,
            "nacional",
            5,
            2,
            Decimal("127.00"),
            4,
            1,
            "invalid",
            Decimal("95.00"),
            4,
            1,
            "partial",
            True,
        ),
        (
            2023,
            "top10",
            3,
            1,
            Decimal("120.00"),
            3,
            0,
            "valid",
            Decimal("90.00"),
            3,
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
            2,
            0,
            "valid",
            Decimal("38.00"),
            2,
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
            1,
            0,
            "valid",
            Decimal("30.00"),
            1,
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
            2,
            0,
            "valid",
            Decimal("58.00"),
            2,
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
            1,
            0,
            "valid",
            Decimal("50.00"),
            1,
            0,
            "valid",
            True,
        ),
    ]
    assert tipos["total_planejado"].startswith("DECIMAL")
    assert tipos["total_realizado"].startswith("DECIMAL")
    assert coorte == [
        (posicao, cnpj, 50000 - posicao * 1000)
        for posicao, cnpj in enumerate(COORTE_CNPJS, start=1)
    ]


def test_coorte_permanece_inalterada_apos_atualizacao_do_indger(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart_test.duckdb"
    preparar_banco(banco, linhas_completas())
    conectar_teste(banco, monkeypatch)

    marts.executar_mart_01()
    with duckdb.connect(str(banco)) as con:
        coorte_original = con.execute(
            """
            SELECT posicao, cnpj, uc_dez_2025
            FROM marts.cohorte_top10_2025
            ORDER BY posicao
            """
        ).fetchall()
        con.execute(
            """
            INSERT INTO refined.indger_comerciais
            VALUES ('99988888000199', '9999999', DATE '2025-12-01', 99999999,
                    'valid', 'Nova distribuidora')
            """
        )

    marts.executar_mart_01()

    with duckdb.connect(str(banco)) as con:
        coorte_apos_reexecucao = con.execute(
            """
            SELECT posicao, cnpj, uc_dez_2025
            FROM marts.cohorte_top10_2025
            ORDER BY posicao
            """
        ).fetchall()
        top10_2023 = con.execute(
            """
            SELECT total_planejado, total_realizado
            FROM marts.investimentos_anuais
            WHERE ano_referencia = 2023 AND escopo = 'top10'
            """
        ).fetchone()

    assert coorte_apos_reexecucao == coorte_original
    assert top10_2023 == (Decimal("120.00"), Decimal("90.00"))


def test_duplicidades_municipais_impedem_criacao_da_coorte(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart_test.duckdb"
    indger = linhas_indger_dezembro()
    indger.append(indger[0])
    preparar_banco(banco, linhas_completas(), indger)
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.investimentos_anuais "
            "AS SELECT 'anterior' AS marcador"
        )
    conectar_teste(banco, monkeypatch)

    with pytest.raises(ValueError, match="chave municipal duplicada"):
        marts.executar_mart_01()

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute(
            "SELECT marcador FROM marts.investimentos_anuais"
        ).fetchall()
        tabelas_coorte = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'marts'
              AND table_name = 'cohorte_top10_2025'
            """
        ).fetchone()[0]
        linhas_indger = con.execute(
            "SELECT COUNT(*) FROM refined.indger_comerciais"
        ).fetchone()[0]

    assert anterior == [("anterior",)]
    assert tabelas_coorte == 0
    assert linhas_indger == 11


def test_mart01_e_idempotente(tmp_path, monkeypatch):
    banco = tmp_path / "mart_test.duckdb"
    preparar_banco(banco, linhas_completas())
    conectar_teste(banco, monkeypatch)

    marts.executar_mart_01()
    marts.executar_mart_01()

    with duckdb.connect(str(banco)) as con:
        total_mart = con.execute(
            "SELECT COUNT(*) FROM marts.investimentos_anuais"
        ).fetchone()[0]
        total_coorte = con.execute(
            "SELECT COUNT(*) FROM marts.cohorte_top10_2025"
        ).fetchone()[0]
    assert total_mart == 6
    assert total_coorte == 10


def test_falha_de_validacao_reverte_mart_e_coorte(tmp_path, monkeypatch):
    banco = tmp_path / "mart_test.duckdb"
    linhas_incompletas = [
        linha
        for linha in linhas_completas()
        if linha[1] in {2023, 2024}
    ]
    preparar_banco(banco, linhas_incompletas)
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
        tabelas_coorte = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'marts'
              AND table_name = 'cohorte_top10_2025'
            """
        ).fetchone()[0]

    assert anterior == [("anterior",)]
    assert tabelas_coorte == 0


def test_mart02_granularidade_tipos_status_e_reconciliacao(tmp_path, monkeypatch):
    banco = tmp_path / "mart02_test.duckdb"
    preparar_banco(banco, linhas_mart02())
    conectar_teste(banco, monkeypatch)

    marts.executar_mart_01()
    resultado = marts.executar_mart_02()

    assert resultado == {"linhas": 12}
    with duckdb.connect(str(banco)) as con:
        linhas = con.execute(
            """
            SELECT ano_referencia, escopo, tipo_obra, categoria_tipo_obra,
                   total_planejado, qtd_planejados_nulos,
                   qtd_planejados_invalidos, status_total_planejado,
                   total_realizado, qtd_realizados_invalidos
            FROM marts.investimentos_por_tipo
            ORDER BY ano_referencia, escopo, tipo_obra NULLS FIRST
            """
        ).fetchall()
        tipos = dict(
            con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'marts'
                  AND table_name = 'investimentos_por_tipo'
                """
            ).fetchall()
        )
        chaves_repetidas = con.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT ano_referencia, escopo, tipo_obra
                FROM marts.investimentos_por_tipo
                GROUP BY ano_referencia, escopo, tipo_obra
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        total_mart01 = con.execute(
            """
            SELECT ano_referencia, escopo, total_planejado, total_realizado
            FROM marts.investimentos_anuais ORDER BY ano_referencia, escopo
            """
        ).fetchall()
        agregado_mart02 = con.execute(
            """
            SELECT ano_referencia, escopo, SUM(total_planejado), SUM(total_realizado)
            FROM marts.investimentos_por_tipo
            GROUP BY ano_referencia, escopo ORDER BY ano_referencia, escopo
            """
        ).fetchall()

    assert chaves_repetidas == 0
    assert tipos["total_planejado"].startswith("DECIMAL")
    assert tipos["total_realizado"].startswith("DECIMAL")
    assert len(linhas) == 12
    assert any(
        linha[0:4] == (2023, "nacional", "Tipo novo", "outras")
        for linha in linhas
    )
    assert any(
        linha[0:4] == (2023, "nacional", "", "sem_tipo") for linha in linhas
    )
    assert any(
        linha[0:4] == (2025, "nacional", None, "sem_tipo") for linha in linhas
    )
    tipo_vazio = next(
        linha for linha in linhas if linha[0:3] == (2023, "nacional", "")
    )
    assert tipo_vazio[5:8] == (1, 0, "null")
    assert tipo_vazio[9] == 1
    tipo_nulo = next(
        linha for linha in linhas if linha[0:3] == (2025, "nacional", None)
    )
    assert tipo_nulo[5:8] == (0, 1, "invalid")
    zero_valido = next(
        linha
        for linha in linhas
        if linha[0:3] == (2023, "top10", "Expansão")
    )
    assert zero_valido[4] == Decimal("0.00")
    assert zero_valido[5:8] == (0, 0, "valid")
    assert total_mart01 == agregado_mart02


def test_mart02_idempotente_e_coorte_persistente(tmp_path, monkeypatch):
    banco = tmp_path / "mart02_idempotente.duckdb"
    preparar_banco(banco, linhas_mart02())
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_01()

    marts.executar_mart_02()
    with duckdb.connect(str(banco)) as con:
        coorte_original = con.execute(
            "SELECT posicao, cnpj, uc_dez_2025 "
            "FROM marts.cohorte_top10_2025 ORDER BY posicao"
        ).fetchall()
        con.execute(
            "UPDATE refined.indger_comerciais SET QtdUCAtiva = 999999999 "
            "WHERE NumCNPJ = ?",
            [COORTE_CNPJS[1]],
        )

    marts.executar_mart_02()

    with duckdb.connect(str(banco)) as con:
        total = con.execute(
            "SELECT COUNT(*) FROM marts.investimentos_por_tipo"
        ).fetchone()[0]
        coorte_atual = con.execute(
            "SELECT posicao, cnpj, uc_dez_2025 "
            "FROM marts.cohorte_top10_2025 ORDER BY posicao"
        ).fetchall()
    assert total == 12
    assert coorte_atual == coorte_original


def test_mart02_rollback_preserva_tabela_anterior(tmp_path, monkeypatch):
    banco = tmp_path / "mart02_rollback.duckdb"
    preparar_banco(banco, linhas_mart02())
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.investimentos_por_tipo "
            "AS SELECT 'anterior' AS marcador"
        )
    conectar_teste(banco, monkeypatch)

    def falhar_apos_sql(con):
        raise ValueError("falha simulada na validação")

    with pytest.raises(ValueError, match="falha simulada"):
        marts.executar_sql_mart(marts.MART_02_SQL, falhar_apos_sql)

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute(
            "SELECT marcador FROM marts.investimentos_por_tipo"
        ).fetchall()
        coorte = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'marts' AND table_name = 'cohorte_top10_2025'
            """
        ).fetchone()[0]
    assert anterior == [("anterior",)]
    assert coorte == 0


def test_mart02_bloqueia_coorte_com_duplicidade_municipal(tmp_path, monkeypatch):
    banco = tmp_path / "mart02_duplicidade.duckdb"
    indger = linhas_indger_dezembro()
    indger.append(indger[0])
    preparar_banco(banco, linhas_mart02(), indger)
    conectar_teste(banco, monkeypatch)

    with pytest.raises(ValueError, match="chave municipal duplicada"):
        marts.executar_mart_02()


def test_mart03_calcula_por_cnpj_ano_com_uc_de_dezembro(tmp_path, monkeypatch):
    banco = tmp_path / "mart03_test.duckdb"
    preparar_banco(banco, linhas_mart03(), linhas_indger_mart03())
    conectar_teste(banco, monkeypatch)

    assert marts.executar_mart_01() == {"linhas": 6}
    assert marts.executar_mart_02() == {"linhas": 12}
    resultado = marts.executar_mart_03()

    assert resultado == {
        "linhas": 12,
        "planejado_por_uc_indisponivel": 6,
        "realizado_por_uc_indisponivel": 6,
    }
    with duckdb.connect(str(banco)) as con:
        linhas = con.execute(
            """
            SELECT ano_referencia, escopo, cnpj, qtd_registros_pdd,
                   total_planejado, qtd_planejados_invalidos,
                   status_total_planejado, total_realizado,
                   qtd_realizados_invalidos, status_total_realizado,
                   qtd_municipios_dezembro, qtd_uc_dezembro,
                   status_cobertura, investimento_planejado_por_uc,
                   status_planejado_por_uc, investimento_realizado_por_uc,
                   status_realizado_por_uc
            FROM marts.investimento_por_uc
            WHERE escopo = 'nacional'
            ORDER BY ano_referencia, cnpj
            """
        ).fetchall()
        tipos = dict(
            con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'marts'
                  AND table_name = 'investimento_por_uc'
                """
            ).fetchall()
        )
        duplicadas = con.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT ano_referencia, escopo, cnpj
                FROM marts.investimento_por_uc
                GROUP BY ano_referencia, escopo, cnpj
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

    assert duplicadas == 0
    assert tipos["cnpj"] == "VARCHAR"
    assert tipos["total_planejado"].startswith("DECIMAL")
    assert tipos["total_realizado"].startswith("DECIMAL")
    assert tipos["investimento_planejado_por_uc"] == "DECIMAL(18,2)"
    assert tipos["investimento_realizado_por_uc"] == "DECIMAL(18,2)"

    top1_2023 = next(
        linha for linha in linhas if linha[0:3] == (2023, "nacional", TOP10_CNPJ)
    )
    assert top1_2023[3] == 2
    assert top1_2023[4:6] == (Decimal("1.00"), 0)
    assert top1_2023[7:9] == (Decimal("1.00"), 0)
    assert top1_2023[10:14] == (
        2,
        3,
        "valid",
        Decimal("0.33"),
    )
    assert top1_2023[15] == Decimal("0.33")

    top2_2023 = next(
        linha
        for linha in linhas
        if linha[0:3] == (2023, "nacional", COORTE_CNPJS[1])
    )
    assert top2_2023[11:17] == (
        0,
        "zero",
        None,
        "denominador_zero",
        None,
        "denominador_zero",
    )
    top3_2023 = next(
        linha
        for linha in linhas
        if linha[0:3] == (2023, "nacional", COORTE_CNPJS[2])
    )
    assert top3_2023[11:14] == (None, "null", None)

    sem_dezembro = next(
        linha for linha in linhas if linha[0:3] == (2023, "nacional", OUTRO_CNPJ)
    )
    assert sem_dezembro[10:14] == (None, None, "sem_referencia", None)
    assert sem_dezembro[15] is None
    assert sem_dezembro[5] == 1
    assert sem_dezembro[8] == 1


def test_mart03_idempotente(tmp_path, monkeypatch):
    banco = tmp_path / "mart03_idempotente.duckdb"
    preparar_banco(banco, linhas_mart03(), linhas_indger_mart03())
    conectar_teste(banco, monkeypatch)

    marts.executar_mart_03()
    with duckdb.connect(str(banco)) as con:
        primeira = con.execute(
            "SELECT * FROM marts.investimento_por_uc "
            "ORDER BY ano_referencia, escopo, cnpj"
        ).fetchall()
    marts.executar_mart_03()
    with duckdb.connect(str(banco)) as con:
        segunda = con.execute(
            "SELECT * FROM marts.investimento_por_uc ORDER BY ano_referencia, escopo, cnpj"
        ).fetchall()

    assert segunda == primeira
    assert len(segunda) == 12


def test_mart03_duplicidade_municipal_bloqueia_e_preserva_resultado(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart03_duplicidade.duckdb"
    preparar_banco(banco, linhas_mart03(), linhas_indger_mart03())
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_03()

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute(
            "SELECT * FROM marts.investimento_por_uc "
            "ORDER BY ano_referencia, escopo, cnpj"
        ).fetchall()
        con.execute(
            """
            INSERT INTO refined.indger_comerciais
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [TOP10_CNPJ, "1000001", date(2024, 12, 1), 15, "valid", "Cemig"],
        )

    with pytest.raises(ValueError, match="Agregação de UCs bloqueada"):
        marts.executar_mart_03()

    with duckdb.connect(str(banco)) as con:
        atual = con.execute(
            "SELECT * FROM marts.investimento_por_uc "
            "ORDER BY ano_referencia, escopo, cnpj"
        ).fetchall()
    assert atual == anterior


def test_mart03_falha_apos_sql_reverte_tabela_e_coorte(tmp_path, monkeypatch):
    banco = tmp_path / "mart03_rollback.duckdb"
    preparar_banco(banco, linhas_mart03(), linhas_indger_mart03())
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.investimento_por_uc "
            "AS SELECT 'anterior' AS marcador"
        )
    conectar_teste(banco, monkeypatch)

    def falhar_apos_sql(con):
        raise ValueError("falha simulada após materializar MART 03")

    with pytest.raises(ValueError, match="falha simulada após materializar"):
        marts.executar_sql_mart(
            marts.MART_03_SQL,
            falhar_apos_sql,
            validacao_previa=marts._validar_chaves_uc_mart_03,
        )

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute(
            "SELECT marcador FROM marts.investimento_por_uc"
        ).fetchall()
        coorte = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'marts' AND table_name = 'cohorte_top10_2025'
            """
        ).fetchone()[0]
    assert anterior == [("anterior",)]
    assert coorte == 0


def test_mart04_calcula_diferencas_percentuais_e_granularidades(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart04_test.duckdb"
    preparar_banco(banco, linhas_mart04())
    conectar_teste(banco, monkeypatch)

    assert marts.executar_mart_01() == {"linhas": 6}
    assert marts.executar_mart_02() == {"linhas": 16}
    assert marts.executar_mart_03()["linhas"] == 22
    resultado = marts.executar_mart_04()

    assert resultado == {"linhas_distribuidoras": 11, "linhas_nacionais": 3}
    with duckdb.connect(str(banco)) as con:
        distribuidoras = con.execute(
            """
            SELECT cnpj, ano_referencia, total_planejado, total_realizado,
                   diferenca_absoluta, percentual_execucao,
                   status_percentual_execucao, diferenca_percentual,
                   status_total_planejado, status_total_realizado,
                   status_diferenca, top10_2025
            FROM marts.planejado_vs_realizado_distribuidora
            """
        ).fetchall()
        nacionais = con.execute(
            """
            SELECT ano_referencia, total_planejado, total_realizado,
                   diferenca_absoluta, percentual_execucao,
                   status_percentual_execucao, diferenca_percentual,
                   status_total_planejado, status_total_realizado
            FROM marts.planejado_vs_realizado_nacional
            ORDER BY ano_referencia
            """
        ).fetchall()
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
        chaves_duplicadas = con.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT cnpj, ano_referencia
                FROM marts.planejado_vs_realizado_distribuidora
                GROUP BY cnpj, ano_referencia HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        nacional_tem_cnpj = con.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = 'marts'
              AND table_name = 'planejado_vs_realizado_nacional'
              AND column_name = 'cnpj'
            """
        ).fetchone()[0]

    assert chaves_duplicadas == 0
    assert nacional_tem_cnpj == 0
    assert tipos["cnpj"] == "VARCHAR"
    assert tipos["total_planejado"].startswith("DECIMAL")
    assert tipos["total_realizado"].startswith("DECIMAL")
    assert tipos["diferenca_absoluta"].startswith("DECIMAL")
    assert tipos["percentual_execucao"] == "DECIMAL(18,2)"
    assert tipos["diferenca_percentual"] == "DECIMAL(18,2)"

    def distribuidora(cnpj, ano):
        return next(
            row for row in distribuidoras if row[0] == cnpj and row[1] == ano
        )

    acima = distribuidora(COORTE_CNPJS[0], 2023)
    assert acima[2:8] == (
        Decimal("100.00"),
        Decimal("120.00"),
        Decimal("20.00"),
        Decimal("120.00"),
        "valid",
        Decimal("20.00"),
    )
    assert acima[11] is True

    abaixo = distribuidora(COORTE_CNPJS[1], 2023)
    assert abaixo[2:8] == (
        Decimal("100.00"),
        Decimal("80.00"),
        Decimal("-20.00"),
        Decimal("80.00"),
        "valid",
        Decimal("-20.00"),
    )

    planejado_zero = distribuidora(COORTE_CNPJS[2], 2023)
    assert planejado_zero[2:8] == (
        Decimal("0.00"),
        Decimal("10.00"),
        Decimal("10.00"),
        None,
        "planejado_zero",
        None,
    )
    assert planejado_zero[8] == "valid"

    planejado_nulo = distribuidora(COORTE_CNPJS[3], 2023)
    assert planejado_nulo[2:8] == (
        None,
        Decimal("5.00"),
        None,
        None,
        "planejado_null",
        None,
    )
    assert planejado_nulo[8:11] == ("null", "valid", "null")

    planejado_invalido = distribuidora(COORTE_CNPJS[4], 2023)
    assert planejado_invalido[2:8] == (
        None,
        Decimal("4.00"),
        None,
        None,
        "planejado_invalid",
        None,
    )
    assert planejado_invalido[8:11] == ("invalid", "valid", "invalid")

    realizado_zero = distribuidora(COORTE_CNPJS[5], 2023)
    assert realizado_zero[2:8] == (
        Decimal("100.00"),
        Decimal("0.00"),
        Decimal("-100.00"),
        Decimal("0.00"),
        "valid",
        Decimal("-100.00"),
    )
    assert realizado_zero[9] == "valid"

    assert nacionais == [
        (
            2023,
            Decimal("300.00"),
            Decimal("219.00"),
            None,
            None,
            "planejado_invalid",
            None,
            "invalid",
            "valid",
        ),
        (
            2024,
            Decimal("350.00"),
            Decimal("175.00"),
            Decimal("-175.00"),
            Decimal("50.00"),
            "valid",
            Decimal("-50.00"),
            "valid",
            "valid",
        ),
        (
            2025,
            Decimal("200.00"),
            Decimal("250.00"),
            Decimal("50.00"),
            Decimal("125.00"),
            "valid",
            Decimal("25.00"),
            "valid",
            "valid",
        ),
    ]


def test_mart04_idempotente(tmp_path, monkeypatch):
    banco = tmp_path / "mart04_idempotente.duckdb"
    preparar_banco(banco, linhas_mart04())
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_01()

    marts.executar_mart_04()
    with duckdb.connect(str(banco)) as con:
        primeira_distribuidora = con.execute(
            "SELECT * FROM marts.planejado_vs_realizado_distribuidora "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
        primeiro_nacional = con.execute(
            "SELECT * FROM marts.planejado_vs_realizado_nacional "
            "ORDER BY ano_referencia"
        ).fetchall()
    marts.executar_mart_04()
    with duckdb.connect(str(banco)) as con:
        segunda_distribuidora = con.execute(
            "SELECT * FROM marts.planejado_vs_realizado_distribuidora "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
        segundo_nacional = con.execute(
            "SELECT * FROM marts.planejado_vs_realizado_nacional "
            "ORDER BY ano_referencia"
        ).fetchall()

    assert segunda_distribuidora == primeira_distribuidora
    assert segundo_nacional == primeiro_nacional


def test_mart04_rollback_preserva_as_duas_saidas(tmp_path, monkeypatch):
    banco = tmp_path / "mart04_rollback.duckdb"
    preparar_banco(banco, linhas_mart04())
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.planejado_vs_realizado_distribuidora "
            "AS SELECT 'anterior_distribuidora' AS marcador"
        )
        con.execute(
            "CREATE TABLE marts.planejado_vs_realizado_nacional "
            "AS SELECT 'anterior_nacional' AS marcador"
        )
    conectar_teste(banco, monkeypatch)

    def falhar_apos_sql(con):
        raise ValueError("falha simulada após materializar MART 04")

    with pytest.raises(ValueError, match="falha simulada após materializar"):
        marts.executar_sql_mart(marts.MART_04_SQL, falhar_apos_sql)

    with duckdb.connect(str(banco)) as con:
        anterior_distribuidora = con.execute(
            "SELECT marcador FROM marts.planejado_vs_realizado_distribuidora"
        ).fetchall()
        anterior_nacional = con.execute(
            "SELECT marcador FROM marts.planejado_vs_realizado_nacional"
        ).fetchall()
    assert anterior_distribuidora == [("anterior_distribuidora",)]
    assert anterior_nacional == [("anterior_nacional",)]


def test_mart05_evolucao_temporal_e_reconciliacao(tmp_path, monkeypatch):
    banco = tmp_path / "mart05_test.duckdb"
    preparar_banco(banco, linhas_mart05())
    conectar_teste(banco, monkeypatch)

    assert marts.executar_mart_01() == {"linhas": 6}
    assert marts.executar_mart_02() == {"linhas": 6}
    assert marts.executar_mart_03()["linhas"] == 19
    assert marts.executar_mart_04() == {
        "linhas_distribuidoras": 11,
        "linhas_nacionais": 3,
    }
    resultado = marts.executar_mart_05()

    assert resultado == {"linhas_distribuidoras": 11, "linhas_agregadas": 6}
    with duckdb.connect(str(banco)) as con:
        distribuidores = con.execute(
            """
            SELECT cnpj, ano_referencia, top10_2025, ano_anterior,
                   total_planejado, variacao_planejado_absoluta,
                   status_variacao_planejado_absoluta,
                   variacao_planejado_percentual,
                   status_variacao_planejado_percentual,
                   total_realizado, variacao_realizado_absoluta,
                   status_variacao_realizado_absoluta,
                   variacao_realizado_percentual,
                   status_variacao_realizado_percentual
            FROM marts.evolucao_investimentos_distribuidora
            """
        ).fetchall()
        agregados = con.execute(
            """
            SELECT ano_referencia, escopo, ano_anterior,
                   total_planejado, variacao_planejado_absoluta,
                   status_variacao_planejado_absoluta,
                   variacao_planejado_percentual,
                   total_realizado, variacao_realizado_absoluta,
                   status_variacao_realizado_absoluta,
                   variacao_realizado_percentual
            FROM marts.evolucao_investimentos_agregada
            ORDER BY ano_referencia, escopo
            """
        ).fetchall()
        anos_exibidos = con.execute(
            """
            SELECT MIN(ano_referencia), MAX(ano_referencia)
            FROM marts.evolucao_investimentos_distribuidora
            """
        ).fetchone()
        tipos = dict(
            con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'marts'
                  AND table_name = 'evolucao_investimentos_distribuidora'
                """
            ).fetchall()
        )
        duplicadas = con.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT cnpj, ano_referencia
                FROM marts.evolucao_investimentos_distribuidora
                GROUP BY cnpj, ano_referencia HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        cnpjs_individuais = con.execute(
            "SELECT COUNT(DISTINCT cnpj) FROM marts.evolucao_investimentos_distribuidora"
        ).fetchone()[0]

    def distribuidora(cnpj, ano):
        return next(row for row in distribuidores if row[0] == cnpj and row[1] == ano)

    evolucao_positiva = distribuidora(COORTE_CNPJS[0], 2023)
    assert evolucao_positiva[2:9] == (
        True,
        2022,
        Decimal("150.00"),
        Decimal("50.00"),
        "valid",
        Decimal("50.00"),
        "valid",
    )
    assert evolucao_positiva[9:14] == (
        Decimal("120.00"),
        Decimal("20.00"),
        "valid",
        Decimal("20.00"),
        "valid",
    )
    assert distribuidora(OUTRO_CNPJ, 2023)[2] is False

    evolucao_zero = distribuidora(COORTE_CNPJS[0], 2024)
    assert evolucao_zero[5:9] == (
        Decimal("0.00"),
        "valid",
        Decimal("0.00"),
        "valid",
    )
    assert evolucao_zero[10:14] == (
        Decimal("0.00"),
        "valid",
        Decimal("0.00"),
        "valid",
    )

    evolucao_negativa = distribuidora(COORTE_CNPJS[0], 2025)
    assert evolucao_negativa[5:9] == (
        Decimal("-30.00"),
        "valid",
        Decimal("-20.00"),
        "valid",
    )
    assert evolucao_negativa[10:14] == (
        Decimal("30.00"),
        "valid",
        Decimal("25.00"),
        "valid",
    )

    sem_ano_anterior = distribuidora(COORTE_CNPJS[1], 2023)
    assert sem_ano_anterior[3] is None
    assert sem_ano_anterior[5] is None
    assert sem_ano_anterior[6] == "ano_anterior_ausente"
    assert sem_ano_anterior[8] == "ano_anterior_ausente"
    ano_intermediario_ausente = distribuidora(COORTE_CNPJS[1], 2025)
    assert ano_intermediario_ausente[3] == 2023
    assert ano_intermediario_ausente[6] == "ano_intermediario_ausente"
    assert ano_intermediario_ausente[8] == "ano_intermediario_ausente"

    base_zero = distribuidora(COORTE_CNPJS[2], 2023)
    assert base_zero[5] == Decimal("20.00")
    assert base_zero[6] == "valid"
    assert base_zero[7] is None
    assert base_zero[8] == "base_zero"
    assert base_zero[10] == Decimal("10.00")
    assert base_zero[13] == "base_zero"

    base_nulo = distribuidora(COORTE_CNPJS[3], 2023)
    assert base_nulo[6] == "valor_anterior_null"
    assert base_nulo[8] == "valor_anterior_null"
    assert base_nulo[11] == "valor_anterior_invalid"
    assert base_nulo[13] == "valor_anterior_invalid"
    base_invalido = distribuidora(COORTE_CNPJS[4], 2023)
    assert base_invalido[6] == "valor_anterior_invalid"
    assert base_invalido[8] == "valor_anterior_invalid"
    assert base_invalido[11] == "valor_anterior_null"
    assert base_invalido[13] == "valor_anterior_null"

    assert len(agregados) == 6
    assert anos_exibidos == (2023, 2025)
    assert all(row[2] == 2022 for row in agregados if row[0] == 2023)
    assert duplicadas == 0
    assert cnpjs_individuais == 6
    assert tipos["cnpj"] == "VARCHAR"
    assert tipos["total_planejado"].startswith("DECIMAL")
    assert tipos["total_realizado"].startswith("DECIMAL")
    assert tipos["variacao_planejado_percentual"] == "DECIMAL(18,2)"
    assert tipos["variacao_realizado_percentual"] == "DECIMAL(18,2)"
    assert all(row[0] >= 2023 for row in agregados)


def test_mart05_idempotente(tmp_path, monkeypatch):
    banco = tmp_path / "mart05_idempotente.duckdb"
    preparar_banco(banco, linhas_mart05())
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_01()

    marts.executar_mart_05()
    with duckdb.connect(str(banco)) as con:
        primeira_distribuidora = con.execute(
            "SELECT * FROM marts.evolucao_investimentos_distribuidora "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
        primeiro_agregado = con.execute(
            "SELECT * FROM marts.evolucao_investimentos_agregada "
            "ORDER BY ano_referencia, escopo"
        ).fetchall()
    marts.executar_mart_05()
    with duckdb.connect(str(banco)) as con:
        segunda_distribuidora = con.execute(
            "SELECT * FROM marts.evolucao_investimentos_distribuidora "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
        segundo_agregado = con.execute(
            "SELECT * FROM marts.evolucao_investimentos_agregada "
            "ORDER BY ano_referencia, escopo"
        ).fetchall()

    assert segunda_distribuidora == primeira_distribuidora
    assert segundo_agregado == primeiro_agregado


def test_mart05_rollback_preserva_as_duas_series(tmp_path, monkeypatch):
    banco = tmp_path / "mart05_rollback.duckdb"
    preparar_banco(banco, linhas_mart05())
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.evolucao_investimentos_distribuidora "
            "AS SELECT 'anterior_distribuidora' AS marcador"
        )
        con.execute(
            "CREATE TABLE marts.evolucao_investimentos_agregada "
            "AS SELECT 'anterior_agregada' AS marcador"
        )
    conectar_teste(banco, monkeypatch)

    def falhar_apos_sql(con):
        raise ValueError("falha simulada após materializar MART 05")

    with pytest.raises(ValueError, match="falha simulada após materializar"):
        marts.executar_sql_mart(marts.MART_05_SQL, falhar_apos_sql)

    with duckdb.connect(str(banco)) as con:
        anterior_distribuidora = con.execute(
            "SELECT marcador FROM marts.evolucao_investimentos_distribuidora"
        ).fetchall()
        anterior_agregada = con.execute(
            "SELECT marcador FROM marts.evolucao_investimentos_agregada"
        ).fetchall()
    assert anterior_distribuidora == [("anterior_distribuidora",)]
    assert anterior_agregada == [("anterior_agregada",)]


def test_mart06_rankings_separados_reconciliam_e_preservam_status(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart06_test.duckdb"
    preparar_banco(banco, linhas_mart06())
    conectar_teste(banco, monkeypatch)

    # Executa a cadeia existente para comprovar integração e permitir reconciliação.
    marts.executar_mart_01()
    marts.executar_mart_02()
    marts.executar_mart_03()
    marts.executar_mart_04()
    marts.executar_mart_05()
    resultado = marts.executar_mart_06()
    assert resultado == {"linhas": 126}

    with duckdb.connect(str(banco)) as con:
        linhas = con.execute(
            """
            SELECT ano_referencia, cnpj, escopo, medida, valor_investimento,
                   status_valor, top10_2025, posicao, rotulo_pdd, rotulo_indger
            FROM marts.ranking_investimentos
            WHERE ano_referencia = 2023
            ORDER BY escopo, medida, posicao NULLS LAST, cnpj
            """
        ).fetchall()
        chaves_duplicadas = con.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT ano_referencia, cnpj, escopo, medida
                FROM marts.ranking_investimentos
                GROUP BY ano_referencia, cnpj, escopo, medida
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        tipos = dict(
            con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'marts'
                  AND table_name = 'ranking_investimentos'
                """
            ).fetchall()
        )
        coorte = con.execute(
            "SELECT cnpj FROM marts.cohorte_top10_2025 ORDER BY posicao"
        ).fetchall()
        escopo_top10_cnpjs = con.execute(
            """
            SELECT DISTINCT cnpj
            FROM marts.ranking_investimentos
            WHERE escopo = 'top10'
            """
        ).fetchall()

    def buscar(cnpj, escopo, medida):
        return next(
            row
            for row in linhas
            if row[1:4] == (cnpj, escopo, medida)
        )

    fora = buscar(OUTRO_CNPJ, "nacional", "planejado")
    assert fora[4:8] == (Decimal("200.00"), "valid", False, 1)
    assert fora[8:] == (f"Agente {OUTRO_CNPJ}", None)

    empatados_nacional = buscar(COORTE_CNPJS[0], "nacional", "planejado")
    empatados_top10 = buscar(COORTE_CNPJS[0], "top10", "planejado")
    assert empatados_nacional[4] == empatados_top10[4] == Decimal("100.00")
    assert empatados_nacional[7] == 2
    assert empatados_top10[7] == 1
    assert buscar(COORTE_CNPJS[1], "top10", "planejado")[7] == 2

    # O realizado tem uma ordem independente da classificação planejada.
    assert buscar(COORTE_CNPJS[3], "nacional", "realizado")[7] == 2
    assert buscar(COORTE_CNPJS[1], "nacional", "realizado")[7] == 3
    assert buscar(COORTE_CNPJS[0], "nacional", "realizado")[7] == 4
    assert buscar(COORTE_CNPJS[0], "top10", "realizado")[7] == 3

    zero = buscar(COORTE_CNPJS[2], "nacional", "planejado")
    assert zero[4:8] == (Decimal("0.00"), "valid", True, 8)
    nulo = buscar(COORTE_CNPJS[3], "nacional", "planejado")
    assert nulo[4:8] == (None, "null", True, None)
    invalido = buscar(COORTE_CNPJS[4], "nacional", "planejado")
    assert invalido[4:8] == (Decimal("500.00"), "invalid", True, None)
    parcial = buscar(COORTE_CNPJS[4], "nacional", "realizado")
    assert parcial[4:8] == (Decimal("1.00"), "partial", True, None)
    assert chaves_duplicadas == 0
    assert tipos["cnpj"] == "VARCHAR"
    assert tipos["valor_investimento"].startswith("DECIMAL")
    assert [linha[0] for linha in coorte] == COORTE_CNPJS
    assert set(escopo_top10_cnpjs) <= set(coorte)


def test_mart06_idempotente(tmp_path, monkeypatch):
    banco = tmp_path / "mart06_idempotente.duckdb"
    preparar_banco(banco, linhas_mart06())
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_01()

    marts.executar_mart_06()
    with duckdb.connect(str(banco)) as con:
        primeira = con.execute(
            "SELECT * FROM marts.ranking_investimentos "
            "ORDER BY ano_referencia, escopo, medida, posicao NULLS LAST, cnpj"
        ).fetchall()
    marts.executar_mart_06()
    with duckdb.connect(str(banco)) as con:
        segunda = con.execute(
            "SELECT * FROM marts.ranking_investimentos "
            "ORDER BY ano_referencia, escopo, medida, posicao NULLS LAST, cnpj"
        ).fetchall()
    assert segunda == primeira


def test_mart06_bloqueia_coorte_top10_incompleta_ou_duplicada(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart06_coorte_incompleta.duckdb"
    preparar_banco(banco, linhas_mart06())
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_01()
    marts.executar_mart_06()

    with duckdb.connect(str(banco)) as con:
        con.execute(
            """
            DELETE FROM marts.ranking_investimentos
            WHERE ano_referencia = 2024 AND escopo = 'top10'
              AND medida = 'planejado' AND cnpj = ?
            """,
            [COORTE_CNPJS[0]],
        )
        with pytest.raises(ValueError, match="coorte.*incompleta.*faltantes"):
            marts._validar_mart_06(con)

    # Recria o resultado válido e confirma que a duplicação também é diagnosticada.
    marts.executar_mart_06()
    with duckdb.connect(str(banco)) as con:
        con.execute(
            """
            INSERT INTO marts.ranking_investimentos
            SELECT * FROM marts.ranking_investimentos
            WHERE ano_referencia = 2024 AND escopo = 'top10'
              AND medida = 'planejado' AND cnpj = ?
            """,
            [COORTE_CNPJS[0]],
        )
        with pytest.raises(ValueError, match="top10 contém CNPJ/ano/medida duplicado"):
            marts._validar_mart_06(con)


def test_mart06_rollback_preserva_tabela_anterior(tmp_path, monkeypatch):
    banco = tmp_path / "mart06_rollback.duckdb"
    preparar_banco(banco, linhas_mart06())
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.ranking_investimentos "
            "AS SELECT 'anterior' AS marcador"
        )
    conectar_teste(banco, monkeypatch)

    def falhar_apos_sql(con):
        raise ValueError("falha simulada após materializar MART 06")

    with pytest.raises(ValueError, match="falha simulada após materializar"):
        marts.executar_sql_mart(marts.MART_06_SQL, falhar_apos_sql)

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute(
            "SELECT marcador FROM marts.ranking_investimentos"
        ).fetchall()
    assert anterior == [("anterior",)]


def test_mart07_top10_nacional_ranking_variacoes_e_regressao(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart07_test.duckdb"
    preparar_banco(banco, linhas_pdd_mart07(), linhas_indger_mart07())
    conectar_teste(banco, monkeypatch)

    marts.executar_mart_01()
    marts.executar_mart_02()
    marts.executar_mart_03()
    marts.executar_mart_04()
    marts.executar_mart_05()
    marts.executar_mart_06()
    resultado = marts.executar_mart_07()
    assert resultado == {"linhas_top10": 30, "linhas_nacionais": 33}

    with duckdb.connect(str(banco)) as con:
        top10 = con.execute(
            """
            SELECT ano_referencia, cnpj, qtd_uc_dezembro, status_cobertura,
                   posicao_anual, posicao_coorte_2025, ano_anterior,
                   qtd_uc_ano_anterior, variacao_absoluta_uc,
                   status_variacao_absoluta, variacao_percentual_uc,
                   status_variacao_percentual
            FROM marts.ranking_por_uc_top10
            ORDER BY ano_referencia, posicao_anual NULLS LAST, cnpj
            """
        ).fetchall()
        nacional = con.execute(
            """
            SELECT ano_referencia, cnpj, qtd_uc_dezembro, posicao_nacional,
                   posicao_coorte_2025, top10_2025
            FROM marts.ranking_por_uc_nacional
            ORDER BY ano_referencia, posicao_nacional NULLS LAST, cnpj
            """
        ).fetchall()
        duplicadas = con.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT ano_referencia, cnpj
                FROM marts.ranking_por_uc_top10
                GROUP BY ano_referencia, cnpj HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        coorte = con.execute(
            "SELECT posicao, cnpj, uc_dez_2025 "
            "FROM marts.cohorte_top10_2025 ORDER BY posicao"
        ).fetchall()
        tipos = {
            (tabela, coluna): tipo
            for tabela, coluna, tipo in con.execute(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'marts'
                  AND table_name IN ('ranking_por_uc_top10', 'ranking_por_uc_nacional')
                """
            ).fetchall()
        }

    assert len(top10) == 30
    assert all(
        sum(row[0] == ano for row in top10) == 10
        for ano in (2023, 2024, 2025)
    )
    assert [row[0] for row in coorte] == list(range(1, 11))
    assert {row[1] for row in top10} == {row[1] for row in coorte}
    assert all(row[1] in {member[1] for member in coorte} for row in top10)
    assert all(
        {row[4] for row in top10 if row[0] == ano} == set(range(1, 11))
        for ano in (2023, 2024, 2025)
    )
    assert duplicadas == 0
    assert len(nacional) == 33
    assert any(row[1] == OUTRO_CNPJ and row[5] is False for row in nacional)
    # Em 2023/24 o outsider lidera o nacional, mas está ausente do top10 fixo.
    assert next(row for row in nacional if row[0:2] == (2023, OUTRO_CNPJ))[3] == 1
    assert next(row for row in nacional if row[0:2] == (2024, OUTRO_CNPJ))[3] == 1
    assert next(
        row for row in top10 if row[0:2] == (2024, COORTE_CNPJS[2])
    )[4] == 1
    assert next(
        row for row in top10 if row[0:2] == (2024, COORTE_CNPJS[1])
    )[4] == 2

    cnpj_top10 = COORTE_CNPJS[0]
    posicao_fixa, uc_dez25 = next(
        (posicao, quantidade)
        for posicao, cnpj, quantidade in coorte
        if cnpj == cnpj_top10
    )
    linha_2025 = next(row for row in top10 if row[0:2] == (2025, cnpj_top10))
    assert linha_2025[2] == uc_dez25
    assert linha_2025[5] == posicao_fixa
    assert linha_2025[8:12] == (
        20,
        "valid",
        Decimal("20.00"),
        "valid",
    )
    linha_2024_zero_base = next(
        row for row in top10 if row[0:2] == (2024, cnpj_top10)
    )
    assert linha_2024_zero_base[8:12] == (
        100,
        "valid",
        None,
        "base_zero",
    )
    assert tipos[("ranking_por_uc_top10", "cnpj")] == "VARCHAR"
    assert tipos[("ranking_por_uc_top10", "qtd_uc_dezembro")] == "BIGINT"
    assert tipos[("ranking_por_uc_nacional", "qtd_uc_dezembro")] == "BIGINT"


def test_mart07_preserva_status_de_uc_e_referencias_ausentes(
    tmp_path, monkeypatch
):
    linhas_indger = linhas_indger_mart07()
    ajustadas = []
    for linha in linhas_indger:
        cnpj, municipio, referencia, quantidade, status = linha
        ano = referencia.year
        if cnpj == COORTE_CNPJS[2] and ano == 2024:
            continue
        if cnpj == COORTE_CNPJS[1] and ano == 2024 and municipio.endswith("00"):
            quantidade, status = None, "null"
        if cnpj == COORTE_CNPJS[3] and ano == 2023 and municipio.endswith("00"):
            quantidade, status = None, "invalid"
        if cnpj == COORTE_CNPJS[4] and ano == 2023:
            quantidade, status = None, "null"
        ajustadas.append((cnpj, municipio, referencia, quantidade, status))

    banco = tmp_path / "mart07_status.duckdb"
    preparar_banco(banco, linhas_pdd_mart07(), ajustadas)
    conectar_teste(banco, monkeypatch)
    resultado = marts.executar_mart_07()
    assert resultado["linhas_top10"] == 30

    with duckdb.connect(str(banco)) as con:
        linhas = con.execute(
            """
            SELECT ano_referencia, cnpj, qtd_municipios_dezembro,
                   qtd_uc_validas, qtd_uc_nulas, qtd_uc_invalidas,
                   qtd_uc_dezembro, status_cobertura, posicao_anual,
                   variacao_absoluta_uc, status_variacao_absoluta,
                   variacao_percentual_uc, status_variacao_percentual
            FROM marts.ranking_por_uc_top10
            """
        ).fetchall()

    def buscar(ano, cnpj):
        return next(row for row in linhas if row[0:2] == (ano, cnpj))

    sem_referencia = buscar(2024, COORTE_CNPJS[2])
    assert sem_referencia[2:9] == (0, 0, 0, 0, None, "sem_referencia", None)
    variacao_base_ausente = buscar(2025, COORTE_CNPJS[2])
    assert variacao_base_ausente[10] == "uc_anterior_sem_referencia"
    assert variacao_base_ausente[9] is None

    parcial = buscar(2024, COORTE_CNPJS[1])
    assert parcial[3:9] == (1, 1, 0, None, "partial", None)
    assert buscar(2025, COORTE_CNPJS[1])[10] == "uc_anterior_partial"

    invalido = buscar(2023, COORTE_CNPJS[3])
    assert invalido[4:9] == (0, 1, None, "invalid", None)
    nulo = buscar(2023, COORTE_CNPJS[4])
    assert nulo[3:9] == (0, 2, 0, None, "null", None)
    zero = buscar(2023, COORTE_CNPJS[0])
    assert zero[6:9] == (0, "zero", 8)


def test_mart07_bloqueia_coorte_incompleta_e_duplicidades(
    tmp_path, monkeypatch
):
    banco = tmp_path / "mart07_coorte_incompleta.duckdb"
    linhas_indger = linhas_indger_mart07()
    preparar_banco(banco, linhas_pdd_mart07(), linhas_indger)
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_07()

    with duckdb.connect(str(banco)) as con:
        con.execute(
            """
            DELETE FROM marts.ranking_por_uc_top10
            WHERE ano_referencia = 2024 AND cnpj = ?
            """,
            [COORTE_CNPJS[0]],
        )
        with pytest.raises(ValueError, match="Saída principal.*incompleta.*faltantes"):
            marts._validar_mart_07(con)

    marts.executar_mart_07()
    with duckdb.connect(str(banco)) as con:
        con.execute(
            """
            INSERT INTO marts.ranking_por_uc_top10
            SELECT * FROM marts.ranking_por_uc_top10
            WHERE ano_referencia = 2024 AND cnpj = ?
            """,
            [COORTE_CNPJS[0]],
        )
        with pytest.raises(ValueError, match="CNPJ/ano duplicada"):
            marts._validar_mart_07(con)

    marts.executar_mart_07()
    duplicada = linhas_indger[0]
    linhas_indger.append(duplicada)
    with duckdb.connect(str(banco)) as con:
        con.execute(
            """
            INSERT INTO refined.indger_comerciais
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (*duplicada, f"Distribuidora {duplicada[0]}"),
        )
    with pytest.raises(ValueError, match="chave CNPJ.*município.*dezembro duplicada"):
        marts.executar_mart_07()


def test_mart07_idempotente_e_rollback(tmp_path, monkeypatch):
    banco = tmp_path / "mart07_idempotencia_rollback.duckdb"
    preparar_banco(banco, linhas_pdd_mart07(), linhas_indger_mart07())
    conectar_teste(banco, monkeypatch)
    marts.executar_mart_07()
    with duckdb.connect(str(banco)) as con:
        primeira_top10 = con.execute(
            "SELECT * FROM marts.ranking_por_uc_top10 "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
        primeira_nacional = con.execute(
            "SELECT * FROM marts.ranking_por_uc_nacional "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
    marts.executar_mart_07()
    with duckdb.connect(str(banco)) as con:
        segunda_top10 = con.execute(
            "SELECT * FROM marts.ranking_por_uc_top10 "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
        segunda_nacional = con.execute(
            "SELECT * FROM marts.ranking_por_uc_nacional "
            "ORDER BY ano_referencia, cnpj"
        ).fetchall()
        con.execute(
            "CREATE OR REPLACE TABLE marts.ranking_por_uc_top10 "
            "AS SELECT 'anterior_top10' AS marcador"
        )
        con.execute(
            "CREATE OR REPLACE TABLE marts.ranking_por_uc_nacional "
            "AS SELECT 'anterior_nacional' AS marcador"
        )

    assert segunda_top10 == primeira_top10
    assert segunda_nacional == primeira_nacional

    def falhar_apos_sql(con):
        raise ValueError("falha simulada após materializar MART 07")

    with pytest.raises(ValueError, match="falha simulada após materializar"):
        marts.executar_sql_mart(
            marts.MART_07_SQL,
            falhar_apos_sql,
            validacao_previa=marts._validar_chaves_uc_mart_07,
        )

    with duckdb.connect(str(banco)) as con:
        top10_anterior = con.execute(
            "SELECT marcador FROM marts.ranking_por_uc_top10"
        ).fetchall()
        nacional_anterior = con.execute(
            "SELECT marcador FROM marts.ranking_por_uc_nacional"
        ).fetchall()
    assert top10_anterior == [("anterior_top10",)]
    assert nacional_anterior == [("anterior_nacional",)]

