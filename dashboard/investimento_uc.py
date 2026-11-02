"""Página de análise do investimento por unidade consumidora."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.comparativo import preparar_ranking_investimento_uc
from dashboard.data import formatar_reais
from dashboard.responsive import renderizar_grade_metricas
from dashboard.summary_table import imagem_distribuidora


def preparar_dados_pagina(dados: dict[str, Any], ano: int) -> list[dict[str, Any]]:
    """Combina MARTS por CNPJ e ano, mantendo indisponibilidades explícitas."""
    linhas = preparar_ranking_investimento_uc(dados, ano)
    membros = {linha["cnpj"] for linha in dados["coorte"]}
    if len(membros) != 10 or {linha["cnpj"] for linha in linhas} != membros:
        raise ValueError("O resultado não corresponde aos dez CNPJs da coorte fixa.")

    linhas_mart03 = [
        linha
        for linha in dados["investimento_por_uc"]
        if linha["ano"] == ano and linha["cnpj"] in membros
    ]
    cnpjs_mart03 = [linha["cnpj"] for linha in linhas_mart03]
    if len(cnpjs_mart03) != len(set(cnpjs_mart03)):
        raise ValueError(f"O MART 03 contém CNPJs duplicados em {ano}.")
    mart03_por_cnpj = {linha["cnpj"]: linha for linha in linhas_mart03}

    for linha in linhas:
        mart03 = mart03_por_cnpj.get(linha["cnpj"], {})
        total_mart03 = mart03.get("total_realizado")
        total_valido = (
            mart03.get("status_total_realizado") == "valid" and total_mart03 is not None
        )
        total_mart06 = linha["total_realizado"]
        total_mart06_valido = linha.get("status_total_realizado_mart06") == "valid"
        linha["total_realizado_mart03"] = total_mart03 if total_valido else None
        linha["status_total_realizado_mart03"] = mart03.get(
            "status_total_realizado", "sem_referencia"
        )
        linha["qtd_uc_mart03"] = mart03.get("qtd_uc_dezembro")
        linha["status_cobertura_mart03"] = mart03.get(
            "status_cobertura", "sem_referencia"
        )
        linha["status_realizado_por_uc"] = mart03.get("status", "sem_referencia")
        linha["total_reconciliado"] = bool(
            total_valido
            and total_mart06_valido
            and total_mart06 is not None
            and total_mart03 == total_mart06
        )
        linha["uc_reconciliada"] = bool(
            mart03.get("status_cobertura") in {"valid", "zero"}
            and mart03.get("qtd_uc_dezembro") is not None
            and linha["qtd_uc"] is not None
            and mart03["qtd_uc_dezembro"] == linha["qtd_uc"]
        )
        linha["total_realizado"] = total_mart03 if linha["total_reconciliado"] else None

    return linhas


def calcular_kpis_coorte(linhas: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula KPIs somente quando a cobertura necessária está completa."""
    cnpjs = {linha["cnpj"] for linha in linhas}
    unidades_completas = (
        len(linhas) == 10
        and len(cnpjs) == 10
        and all(
            linha["status_uc"] in {"valid", "zero"}
            and linha["qtd_uc"] is not None
            and linha["qtd_uc"] >= 0
            for linha in linhas
        )
    )
    total_uc = sum(linha["qtd_uc"] for linha in linhas) if unidades_completas else None

    investimentos_completos = unidades_completas and all(
        linha["total_reconciliado"]
        and linha["uc_reconciliada"]
        and linha["status_realizado_por_uc"] in {"valid", "denominador_zero"}
        and (
            linha["status_realizado_por_uc"] != "denominador_zero"
            or linha["qtd_uc"] == 0
        )
        for linha in linhas
    )
    indicador_coorte = None
    if investimentos_completos and total_uc and total_uc > 0:
        total_realizado = sum(
            (linha["total_realizado"] for linha in linhas), Decimal(0)
        )
        indicador_coorte = (total_realizado / Decimal(total_uc)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    validos = [linha for linha in linhas if linha["disponível"]]
    maior = min(
        validos,
        key=lambda linha: (-linha["valor"], linha["cnpj"]),
        default=None,
    )
    menor = min(
        validos, key=lambda linha: (linha["valor"], linha["cnpj"]), default=None
    )
    divergencias = [
        linha["cnpj"]
        for linha in linhas
        if not linha["total_reconciliado"] or not linha["uc_reconciliada"]
    ]

    return {
        "maior": maior,
        "menor": menor,
        "qtd_uc": total_uc,
        "indicador_coorte": indicador_coorte,
        "indicadores_disponiveis": len(validos),
        "divergencias": divergencias,
    }


def _nome_uf(linha: dict[str, Any]) -> str:
    return f"{linha['rótulo']} · {linha['uf']}"


def renderizar_pagina_investimento_uc(dados: dict[str, Any], ano: int) -> None:
    """Renderiza KPIs, ranking, dispersão e tabela da coorte top 10."""
    try:
        linhas = preparar_dados_pagina(dados, ano)
    except ValueError as erro:
        st.error(str(erro), title="Não foi possível montar o ranking por UC")
        return

    kpis = calcular_kpis_coorte(linhas)
    st.subheader("Investimento por Unidade Consumidora", anchor=False)

    renderizar_grade_metricas(
        [
            {
                "title": "Maior investimento realizado por UC",
                "label": "R$/UC",
                "value": formatar_reais(kpis["maior"]["valor"] if kpis["maior"] else None),
                "icon": ":material/trending_up:",
                "color": "green",
                "caption": _nome_uf(kpis["maior"]) if kpis["maior"] else "Indicador indispon\u00edvel",
            },
            {
                "title": "Menor investimento realizado por UC",
                "label": "R$/UC",
                "value": formatar_reais(kpis["menor"]["valor"] if kpis["menor"] else None),
                "icon": ":material/trending_down:",
                "color": "blue",
                "caption": _nome_uf(kpis["menor"]) if kpis["menor"] else "Indicador indispon\u00edvel",
            },
            {
                "title": "Unidades consumidoras",
                "label": f"UCs ativas \u00b7 dezembro {ano}",
                "value": f"{kpis['qtd_uc']:,}".replace(",", ".") if kpis["qtd_uc"] is not None else "N\u00e3o dispon\u00edvel",
                "icon": ":material/groups:",
                "color": "violet",
                "caption": "Coorte fixa de dez distribuidoras",
            },
            {
                "title": "Indicador agregado da coorte",
                "label": "Investido por UC",
                "value": formatar_reais(kpis["indicador_coorte"]),
                "icon": ":material/analytics:",
                "color": "orange",
                "help": (
                    "Total realizado da coorte dividido pelo total de UCs v\u00e1lidas. "
                    "N\u00e3o \u00e9 a m\u00e9dia simples dos indicadores individuais."
                ),
                "caption": (
                    f"{kpis['indicadores_disponiveis']} de 10 valores individuais "
                    "dispon\u00edveis"
                ),
            },
        ],
        chave="investimento-uc",
        colunas_desktop=4,
    )

    if kpis["divergencias"]:
        st.warning(
            "Há diferenças entre os valores do MART 03, MART 06 e MART 07. "
            "Os totais ou agregados afetados aparecem como não disponíveis."
        )

    _renderizar_ranking(linhas, ano)
    _renderizar_dispersao(linhas, ano)
    _renderizar_tabela(linhas, ano)
    st.caption(
        "Fonte: dados públicos da ANEEL · R$/UC: MART 03 · unidades consumidoras: "
        "MART 07 · posição financeira: MART 06."
    )


def _renderizar_ranking(linhas: list[dict[str, Any]], ano: int) -> None:
    st.subheader("Ranking de Investimento por UC", anchor=False)
    st.caption("Compare quanto cada distribuidora investiu por unidade consumidora.")

    ordem = [linha["distribuidora"] for linha in linhas]
    registros = [
        {
            **linha,
            "valor_grafico": float(linha["valor"]) if linha["disponível"] else None,
            "posicao_rotulo": float(linha["valor"]) if linha["disponível"] else 0.0,
            "valor_rotulo": linha["valor_exibido"],
            "ucs_rotulo": (
                f"{linha['qtd_uc']:,}".replace(",", ".")
                if linha["qtd_uc"] is not None
                else "Não disponível"
            ),
            "total_rotulo": formatar_reais(linha["total_realizado"]),
            "financeiro_rotulo": (
                f"#{linha['posicao_investimento']}"
                if linha["posicao_investimento"] is not None
                else "Não disponível"
            ),
        }
        for linha in linhas
    ]
    df = pd.DataFrame(registros)
    maior = max(
        (linha["valor"] for linha in linhas if linha["disponível"]),
        default=Decimal(0),
    )
    limite = float(maior) * 1.25 if maior > 0 else 1.0
    eixo_y = alt.Y(
        "distribuidora:N",
        sort=ordem,
        title=None,
        axis=alt.Axis(labelFontSize=15, labelLimit=250, labelPadding=9),
    )
    barras = (
        alt.Chart(df)
        .mark_bar(height=25, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "valor_grafico:Q",
                scale=alt.Scale(domain=[0, limite]),
                title="Investimento realizado por UC (R$)",
                axis=alt.Axis(format=",.0f", tickCount=5, labelFontSize=13),
            ),
            y=eixo_y,
            color=alt.Color(
                "destaque:N",
                scale=alt.Scale(
                    domain=["Top 3", "Demais"],
                    range=["#29D3C2", "#53657D"],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("rótulo:N", title="Distribuidora"),
                alt.Tooltip("uf:N", title="UF"),
                alt.Tooltip("regiao:N", title="Região"),
                alt.Tooltip("ano:Q", title="Ano"),
                alt.Tooltip("ucs_rotulo:N", title="UCs ativas em dezembro"),
                alt.Tooltip("total_rotulo:N", title="Investimento realizado total"),
                alt.Tooltip("valor_exibido:N", title="Investimento realizado por UC"),
                alt.Tooltip("financeiro_rotulo:N", title="Ranking financeiro"),
            ],
        )
    )
    rotulos = (
        alt.Chart(df)
        .mark_text(
            align="left",
            baseline="middle",
            dx=8,
            fontSize=16,
            fontWeight=700,
            color="#F4F7FB",
        )
        .encode(
            x=alt.X("posicao_rotulo:Q", scale=alt.Scale(domain=[0, limite])),
            y=alt.Y(
                "distribuidora:N",
                sort=ordem,
            ),
            text=alt.Text("valor_rotulo:N"),
        )
    )
    st.altair_chart(
        alt.layer(barras, rotulos).properties(height=460),
        width="stretch",
        alt=f"Ranking das dez distribuidoras por investimento por UC em {ano}",
        key="gridinvest-chart-investimento-uc-ranking",
    )


def _renderizar_dispersao(linhas: list[dict[str, Any]], ano: int) -> None:
    st.subheader("Investimento total versus R$/UC", anchor=False)
    st.caption(
        "Cada ponto representa uma distribuidora; o tamanho acompanha o investimento total."
    )
    registros = [
        {
            "distribuidora": linha["rótulo"],
            "uf": linha["uf"],
            "regiao": linha["regiao"],
            "ano": linha["ano"],
            "qtd_uc": linha["qtd_uc"],
            "valor": float(linha["valor"]),
            "total_bilhoes": float(linha["total_realizado"] / Decimal(1_000_000_000)),
            "total_rotulo": formatar_reais(linha["total_realizado"]),
            "valor_rotulo": linha["valor_exibido"],
            "destaque": linha["destaque"],
            "posicao_financeira": linha["posicao_investimento"],
        }
        for linha in linhas
        if linha["disponível"]
        and linha["qtd_uc"] is not None
        and linha["total_realizado"] is not None
    ]
    if not registros:
        st.info("Não há dados completos para comparar UCs, investimento total e R$/UC.")
        return

    df = pd.DataFrame(registros)
    grafico = (
        alt.Chart(df)
        .mark_circle(opacity=0.82, stroke="#DCE8F5", strokeWidth=0.7)
        .encode(
            x=alt.X(
                "qtd_uc:Q",
                title="UCs ativas em dezembro",
                axis=alt.Axis(format="~s", labelFontSize=13),
            ),
            y=alt.Y(
                "valor:Q",
                title="Investimento realizado por UC (R$)",
                axis=alt.Axis(format=",.2f", labelFontSize=13),
            ),
            size=alt.Size(
                "total_bilhoes:Q",
                title="Investimento total (R$ bi)",
                scale=alt.Scale(range=[70, 850]),
                legend=alt.Legend(format=".1f"),
            ),
            color=alt.Color(
                "destaque:N",
                scale=alt.Scale(
                    domain=["Top 3", "Demais"],
                    range=["#29D3C2", "#718096"],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("distribuidora:N", title="Distribuidora"),
                alt.Tooltip("uf:N", title="UF"),
                alt.Tooltip("regiao:N", title="Região"),
                alt.Tooltip("ano:Q", title="Ano"),
                alt.Tooltip("qtd_uc:Q", title="UCs ativas", format=","),
                alt.Tooltip("total_rotulo:N", title="Investimento total"),
                alt.Tooltip("valor_rotulo:N", title="Investimento realizado por UC"),
                alt.Tooltip("posicao_financeira:Q", title="Ranking financeiro"),
            ],
        )
        .properties(height=380)
    )
    st.altair_chart(
        grafico,
        width="stretch",
        alt=f"Relação entre UCs, investimento total e investimento por UC em {ano}",
        key="gridinvest-chart-investimento-uc-dispersao",
    )


def _renderizar_tabela(linhas: list[dict[str, Any]], ano: int) -> None:
    st.subheader("Comparativo das distribuidoras", anchor=False)

    def cnpj_sort(row: dict[str, Any]) -> str:
        return row["cnpj"]

    ordenadas = sorted(
        linhas,
        key=lambda linha: (
            not linha["disponível"],
            -linha["valor"] if linha["disponível"] else Decimal(0),
            cnpj_sort(linha),
        ),
    )
    dados_tabela = [
        {
            "Posição R$/UC": (
                f"#{linha['posicao_uc']}" if linha["posicao_uc"] is not None else "—"
            ),
            "Logo": imagem_distribuidora(linha["cnpj"], linha["rótulo"], linha["uf"]),
            "Distribuidora": linha["rótulo"],
            "UCs ativas": (
                f"{linha['qtd_uc']:,}".replace(",", ".")
                if linha["qtd_uc"] is not None
                else "Não disponível"
            ),
            "Investimento realizado": formatar_reais(linha["total_realizado"]),
            "Investimento realizado por UC": formatar_reais(
                linha["valor"] if linha["disponível"] else None
            ),
            "Posição financeira": (
                f"#{linha['posicao_investimento']}"
                if linha["posicao_investimento"] is not None
                else "Não disponível"
            ),
        }
        for linha in ordenadas
    ]
    df = pd.DataFrame(dados_tabela)
    st.dataframe(
        df,
        column_config={
            "Posição R$/UC": st.column_config.TextColumn(
                "Posição R$/UC", width="small"
            ),
            "Logo": st.column_config.ImageColumn("Logo", width="small"),
            "Distribuidora": st.column_config.TextColumn(
                "Distribuidora", width="medium"
            ),
            "UCs ativas": st.column_config.TextColumn("UCs ativas", width="small"),
            "Investimento realizado": st.column_config.TextColumn(
                "Investimento realizado", width="medium"
            ),
            "Investimento realizado por UC": st.column_config.TextColumn(
                "Investimento realizado por UC", width="medium"
            ),
            "Posição financeira": st.column_config.TextColumn(
                "Posição financeira", width="small"
            ),
        },
        hide_index=True,
        width="stretch",
        height=420,
        row_height=42,
        alt=f"Comparação das dez distribuidoras por R$/UC em {ano}",
        key="gridinvest-table-investimento-uc",
    )
