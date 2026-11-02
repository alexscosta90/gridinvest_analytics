"""Cabeçalho horizontal compartilhado por todas as páginas do dashboard."""

from pathlib import Path

import streamlit as st

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logos" / "gridinvest_analytics.png"


def renderizar_cabecalho() -> None:
    """Exibe a logo e o texto institucional responsivo em um único componente."""
    if not LOGO_PATH.is_file():
        st.error(f"Logo oficial não encontrada: {LOGO_PATH}")
        return

    st.image(
        LOGO_PATH.read_bytes(),
        width="stretch",
        alt="GridInvest Analytics — Inteligência de dados do setor elétrico",
    )
    st.markdown(
        """
        <style>
        .gridinvest-cabecalho-titulo {
            color: #F4F7FB;
            font-size: clamp(1.65rem, 3vw, 2.6rem);
            font-weight: 750;
            line-height: 1.15;
            margin: 0.45rem 0 0.55rem;
            overflow-wrap: anywhere;
        }
        .gridinvest-cabecalho-descricao {
            color: #CBD5E1;
            font-size: clamp(1rem, 1.35vw, 1.15rem);
            line-height: 1.55;
            margin: 0 0 0.45rem;
        }
        .gridinvest-cabecalho-fonte {
            color: #94A3B8;
            font-size: 0.84rem;
            line-height: 1.4;
            margin: 0 0 0.85rem;
        }
        @media (max-width: 640px) {
            .gridinvest-cabecalho-titulo {
                font-size: 1.55rem;
                line-height: 1.2;
            }
        }
        </style>
        <section class="gridinvest-cabecalho">
          <h1 class="gridinvest-cabecalho-titulo">Investimentos nas Redes de Distribuição de Energia Elétrica no Brasil</h1>
          <p class="gridinvest-cabecalho-descricao">Explore quanto as distribuidoras investem, compare os valores planejados e realizados e descubra como os recursos são aplicados na expansão, melhoria e renovação das redes elétricas.</p>
          <p class="gridinvest-cabecalho-fonte">Fonte: Dados Públicos ANEEL.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
