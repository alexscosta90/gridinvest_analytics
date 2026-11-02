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
from dashboard.logos import ARQUIVOS_LOGO_POR_CNPJ, resolver_logo
from dashboard.metadata import (
    METADADOS_POR_CNPJ,
    NOMES_MARCA_POR_CNPJ,
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
                VALUES (?, 'top10', ?, 42, 'valid', 2.50, 'valid')
                """,
                [ano, f"cnpj-{posicao}"],
            )
            con.execute(
                """
                INSERT INTO marts.planejado_vs_realizado_distribuidora
                VALUES (?, ?, 120.00, 'valid', 30.00, 'valid', 25.00, 'valid', TRUE)
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
        VALUES (2025, 'nacional', 'cnpj-1', 99999, 'valid', 999.00, 'valid')
        """
    )
    con.execute(
        """
        INSERT INTO marts.planejado_vs_realizado_distribuidora
        VALUES ('cnpj-1', 2025, 999.00, 'valid', 999.00, 'valid', 100.00, 'valid', FALSE)
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
    assert financeiro["planejado"] == Decimal("120.00")
    assert financeiro["realizado"] == Decimal("30.00")
    assert financeiro["taxa_execucao"] == Decimal("25.00")
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
    assert valor_uc["valor"] == Decimal("2.50")


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
        base64.b64decode(imagem_distribuidora(cnpj, "ENEL", uf).split(",", 1)[1])
        .decode("utf-8")
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
    assert len(app.expander) == 10
    assert len(app.metric) == 20
    assert any("Comparativo Top 10" in item.value for item in app.title)
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
        *([Decimal("2.50")] * 8),
        Decimal("1.00"),
    ]
    assert ranking[0]["cnpj"] == "cnpj-2"
    assert ranking[1]["cnpj"] == "cnpj-10"
    assert ranking[-1]["cnpj"] == "cnpj-1"
    copel = next(linha for linha in ranking if linha["cnpj"] == "cnpj-1")
    assert copel["total_realizado"] == Decimal("30.00")
    assert copel["qtd_uc"] == 1000
    assert copel["posicao_investimento"] == 1
    assert copel["posicao_coorte"] == 1


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
