import base64
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.comparativo import preparar_ranking_investimento_uc
from dashboard.data import (
    calcular_taxa_execucao,
    formatar_reais,
    formatar_valor_validado,
    ler_dados_visao_geral,
)
from dashboard.investimento_uc import (
    calcular_kpis_coorte,
    preparar_dados_pagina,
)
from dashboard.logos import ARQUIVOS_LOGO_POR_CNPJ, resolver_logo
from dashboard.metadata import (
    METADADOS_POR_CNPJ,
    NOMES_MARCA_POR_CNPJ,
    TIPOS_INVESTIMENTO_EXIBIDOS,
    nome_marca,
)
from dashboard.perfil_investimentos import (
    _construir_graficos as construir_graficos_perfil,
)
from dashboard.perfil_investimentos import (
    preparar_dados_pagina as preparar_perfil_investimentos,
)
from dashboard.planejado_realizado import (
    _formatar_diferenca_bilhoes,
    construir_grafico_colunas,
)
from dashboard.planejado_realizado import (
    preparar_dados_pagina as preparar_planejado_realizado,
)
from dashboard.summary_table import imagem_distribuidora
from dashboard.visuals import (
    formatar_bilhoes,
    ordem_por_ranking_financeiro,
    rotulo_grafico,
    validar_reconciliacao_tipos,
)


def assert_cabecalho_compartilhado(app):
    conteudo = "\n".join(item.value for item in app.markdown)
    assert len(app.image) == 1
    assert (
        conteudo.count(
            "Investimentos nas Redes de Distribuição de Energia Elétrica no Brasil"
        )
        == 1
    )
    assert (
        conteudo.count(
            "Explore quanto as distribuidoras investem, compare os valores planejados e "
            "realizados e descubra como os recursos são aplicados na expansão, melhoria "
            "e renovação das redes elétricas."
        )
        == 1
    )
    assert conteudo.count("Fonte: Dados Públicos ANEEL.") == 1


@pytest.fixture
def banco_dashboard(tmp_path):
    caminho = tmp_path / "dashboard.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    con.execute(
        """
        CREATE TABLE marts.investimentos_anuais (
            ano_referencia SMALLINT,
            escopo VARCHAR,
            total_planejado DECIMAL(18, 2),
            status_total_planejado VARCHAR,
            total_realizado DECIMAL(18, 2),
            status_total_realizado VARCHAR,
            qtd_cnpjs BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE marts.cohorte_top10_2025 (
            posicao INTEGER,
            cnpj VARCHAR,
            uc_dez_2025 BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE marts.ranking_investimentos (
            ano_referencia SMALLINT,
            cnpj VARCHAR,
            escopo VARCHAR,
            medida VARCHAR,
            valor_investimento DECIMAL(18, 2),
            status_valor VARCHAR,
            posicao BIGINT,
            rotulo_pdd VARCHAR,
            rotulo_indger VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE marts.perfil_investimentos (
            escopo VARCHAR,
            ano_referencia SMALLINT,
            cnpj VARCHAR,
            rotulo_pdd VARCHAR,
            tipo_obra VARCHAR,
            classe_obra VARCHAR,
            total_realizado DECIMAL(18, 2),
            qtd_realizados_validos BIGINT,
            qtd_realizados_nulos BIGINT,
            qtd_realizados_invalidos BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE marts.investimento_por_uc (
            ano_referencia SMALLINT,
            escopo VARCHAR,
            cnpj VARCHAR,
            qtd_uc_dezembro BIGINT,
            status_cobertura VARCHAR,
            total_realizado DECIMAL(18, 2),
            status_total_realizado VARCHAR,
            investimento_realizado_por_uc DECIMAL(18, 2),
            status_realizado_por_uc VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE marts.planejado_vs_realizado_distribuidora (
            cnpj VARCHAR,
            ano_referencia SMALLINT,
            total_planejado DECIMAL(18, 2),
            status_total_planejado VARCHAR,
            total_realizado DECIMAL(18, 2),
            status_total_realizado VARCHAR,
            percentual_execucao DECIMAL(18, 2),
            status_percentual_execucao VARCHAR,
            diferenca_absoluta DECIMAL(18, 2),
            status_diferenca VARCHAR,
            diferenca_percentual DECIMAL(18, 2),
            status_diferenca_percentual VARCHAR,
            top10_2025 BOOLEAN
        )
        """
    )
    con.execute(
        """
        CREATE TABLE marts.ranking_por_uc_top10 (
            ano_referencia SMALLINT,
            cnpj VARCHAR,
            qtd_uc_dezembro BIGINT,
            status_cobertura VARCHAR
        )
        """
    )
    for ano in (2023, 2024, 2025):
        con.execute(
            "INSERT INTO marts.investimentos_anuais VALUES (?, 'top10', 100.00, 'valid', 75.00, 'valid', 10)",
            [ano],
        )
    con.execute(
        "INSERT INTO marts.investimentos_anuais VALUES (2025, 'nacional', 999.00, 'valid', 800.00, 'valid', 20)"
    )
    for posicao in range(1, 11):
        con.execute(
            "INSERT INTO marts.cohorte_top10_2025 VALUES (?, ?, ?)",
            [posicao, f"cnpj-{posicao}", 1000 - posicao],
        )
        for ano in (2023, 2024, 2025):
            con.execute(
                """
                INSERT INTO marts.investimento_por_uc
                VALUES (?, 'top10', ?, 1000, 'valid', 30.00, 'valid', 0.03, 'valid')
                """,
                [ano, f"cnpj-{posicao}"],
            )
            con.execute(
                """
                INSERT INTO marts.planejado_vs_realizado_distribuidora
                VALUES (?, ?, 10.00, 'valid', 7.50, 'valid', 75.00, 'valid',
                        -2.50, 'valid', -25.00, 'valid', TRUE)
                """,
                [f"cnpj-{posicao}", ano],
            )
            con.execute(
                """
                INSERT INTO marts.ranking_por_uc_top10
                VALUES (?, ?, 1000, 'valid')
                """,
                [ano, f"cnpj-{posicao}"],
            )
            for medida, valor, posicao_financeira in (
                ("planejado", 120, posicao),
                ("realizado", 30, posicao),
            ):
                con.execute(
                    """
                    INSERT INTO marts.ranking_investimentos
                    VALUES (?, ?, 'top10', ?, ?, 'valid', ?, ?, NULL)
                    """,
                    [
                        ano,
                        f"cnpj-{posicao}",
                        medida,
                        valor,
                        posicao_financeira,
                        f"Distribuidora {posicao}",
                    ],
                )
            for tipo in TIPOS_INVESTIMENTO_EXIBIDOS:
                for classe, valor in (
                    ("Classe teste A", 4.00),
                    ("Classe teste B", 6.00),
                ):
                    con.execute(
                        """
                        INSERT INTO marts.perfil_investimentos
                        VALUES ('top10', ?, ?, ?, ?, ?, ?, 1, 0, 0)
                        """,
                        [
                            ano,
                            f"cnpj-{posicao}",
                            f"Distribuidora {posicao}",
                            tipo,
                            classe,
                            valor,
                        ],
                    )
    con.execute(
        """
        INSERT INTO marts.investimento_por_uc
        VALUES (2025, 'nacional', 'cnpj-1', 99999, 'valid', 999.00, 'valid', 999.00, 'valid')
        """
    )
    con.execute(
        """
        INSERT INTO marts.planejado_vs_realizado_distribuidora
        VALUES ('cnpj-1', 2025, 999.00, 'valid', 999.00, 'valid', 100.00, 'valid',
                0.00, 'valid', 0.00, 'valid', FALSE)
        """
    )
    con.execute(
        """
        INSERT INTO marts.ranking_investimentos
        VALUES (2025, 'cnpj-1', 'nacional', 'realizado', 999.00, 'valid', 1,
                'Fora da coorte', NULL)
        """
    )
    con.execute(
        """
        INSERT INTO marts.perfil_investimentos
        VALUES ('nacional', 2025, 'cnpj-1', 'Fora da coorte', 'Expansão',
                'Classe teste', 999.00, 1, 0, 0)
        """
    )
    con.execute(
        """
        INSERT INTO marts.perfil_investimentos
        VALUES ('top10', 2025, 'cnpj-1', 'Distribuidora 1',
                'Obra com Participação Financeira', 'Classe teste',
                500.00, 1, 0, 0)
        """
    )
    con.close()
    return caminho


def test_leitura_consulta_somente_top10_e_coorte(banco_dashboard):
    dados = ler_dados_visao_geral(banco_dashboard)

    assert [linha["ano"] for linha in dados["historico"]] == [2023, 2024, 2025]
    assert all(linha["planejado"] == Decimal("100.00") for linha in dados["historico"])
    assert all(linha["realizado"] == Decimal("75.00") for linha in dados["historico"])
    assert dados["quantidade_coorte"] == 10
    assert len(dados["coorte"]) == 10
    assert dados["coorte"][0]["nome"] == "Distribuidora 1"
    assert dados["coorte"][0]["posicao"] == 1
    assert len(dados["ranking"]) == 30
    membros = {linha["cnpj"] for linha in dados["coorte"]}
    for ano in (2023, 2024, 2025):
        ranking_ano = [linha for linha in dados["ranking"] if linha["ano"] == ano]
        assert {linha["cnpj"] for linha in ranking_ano} == membros
        assert sorted(linha["posicao_ranking"] for linha in ranking_ano) == list(
            range(1, 11)
        )
    assert len(dados["tipos"]) == 90
    assert all("classe" not in linha for linha in dados["tipos"])
    assert all(item["realizado"] == Decimal("10.00") for item in dados["tipos"])
    assert {item["tipo"] for item in dados["tipos"]} == set(TIPOS_INVESTIMENTO_EXIBIDOS)
    assert dados["categorias_adicionais"] == ["Obra com Participação Financeira"]
    assert len(dados["detalhes_financeiros"]) == 30
    assert len(dados["unidades_consumidoras"]) == 30
    assert len(dados["investimento_por_uc"]) == 30
    financeiro = next(
        item
        for item in dados["detalhes_financeiros"]
        if item["cnpj"] == "cnpj-1" and item["ano"] == 2025
    )
    assert financeiro["planejado"] == Decimal("10.00")
    assert financeiro["realizado"] == Decimal("7.50")
    assert financeiro["taxa_execucao"] == Decimal("75.00")
    assert financeiro["diferenca_absoluta"] == Decimal("-2.50")
    assert financeiro["diferenca_percentual"] == Decimal("-25.00")
    uc = next(
        item
        for item in dados["unidades_consumidoras"]
        if item["cnpj"] == "cnpj-1" and item["ano"] == 2025
    )
    assert uc["qtd_uc_dezembro"] == 1000
    valor_uc = next(
        item
        for item in dados["investimento_por_uc"]
        if item["cnpj"] == "cnpj-1" and item["ano"] == 2025
    )
    assert valor_uc["valor"] == Decimal("0.03")


def test_calculo_taxa_execucao_arredondado():
    taxa = calcular_taxa_execucao(Decimal("3.00"), Decimal("1.00"), "valid", "valid")
    assert taxa == Decimal("33.33")


@pytest.mark.parametrize(
    ("planejado", "realizado", "status_planejado", "status_realizado"),
    [
        (Decimal("0.00"), Decimal("5.00"), "valid", "valid"),
        (None, Decimal("5.00"), "null", "valid"),
        (Decimal("10.00"), None, "valid", "invalid"),
        (Decimal("10.00"), Decimal("5.00"), "invalid", "valid"),
    ],
)
def test_taxa_indisponivel_sem_base_financeira_valida(
    planejado, realizado, status_planejado, status_realizado
):
    assert (
        calcular_taxa_execucao(planejado, realizado, status_planejado, status_realizado)
        is None
    )


def test_formatacao_monetaria_brasileira():
    assert formatar_reais(Decimal("23441619152.98")) == "R$ 23.441.619.152,98"


def test_formatacao_compacta_em_bilhoes():
    assert formatar_bilhoes(Decimal("2930000000.00")) == "R$ 2,93 bi"
    assert formatar_bilhoes(None) == "Não disponível"


def test_indicador_indisponivel_nao_vira_zero():
    assert formatar_valor_validado(None, "null") == "Não disponível"
    assert formatar_valor_validado(Decimal("45.00"), "invalid") == "Não disponível"
    assert formatar_valor_validado(Decimal("0.00"), "valid") == "R$ 0,00"


def test_banco_ausente_nao_e_criado(tmp_path):
    caminho = tmp_path / "inexistente.duckdb"

    with pytest.raises(FileNotFoundError, match="Banco DuckDB não encontrado"):
        ler_dados_visao_geral(caminho)

    assert not caminho.exists()


def test_tabelas_ausentes_sao_informadas(banco_dashboard):
    con = duckdb.connect(str(banco_dashboard))
    con.execute("DROP TABLE marts.cohorte_top10_2025")
    con.close()

    with pytest.raises(RuntimeError, match="cohorte_top10_2025"):
        ler_dados_visao_geral(banco_dashboard)


def test_mapeamento_de_logos_cobre_a_coorte_fixa():
    assert len(ARQUIVOS_LOGO_POR_CNPJ) == 10
    assert ARQUIVOS_LOGO_POR_CNPJ["06981180000116"] == "cemig.png"
    assert all(
        (Path(__file__).resolve().parents[1] / "assets" / "logos" / nome).is_file()
        for nome in ARQUIVOS_LOGO_POR_CNPJ.values()
    )


def test_imagem_tabela_resolve_logos_por_cnpj_para_marcas_repetidas():
    cnpjs = ("61695227000193", "07047251000170")
    ufs = ("SP", "CE")
    svgs = [
        base64.b64decode(
            imagem_distribuidora(cnpj, "ENEL", uf).split(",", 1)[1]
        ).decode("utf-8")
        for cnpj, uf in zip(cnpjs, ufs, strict=True)
    ]

    assert "ENEL" in svgs[0] and "SP" in svgs[0]
    assert "ENEL" in svgs[1] and "CE" in svgs[1]
    for cnpj, svg in zip(cnpjs, svgs, strict=True):
        caminho_logo = resolver_logo(cnpj)
        conteudo_logo = base64.b64encode(caminho_logo.read_bytes()).decode("ascii")
        assert conteudo_logo in svg
    assert svgs[0] != svgs[1]


def test_metadados_geograficos_cobrem_a_coorte():
    assert len(METADADOS_POR_CNPJ) == 10
    assert METADADOS_POR_CNPJ["06981180000116"] == {
        "uf": "MG",
        "regiao": "Sudeste",
    }


@pytest.mark.parametrize(
    ("cnpj", "marca"),
    [
        ("06981180000116", "CEMIG"),
        ("61695227000193", "ENEL"),
        ("15139629000194", "NEOENERGIA"),
        ("04368898000106", "COPEL"),
        ("33050196000188", "CPFL"),
        ("60444437000146", "LIGHT"),
        ("07047251000170", "ENEL"),
        ("10835932000108", "NEOENERGIA"),
        ("08336783000190", "CELESC"),
        ("01543032000104", "EQUATORIAL"),
    ],
)
def test_nome_principal_da_marca_e_resolvido_por_cnpj(cnpj, marca):
    assert nome_marca(cnpj, "Nome original com sufixo") == marca


def test_marcas_repetidas_tem_cnpjs_independentes():
    enel_sp = "61695227000193"
    enel_ce = "07047251000170"
    neoenergia_coelba = "15139629000194"
    neoenergia_pernambuco = "10835932000108"

    assert NOMES_MARCA_POR_CNPJ[enel_sp] == NOMES_MARCA_POR_CNPJ[enel_ce]
    assert (
        NOMES_MARCA_POR_CNPJ[neoenergia_coelba]
        == NOMES_MARCA_POR_CNPJ[neoenergia_pernambuco]
    )
    assert enel_sp != enel_ce
    assert neoenergia_coelba != neoenergia_pernambuco


def test_perfil_agrega_classes_sem_exibi_las(banco_dashboard):
    con = duckdb.connect(str(banco_dashboard))
    con.execute(
        """
        UPDATE marts.perfil_investimentos
        SET qtd_realizados_invalidos = 1
        WHERE ano_referencia = 2025
          AND cnpj = 'cnpj-1'
          AND tipo_obra = 'Expansão'
          AND classe_obra = 'Classe teste B'
        """
    )
    con.close()

    dados = ler_dados_visao_geral(banco_dashboard)
    tipo = next(
        linha
        for linha in dados["tipos"]
        if linha["ano"] == 2025
        and linha["cnpj"] == "cnpj-1"
        and linha["tipo"] == "Expansão"
    )
    assert tipo["status_realizado"] == "partial_invalid"
    assert tipo["realizado"] == Decimal("10.00")


def test_logo_ausente_usa_fallback_sem_falhar(tmp_path):
    assert resolver_logo("06981180000116", tmp_path) is None
    assert resolver_logo("cnpj-desconhecido", tmp_path) is None


def test_logo_existente_e_resolvido_por_cnpj(tmp_path):
    arquivo = tmp_path / "cemig.png"
    arquivo.write_bytes(b"logo ficticio de teste")

    assert resolver_logo("06981180000116", tmp_path) == arquivo


def test_rotulo_grafico_distingue_marcas_repetidas_por_uf():
    assert (
        rotulo_grafico(
            "61695227000193",
            "Enel Distribuição SP",
            ["61695227000193", "07047251000170"],
        )
        == "ENEL · SP"
    )
    assert (
        rotulo_grafico(
            "06981180000116", "Cemig-D", ["06981180000116", "61695227000193"]
        )
        == "CEMIG"
    )


@pytest.mark.parametrize(
    "ordem_esperada",
    [
        ["COPEL", "CEMIG", "NEOENERGIA", "EQUATORIAL"],
        ["CEMIG", "COPEL", "EQUATORIAL", "NEOENERGIA"],
    ],
)
def test_ordem_do_grafico_segue_posicao_financeira_dinamica(ordem_esperada):
    ranking = [
        {"cnpj": f"cnpj-{rotulo}", "posicao_ranking": posicao}
        for posicao, rotulo in reversed(list(enumerate(ordem_esperada, start=1)))
    ]
    rotulos = {f"cnpj-{rotulo}": rotulo for rotulo in ordem_esperada}

    assert ordem_por_ranking_financeiro(ranking, rotulos) == ordem_esperada


def test_ordem_visual_do_ranking_e_crescente_por_posicao_em_todos_os_anos():
    ranking = [
        {"ano": ano, "cnpj": f"cnpj-{posicao}", "posicao_ranking": posicao}
        for ano in (2023, 2024, 2025)
        for posicao in range(10, 0, -1)
    ]
    rotulos = {
        f"cnpj-{posicao}": f"DISTRIBUIDORA {posicao}" for posicao in range(1, 11)
    }

    for ano in (2023, 2024, 2025):
        ranking_ano = [linha for linha in ranking if linha["ano"] == ano]
        ordem = ordem_por_ranking_financeiro(ranking_ano, rotulos)
        assert ordem == [f"DISTRIBUIDORA {posicao}" for posicao in range(1, 11)]


def test_reconciliacao_dos_tipos_por_distribuidora():
    ranking = [
        {
            "ano": 2025,
            "cnpj": "a",
            "realizado": Decimal("60.00"),
            "status_realizado": "valid",
        }
    ]
    financeiro = [
        {
            "ano": 2025,
            "cnpj": "a",
            "realizado": Decimal("60.00"),
            "status_realizado": "valid",
        }
    ]
    tipos = [
        {
            "ano": 2025,
            "cnpj": "a",
            "tipo": tipo,
            "realizado": Decimal("20.00"),
            "status_realizado": "valid",
        }
        for tipo in TIPOS_INVESTIMENTO_EXIBIDOS
    ]

    assert validar_reconciliacao_tipos(ranking, tipos, financeiro, 2025) == []
    financeiro[0]["realizado"] = Decimal("61.00")
    divergencias_fontes = validar_reconciliacao_tipos(ranking, tipos, financeiro, 2025)
    assert "MART 06 difere do MART 04" in divergencias_fontes[0]["motivo"]
    financeiro[0]["realizado"] = Decimal("60.00")
    tipos[0]["realizado"] = Decimal("19.00")
    divergencias = validar_reconciliacao_tipos(ranking, tipos, financeiro, 2025)
    assert divergencias == [
        {
            "cnpj": "a",
            "soma_tipos": Decimal("59.00"),
            "total_realizado": Decimal("60.00"),
            "diferenca": Decimal("1.00"),
            "motivo": "soma do MART 08 difere do MART 06; soma do MART 08 difere do MART 04",
        }
    ]
    assert (
        validar_reconciliacao_tipos(ranking, tipos[:2], financeiro, 2025)[0]["motivo"]
        == "categorias ausentes ou valores indisponiveis"
    )


def test_home_atualiza_ano_e_mantem_os_graficos_principais(
    banco_dashboard, monkeypatch
):
    from dashboard import data

    monkeypatch.setattr(data, "DB_PATH", banco_dashboard)
    data.carregar_dados_visao_geral.clear()
    caminho_app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(caminho_app, default_timeout=15).run()

    assert not app.exception
    assert len(app.metric) == 4
    assert_cabecalho_compartilhado(app)
    assert not any(
        "PAINEL DE DISTRIBUIÇÃO ELÉTRICA" in item.value for item in app.title
    )
    assert not any("GridInvest Analytics" in item.value for item in app.header)
    assert any(
        "Ranking de Investimentos por Distribuidora" in item.value
        for item in app.subheader
    )
    codigo_app = caminho_app.read_text(encoding="utf-8")
    assert codigo_app.count("st.altair_chart(") == 1
    assert "Ranking de investimentos realizados" not in codigo_app
    assert "Evolução dos investimentos" not in codigo_app
    assert "sort=ordem_distribuidoras" in codigo_app
    assert codigo_app.count("sort=ordem_distribuidoras") == 2
    assert "scale=alt.Scale(reverse=True)" not in codigo_app
    assert "strokeWidth=" not in codigo_app
    assert "Contorno dourado" not in codigo_app
    assert "Tabela ordenável pelas colunas numéricas" not in codigo_app
    assert "A coorte permanece fixa:" not in codigo_app
    assert "não uma medida isolada de eficiência operacional" not in codigo_app
    assert len(app.dataframe) == 0
    assert len(app.table) == 1
    assert len(app.table[0].value) == 10
    assert list(app.table[0].value.columns) == [
        "Posição",
        "Distribuidora",
        "Investimento realizado (R$ bi)",
        "Execução financeira (%)",
        "Realizado por UC (R$/UC)",
    ]
    assert list(app.table[0].value["Posição"]) == list(range(1, 11))
    assert all(
        "data:image/svg+xml;base64," in valor
        for valor in app.table[0].value["Distribuidora"]
    )
    assert len(app.expander) == 0
    assert app.selectbox(key="ano_referencia").value == 2025
    assert len(app.selectbox) == 2
    assert len(app.checkbox) == 0

    app.selectbox(key="ordenacao_resumo_distribuidoras").select(
        "Investimento realizado"
    ).run()
    assert not app.exception
    assert len(app.table[0].value) == 10

    app.selectbox(key="ano_referencia").select(2024).run()
    assert not app.exception
    assert app.metric[0].label == "Planejado · 2024"
    assert any(
        "Ranking de Investimentos por Distribuidora" in item.value
        for item in app.subheader
    )


def test_navegacao_comparativo_top10_renderiza_dez_cards(banco_dashboard, monkeypatch):
    from dashboard import data

    monkeypatch.setattr(data, "DB_PATH", banco_dashboard)
    data.carregar_dados_visao_geral.clear()
    caminho_app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(caminho_app, default_timeout=15).run()

    app.radio[0].set_value("Comparativo Top 10").run()

    assert not app.exception
    assert_cabecalho_compartilhado(app)
    assert len(app.expander) == 10
    assert len(app.metric) == 20
    assert any("Comparativo Top 10" in item.value for item in app.subheader)
    assert any("Ranking de investimento por UC" in item.value for item in app.subheader)
    assert app.selectbox(key="ano_referencia").value == 2025
    assert len(app.selectbox) == 1
    assert len(app.expander) == 10
    textos_info = " ".join(item.value for item in app.info)
    assert textos_info == ""
    textos_caption = " ".join(item.value for item in app.caption)
    assert "Ano de referência 2025" not in textos_caption
    assert "R$/UC representa a intensidade média" not in textos_caption


def test_ranking_investimento_uc_usa_mart03_e_ordenacao_decrescente(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    for linha in dados["investimento_por_uc"]:
        if linha["ano"] == 2025 and linha["cnpj"] == "cnpj-1":
            linha["valor"] = Decimal("1.00")
        elif linha["ano"] == 2025 and linha["cnpj"] == "cnpj-2":
            linha["valor"] = Decimal("9.00")
    ranking = preparar_ranking_investimento_uc(dados, 2025)

    assert len(ranking) == 10
    assert {linha["cnpj"] for linha in ranking} == {
        linha["cnpj"] for linha in dados["coorte"]
    }
    assert [linha["valor"] for linha in ranking] == [
        Decimal("9.00"),
        Decimal("1.00"),
        *([Decimal("0.03")] * 8),
    ]
    assert ranking[0]["cnpj"] == "cnpj-2"
    assert ranking[1]["cnpj"] == "cnpj-1"
    assert ranking[-1]["cnpj"] == "cnpj-9"
    copel = next(linha for linha in ranking if linha["cnpj"] == "cnpj-1")
    assert copel["total_realizado"] == Decimal("30.00")
    assert copel["qtd_uc"] == 1000
    assert copel["posicao_investimento"] == 1
    assert copel["posicao_coorte"] == 1


def test_pagina_investimento_uc_prepara_dez_cnpjs_e_kpis_coerentes(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    linhas = preparar_dados_pagina(dados, 2025)
    kpis = calcular_kpis_coorte(linhas)

    assert len(linhas) == 10
    assert len({linha["cnpj"] for linha in linhas}) == 10
    assert [linha["valor"] for linha in linhas] == [Decimal("0.03")] * 10
    assert [linha["posicao_uc"] for linha in linhas] == list(range(1, 11))
    assert kpis["qtd_uc"] == 10_000
    assert kpis["indicador_coorte"] == Decimal("0.03")
    assert kpis["indicadores_disponiveis"] == 10


def test_kpi_agregado_usa_razao_das_somas_e_bloqueia_cobertura_incompleta(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    linhas = preparar_dados_pagina(dados, 2025)
    for indice, linha in enumerate(linhas):
        total = Decimal("1000.00") if indice == 0 else Decimal("100.00")
        unidades = 100 if indice == 0 else 900
        linha["total_realizado"] = total
        linha["total_reconciliado"] = True
        linha["uc_reconciliada"] = True
        linha["status_realizado_por_uc"] = "valid"
        linha["status_uc"] = "valid"
        linha["qtd_uc"] = unidades

    kpis = calcular_kpis_coorte(linhas)
    assert kpis["qtd_uc"] == 8_200
    assert kpis["indicador_coorte"] == Decimal("0.23")
    assert kpis["indicador_coorte"] != Decimal("1.10")

    linhas[0]["status_uc"] = "partial"
    kpis_incompletos = calcular_kpis_coorte(linhas)
    assert kpis_incompletos["qtd_uc"] is None
    assert kpis_incompletos["indicador_coorte"] is None


def test_pagina_investimento_uc_rejeita_duplicidade_municipal_ja_agregada(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    linha_uc = next(
        linha for linha in dados["unidades_consumidoras"] if linha["ano"] == 2025
    )
    dados["unidades_consumidoras"].append(linha_uc.copy())

    with pytest.raises(ValueError, match="MART 07 contém CNPJs duplicados"):
        preparar_dados_pagina(dados, 2025)


def test_pagina_investimento_uc_trata_zero_e_valores_indisponiveis(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    for linha in dados["unidades_consumidoras"]:
        if linha["ano"] == 2025 and linha["cnpj"] == "cnpj-1":
            linha["qtd_uc_dezembro"] = 0
            linha["status"] = "zero"
    for linha in dados["investimento_por_uc"]:
        if linha["ano"] == 2025 and linha["cnpj"] == "cnpj-1":
            linha["valor"] = None
            linha["status"] = "denominador_zero"
            linha["qtd_uc_dezembro"] = 0
            linha["status_cobertura"] = "zero"
        elif linha["ano"] == 2025 and linha["cnpj"] == "cnpj-2":
            linha["valor"] = None
            linha["status"] = "invalid"

    linhas = preparar_dados_pagina(dados, 2025)
    primeiro = next(linha for linha in linhas if linha["cnpj"] == "cnpj-1")
    segundo = next(linha for linha in linhas if linha["cnpj"] == "cnpj-2")
    kpis = calcular_kpis_coorte(linhas)

    assert primeiro["qtd_uc"] == 0
    assert not primeiro["disponível"]
    assert primeiro["posicao_uc"] is None
    assert not segundo["disponível"]
    assert kpis["qtd_uc"] == 9_000


def test_ranking_investimento_uc_preserva_zero_e_indisponibilidade(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    for linha in dados["investimento_por_uc"]:
        if linha["ano"] == 2025 and linha["cnpj"] == "cnpj-1":
            linha["valor"] = Decimal("0.00")
            linha["status"] = "valid"
        elif linha["ano"] == 2025 and linha["cnpj"] == "cnpj-2":
            linha["valor"] = None
            linha["status"] = "invalid"

    ranking = preparar_ranking_investimento_uc(dados, 2025)

    assert len(ranking) == 10
    assert ranking[-2]["cnpj"] == "cnpj-1"
    assert ranking[-2]["valor_exibido"] == "R$ 0,00"
    assert ranking[-1]["cnpj"] == "cnpj-2"
    assert ranking[-1]["valor"] is None
    assert ranking[-1]["valor_exibido"] == "Não disponível"


def test_card_recolhivel_permanece_reutilizavel():
    script = """
import streamlit as st
from decimal import Decimal
from dashboard.components import renderizar_card_distribuidora

distribuidora = {
    'cnpj': '06981180000116', 'nome': 'Cemig-D', 'posicao_ranking': 1,
    'posicao_coorte': 1, 'realizado': Decimal('100.00'),
    'status_realizado': 'valid'
}
dados = {
    'detalhes_financeiros': [{'cnpj': distribuidora['cnpj'], 'ano': 2025,
        'planejado': Decimal('120.00'), 'status_planejado': 'valid',
        'realizado': Decimal('100.00'), 'status_realizado': 'valid',
        'taxa_execucao': Decimal('83.33'), 'status_taxa_execucao': 'valid'}],
    'unidades_consumidoras': [{'cnpj': distribuidora['cnpj'], 'ano': 2025,
        'qtd_uc_dezembro': 1000, 'status': 'valid'}],
    'investimento_por_uc': [{'cnpj': distribuidora['cnpj'], 'ano': 2025,
        'valor': Decimal('0.10'), 'status': 'valid'}],
    'tipos': []
}
with st.container():
    renderizar_card_distribuidora(distribuidora, dados, 2025)
"""
    app = AppTest.from_string(script, default_timeout=10).run()

    assert not app.exception
    assert len(app.expander) == 1


def test_navegacao_investimento_por_uc_renderiza_dez_distribuidoras(
    banco_dashboard, monkeypatch
):
    from dashboard import data

    monkeypatch.setattr(data, "DB_PATH", banco_dashboard)
    data.carregar_dados_visao_geral.clear()
    caminho_app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(caminho_app, default_timeout=15).run()

    app.radio[0].set_value("Investimento por UC").run()

    assert not app.exception
    assert_cabecalho_compartilhado(app)
    assert any(
        "Investimento por Unidade Consumidora" in item.value for item in app.subheader
    )
    assert len(app.metric) == 4
    assert len(app.table) == 1
    assert len(app.table[0].value) == 10
    assert list(app.table[0].value["Posição R$/UC"]) == [
        f"#{posicao}" for posicao in range(1, 11)
    ]
    assert any("Ranking de Investimento por UC" in item.value for item in app.subheader)
    assert any(
        "Investimento total versus R$/UC" in item.value for item in app.subheader
    )
    assert app.selectbox(key="ano_referencia").value == 2025

    app.selectbox(key="ano_referencia").select(2024).run()
    assert not app.exception
    assert app.selectbox(key="ano_referencia").value == 2024
    assert len(app.table[0].value) == 10


def test_planejado_realizado_prepara_coorte_e_reconcilia_mart01_mart04(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)

    resultado = preparar_planejado_realizado(dados, 2025)

    assert len(resultado["linhas"]) == 10
    assert {linha["cnpj"] for linha in resultado["linhas"]} == {
        linha["cnpj"] for linha in dados["coorte"]
    }
    assert resultado["kpis"] == {
        "planejado": Decimal("100.00"),
        "realizado": Decimal("75.00"),
        "execucao": Decimal("75.00"),
        "diferenca": Decimal("-25.00"),
    }
    assert all(resultado["reconciliacoes"].values())
    assert resultado["linhas"][0]["realizado_valido"] == Decimal("7.50")
    assert resultado["linhas"][0]["diferenca_valida"] == Decimal("-2.50")


def test_planejado_realizado_preserva_execucao_acima_de_cem_e_diferencas_com_sinal(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    item = next(
        linha
        for linha in dados["detalhes_financeiros"]
        if linha["ano"] == 2025 and linha["cnpj"] == "cnpj-1"
    )
    item.update(
        planejado=Decimal("1000.00"),
        realizado=Decimal("1597.40"),
        taxa_execucao=Decimal("159.74"),
        diferenca_absoluta=Decimal("597.40"),
        diferenca_percentual=Decimal("59.74"),
    )
    agregado = next(linha for linha in dados["historico"] if linha["ano"] == 2025)
    agregado.update(planejado=Decimal("1090.00"), realizado=Decimal("1664.90"))

    resultado = preparar_planejado_realizado(dados, 2025)
    equatorial = next(
        linha for linha in resultado["linhas"] if linha["cnpj"] == "cnpj-1"
    )

    assert resultado["reconciliacoes"] == {
        "planejado": True,
        "realizado": True,
        "diferenca": True,
    }
    assert equatorial["execucao_valida"] == Decimal("159.74")
    assert equatorial["diferenca_valida"] == Decimal("597.40")
    assert resultado["linhas"][-1]["diferenca_valida"] == Decimal("-2.50")
    assert _formatar_diferenca_bilhoes(Decimal("597400000.00")) == "+R$ 0,60 bi"
    assert _formatar_diferenca_bilhoes(Decimal("-597400000.00")) == "−R$ 0,60 bi"


def test_planejado_realizado_mantem_indisponibilidades_sem_converter_em_zero(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    item = next(
        linha
        for linha in dados["detalhes_financeiros"]
        if linha["ano"] == 2025 and linha["cnpj"] == "cnpj-1"
    )
    item["status_planejado"] = "invalid"
    item["planejado"] = None
    item["status_taxa_execucao"] = "planejado_invalid"
    item["taxa_execucao"] = None
    item["status_diferenca"] = "invalid"
    item["diferenca_absoluta"] = None
    item["status_diferenca_percentual"] = "invalid"
    item["diferenca_percentual"] = None

    resultado = preparar_planejado_realizado(dados, 2025)
    linha = next(x for x in resultado["linhas"] if x["cnpj"] == "cnpj-1")

    assert resultado["kpis"]["planejado"] is None
    assert resultado["kpis"]["execucao"] is None
    assert linha["planejado_valido"] is None
    assert linha["execucao_valida"] is None
    assert linha["diferenca_valida"] is None
    assert linha["diferenca_percentual_valida"] is None


def test_navegacao_planejado_realizado_renderiza_pagina_e_filtro(
    banco_dashboard, monkeypatch
):
    from dashboard import data

    monkeypatch.setattr(data, "DB_PATH", banco_dashboard)
    data.carregar_dados_visao_geral.clear()
    caminho_app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(caminho_app, default_timeout=15).run()

    app.radio[0].set_value("Planejado x Realizado").run()

    assert not app.exception
    assert_cabecalho_compartilhado(app)
    assert any("Planejado x Realizado" in item.value for item in app.subheader)
    assert len(app.metric) == 4
    assert len(app.dataframe) == 1
    assert len(app.dataframe[0].value) == 10
    assert len(app.selectbox) == 1
    assert app.selectbox(key="ano_referencia").value == 2025
    assert any("Resumo comparativo" in item.value for item in app.subheader)
    caminho_pagina = (
        Path(__file__).resolve().parents[1] / "dashboard" / "planejado_realizado.py"
    )
    codigo_pagina = caminho_pagina.read_text(encoding="utf-8")
    assert codigo_pagina.count("st.altair_chart(") == 1
    assert "mark_circle" not in codigo_pagina
    assert "mark_line" not in codigo_pagina

    app.selectbox(key="ano_referencia").select(2024).run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 10


def test_grafico_tem_duas_colunas_por_distribuidora_e_tooltip_completo(
    banco_dashboard,
):
    dados = ler_dados_visao_geral(banco_dashboard)
    linhas = preparar_planejado_realizado(dados, 2025)["linhas"]

    grafico = construir_grafico_colunas(linhas, 2025)
    especificacao = grafico.to_dict()

    assert especificacao["mark"]["type"] == "bar"
    assert especificacao["encoding"]["x"]["field"] == "Distribuidora"
    assert especificacao["encoding"]["x"]["sort"] == [
        linha["rotulo"] for linha in linhas
    ]
    assert all(
        rotulo == rotulo.upper() for rotulo in especificacao["encoding"]["x"]["sort"]
    )
    assert especificacao["encoding"]["x"]["axis"]["labelAlign"] == "center"
    assert especificacao["encoding"]["x"]["scale"]["paddingInner"] == 0.25
    assert especificacao["encoding"]["xOffset"]["field"] == "Métrica"
    assert especificacao["encoding"]["xOffset"]["scale"]["paddingInner"] == 0
    assert especificacao["encoding"]["xOffset"]["scale"]["paddingOuter"] == 0
    assert "size" not in especificacao["mark"]
    assert especificacao["encoding"]["y"]["title"] == "Investimento (R$ bilhões)"
    assert especificacao["encoding"]["color"]["scale"]["range"] == [
        "#38BDF8",
        "#A78BFA",
    ]
    assert "layer" not in especificacao
    assert "point" not in especificacao["mark"]
    campos_tooltip = {
        detalhe["field"] for detalhe in especificacao["encoding"]["tooltip"]
    }
    assert {
        "Planejado completo",
        "Realizado completo",
    } <= campos_tooltip

    dados_grafico = especificacao["datasets"][especificacao["data"]["name"]]
    assert len(dados_grafico) == 20
    assert {linha["Distribuidora"] for linha in dados_grafico} == {
        linha["rotulo"] for linha in linhas
    }
    for distribuidora in {linha["Distribuidora"] for linha in dados_grafico}:
        registros_empresa = [
            linha for linha in dados_grafico if linha["Distribuidora"] == distribuidora
        ]
        metricas = {linha["Métrica"] for linha in registros_empresa}
        assert metricas == {"Planejado", "Realizado"}
        registro_empresa = next(
            linha for linha in linhas if linha["rotulo"] == distribuidora
        )
        for coluna in registros_empresa:
            assert coluna["Planejado completo"] == formatar_reais(
                registro_empresa["planejado_valido"]
            )
            assert coluna["Realizado completo"] == formatar_reais(
                registro_empresa["realizado_valido"]
            )


def test_ranking_investimento_uc_usa_ordem_de_cima_para_baixo():
    caminho = Path(__file__).resolve().parents[1] / "dashboard" / "investimento_uc.py"
    codigo = caminho.read_text(encoding="utf-8")
    grafico = codigo.split("def _renderizar_ranking", maxsplit=1)[1].split(
        "def _renderizar_dispersao", maxsplit=1
    )[0]

    assert grafico.count("sort=ordem") == 2
    assert "reverse=True" not in grafico


def test_perfil_usa_mart08_reconcilia_e_preserva_coorte(banco_dashboard):
    dados = ler_dados_visao_geral(banco_dashboard)
    dados["historico"][2]["realizado"] = Decimal("800.00")

    resultado = preparar_perfil_investimentos(dados, 2025)
    rosca, barras = construir_graficos_perfil(resultado)

    assert len(resultado["detalhes"]) == 10
    assert len(resultado["ordenados"]) == 10
    assert resultado["total"] == Decimal("800.00")
    assert resultado["total_reconciliado"] is True
    assert resultado["categorias"]["Expansão"] == Decimal("100.00")
    assert resultado["categorias"]["Melhoria"] == Decimal("100.00")
    assert resultado["categorias"]["Renovação"] == Decimal("100.00")
    assert resultado["categorias"]["Outros tipos"] == Decimal("500.00")
    assert resultado["ordenados"][0]["cnpj"] == "cnpj-1"
    assert rosca is not None
    assert barras.to_dict()["encoding"]["y"]["sort"] == [
        item["rotulo"] for item in resultado["ordenados"]
    ]
    assert (
        "classe"
        not in barras.to_dict()["datasets"][barras.to_dict()["data"]["name"]][0]
    )


def test_perfil_mantem_indisponibilidade_e_zero_valido(banco_dashboard):
    dados = ler_dados_visao_geral(banco_dashboard)
    dados["historico"][1]["realizado"] = Decimal("290.00")
    dados["totais_perfil"] = [
        {**item, "realizado": Decimal("20.00")}
        if item["cnpj"] == "cnpj-1" and item["ano"] == 2024
        else item
        for item in dados["totais_perfil"]
    ]
    for item in dados["tipos_completos"]:
        if item["cnpj"] == "cnpj-1" and item["ano"] == 2024:
            item["realizado"] = (
                Decimal("0.00") if item["tipo"] == "Expansão" else item["realizado"]
            )

    resultado = preparar_perfil_investimentos(dados, 2024)
    detalhe = resultado["detalhes"]["cnpj-1"]
    assert detalhe["valores"]["Expansão"] == Decimal("0.00")
    assert detalhe["reconciliado"] is True

    dados["tipos_completos"] = [
        {
            **item,
            "status_realizado": "invalid",
            "realizado": None,
        }
        if item["cnpj"] == "cnpj-1"
        and item["ano"] == 2024
        and item["tipo"] == "Melhoria"
        else item
        for item in dados["tipos_completos"]
    ]
    indisponivel = preparar_perfil_investimentos(dados, 2024)
    assert indisponivel["detalhes"]["cnpj-1"]["valores"]["Melhoria"] is None
    assert indisponivel["categorias"]["Melhoria"] is None
    assert indisponivel["total"] is None


def test_pagina_perfil_renderiza_mart08_e_filtro_de_ano(banco_dashboard, monkeypatch):
    from dashboard import data

    con = duckdb.connect(str(banco_dashboard))
    con.execute(
        "UPDATE marts.investimentos_anuais SET total_realizado = 300.00 "
        "WHERE ano_referencia = 2024 AND escopo = 'top10'"
    )
    con.execute(
        "UPDATE marts.investimentos_anuais SET total_realizado = 800.00 "
        "WHERE ano_referencia = 2025 AND escopo = 'top10'"
    )
    con.close()
    monkeypatch.setattr(data, "DB_PATH", banco_dashboard)
    data.carregar_dados_visao_geral.clear()
    caminho_app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(caminho_app, default_timeout=15).run()

    app.radio[0].set_value("Perfil de Investimentos").run()

    assert not app.exception
    assert_cabecalho_compartilhado(app)
    assert any("Perfil de Investimentos" in item.value for item in app.subheader)
    assert len(app.metric) == 7
    assert app.selectbox(key="ano_referencia").value == 2025
    assert app.selectbox(key="perfil_distribuidora").value == "cnpj-1"

    app.selectbox(key="ano_referencia").select(2024).run()
    assert not app.exception
    assert app.selectbox(key="ano_referencia").value == 2024
    assert len(app.metric) == 7


def test_pagina_perfil_cabecalho_especifico():
    caminho_app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    app = AppTest.from_file(caminho_app, default_timeout=15).run()

    app.radio[0].set_value("Perfil de Investimentos").run()

    assert not app.exception
    assert_cabecalho_compartilhado(app)
    assert any("Perfil de Investimentos" in item.value for item in app.subheader)
    assert not any(
        "Explore como os investimentos" in item.value for item in app.caption
    )


def test_cabecalho_le_a_logo_atualizada_sem_cache(tmp_path, monkeypatch):
    from dashboard import header

    caminho_logo = tmp_path / "gridinvest_analytics.png"
    caminho_logo.write_bytes(b"versao antiga")
    chamadas = []
    monkeypatch.setattr(header, "LOGO_PATH", caminho_logo)
    monkeypatch.setattr(
        header.st,
        "image",
        lambda conteudo, **opcoes: chamadas.append((conteudo, opcoes)),
    )

    header.renderizar_cabecalho()
    caminho_logo.write_bytes(b"versao atualizada")
    header.renderizar_cabecalho()

    assert [conteudo for conteudo, _ in chamadas] == [
        b"versao antiga",
        b"versao atualizada",
    ]
    assert all(opcoes["width"] == "stretch" for _, opcoes in chamadas)
    assert all(
        opcoes["alt"].startswith("GridInvest Analytics") for _, opcoes in chamadas
    )
