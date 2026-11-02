"""Metadados geográficos manuais para os dez CNPJs da coorte fixa."""

METADADOS_POR_CNPJ = {
    "06981180000116": {"uf": "MG", "regiao": "Sudeste"},
    "61695227000193": {"uf": "SP", "regiao": "Sudeste"},
    "15139629000194": {"uf": "BA", "regiao": "Nordeste"},
    "04368898000106": {"uf": "PR", "regiao": "Sul"},
    "33050196000188": {"uf": "SP", "regiao": "Sudeste"},
    "60444437000146": {"uf": "RJ", "regiao": "Sudeste"},
    "07047251000170": {"uf": "CE", "regiao": "Nordeste"},
    "10835932000108": {"uf": "PE", "regiao": "Nordeste"},
    "08336783000190": {"uf": "SC", "regiao": "Sul"},
    "01543032000104": {"uf": "GO", "regiao": "Centro-Oeste"},
}

NOMES_MARCA_POR_CNPJ = {
    "06981180000116": "CEMIG",
    "61695227000193": "ENEL",
    "15139629000194": "NEOENERGIA",
    "04368898000106": "COPEL",
    "33050196000188": "CPFL",
    "60444437000146": "LIGHT",
    "07047251000170": "ENEL",
    "10835932000108": "NEOENERGIA",
    "08336783000190": "CELESC",
    "01543032000104": "EQUATORIAL",
}

TIPOS_INVESTIMENTO_EXIBIDOS = ("Expansão", "Melhoria", "Renovação")


def nome_marca(cnpj: str, nome_fallback: str = "") -> str:
    """Retorna o nome curto da marca usando CNPJ como chave estável."""
    return NOMES_MARCA_POR_CNPJ.get(cnpj, nome_fallback).upper()
