"""Componentes visuais reutilizáveis entre as páginas do dashboard."""

from decimal import Decimal

import streamlit as st

from dashboard.data import formatar_reais, formatar_valor_validado
from dashboard.logos import resolver_logo
from dashboard.metadata import (
    METADADOS_POR_CNPJ,
    TIPOS_INVESTIMENTO_EXIBIDOS,
    nome_marca,
)


def renderizar_card_distribuidora(
    distribuidora: dict,
    dados: dict,
    ano: int,
    compacto: bool = False,
    destaque: bool = False,
) -> None:
    """Renderiza um card recolhível para a futura página Comparativo Top 10."""
    cnpj = distribuidora["cnpj"]
    geo = METADADOS_POR_CNPJ.get(cnpj, {})
    marca = nome_marca(cnpj, distribuidora.get("nome", ""))
    logo = resolver_logo(cnpj)

    if compacto:
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(f"#{distribuidora['posicao_ranking']}", color="blue")
            if logo:
                st.image(str(logo), width=42, alt=f"Logo de {marca}")
            st.markdown(f"**{marca}**")
    else:
        st.badge(
            f"#{distribuidora['posicao_ranking']}",
            icon=":material/emoji_events:" if destaque else None,
            color="orange" if destaque else "blue",
        )
        if logo:
            st.image(str(logo), width=104, alt=f"Logo de {marca}")
        st.markdown(f"### {marca}")

    st.badge(
        f"{geo.get('uf', 'UF indisponível')} · "
        f"{geo.get('regiao', 'Região indisponível')}",
        icon=":material/location_on:",
        color="green",
    )
    realizado = (
        distribuidora["realizado"]
        if distribuidora.get("status_realizado") == "valid"
        else None
    )
    st.metric("Investido", formatar_reais(realizado), border=destaque)
    st.caption(f"Posição fixa por UCs: #{distribuidora['posicao_coorte']}")

    with st.expander("Ver detalhes", expanded=False):
        financeiros = _buscar(dados["detalhes_financeiros"], cnpj, ano)
        unidades = _buscar(dados["unidades_consumidoras"], cnpj, ano)
        valor_uc = _buscar(dados["investimento_por_uc"], cnpj, ano)
        tipos = [
            linha
            for linha in dados["tipos"]
            if linha["cnpj"] == cnpj and linha["ano"] == ano
        ]
        por_tipo = {linha["tipo"]: linha for linha in tipos}
        valores_validos = [
            linha["realizado"]
            for linha in tipos
            if linha["status_realizado"] == "valid" and linha["realizado"] is not None
        ]
        maior_tipo = max(valores_validos, default=None)

        st.markdown("**Investimento realizado por tipo de obra**")
        for tipo in TIPOS_INVESTIMENTO_EXIBIDOS:
            item = por_tipo.get(tipo)
            if item is None or item["realizado"] is None:
                st.caption(f"{tipo} · Não disponível")
            elif item["status_realizado"] == "valid":
                proporcao = (
                    float(item["realizado"] / maior_tipo)
                    if maior_tipo and maior_tipo > Decimal(0)
                    else 0.0
                )
                st.progress(
                    proporcao,
                    text=f"{tipo} · {formatar_reais(item['realizado'])}",
                )
            else:
                st.caption(f"{tipo} · Parcial · {formatar_reais(item['realizado'])}")
        st.caption("Barras relativas ao maior tipo válido desta distribuidora.")

        st.markdown(
            f"**Total planejado:** "
            f"{formatar_valor_validado(financeiros.get('planejado'), financeiros.get('status_planejado')) if financeiros else 'Não disponível'}  \n"
            f"**Total realizado:** "
            f"{formatar_valor_validado(financeiros.get('realizado'), financeiros.get('status_realizado')) if financeiros else 'Não disponível'}"
        )
        taxa = (
            financeiros.get("taxa_execucao")
            if financeiros and financeiros.get("status_taxa_execucao") == "valid"
            else None
        )
        st.caption(
            f"Taxa de execução financeira: {taxa:.2f}%"
            if taxa is not None
            else "Taxa de execução financeira: Não disponível"
        )
        quantidade_uc = (
            unidades.get("qtd_uc_dezembro")
            if unidades and unidades.get("status") == "valid"
            else None
        )
        uc_texto = (
            f"{quantidade_uc:,}".replace(",", ".")
            if quantidade_uc is not None
            else "Não disponível"
        )
        st.caption(f"UCs ativas em dezembro: {uc_texto}")
        valor_por_uc = (
            valor_uc.get("valor")
            if valor_uc and valor_uc.get("status") == "valid"
            else None
        )
        st.metric(
            "Investimento realizado por UC",
            formatar_reais(valor_por_uc),
            help=(
                "Intensidade média de investimento por unidade consumidora; "
                "não é um valor individual recebido pelo consumidor."
            ),
        )


def _buscar(linhas: list[dict], cnpj: str, ano: int) -> dict | None:
    return next(
        (linha for linha in linhas if linha["cnpj"] == cnpj and linha["ano"] == ano),
        None,
    )
