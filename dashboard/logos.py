"""Mapeamento opcional de CNPJs da coorte para arquivos locais de logo."""

from pathlib import Path

from pipeline.db import BASE_DIR

DIRETORIO_LOGOS = BASE_DIR / "assets" / "logos"

# Os nomes exibidos vêm do MART 06; esta tabela associa o CNPJ ao arquivo local.
ARQUIVOS_LOGO_POR_CNPJ = {
    "06981180000116": "cemig.png",
    "61695227000193": "enel_sp.png",
    "15139629000194": "neoenergia_coelba.png",
    "04368898000106": "copel.png",
    "33050196000188": "cpfl_paulista.png",
    "60444437000146": "light.png",
    "07047251000170": "enel_ceara.png",
    "10835932000108": "neoenergia_pernambuco.png",
    "08336783000190": "celesc.png",
    "01543032000104": "equatorial_goias.png",
}


def resolver_logo(
    cnpj: str,
    diretorio: str | Path = DIRETORIO_LOGOS,
) -> Path | None:
    """Retorna o logo existente ou None para usar o rótulo como fallback."""
    nome_arquivo = ARQUIVOS_LOGO_POR_CNPJ.get(cnpj)
    if nome_arquivo is None:
        return None

    caminho = Path(diretorio) / nome_arquivo
    return caminho if caminho.is_file() else None
