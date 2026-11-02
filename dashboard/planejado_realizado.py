"""Página de comparação entre investimentos planejados e realizados."""

from decimal import Decimal
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.data import calcular_taxa_execucao, formatar_reais
from dashboard.metadata import METADADOS_POR_CNPJ, nome_marca
from dashboard.responsive import renderizar_grade_metricas
from dashboard.visuals import formatar_bilhoes, rotulo_grafico


def preparar_dados_pagina(dados: dict[str, Any], ano: int) -> dict[str, Any]:
    """Prepara os dez CNPJs e reconcilia MART 04 com os totais do MART 01."""
    membros = {linha["cnpj"] for linha in dados["coorte"]}
    if len(membros) != 10:
        raise ValueError("A coorte fixa precisa conter dez CNPJs distintos.")

    anuais = [linha for linha in dados["historico"] if linha["ano"] == ano]
    if len(anuais) != 1 or anuais[0]["qtd_cnpjs"] != 10:
        raise ValueError(f"O MART 01 não retornou os dez CNPJs para {ano}.")
    anual = anuais[0]

    financeiro = [
        linha
        for linha in dados["detalhes_financeiros"]
        if linha["ano"] == ano and linha["cnpj"] in membros
    ]
    cnpjs = [linha["cnpj"] for linha in financeiro]
    if len(cnpjs) != 10 or len(set(cnpjs)) != 10 or set(cnpjs) != membros:
        raise ValueError(f"O MART 04 não contém exatamente a coorte fixa em {ano}.")

    ranking = {
        linha["cnpj"]: linha
        for linha in dados["ranking"]
        if linha["ano"] == ano and linha["cnpj"] in membros
    }
    nomes = {
        cnpj: nome_marca(cnpj, ranking.get(cnpj, {}).get("nome", cnpj))
        for cnpj in membros
    }
    rotulos = {
        cnpj: rotulo_grafico(cnpj, nomes[cnpj], sorted(membros)) for cnpj in membros
    }

    linhas = []
    for item in financeiro:
        cnpj = item["cnpj"]
        meta = METADADOS_POR_CNPJ.get(cnpj, {})
        linhas.append(
            {
                **item,
                "rotulo": rotulos[cnpj],
                "uf": meta.get("uf", "Não disponível"),
                "realizado_valido": (
                    item["realizado"]
                    if item["status_realizado"] == "valid"
                    and item["realizado"] is not None
                    else None
                ),
                "planejado_valido": (
                    item["planejado"]
                    if item["status_planejado"] == "valid"
                    and item["planejado"] is not None
                    else None
                ),
                "execucao_valida": (
                    item["taxa_execucao"]
                    if item["status_taxa_execucao"] == "valid"
                    and item["taxa_execucao"] is not None
                    else None
                ),
                "diferenca_valida": (
                    item["diferenca_absoluta"]
                    if item["status_diferenca"] == "valid"
                    and item["diferenca_absoluta"] is not None
                    else None
                ),
                "diferenca_percentual_valida": (
                    item["diferenca_percentual"]
                    if item["status_diferenca_percentual"] == "valid"
                    and item["diferenca_percentual"] is not None
                    else None
                ),
            }
        )

    linhas.sort(
        key=lambda linha: (
            linha["realizado_valido"] is None,
            -(linha["realizado_valido"] or Decimal(0)),
            linha["cnpj"],
        )
    )

    planejados_completos = all(
        linha["planejado_valido"] is not None for linha in linhas
    )
    realizados_completos = all(
        linha["realizado_valido"] is not None for linha in linhas
    )
    diferencas_completas = all(
        linha["diferenca_valida"] is not None for linha in linhas
    )

    soma_planejada = (
        sum((linha["planejado_valido"] for linha in linhas), start=Decimal(0))
        if planejados_completos
        else None
    )
    soma_realizada = (
        sum((linha["realizado_valido"] for linha in linhas), start=Decimal(0))
        if realizados_completos
        else None
    )
    soma_diferenca = (
        sum((linha["diferenca_valida"] for linha in linhas), start=Decimal(0))
        if diferencas_completas
        else None
    )

    planejado_reconciliado = bool(
        planejados_completos
        and anual["status_planejado"] == "valid"
        and anual["planejado"] is not None
        and soma_planejada == anual["planejado"]
    )
    realizado_reconciliado = bool(
        realizados_completos
        and anual["status_realizado"] == "valid"
        and anual["realizado"] is not None
        and soma_realizada == anual["realizado"]
    )
    diferenca_reconciliada = bool(
        diferencas_completas
        and planejado_reconciliado
        and realizado_reconciliado
        and soma_diferenca == anual["realizado"] - anual["planejado"]
    )

    total_planejado = anual["planejado"] if planejado_reconciliado else None
    total_realizado = anual["realizado"] if realizado_reconciliado else None
    diferenca_total = soma_diferenca if diferenca_reconciliada else None
    execucao_total = (
        calcular_taxa_execucao(
            total_planejado,
            total_realizado,
            "valid" if total_planejado is not None else "unavailable",
            "valid" if total_realizado is not None else "unavailable",
        )
        if total_planejado is not None and total_realizado is not None
        else None
    )

    return {
        "linhas": linhas,
        "kpis": {
            "planejado": total_planejado,
            "realizado": total_realizado,
            "execucao": execucao_total,
            "diferenca": diferenca_total,
        },
        "reconciliacoes": {
            "planejado": planejado_reconciliado,
            "realizado": realizado_reconciliado,
            "diferenca": diferenca_reconciliada,
        },
    }


def _formatar_diferenca_bilhoes(valor: Decimal | None) -> str:
    if valor is None:
        return "Não disponível"
    if valor == 0:
        return formatar_bilhoes(valor)
    sinal = "+" if valor > 0 else "−"
    return f"{sinal}{formatar_bilhoes(abs(valor))}"


def renderizar_pagina(dados: dict[str, Any], ano: int) -> None:
    """Renderiza KPIs, comparações financeiras e tabela da coorte fixa."""
    try:
        preparados = preparar_dados_pagina(dados, ano)
    except ValueError as erro:
        st.error(str(erro), title="Não foi possível montar a comparação")
        return

    linhas = preparados["linhas"]
    kpis = preparados["kpis"]
    st.subheader("Planejado x Realizado", anchor=False)

    indicadores = (
        (
            "Investimento planejado",
            formatar_bilhoes(kpis["planejado"]),
            ":material/event_note:",
            "blue",
        ),
        (
            "Investimento realizado",
            formatar_bilhoes(kpis["realizado"]),
            ":material/payments:",
            "green",
        ),
        (
            "Execução do planejado",
            f"{kpis['execucao']:.2f}%"
            if kpis["execucao"] is not None
            else "Não disponível",
            ":material/percent:",
            "violet",
        ),
        (
            "Diferença financeira",
            _formatar_diferenca_bilhoes(kpis["diferenca"]),
            ":material/compare_arrows:",
            "orange",
        ),
    )
    renderizar_grade_metricas(
        [
            {
                "title": titulo,
                "label": f"{ano} · coorte fixa",
                "value": valor,
                "icon": icone,
                "color": cor,
            }
            for titulo, valor, icone, cor in indicadores
        ],
        chave="planejado-realizado",
        colunas_desktop=4,
    )

    if not all(preparados["reconciliacoes"].values()):
        st.warning(
            "Os totais do MART 01 e os detalhes do MART 04 não reconciliaram "
            "integralmente. Os KPIs afetados aparecem como não disponíveis."
        )

    st.altair_chart(
        construir_grafico_colunas(linhas, ano),
        width="stretch",
        alt=f"Investimentos planejados e realizados por distribuidora em {ano}",
        key="gridinvest-chart-planejado-realizado",
    )
    _renderizar_tabela(linhas)
    st.caption(
        "Fonte: dados públicos da ANEEL · MART 01 e MART 04 · coorte fixa top 10."
    )


def construir_grafico_colunas(linhas: list[dict[str, Any]], ano: int) -> alt.Chart:
    """Cria duas colunas financeiras agrupadas para cada distribuidora."""
    ordem = [linha["rotulo"] for linha in linhas]
    registros = []
    for linha in linhas:
        for metrica, campo in (
            ("Planejado", "planejado_valido"),
            ("Realizado", "realizado_valido"),
        ):
            valor = linha[campo]
            registros.append(
                {
                    "cnpj": linha["cnpj"],
                    "Distribuidora": linha["rotulo"],
                    "UF": linha["uf"],
                    "Ano": ano,
                    "Métrica": metrica,
                    "Investimento (R$ bi)": (
                        float(valor / Decimal(1_000_000_000))
                        if valor is not None
                        else None
                    ),
                    "Planejado completo": formatar_reais(linha["planejado_valido"]),
                    "Realizado completo": formatar_reais(linha["realizado_valido"]),
                }
            )
    return (
        alt.Chart(pd.DataFrame(registros))
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=alt.X(
                "Distribuidora:N",
                sort=ordem,
                scale=alt.Scale(paddingInner=0.25, paddingOuter=0.08),
                title=None,
                axis=alt.Axis(
                    labelAngle=-40,
                    labelAlign="center",
                    labelLimit=200,
                    labelPadding=9,
                ),
            ),
            xOffset=alt.XOffset(
                "Métrica:N",
                sort=["Planejado", "Realizado"],
                scale=alt.Scale(paddingInner=0, paddingOuter=0),
            ),
            y=alt.Y(
                "Investimento (R$ bi):Q",
                title="Investimento (R$ bilhões)",
                axis=alt.Axis(format=".1f", tickCount=6, labelFontSize=12),
            ),
            color=alt.Color(
                "Métrica:N",
                scale=alt.Scale(
                    domain=["Planejado", "Realizado"],
                    range=["#38BDF8", "#A78BFA"],
                ),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=[
                alt.Tooltip("Distribuidora:N"),
                alt.Tooltip("UF:N"),
                alt.Tooltip("Ano:Q"),
                alt.Tooltip("Métrica:N"),
                alt.Tooltip("Planejado completo:N", title="Planejado"),
                alt.Tooltip("Realizado completo:N", title="Realizado"),
            ],
        )
        .properties(height=460)
    )


def _renderizar_tabela(linhas: list[dict[str, Any]]) -> None:
    st.subheader("Resumo comparativo", anchor=False)
    tabela = pd.DataFrame(
        [
            {
                "Distribuidora": f"{linha['rotulo']} · {linha['uf']}",
                "Investimento planejado": formatar_reais(linha["planejado_valido"]),
                "Investimento realizado": formatar_reais(linha["realizado_valido"]),
                "Diferença absoluta": formatar_reais(linha["diferenca_valida"]),
                "Diferença percentual": (
                    f"{linha['diferenca_percentual_valida']:+.2f}%"
                    if linha["diferenca_percentual_valida"] is not None
                    else "Não disponível"
                ),
                "Execução do planejado": (
                    f"{linha['execucao_valida']:.2f}%"
                    if linha["execucao_valida"] is not None
                    else "Não disponível"
                ),
            }
            for linha in linhas
        ]
    )
    configuracao = {
        "Distribuidora": st.column_config.TextColumn("Distribuidora", width="medium"),
        "Investimento planejado": st.column_config.TextColumn(
            "Investimento planejado", width="medium"
        ),
        "Investimento realizado": st.column_config.TextColumn(
            "Investimento realizado", width="medium"
        ),
        "Diferença absoluta": st.column_config.TextColumn(
            "Diferença absoluta", width="medium"
        ),
        "Diferença percentual": st.column_config.TextColumn(
            "Diferença percentual", width="small"
        ),
        "Execução do planejado": st.column_config.TextColumn(
            "Execução do planejado", width="small"
        ),
    }
    st.dataframe(
        tabela,
        column_config=configuracao,
        hide_index=True,
        height=420,
        width="stretch",
        row_height=36,
        key="gridinvest-table-planejado-realizado",
    )
