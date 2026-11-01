from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from pipeline import refined
from pipeline.ingestao_indger import COLUNAS_INDGER

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


def preparar_raw_indger(
    caminho: Path, linhas: list[tuple[str, ...]]
) -> None:
    con = duckdb.connect(str(caminho))
    definicao = ", ".join(f'"{coluna}" VARCHAR' for coluna in COLUNAS_INDGER)
    con.execute("CREATE SCHEMA raw")
    con.execute(f"CREATE TABLE raw.indger_comerciais ({definicao})")
    placeholders = ", ".join("?" for _ in COLUNAS_INDGER)
    con.executemany(
        f"INSERT INTO raw.indger_comerciais VALUES ({placeholders})", linhas
    )
    con.close()


def linha_indger(**valores: str) -> tuple[str, ...]:
    registro = {coluna: "" for coluna in COLUNAS_INDGER}
    registro.update(
        {
            "DatGeracaoConjuntoDados": "2025-03-15",
            "NumCNPJ": "00123456000199",
            "NomAgente": "Distribuidora Exemplo",
            "DatReferenciaInformada": "2025-03-01",
            "CodMunicipioIBGE": "0012345",
            "QtdUCAtiva": "1500",
            "DthCarga": "2025-03-16 12:30:45",
        }
    )
    registro.update(valores)
    return tuple(registro[coluna] for coluna in COLUNAS_INDGER)


def conectar_indger_teste(caminho: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        refined,
        "conectar",
        lambda: duckdb.connect(str(caminho)),
    )


def test_transformar_indger_converte_tipos_e_preserva_origem(
    tmp_path, monkeypatch
):
    banco = tmp_path / "indger.duckdb"
    preparar_raw_indger(
        banco,
        [
            linha_indger(),
            linha_indger(
                NumCNPJ="00987654000111",
                DatReferenciaInformada="data-invalida",
                DatGeracaoConjuntoDados="",
                DthCarga="timestamp-invalido",
                QtdUCAtiva="nao-inteiro",
            ),
        ],
    )
    conectar_indger_teste(banco, monkeypatch)

    resultado = refined.transformar_indger()

    assert resultado["linhas_origem"] == 2
    assert resultado["linhas_destino"] == 2
    assert resultado["referencias_invalidas"] == 1
    assert resultado["datas_geracao_invalidas"] == 0
    assert resultado["cargas_invalidas"] == 1
    assert resultado["uc_ativas_invalidas"] == 1
    with duckdb.connect(str(banco)) as con:
        registros = con.execute(
            """
            SELECT NumCNPJ, CodMunicipioIBGE,
                   DatReferenciaInformada, DatReferenciaInformada_raw,
                   DatReferenciaInformada_status,
                   DatGeracaoConjuntoDados, DatGeracaoConjuntoDados_raw,
                   DatGeracaoConjuntoDados_status,
                   DthCarga, DthCarga_raw, DthCarga_status,
                   QtdUCAtiva, QtdUCAtiva_raw, QtdUCAtiva_status
            FROM refined.indger_comerciais ORDER BY NumCNPJ
            """
        ).fetchall()
        tipos = dict(
            con.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'refined'
                  AND table_name = 'indger_comerciais'
                """
            ).fetchall()
        )
        raw_total = con.execute(
            "SELECT COUNT(*) FROM raw.indger_comerciais"
        ).fetchone()[0]

    assert registros == [
        (
            "00123456000199",
            "0012345",
            date(2025, 3, 1),
            "2025-03-01",
            "valid",
            date(2025, 3, 15),
            "2025-03-15",
            "valid",
            datetime(2025, 3, 16, 12, 30, 45),
            "2025-03-16 12:30:45",
            "valid",
            1500,
            "1500",
            "valid",
        ),
        (
            "00987654000111",
            "0012345",
            None,
            "data-invalida",
            "invalid",
            None,
            "",
            "null",
            None,
            "timestamp-invalido",
            "invalid",
            None,
            "nao-inteiro",
            "invalid",
        ),
    ]
    assert tipos["NumCNPJ"] == "VARCHAR"
    assert tipos["CodMunicipioIBGE"] == "VARCHAR"
    assert tipos["DatReferenciaInformada"] == "DATE"
    assert tipos["DatGeracaoConjuntoDados"] == "DATE"
    assert tipos["DthCarga"] == "TIMESTAMP"
    assert tipos["QtdUCAtiva"] == "BIGINT"
    assert raw_total == 2


def test_transformar_indger_preserva_duplicidades_e_sinaliza_ibge_zero(
    tmp_path, monkeypatch
):
    banco = tmp_path / "indger.duckdb"
    duplicada = linha_indger(
        NumCNPJ="00999999000199",
        DatReferenciaInformada="2026-06-01",
        CodMunicipioIBGE="4306072",
    )
    linhas = [duplicada, duplicada]
    linhas.extend(
        linha_indger(
            NumCNPJ=f"{numero:014d}",
            CodMunicipioIBGE="0",
            DatReferenciaInformada=f"2025-{(numero - 1) % 12 + 1:02d}-01",
        )
        for numero in range(1, 16)
    )
    preparar_raw_indger(banco, linhas)
    conectar_indger_teste(banco, monkeypatch)

    resultado = refined.transformar_indger()

    assert resultado["linhas_origem"] == 17
    assert resultado["linhas_destino"] == 17
    assert resultado["grupos_chave_repetida"] == 1
    assert resultado["linhas_com_chave_repetida"] == 2
    assert resultado["ibge_zero_para_revisao"] == 15
    with duckdb.connect(str(banco)) as con:
        linhas_duplicadas = con.execute(
            """
            SELECT NumCNPJ, CodMunicipioIBGE, DatReferenciaInformada_raw,
                   QtdUCAtiva_raw, CodMunicipioIBGE_revisar, duplicidade_chave
            FROM refined.indger_comerciais
            WHERE NumCNPJ = '00999999000199'
            ORDER BY NumCNPJ
            """
        ).fetchall()
        ibge_zero = con.execute(
            """
            SELECT COUNT(*) FROM refined.indger_comerciais
            WHERE CodMunicipioIBGE = '0' AND CodMunicipioIBGE_revisar
            """
        ).fetchone()[0]

    assert len(linhas_duplicadas) == 2
    assert linhas_duplicadas[0] == linhas_duplicadas[1]
    assert linhas_duplicadas[0][-2:] == (False, True)
    assert ibge_zero == 15


def test_transformar_indger_pode_ser_reexecutada_sem_duplicar(
    tmp_path, monkeypatch
):
    banco = tmp_path / "indger.duckdb"
    duplicada = linha_indger()
    preparar_raw_indger(banco, [duplicada, duplicada])
    conectar_indger_teste(banco, monkeypatch)

    refined.transformar_indger()
    refined.transformar_indger()

    with duckdb.connect(str(banco)) as con:
        total = con.execute(
            "SELECT COUNT(*) FROM refined.indger_comerciais"
        ).fetchone()[0]
        repetidas = con.execute(
            """
            SELECT COUNT(*) FROM refined.indger_comerciais
            WHERE duplicidade_chave
            """
        ).fetchone()[0]
    assert total == 2
    assert repetidas == 2


def test_falha_indger_apos_substituicao_reverte_tabela_anterior(
    tmp_path, monkeypatch
):
    banco = tmp_path / "indger.duckdb"
    preparar_raw_indger(banco, [linha_indger()])
    with duckdb.connect(str(banco)) as con:
        con.execute("CREATE SCHEMA refined")
        con.execute(
            "CREATE TABLE refined.indger_comerciais "
            "AS SELECT 'anterior' AS marcador"
        )

    class FalhaAposSubstituicao:
        def __init__(self):
            self.con = duckdb.connect(str(banco))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.con.close()

        def execute(self, consulta):
            if consulta.strip().startswith(
                "SELECT COUNT(*) FROM refined.indger_comerciais"
            ):
                raise RuntimeError("falha de validação simulada")
            return self.con.execute(consulta)

    monkeypatch.setattr(refined, "conectar", FalhaAposSubstituicao)

    with pytest.raises(RuntimeError, match="falha de validação"):
        refined.transformar_indger()

    with duckdb.connect(str(banco)) as con:
        anterior = con.execute(
            "SELECT marcador FROM refined.indger_comerciais"
        ).fetchall()
        raw_total = con.execute(
            "SELECT COUNT(*) FROM raw.indger_comerciais"
        ).fetchone()[0]

    assert anterior == [("anterior",)]
    assert raw_total == 1
