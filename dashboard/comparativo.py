"""Página Comparativo Top 10, com detalhes individuais por distribuidora."""

from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.components import renderizar_card_distribuidora
from dashboard.data import formatar_reais, formatar_valor_validado
from dashboard.metadata import METADADOS_POR_CNPJ
from dashboard.visuals import rotulo_grafico


def preparar_ranking_investimento_uc(dados: dict, ano: int) -> list[dict]:
    """Ordena os membros da coorte por R$/UC sem substituir ausências por zero."""
    ranking = [linha for linha in dados["ranking"] if linha["ano"] == ano]
    membros = {linha["cnpj"] for linha in ranking}
    if len(ranking) != 10 or len(membros) != 10:
        raise ValueError(f"O MART 06 não contém os dez CNPJs da coorte em {ano}.")

    linhas_uc = [
        linha
        for linha in dados["investimento_por_uc"]
        if linha["ano"] == ano and linha["cnpj"] in membros
    ]
    cnpjs_uc = [linha["cnpj"] for linha in linhas_uc]
    if len(cnpjs_uc) != len(set(cnpjs_uc)):
        raise ValueError(f"O MART 03 contém CNPJs duplicados em {ano}.")
    uc_por_cnpj = {linha["cnpj"]: linha for linha in linhas_uc}
    linhas_unidades = [
        linha
        for linha in dados["unidades_consumidoras"]
        if linha["ano"] == ano and linha["cnpj"] in membros
    ]
    cnpjs_unidades = [linha["cnpj"] for linha in linhas_unidades]
    if len(cnpjs_unidades) != len(set(cnpjs_unidades)):
        raise ValueError(f"O MART 07 contém CNPJs duplicados em {ano}.")
    unidades_por_cnpj = {linha["cnpj"]: linha for linha in linhas_unidades}
    rótulos = {
        linha["cnpj"]: rotulo_grafico(linha["cnpj"], linha["nome"], sorted(membros))
        for linha in ranking
    }

    preparadas = []
    for linha in ranking:
        cnpj = linha["cnpj"]
        uc = uc_por_cnpj.get(cnpj)
        valor = uc.get("valor") if uc else None
        disponivel = bool(uc and uc.get("status") == "valid" and valor is not None)
        geo = METADADOS_POR_CNPJ.get(cnpj, {})
        unidades = unidades_por_cnpj.get(cnpj)
        status_uc = unidades.get("status") if unidades else "sem_referencia"
        qtd_uc = (
            unidades.get("qtd_uc_dezembro")
            if unidades and status_uc in {"valid", "zero"}
            else None
        )
        total_realizado = (
            linha["realizado"] if linha["status_realizado"] == "valid" else None
        )
        preparadas.append(
            {
                "cnpj": cnpj,
                "ano": ano,
                "rótulo": rótulos[cnpj],
                "valor": valor if disponivel else None,
                "disponível": disponivel,
                "total_realizado": total_realizado,
                "status_total_realizado_mart06": linha["status_realizado"],
                "qtd_uc": qtd_uc,
                "status_uc": status_uc,
                "uf": geo.get("uf", "Não disponível"),
                "regiao": geo.get("regiao", "Não disponível"),
                "posicao_investimento": linha["posicao_ranking"],
                "posicao_coorte": linha["posicao_coorte"],
            }
        )

    preparadas.sort(
        key=lambda linha: (
            not linha["disponível"],
            -linha["valor"] if linha["disponível"] else Decimal(0),
            linha["cnpj"],
        )
    )
    for posicao, linha in enumerate(preparadas, start=1):
        linha["posicao_uc"] = posicao if linha["disponível"] else None
        linha["destaque"] = (
            "Top 3" if linha["disponível"] and posicao <= 3 else "Demais"
        )
        linha["distribuidora"] = (
            f"#{posicao} · {linha['rótulo']}"
            if linha["disponível"]
            else linha["rótulo"]
        )
        linha["valor_exibido"] = (
            formatar_reais(linha["valor"]) if linha["disponível"] else "Não disponível"
        )
        linha["total_exibido"] = formatar_valor_validado(
            linha["total_realizado"],
            "valid" if linha["total_realizado"] is not None else "unavailable",
        )
        linha["ucs_exibidas"] = (
            f"{linha['qtd_uc']:,}".replace(",", ".")
            if linha["qtd_uc"] is not None
            else "Não disponível"
        )
    return preparadas


def renderizar_grafico_investimento_uc(dados: dict, ano: int) -> None:
    """Mostra o MART 03 ordenado por R$/UC para os dez CNPJs da coorte."""
    try:
        linhas = preparar_ranking_investimento_uc(dados, ano)
    except ValueError as erro:
        st.error(str(erro), title="Não foi possível montar o ranking por UC")
        return

    st.subheader("Ranking de investimento por UC", anchor=False)
    st.caption(
        "Comparação do investimento realizado por unidade consumidora entre as "
        "distribuidoras da coorte top 10."
    )

    df = pd.DataFrame(
        [
            {
                **linha,
                "R$/UC": float(linha["valor"]) if linha["disponível"] else None,
            }
            for linha in linhas
        ]
    )
    valores_validos = [linha["valor"] for linha in linhas if linha["disponível"]]
    maior_valor = max(valores_validos, default=Decimal(0))
    limite = float(maior_valor) * 1.2 if maior_valor > 0 else 1.0
    ordem = [linha["distribuidora"] for linha in linhas]
    eixo_x = alt.X(
        "R$/UC:Q",
        scale=alt.Scale(domain=[0, limite]),
        title="Investimento realizado por UC (R$)",
        axis=alt.Axis(
            format=",.0f",
            tickCount=5,
            labelFontSize=15,
            titleFontSize=14,
            gridColor="#26364B",
        ),
    )
    eixo_y = alt.Y(
        "distribuidora:N",
        sort=ordem,
        title=None,
            axis=alt.Axis(labelFontSize=16, labelLimit=260, labelPadding=10),
    )
    barras = (
        alt.Chart(df)
        .mark_bar(height=24, cornerRadiusEnd=4)
        .encode(
            x=eixo_x,
            y=eixo_y,
            color=alt.Color(
                "destaque:N",
                scale=alt.Scale(
                    domain=["Top 3", "Demais"],
                    range=["#29D3C2", "#53657D"],
                ),
                title="Posição por R$/UC",
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("rótulo:N", title="Distribuidora"),
                alt.Tooltip("ano:Q", title="Ano"),
                alt.Tooltip("valor_exibido:N", title="Investimento realizado por UC"),
                alt.Tooltip("total_exibido:N", title="Investimento realizado total"),
                alt.Tooltip("ucs_exibidas:N", title="UCs ativas em dezembro"),
                alt.Tooltip("uf:N", title="UF"),
                alt.Tooltip("regiao:N", title="Região"),
                alt.Tooltip("posicao_investimento:Q", title="Posição por investimento"),
                alt.Tooltip("posicao_coorte:Q", title="Posição fixa por UCs"),
            ],
        )
    )
    rotulos = (
        alt.Chart(df)
        .mark_text(
            align="left",
            baseline="middle",
            dx=7,
            fontSize=17,
            fontWeight=600,
            color="#F4F7FB",
        )
        .encode(
            x=alt.X("R$/UC:Q", scale=alt.Scale(domain=[0, limite])),
            y=alt.Y("distribuidora:N", sort=ordem),
            text=alt.Text("valor_exibido:N"),
        )
    )
    st.altair_chart(
        alt.layer(barras, rotulos).properties(height=480),
        width="stretch",
        alt=f"Ranking de investimento realizado por UC das dez distribuidoras em {ano}",
    )
    st.caption(
        "Destaque turquesa: três maiores valores de R$/UC. Os rótulos ao fim das "
        "barras mostram o valor de cada distribuidora."
    )


def renderizar_comparativo_top10(dados: dict, ano: int) -> None:
    """Exibe a coorte fixa ordenada pelo ranking financeiro do ano selecionado."""
    ranking = sorted(
        (linha for linha in dados["ranking"] if linha["ano"] == ano),
        key=lambda linha: linha["posicao_ranking"],
    )
    if len(ranking) != 10 or len({linha["cnpj"] for linha in ranking}) != 10:
        st.error(
            f"O MART 06 não retornou os dez CNPJs da coorte para {ano}; "
            "o comparativo não pode ser exibido com segurança."
        )
        return

    st.subheader("Comparativo Top 10", anchor=False)

    renderizar_grafico_investimento_uc(dados, ano)

    st.markdown("#### Três maiores investimentos realizados no ano")
    colunas_destaque = st.columns(3, gap="medium")
    for coluna, distribuidora in zip(colunas_destaque, ranking[:3], strict=True):
        with coluna, st.container(border=True):
            renderizar_card_distribuidora(
                distribuidora, dados, ano, compacto=False, destaque=True
            )

    st.markdown("#### Demais distribuidoras da coorte")
    restantes = ranking[3:]
    for inicio in range(0, len(restantes), 3):
        colunas = st.columns(3, gap="small")
        for coluna, distribuidora in zip(
            colunas, restantes[inicio : inicio + 3], strict=False
        ):
            with coluna, st.container(border=True):
                renderizar_card_distribuidora(distribuidora, dados, ano, compacto=True)

    st.caption(
        "Fonte: dados públicos da ANEEL · MARTS 03, 04, 06, 07 e 08. "
        "A comparação usa apenas os CNPJs da coorte fixa; os escopos nacional e "
        "top10 não são somados."
    )
