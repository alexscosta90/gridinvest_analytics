"""Helpers e estilos compartilhados para layouts responsivos do dashboard."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

RESPONSIVE_STYLES = """
<style>
[class*="st-key-gridinvest-kpi-scope-"] {
  container-type: inline-size !important;
  width: 100% !important;
}

[class*="st-key-gridinvest-kpi-grid-"] {
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) !important;
  gap: 1rem !important;
  align-items: stretch !important;
  width: 100% !important;
}

@container (min-width: 34rem) {
  [class*="st-key-gridinvest-kpi-grid-"] {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
}

@container (min-width: 66rem) {
  [class*="st-key-gridinvest-kpi-grid-"] {
    grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
  }
}

[class*="st-key-gridinvest-kpi-card-"] {
  width: auto !important;
  min-width: 0 !important;
  max-width: 100% !important;
  flex: none !important;
}

[class*="st-key-gridinvest-kpi-card-"] *,
[class*="st-key-gridinvest-kpi-card-"] p {
  min-width: 0 !important;
  max-width: 100% !important;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  text-overflow: clip !important;
  overflow: visible !important;
}

@media (max-width: 640px) {
  h1 {
    font-size: clamp(1.4rem, 5.8vw, 1.8rem) !important;
    line-height: 1.2 !important;
    overflow-wrap: anywhere;
  }

  h2 {
    font-size: clamp(1.2rem, 5vw, 1.5rem) !important;
    line-height: 1.25 !important;
    overflow-wrap: anywhere;
  }

  h3 {
    font-size: clamp(1.05rem, 4.5vw, 1.3rem) !important;
    line-height: 1.25 !important;
    overflow-wrap: anywhere;
  }

  [class*="st-key-gridinvest-chart-"] svg text {
    font-size: clamp(10px, 2.8vw, 12px) !important;
  }

  [class*="st-key-gridinvest-table-"] {
    min-width: 0 !important;
    max-width: 100% !important;
  }
}

</style>
"""


def injetar_estilos_responsivos() -> None:
    """Aplica regras mobile usando somente chaves/classes próprias do projeto."""
    st.html(RESPONSIVE_STYLES)


def renderizar_grade_metricas(
    indicadores: Sequence[Mapping[str, Any]],
    *,
    chave: str,
    colunas_desktop: int = 4,
    borda_card: bool = True,
) -> None:
    """Renderiza métricas nativas em cards que quebram em larguras menores."""
    if colunas_desktop not in {1, 3, 4}:
        raise ValueError("colunas_desktop deve ser 1, 3 ou 4.")

    # Container queries measure the KPI area's real width, including browser zoom.
    with (
        st.container(key=f"gridinvest-kpi-scope-{chave}", width="stretch"),
        st.container(key=f"gridinvest-kpi-grid-{chave}"),
    ):
        for indice, indicador in enumerate(indicadores):
            with st.container(
                border=borda_card,
                width="stretch",
                key=f"gridinvest-kpi-card-{chave}-{indice}",
            ):
                titulo = indicador.get("title")
                if titulo:
                    st.badge(
                        titulo,
                        icon=indicador.get("icon"),
                        color=indicador.get("color", "blue"),
                    )
                st.metric(
                    indicador["label"],
                    indicador["value"],
                    border=False,
                    help=indicador.get("help"),
                )
                caption = indicador.get("caption")
                if caption:
                    st.caption(caption)
