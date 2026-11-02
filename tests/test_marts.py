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
        (cnpj, f"{posicao:07d}", date(2025, 12, 1), 50000 - posicao * 1000)
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
    con.executemany(
        "INSERT INTO refined.pdd VALUES (?, ?, ?, ?, ?, ?, ?)",
        linhas_pdd,
    )
    con.execute(
        """
        CREATE TABLE refined.indger_comerciais (
            NumCNPJ VARCHAR,
            CodMunicipioIBGE VARCHAR,
            DatReferenciaInformada DATE,
            QtdUCAtiva BIGINT
        )
        """
    )
    con.executemany(
        "INSERT INTO refined.indger_comerciais VALUES (?, ?, ?, ?)",
        linhas_indger if linhas_indger is not None else linhas_indger_dezembro(),
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
            VALUES ('99988888000199', '9999999', DATE '2025-12-01', 99999999)
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

