"""Página inicial do dashboard GridInvest Analytics."""

import sys
from decimal import Decimal
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.comparativo import renderizar_comparativo_top10
from dashboard.data import (
    calcular_taxa_execucao,
    carregar_dados_visao_geral,
    formatar_reais,
    formatar_valor_validado,
)
from dashboard.metadata import (
    METADADOS_POR_CNPJ,
    TIPOS_INVESTIMENTO_EXIBIDOS,
    nome_marca,
)
from dashboard.summary_table import imagem_distribuidora
from dashboard.visuals import (
    formatar_bilhoes,
    ordem_por_ranking_financeiro,
    rotulo_grafico,
    validar_reconciliacao_tipos,
)

st.set_page_config(
    page_title="GridInvest Analytics",
    page_icon=":material/bolt:",
    layout="wide",
)

with st.sidebar:
    st.title("GridInvest", icon=":material/bolt:")
    st.caption("Analytics · dados públicos da ANEEL")
    st.markdown("#### Navegação")
    pagina = st.radio(
        "Navegação",
        [
            "Visão Geral",
            "Comparativo Top 10",
            "Investimento por UC",
            "Planejado x Realizado",
            "Perfil de Investimentos",
        ],
        index=0,
        label_visibility="collapsed",
    )

st.title("PAINEL DE DISTRIBUIÇÃO ELÉTRICA — ANEEL", anchor=False)
st.header("GridInvest Analytics", anchor=False)

with st.sidebar:
    ano_selecionado = st.selectbox(
        "Ano de referência", [2025, 2024, 2023], index=0, key="ano_referencia"
    )

if pagina not in {"Visão Geral", "Comparativo Top 10"}:
    st.info(
        "Esta página será construída em uma próxima etapa.",
        icon=":material/construction:",
    )
    st.stop()

try:
    dados = carregar_dados_visao_geral()
except (FileNotFoundError, RuntimeError) as erro:
    st.error(str(erro), title="Não foi possível carregar os indicadores")
    st.stop()

if pagina == "Comparativo Top 10":
    renderizar_comparativo_top10(dados, ano_selecionado)
    st.stop()

st.subheader(
    "Descubra quais distribuidoras lideram os investimentos no Brasil",
    anchor=False,
)
st.caption(
    "Compare investimentos realizados, perfil das obras e indicadores por empresa "
    "com dados públicos da ANEEL."
)

registro_ano = next(
    item for item in dados["historico"] if item["ano"] == ano_selecionado
)
planejado = (
    registro_ano["planejado"] if registro_ano["status_planejado"] == "valid" else None
)
realizado = (
    registro_ano["realizado"] if registro_ano["status_realizado"] == "valid" else None
)
taxa = calcular_taxa_execucao(
    planejado,
    realizado,
    registro_ano["status_planejado"],
    registro_ano["status_realizado"],
)


with st.container(horizontal=True):
    indicadores = (
        (
            "Investimento planejado",
            f"Planejado · {ano_selecionado}",
            formatar_bilhoes(planejado),
            ":material/account_balance_wallet:",
            "blue",
            f"Valor integral: {formatar_valor_validado(planejado, registro_ano['status_planejado'])}",
        ),
        (
            "Investimento realizado",
            f"Realizado · {ano_selecionado}",
            formatar_bilhoes(realizado),
            ":material/payments:",
            "green",
            f"Valor integral: {formatar_valor_validado(realizado, registro_ano['status_realizado'])}",
        ),
        (
            "Execução financeira",
            "Taxa de execução",
            f"{taxa:.2f}%" if taxa is not None else "Não disponível",
            ":material/speed:",
            "violet",
            "Investimento realizado dividido pelo planejado; considera somente valores válidos.",
        ),
        (
            "Distribuidoras analisadas",
            "Distribuidoras",
            str(dados["quantidade_coorte"]),
            ":material/domain:",
            "orange",
            "CNPJs da coorte fixa selecionada pelas UCs ativas de dezembro de 2025.",
        ),
    )
    for titulo, rotulo, valor, icone, cor, ajuda in indicadores:
        with st.container(border=True):
            st.badge(titulo, icon=icone, color=cor)
            st.metric(rotulo, valor, border=False, help=ajuda)

ranking_ano = sorted(
    (linha for linha in dados["ranking"] if linha["ano"] == ano_selecionado),
    key=lambda linha: linha["posicao_ranking"],
)
cnpjs = [linha["cnpj"] for linha in ranking_ano]
tipos_ano = [linha for linha in dados["tipos"] if linha["ano"] == ano_selecionado]
financeiros_ano = [
    linha for linha in dados["detalhes_financeiros"] if linha["ano"] == ano_selecionado
]

st.subheader("Ranking de Investimentos por Distribuidora")
st.caption(
    "Descubra quanto cada distribuidora investiu e como os recursos foram "
    "distribuídos entre Expansão, Melhoria e Renovação."
)

rotulo_por_cnpj = {
    linha["cnpj"]: rotulo_grafico(linha["cnpj"], linha["nome"], cnpjs)
    for linha in ranking_ano
}
ordem_distribuidoras = ordem_por_ranking_financeiro(
    ranking_ano, rotulo_por_cnpj
)

categorias_adicionais = dados["categorias_adicionais"]
if categorias_adicionais:
    st.warning(
        "O MART 08 contém tipos adicionais fora das três categorias deste gráfico: "
        + ", ".join(categorias_adicionais)
        + ". Eles não foram incorporados silenciosamente; confira o perfil completo "
        "antes de interpretar os totais como abrangentes."
    )

divergencias = validar_reconciliacao_tipos(
    ranking_ano, tipos_ano, financeiros_ano, ano_selecionado
)
if divergencias:
    empresas = ", ".join(
        nome_marca(
            item["cnpj"],
            next(
                linha["nome"] for linha in ranking_ano if linha["cnpj"] == item["cnpj"]
            ),
        )
        for item in divergencias
    )
    st.warning(
        "A soma de Expansão, Melhoria e Renovação não reconcilia com o total "
        f"realizado de: {empresas}. O gráfico mostra as categorias identificadas "
        "e não representa todo o investimento nesses casos."
    )

cores_tipos = alt.Scale(
    domain=list(TIPOS_INVESTIMENTO_EXIBIDOS),
    range=["#38BDF8", "#34D399", "#A78BFA"],
)
tipos_por_chave = {(linha["cnpj"], linha["tipo"]): linha for linha in tipos_ano}
linhas_grafico_tipos = []
linhas_rotulos_totais = []

for distribuidora in ranking_ano:
    cnpj = distribuidora["cnpj"]
    rotulo = rotulo_por_cnpj[cnpj]
    valor_total = (
        distribuidora["realizado"]
        if distribuidora["status_realizado"] == "valid"
        else None
    )
    status_total = distribuidora["status_realizado"]
    soma_tipos_validos = Decimal(0)

    for tipo in TIPOS_INVESTIMENTO_EXIBIDOS:
        item = tipos_por_chave.get((cnpj, tipo))
        valor_tipo = (
            item["realizado"] if item and item["status_realizado"] == "valid" else None
        )
        if valor_tipo is not None:
            soma_tipos_validos += valor_tipo

        participacao = None
        if valor_tipo is not None and valor_total is not None and valor_total > 0:
            participacao = float(valor_tipo / valor_total * Decimal(100))

        if item is None or item["realizado"] is None:
            valor_tooltip = "Não disponível"
        elif item["status_realizado"] == "valid":
            valor_tooltip = formatar_reais(item["realizado"])
        else:
            valor_tooltip = f"Parcial · {formatar_reais(item['realizado'])}"

        linhas_grafico_tipos.append(
            {
                "cnpj": cnpj,
                "Distribuidora": rotulo,
                "Posição": distribuidora["posicao_ranking"],
                "Tipo de obra": tipo,
                "Investimento (R$ bi)": (
                    float(valor_tipo / Decimal(1_000_000_000))
                    if valor_tipo is not None
                    else None
                ),
                "Valor individual": valor_tooltip,
                "Participação exibida": (
                    f"{participacao:.1f}%"
                    if participacao is not None
                    else "Não disponível"
                ),
                "Total realizado": formatar_valor_validado(valor_total, status_total),
            }
        )

    linhas_rotulos_totais.append(
        {
            "cnpj": cnpj,
            "Distribuidora": rotulo,
            "Posição": distribuidora["posicao_ranking"],
            "Ponta da barra (R$ bi)": float(
                soma_tipos_validos / Decimal(1_000_000_000)
            ),
            "Total realizado (R$ bi)": (
                float(valor_total / Decimal(1_000_000_000))
                if valor_total is not None
                else None
            ),
            "Total compacto": formatar_bilhoes(valor_total),
        }
    )

tipos_df = pd.DataFrame(linhas_grafico_tipos)
rotulos_totais_df = pd.DataFrame(linhas_rotulos_totais)
valores_escala = [
    serie
    for serie in (
        tipos_df["Investimento (R$ bi)"].max(skipna=True),
        rotulos_totais_df["Ponta da barra (R$ bi)"].max(skipna=True),
        rotulos_totais_df["Total realizado (R$ bi)"].max(skipna=True),
    )
    if pd.notna(serie)
]
maior_valor_grafico = max(valores_escala, default=1.0)
limite_grafico = maior_valor_grafico * 1.2 if maior_valor_grafico > 0 else 1.0

grafico_tipos = (
    alt.Chart(tipos_df)
    .mark_bar(height=27, cornerRadiusEnd=3)
    .encode(
        x=alt.X(
            "Investimento (R$ bi):Q",
            stack="zero",
            scale=alt.Scale(domain=[0, limite_grafico]),
            title="Investimento realizado (R$ bilhões)",
            axis=alt.Axis(
                format=".1f",
                tickCount=5,
                labelFontSize=14,
                titleFontSize=15,
                titlePadding=12,
                labelPadding=8,
                gridColor="#26364B",
            ),
        ),
        y=alt.Y(
            "Distribuidora:N",
            sort=ordem_distribuidoras,
            scale=alt.Scale(reverse=True),
            title=None,
            axis=alt.Axis(labelLimit=240, labelFontSize=16, labelPadding=10),
        ),
        color=alt.Color(
            "Tipo de obra:N",
            scale=cores_tipos,
            title="Tipo de investimento",
            legend=alt.Legend(
                orient="top",
                labelFontSize=14,
                titleFontSize=15,
                symbolSize=140,
            ),
        ),
        order=alt.Order("Tipo de obra:N", sort="ascending"),
        tooltip=[
            alt.Tooltip("Posição:Q", title="Posição no ranking realizado"),
            alt.Tooltip("Distribuidora:N", title="Distribuidora"),
            alt.Tooltip("Tipo de obra:N", title="Tipo de investimento"),
            alt.Tooltip("Valor individual:N", title="Investimento realizado"),
            alt.Tooltip(
                "Participação exibida:N", title="Participação no total realizado"
            ),
            alt.Tooltip("Total realizado:N", title="Total realizado da distribuidora"),
        ],
    )
    .properties(height=460)
)
rotulos_totais = (
    alt.Chart(rotulos_totais_df)
    .mark_text(
        align="left",
        baseline="middle",
        dx=8,
        fontSize=14,
        fontWeight=600,
        color="#E5EDF7",
    )
    .encode(
        x=alt.X(
            "Ponta da barra (R$ bi):Q",
            scale=alt.Scale(domain=[0, limite_grafico]),
        ),
        y=alt.Y(
            "Distribuidora:N",
            sort=ordem_distribuidoras,
            scale=alt.Scale(reverse=True),
        ),
        text=alt.Text("Total compacto:N"),
    )
)
st.altair_chart(
    alt.layer(grafico_tipos, rotulos_totais),
    width="stretch",
    alt=(
        "Ranking das dez distribuidoras por investimento total realizado, "
        "dividido entre Expansão, Melhoria e Renovação"
    ),
)
st.subheader("Resumo das distribuidoras")
financeiros_por_cnpj = {linha["cnpj"]: linha for linha in financeiros_ano}
uc_por_cnpj = {
    linha["cnpj"]: linha
    for linha in dados["investimento_por_uc"]
    if linha["ano"] == ano_selecionado
}
linhas_resumo = []
for linha in ranking_ano:
    cnpj = linha["cnpj"]
    financeiro = financeiros_por_cnpj.get(cnpj, {})
    valor_uc = uc_por_cnpj.get(cnpj, {})
    geo = METADADOS_POR_CNPJ.get(cnpj, {})
    marca = nome_marca(cnpj, linha["nome"])
    linhas_resumo.append(
        {
            "cnpj": cnpj,
            "posição": linha["posicao_ranking"],
            "logo_marca_uf": imagem_distribuidora(
                cnpj, marca, geo.get("uf", "Não disponível")
            ),
            "realizado": (
                linha["realizado"]
                if linha["status_realizado"] == "valid"
                and linha["realizado"] is not None
                else None
            ),
            "execução": (
                financeiro["taxa_execucao"]
                if financeiro.get("status_taxa_execucao") == "valid"
                and financeiro.get("taxa_execucao") is not None
                else None
            ),
            "realizado_por_uc": (
                valor_uc["valor"]
                if valor_uc.get("status") == "valid"
                and valor_uc.get("valor") is not None
                else None
            ),
        }
    )
opcoes_ordenacao = {
    "Posição no ranking": "posição",
    "Investimento realizado": "realizado",
    "Execução financeira (%)": "execução",
    "Realizado por UC (R$/UC)": "realizado_por_uc",
}
ordenacao = st.selectbox(
    "Ordenar tabela por",
    list(opcoes_ordenacao),
    index=0,
    key="ordenacao_resumo_distribuidoras",
)
campo_ordenacao = opcoes_ordenacao[ordenacao]
linhas_resumo.sort(
    key=lambda item: (
        item[campo_ordenacao] is None,
        item[campo_ordenacao]
        if campo_ordenacao == "posição"
        else -(item[campo_ordenacao] or Decimal(0)),
        item["cnpj"],
    )
)


def numero_brasileiro(valor: Decimal) -> str:
    """Formata valores com duas casas e separadores brasileiros."""
    return f"{valor:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


df_resumo = pd.DataFrame(
    [
        {
            "Posição": linha["posição"],
            "Distribuidora": (
                f"![{nome_marca(linha['cnpj'], '')}]({linha['logo_marca_uf']})"
            ),
            "Investimento realizado (R$ bi)": (
                f"R$ {numero_brasileiro(linha['realizado'] / Decimal(1_000_000_000))} bi"
                if linha["realizado"] is not None
                else "Não disponível"
            ),
            "Execução financeira (%)": (
                f"{numero_brasileiro(linha['execução'])}%"
                if linha["execução"] is not None
                else "Não disponível"
            ),
            "Realizado por UC (R$/UC)": (
                f"R$ {numero_brasileiro(linha['realizado_por_uc'])}"
                if linha["realizado_por_uc"] is not None
                else "Não disponível"
            ),
        }
        for linha in linhas_resumo
    ]
)
larguras_colunas = ("70px", "230px", "185px", "170px", "187px")
estilos_colunas = [
    {
        "selector": f"th.col{indice}, td.col{indice}",
        "props": [
            ("width", largura),
            ("min-width", largura),
            ("max-width", largura),
            ("padding", "5px 8px"),
            ("text-align", "right" if indice != 1 else "left"),
        ],
    }
    for indice, largura in enumerate(larguras_colunas)
]
st.table(
    df_resumo.style.set_table_styles(estilos_colunas),
    hide_index=True,
    width=842,
    alt=f"Resumo ordenável das dez distribuidoras da coorte em {ano_selecionado}",
)

st.caption(
    "Fonte: dados públicos da ANEEL. KPIs: MART 01 · ranking e valores: MART 06 · "
    "UCs e R$/UC: MARTS 07 e 03 · execução: MART 04 · tipo de obra: MART 08."
)
