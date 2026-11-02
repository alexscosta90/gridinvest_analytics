"""Preparação leve dos rótulos e validações da página inicial."""

from collections import Counter
from decimal import Decimal
from typing import Any

from dashboard.metadata import METADADOS_POR_CNPJ, nome_marca


def formatar_bilhoes(valor: Decimal | None) -> str:
    """Mostra valores em bilhões com duas casas e separadores brasileiros."""
    if valor is None:
        return "Não disponível"
    bilhoes = valor / Decimal(1_000_000_000)
    numero = f"{bilhoes:,.2f}"
    numero = numero.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {numero} bi"


def rotulo_grafico(cnpj: str, nome: str, cnpjs: list[str]) -> str:
    """Distingue marcas repetidas no gráfico com a UF, sem mudar sua identidade."""
    marca = nome_marca(cnpj, nome)
    contagem = Counter(nome_marca(item, "") for item in cnpjs)
    if contagem[marca] > 1:
        uf = METADADOS_POR_CNPJ.get(cnpj, {}).get("uf")
        return f"{marca} · {uf}" if uf else marca
    return marca


def ordem_por_ranking_financeiro(
    ranking: list[dict[str, Any]], rotulos_por_cnpj: dict[str, str]
) -> list[str]:
    """Retorna os rótulos na ordem de posição do MART 06, sem ordenar por nome."""
    return [
        rotulos_por_cnpj[linha["cnpj"]]
        for linha in sorted(ranking, key=lambda linha: linha["posicao_ranking"])
    ]


def validar_reconciliacao_tipos(
    ranking: list[dict[str, Any]],
    tipos: list[dict[str, Any]],
    financeiros: list[dict[str, Any]],
    ano: int,
) -> list[dict[str, Any]]:
    """Compara as categorias do MART 08 com os totais dos MARTS 06 e 04."""
    tipos_esperados = {
        "Expans\u00e3o",
        "Melhoria",
        "Renova\u00e7\u00e3o",
    }
    totais_ranking = {linha["cnpj"]: linha for linha in ranking if linha["ano"] == ano}
    totais_financeiros = {
        linha["cnpj"]: linha for linha in financeiros if linha["ano"] == ano
    }
    grupos: dict[str, list[dict[str, Any]]] = {}
    for linha in tipos:
        if linha["ano"] == ano:
            grupos.setdefault(linha["cnpj"], []).append(linha)

    divergencias = []
    for cnpj, ranking_item in totais_ranking.items():
        financeiro = totais_financeiros.get(cnpj)
        total_mart06 = (
            ranking_item.get("realizado")
            if ranking_item.get("status_realizado") == "valid"
            else None
        )
        total_mart04 = (
            financeiro.get("realizado")
            if financeiro and financeiro.get("status_realizado") == "valid"
            else None
        )
        motivos = []
        if total_mart06 is None:
            motivos.append("total realizado do MART 06 indisponivel")
        if total_mart04 is None:
            motivos.append("total realizado do MART 04 indisponivel")
        if (
            total_mart06 is not None
            and total_mart04 is not None
            and total_mart06 != total_mart04
        ):
            motivos.append("MART 06 difere do MART 04")

        categorias = grupos.get(cnpj, [])
        tipos_encontrados = {item["tipo"] for item in categorias}
        categorias_validas = (
            tipos_encontrados == tipos_esperados
            and len(categorias) == len(tipos_esperados)
            and all(
                item.get("status_realizado") == "valid"
                and item.get("realizado") is not None
                for item in categorias
            )
        )
        soma_tipos = None
        if not categorias_validas:
            motivos.append("categorias ausentes ou valores indisponiveis")
        else:
            soma_tipos = sum(
                (item["realizado"] for item in categorias), start=Decimal(0)
            )
            if total_mart06 is not None and soma_tipos != total_mart06:
                motivos.append("soma do MART 08 difere do MART 06")
            if total_mart04 is not None and soma_tipos != total_mart04:
                motivos.append("soma do MART 08 difere do MART 04")

        if motivos:
            divergencias.append(
                {
                    "cnpj": cnpj,
                    "soma_tipos": soma_tipos,
                    "total_realizado": total_mart06,
                    "diferenca": (
                        total_mart06 - soma_tipos
                        if total_mart06 is not None and soma_tipos is not None
                        else None
                    ),
                    "motivo": "; ".join(motivos),
                }
            )
    return divergencias
