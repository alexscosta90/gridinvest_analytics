import csv
from pathlib import Path

import duckdb
import pytest

from pipeline import ingestao
from pipeline.ingestao import validar_linha


def test_preserva_cnpj_com_zero_inicial(tmp_path):
    """Verifica se a leitura mantém zeros à esquerda."""

    arquivo = tmp_path / "teste.csv"

    with arquivo.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["NumCPFCNPJ", "VlrTotalRealizado"])
        escritor.writerow(["02341467000120", "415539,72"])

    with arquivo.open("r", encoding="utf-8", newline="") as f:
        leitor = csv.DictReader(f)
        registro = next(leitor)

    assert registro["NumCPFCNPJ"] == "02341467000120"
    assert registro["VlrTotalRealizado"] == "415539,72"


def test_validar_linha_com_12_colunas():
    """Uma linha válida não deve produzir erro."""
    linha = ["valor"] * 12

    validar_linha(linha, numero_linha=2)


def test_validar_linha_com_11_colunas():
    """Uma linha incompleta deve produzir ValueError."""
    linha = ["valor"] * 11

    with pytest.raises(ValueError, match="esperadas 12 colunas"):
        validar_linha(linha, numero_linha=3)


def test_validar_linha_com_13_colunas():
    """Uma linha com campos extras também deve falhar."""
    linha = ["valor"] * 13

    with pytest.raises(ValueError, match="encontradas 13"):
        validar_linha(linha, numero_linha=4)


def test_ingerir_csv_com_dados_ficticios(tmp_path, monkeypatch):
    """Testa a ingestão usando um banco temporário."""

    # Cria um CSV fictício
    arquivo = tmp_path / "dados_teste.csv"

    arquivo.write_text(
        "NumCNPJ;QtdUCAtiva\n02341467000120;5000\n04368898000106;8000\n",
        encoding="utf-8",
    )

    # Cria um banco DuckDB temporário
    banco_teste = tmp_path / "teste.duckdb"

    def conectar_teste():
        return duckdb.connect(str(banco_teste))

    # Substitui a conexão real pela conexão de teste
    monkeypatch.setattr(ingestao, "conectar", conectar_teste)

    # Executa a função real de ingestão
    ingestao.ingerir_csv(
        caminho=Path(arquivo),
        tabela="indger_comerciais",
        separador=";",
        colunas_esperadas=["NumCNPJ", "QtdUCAtiva"],
    )

    # Consulta os dados inseridos
    with duckdb.connect(str(banco_teste)) as con:
        registros = con.execute(
            "SELECT NumCNPJ, QtdUCAtiva FROM raw.indger_comerciais ORDER BY NumCNPJ"
        ).fetchall()

    # Compara os resultados com os valores esperados
    assert registros == [
        ("02341467000120", "5000"),
        ("04368898000106", "8000"),
    ]


def test_ingerir_csv_duas_vezes(tmp_path, monkeypatch):
    """Verifica se duas execuções não duplicam registros."""

    arquivo = tmp_path / "dados_teste.csv"
    arquivo.write_text(
        "NumCNPJ;QtdUCAtiva\n02341467000120;5000\n04368898000106;8000\n",
        encoding="utf-8",
    )

    banco_teste = tmp_path / "teste.duckdb"

    def conectar_teste():
        return duckdb.connect(str(banco_teste))

    monkeypatch.setattr(ingestao, "conectar", conectar_teste)

    for _ in range(2):
        ingestao.ingerir_csv(
            caminho=arquivo,
            tabela="indger_comerciais",
            separador=";",
            colunas_esperadas=["NumCNPJ", "QtdUCAtiva"],
        )

    with duckdb.connect(str(banco_teste)) as con:
        total = con.execute("SELECT COUNT(*) FROM raw.indger_comerciais").fetchone()[0]

    assert total == 2


def test_ingerir_csv_rollback_preserva_dados(tmp_path, monkeypatch):
    """Verifica se um erro preserva os dados da ingestão anterior."""

    arquivo = tmp_path / "dados_teste.csv"
    banco_teste = tmp_path / "teste.duckdb"

    def conectar_teste():
        return duckdb.connect(str(banco_teste))

    monkeypatch.setattr(ingestao, "conectar", conectar_teste)

    # Primeira ingestão: arquivo válido
    arquivo.write_text(
        "NumCNPJ;QtdUCAtiva\n02341467000120;5000\n04368898000106;8000\n",
        encoding="utf-8",
    )

    ingestao.ingerir_csv(
        caminho=arquivo,
        tabela="indger_comerciais",
        separador=";",
        colunas_esperadas=["NumCNPJ", "QtdUCAtiva"],
    )

    # Segunda ingestão: arquivo com uma linha inválida
    arquivo.write_text(
        "NumCNPJ;QtdUCAtiva\n"
        "11111111000111;9000\n"
        "22222222000122;10000\n"
        "33333333000133\n",
        encoding="utf-8",
    )

    # A segunda ingestão deve falhar
    with pytest.raises(ValueError, match="esperadas 2 colunas"):
        ingestao.ingerir_csv(
            caminho=arquivo,
            tabela="indger_comerciais",
            separador=";",
            colunas_esperadas=["NumCNPJ", "QtdUCAtiva"],
        )

    # Confere se os dados da primeira ingestão continuam no banco
    with duckdb.connect(str(banco_teste)) as con:
        registros = con.execute(
            "SELECT NumCNPJ, QtdUCAtiva FROM raw.indger_comerciais ORDER BY NumCNPJ"
        ).fetchall()

    assert registros == [
        ("02341467000120", "5000"),
        ("04368898000106", "8000"),
    ]
