"""Visualizações do perfil de investimentos a partir do MART 08."""

from collections import defaultdict
from decimal import Decimal
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.data import formatar_reais
from dashboard.metadata import (
    METADADOS_POR_CNPJ,
    TIPOS_INVESTIMENTO_EXIBIDOS,
    nome_marca,
)
from dashboard.responsive import renderizar_grade_metricas
from dashboard.visuals import formatar_bilhoes, rotulo_grafico

CORES_TIPOS = {
    "Expansão": "#38BDF8",
    "Melhoria": "#34D399",
    "Renovação": "#A78BFA",
    "Outros tipos": "#94A3B8",
}


def preparar_dados_pagina(dados: dict[str, Any], ano: int) -> dict[str, Any]:
    """Prepara os dez membros e verifica se as categorias reconciliam com MART 08."""
    ranking = [item for item in dados["ranking"] if item["ano"] == ano]
    coorte = {item["cnpj"]: item for item in dados["coorte"]}
    ranking = [item for item in ranking if item["cnpj"] in coorte]
    if len(ranking) != 10 or len({item["cnpj"] for item in ranking}) != 10:
        raise ValueError(f"O MART 06 não contém os dez CNPJs da coorte em {ano}.")

    membros = {item["cnpj"] for item in ranking}
    tipos = [
        item
        for item in dados["tipos_completos"]
        if item["ano"] == ano and item["cnpj"] in membros
    ]
    totais = {
        item["cnpj"]: item
        for item in dados["totais_perfil"]
        if item["ano"] == ano and item["cnpj"] in membros
    }
    por_cnpj: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in tipos:
        por_cnpj[item["cnpj"]].append(item)

    cnpjs_ordenados = [item["cnpj"] for item in ranking]
    rotulos = {
        item["cnpj"]: rotulo_grafico(item["cnpj"], item["nome"], cnpjs_ordenados)
        for item in ranking
    }
    detalhes: dict[str, dict[str, Any]] = {}
    reconciliacao: list[dict[str, Any]] = []
    for item in ranking:
        cnpj = item["cnpj"]
        linhas = por_cnpj.get(cnpj, [])
        total_info = totais.get(cnpj, {"status": "unavailable", "realizado": None})
        total = total_info["realizado"] if total_info["status"] == "valid" else None
        linhas_validas = all(
            linha["status_realizado"] == "valid" and linha["realizado"] is not None
            for linha in linhas
        )
        soma_linhas = (
            sum((linha["realizado"] for linha in linhas), start=Decimal(0))
            if linhas_validas
            else None
        )
        completa = total is not None and soma_linhas == total

        valores: dict[str, Decimal | None] = {}
        adicionais = [
            linha
            for linha in linhas
            if linha["tipo"] not in TIPOS_INVESTIMENTO_EXIBIDOS
        ]
        for tipo in TIPOS_INVESTIMENTO_EXIBIDOS:
            correspondentes = [linha for linha in linhas if linha["tipo"] == tipo]
            if correspondentes and all(
                linha["status_realizado"] == "valid" and linha["realizado"] is not None
                for linha in correspondentes
            ):
                valores[tipo] = sum(
                    (linha["realizado"] for linha in correspondentes),
                    start=Decimal(0),
                )
            else:
                valores[tipo] = Decimal(0) if completa and not correspondentes else None

        if adicionais and all(
            linha["status_realizado"] == "valid" and linha["realizado"] is not None
            for linha in adicionais
        ):
            valores["Outros tipos"] = sum(
                (linha["realizado"] for linha in adicionais), start=Decimal(0)
            )
        else:
            valores["Outros tipos"] = (
                Decimal(0) if completa and not adicionais else None
            )

        soma_exibida = (
            sum(
                (valor for valor in valores.values() if valor is not None),
                start=Decimal(0),
            )
            if all(valor is not None for valor in valores.values())
            else None
        )
        reconciliado = total is not None and soma_exibida == total
        if not reconciliado:
            reconciliacao.append({"cnpj": cnpj, "total_mart08": total})
        detalhes[cnpj] = {
            **item,
            "rotulo": rotulos[cnpj],
            "total": total,
            "valores": valores,
            "status_total": total_info["status"],
            "reconciliado": reconciliado,
        }

    totais_completos = all(detalhes[cnpj]["total"] is not None for cnpj in membros)
    total_coorte = (
        sum((detalhes[cnpj]["total"] for cnpj in membros), start=Decimal(0))
        if totais_completos
        else None
    )
    categorias: dict[str, Decimal | None] = {}
    for tipo in (*TIPOS_INVESTIMENTO_EXIBIDOS, "Outros tipos"):
        valores = [detalhes[cnpj]["valores"][tipo] for cnpj in membros]
        categorias[tipo] = (
            sum(valores, start=Decimal(0))
            if all(valor is not None for valor in valores)
            else None
        )

    registro_mart01 = next(
        (linha for linha in dados["historico"] if linha["ano"] == ano), None
    )
    total_mart01 = (
        registro_mart01["realizado"]
        if registro_mart01 and registro_mart01["status_realizado"] == "valid"
        else None
    )
    total_reconciliado = (
        total_coorte is not None
        and total_mart01 is not None
        and total_coorte == total_mart01
        and not reconciliacao
    )
    detalhes_ordenados = sorted(
        detalhes.values(),
        key=lambda item: (
            item["total"] is None,
            -(item["total"] or Decimal(0)),
            item["cnpj"],
        ),
    )
    return {
        "ano": ano,
        "detalhes": detalhes,
        "ordenados": detalhes_ordenados,
        "categorias": categorias,
        "total": total_coorte if total_reconciliado else None,
        "total_mart08": total_coorte,
        "total_mart01": total_mart01,
        "total_reconciliado": total_reconciliado,
        "divergencias": reconciliacao,
        "reconciliacao_completa": not reconciliacao,
    }


def _construir_graficos(
    resultado: dict[str, Any],
) -> tuple[alt.Chart | None, alt.Chart]:
    total = resultado["total"]
    categorias = resultado["categorias"]
    fatias = [
        {
            "Tipo": tipo,
            "Valor": float(valor),
            "Valor completo": formatar_reais(valor),
            "Participação": float(valor / total * Decimal(100)),
        }
        for tipo, valor in categorias.items()
        if valor is not None and total is not None and total > 0
    ]
    rosca = None
    if fatias:
        rosca = (
            alt.Chart(pd.DataFrame(fatias))
            .mark_arc(innerRadius=78, outerRadius=150, cornerRadius=4)
            .encode(
                theta=alt.Theta("Valor:Q", stack=True),
                color=alt.Color(
                    "Tipo:N",
                    scale=alt.Scale(
                        domain=list(CORES_TIPOS), range=list(CORES_TIPOS.values())
                    ),
                    legend=alt.Legend(title=None, orient="bottom"),
                ),
                tooltip=[
                    alt.Tooltip("Tipo:N", title="Tipo de investimento"),
                    alt.Tooltip("Valor completo:N", title="Investimento realizado"),
                    alt.Tooltip("Participação:Q", title="Participação", format=".2f"),
                ],
            )
            .properties(height=320)
        )

    linhas_grafico = []
    ordem = []
    for item in resultado["ordenados"]:
        ordem.append(item["rotulo"])
        for tipo in CORES_TIPOS:
            valor = item["valores"][tipo]
            linhas_grafico.append(
                {
                    "Distribuidora": item["rotulo"],
                    "CNPJ": item["cnpj"],
                    "Tipo": tipo,
                    "Valor (R$ bi)": float(valor / Decimal(1_000_000_000))
                    if valor is not None
                    else None,
                    "Valor completo": formatar_reais(valor),
                    "Total realizado": formatar_reais(item["total"]),
                }
            )
    barras = (
        alt.Chart(pd.DataFrame(linhas_grafico))
        .mark_bar(height=25, cornerRadiusEnd=3)
        .encode(
            x=alt.X(
                "Valor (R$ bi):Q",
                stack="zero",
                title="Investimento realizado (R$ bilhões)",
                axis=alt.Axis(format=".1f", tickCount=5, gridColor="#26364B"),
            ),
            y=alt.Y(
                "Distribuidora:N",
                sort=ordem,
                title=None,
                axis=alt.Axis(labelLimit=220),
            ),
            color=alt.Color(
                "Tipo:N",
                scale=alt.Scale(
                    domain=list(CORES_TIPOS), range=list(CORES_TIPOS.values())
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            order=alt.Order("Tipo:N", sort="ascending"),
            tooltip=[
                alt.Tooltip("Distribuidora:N"),
                alt.Tooltip("CNPJ:N"),
                alt.Tooltip("Tipo:N", title="Tipo de investimento"),
                alt.Tooltip("Valor completo:N", title="Investimento por tipo"),
                alt.Tooltip("Total realizado:N"),
            ],
        )
        .properties(height=410)
    )
    return rosca, barras


def renderizar_pagina(dados: dict[str, Any], ano: int) -> None:
    """Renderiza o perfil anual da coorte fixa usando os dados do MART 08."""
    st.subheader("Perfil de Investimentos", anchor=False)
    resultado = preparar_dados_pagina(dados, ano)
    if resultado["total_mart08"] is None:
        st.warning(
            "O total realizado do MART 08 está indisponível para este ano; "
            "os valores incompletos não foram tratados como zero.",
            icon=":material/info:",
        )
    elif not resultado["total_reconciliado"]:
        st.warning(
            "Os totais do MART 08 não reconciliam integralmente com o MART 01. "
            "O total do perfil ficará indisponível até que os dados estejam consistentes.",
            icon=":material/warning:",
        )

    if resultado["divergencias"]:
        st.warning(
            "Há valores de tipo ou classe indisponíveis no MART 08; os indicadores "
            "afetados são exibidos como não disponíveis.",
            icon=":material/warning:",
        )

    titulos = (
        (
            "Investimento total realizado",
            resultado["total"],
            ":material/payments:",
            "blue",
        ),
        ("Expansão", resultado["categorias"]["Expansão"], ":material/bolt:", "blue"),
        ("Melhoria", resultado["categorias"]["Melhoria"], ":material/build:", "green"),
        (
            "Renovação",
            resultado["categorias"]["Renovação"],
            ":material/autorenew:",
            "violet",
        ),
    )
    renderizar_grade_metricas(
        [
            {
                "title": titulo,
                "label": titulo,
                "value": formatar_bilhoes(valor),
                "icon": icone,
                "color": cor,
            }
            for titulo, valor, icone, cor in titulos
        ],
        chave="perfil-investimentos",
        colunas_desktop=4,
    )

    rosca, barras = _construir_graficos(resultado)
    col_rosca, col_barras = st.columns([0.8, 1.5], gap="large", wrap=True)
    with col_rosca.container(border=True):
        st.markdown("**Participação por tipo**")
        if rosca is None:
            st.info("Participação indisponível para este ano.")
        else:
            st.altair_chart(
                rosca,
                width="stretch",
                alt="Participação percentual dos tipos de investimento no total realizado",
                key="gridinvest-chart-perfil-rosca",
            )
    with col_barras.container(border=True):
        st.markdown("**Investimentos por distribuidora**")
        st.altair_chart(
            barras,
            width="stretch",
            alt="Comparação do investimento realizado por tipo entre as dez distribuidoras",
            key="gridinvest-chart-perfil-distribuidoras",
        )

    opcoes = [item["cnpj"] for item in resultado["ordenados"]]
    rotulos = {cnpj: resultado["detalhes"][cnpj]["rotulo"] for cnpj in opcoes}
    selecionada = st.selectbox(
        "Distribuidora",
        opcoes,
        index=0,
        format_func=lambda cnpj: rotulos[cnpj],
        key="perfil_distribuidora",
    )
    detalhe = resultado["detalhes"][selecionada]
    st.markdown(f"**Composição de {detalhe['rotulo']} · {ano}**")
    renderizar_grade_metricas(
        [
            {
                "title": tipo,
                "label": "Investimento",
                "value": formatar_bilhoes(detalhe["valores"][tipo]),
                "color": {
                    "Expansão": "blue",
                    "Melhoria": "green",
                    "Renovação": "violet",
                }[tipo],
                "caption": (
                    f"Valor integral: {formatar_reais(detalhe['valores'][tipo])} · "
                    f"{_formatar_participacao_tipo(detalhe, tipo)} do total realizado"
                ),
            }
            for tipo in TIPOS_INVESTIMENTO_EXIBIDOS
        ],
        chave="perfil-detalhe",
        colunas_desktop=3,
    )
    outros = detalhe["valores"]["Outros tipos"]
    if outros not in (None, Decimal(0)):
        uf = METADADOS_POR_CNPJ.get(selecionada, {}).get("uf")
        nome = nome_marca(selecionada, detalhe["nome"])
        st.caption(
            f"Outros tipos · {nome}{f' ({uf})' if uf else ''}: {formatar_reais(outros)}"
        )


def _formatar_participacao_tipo(detalhe: dict[str, Any], tipo: str) -> str:
    valor = detalhe["valores"][tipo]
    total = detalhe["total"]
    if valor is None or total is None or total <= 0:
        return "Não disponível"
    return f"{valor * Decimal(100) / total:.2f}%"
