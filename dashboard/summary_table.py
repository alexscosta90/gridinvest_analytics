"""Helpers visuais para a tabela executiva da Visão Geral."""

import base64
from html import escape

from dashboard.logos import resolver_logo
from dashboard.metadata import nome_marca


def imagem_distribuidora(cnpj: str, nome: str, uf: str) -> str:
    """Monta logo, marca e UF numa imagem única para uma célula compacta."""
    marca = nome_marca(cnpj, nome)
    caminho_logo = resolver_logo(cnpj)
    imagem = ""

    if caminho_logo:
        conteudo = base64.b64encode(caminho_logo.read_bytes()).decode("ascii")
        imagem = (
            '<image x="8" y="8" width="42" height="34" '
            'preserveAspectRatio="xMidYMid meet" '
            f'href="data:image/png;base64,{conteudo}" />'
        )
    else:
        inicial = escape(marca[:1] or "D")
        imagem = (
            '<circle cx="27" cy="25" r="17" fill="#19302d" />'
            f'<text x="27" y="30" text-anchor="middle" fill="#58d6a0" '
            f'font-size="14" font-weight="700">{inicial}</text>'
        )

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="210" height="50" '
        'viewBox="0 0 210 50">'
        f"{imagem}"
        f'<text x="58" y="22" fill="#f2f5f7" font-family="Arial, sans-serif" '
        f'font-size="13" font-weight="700">{escape(marca)}</text>'
        f'<text x="58" y="39" fill="#9baab3" font-family="Arial, sans-serif" '
        f'font-size="11">{escape(uf.upper())}</text>'
        "</svg>"
    )
    uri = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{uri}"
