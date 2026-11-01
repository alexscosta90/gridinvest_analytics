import csv


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


import pytest

from pipeline.ingestao import validar_linha


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
