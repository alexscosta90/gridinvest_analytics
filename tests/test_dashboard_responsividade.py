from streamlit.testing.v1 import AppTest

from dashboard.responsive import RESPONSIVE_STYLES


def test_grade_de_kpis_exibe_todos_os_valores_sem_alteracao():
    app = AppTest.from_string(
        """
from dashboard.responsive import injetar_estilos_responsivos, renderizar_grade_metricas

injetar_estilos_responsivos()
renderizar_grade_metricas(
    [
        {"title": "Título completo do indicador", "label": "Valor", "value": "R$ 1.234.567,89"},
        {"title": "Quantidade completa", "label": "UCs ativas", "value": "1.234.567"},
    ],
    chave="teste-responsivo",
    colunas_desktop=4,
)
"""
    ).run()

    assert not app.exception
    assert [metric.value for metric in app.metric] == ["R$ 1.234.567,89", "1.234.567"]
    assert len(app.html) == 1


def test_estilos_de_kpi_usam_container_queries_e_permitem_quebra():
    assert "container-type: inline-size" in RESPONSIVE_STYLES
    assert "@container (min-width: 34rem)" in RESPONSIVE_STYLES
    assert "@container (min-width: 66rem)" in RESPONSIVE_STYLES
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in RESPONSIVE_STYLES
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in RESPONSIVE_STYLES
    assert "white-space: normal" in RESPONSIVE_STYLES
    assert "text-overflow: clip" in RESPONSIVE_STYLES
