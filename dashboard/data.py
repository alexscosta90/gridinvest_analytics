"""Leitura somente leitura dos indicadores usados na Visão Geral."""

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import duckdb
import streamlit as st

from dashboard.metadata import TIPOS_INVESTIMENTO_EXIBIDOS
from pipeline.db import DB_PATH

ANOS_ANALISE = (2023, 2024, 2025)
TABELAS_OBRIGATORIAS = (
    ("marts", "investimentos_anuais"),
    ("marts", "cohorte_top10_2025"),
    ("marts", "ranking_investimentos"),
    ("marts", "perfil_investimentos"),
    ("marts", "investimento_por_uc"),
    ("marts", "planejado_vs_realizado_distribuidora"),
    ("marts", "ranking_por_uc_top10"),
)


def ler_dados_visao_geral(
    caminho_banco: str | Path = DB_PATH,
) -> dict[str, Any]:
    """Busca MART 01 e a coorte fixa em uma única conexão somente leitura."""
    caminho = Path(caminho_banco)
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Banco DuckDB não encontrado em {caminho}. "
            "Execute as etapas de dados do projeto antes de abrir o dashboard."
        )

    con = duckdb.connect(str(caminho), read_only=True)
    try:
        tabelas_existentes = set(
            con.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema = 'marts'
                  AND table_name IN (?, ?, ?, ?, ?, ?, ?)
                """,
                [tabela for _, tabela in TABELAS_OBRIGATORIAS],
            ).fetchall()
        )
        faltantes = set(TABELAS_OBRIGATORIAS) - tabelas_existentes
        if faltantes:
            nomes = ", ".join(
                f"{schema}.{tabela}" for schema, tabela in sorted(faltantes)
            )
            raise RuntimeError(
                f"Tabelas necessárias ao dashboard indisponíveis: {nomes}. "
                "Execute as etapas correspondentes do pipeline antes de abrir a página."
            )

        linhas = con.execute(
            """
            SELECT
                ano_referencia,
                total_planejado,
                status_total_planejado,
                total_realizado,
                status_total_realizado,
                qtd_cnpjs
            FROM marts.investimentos_anuais
            WHERE escopo = 'top10'
              AND ano_referencia BETWEEN 2023 AND 2025
            ORDER BY ano_referencia
            """
        ).fetchall()
        quantidade_coorte = con.execute(
            "SELECT COUNT(DISTINCT cnpj) FROM marts.cohorte_top10_2025"
        ).fetchone()[0]
        distribuidoras = con.execute(
            """
            WITH rotulos AS (
                SELECT
                    cnpj,
                    MAX(NULLIF(TRIM(rotulo_pdd), '')) AS rotulo_pdd,
                    MAX(NULLIF(TRIM(rotulo_indger), '')) AS rotulo_indger
                FROM marts.ranking_investimentos
                WHERE ano_referencia = 2025 AND escopo = 'top10'
                GROUP BY cnpj
            )
            SELECT
                c.posicao,
                c.cnpj,
                c.uc_dez_2025,
                COALESCE(r.rotulo_pdd, r.rotulo_indger, c.cnpj) AS nome
            FROM marts.cohorte_top10_2025 AS c
            LEFT JOIN rotulos AS r USING (cnpj)
            ORDER BY c.posicao
            """
        ).fetchall()
        ranking = con.execute(
            """
            WITH valores AS (
                SELECT
                    ano_referencia,
                    cnpj,
                    MAX(NULLIF(TRIM(rotulo_pdd), '')) AS rotulo_pdd,
                    MAX(NULLIF(TRIM(rotulo_indger), '')) AS rotulo_indger,
                    MAX(valor_investimento) FILTER (
                        WHERE medida = 'planejado'
                    ) AS planejado,
                    MAX(status_valor) FILTER (
                        WHERE medida = 'planejado'
                    ) AS status_planejado
                FROM marts.ranking_investimentos
                WHERE escopo = 'top10'
                  AND ano_referencia BETWEEN 2023 AND 2025
                GROUP BY ano_referencia, cnpj
            )
            SELECT
                r.ano_referencia,
                r.cnpj,
                COALESCE(NULLIF(TRIM(r.rotulo_pdd), ''),
                         NULLIF(TRIM(r.rotulo_indger), ''), r.cnpj) AS nome,
                r.valor_investimento AS realizado,
                r.status_valor AS status_realizado,
                r.posicao AS posicao_ranking,
                v.planejado,
                v.status_planejado,
                c.posicao AS posicao_coorte
            FROM marts.ranking_investimentos AS r
            LEFT JOIN valores AS v USING (ano_referencia, cnpj)
            LEFT JOIN marts.cohorte_top10_2025 AS c USING (cnpj)
            WHERE r.escopo = 'top10'
              AND r.medida = 'realizado'
              AND r.ano_referencia BETWEEN 2023 AND 2025
            ORDER BY r.ano_referencia, r.posicao, r.cnpj
            """
        ).fetchall()
        tipos = con.execute(
            """
            SELECT
                ano_referencia,
                cnpj,
                MAX(NULLIF(TRIM(rotulo_pdd), '')) AS nome,
                tipo_obra,
                CASE
                    WHEN SUM(qtd_realizados_invalidos) > 0 THEN 'partial_invalid'
                    WHEN SUM(qtd_realizados_nulos) > 0 THEN 'partial_null'
                    WHEN SUM(qtd_realizados_validos) = 0 THEN 'unavailable'
                    ELSE 'valid'
                END AS status_realizado,
                CASE
                    WHEN SUM(qtd_realizados_validos) = 0 THEN NULL
                    ELSE SUM(total_realizado)
                END AS total_realizado,
                SUM(qtd_realizados_validos) AS qtd_validos,
                SUM(qtd_realizados_nulos) AS qtd_nulos,
                SUM(qtd_realizados_invalidos) AS qtd_invalidos
            FROM marts.perfil_investimentos
            WHERE escopo = 'top10'
              AND ano_referencia BETWEEN 2023 AND 2025
              AND tipo_obra IN (?, ?, ?)
            GROUP BY ano_referencia, cnpj, tipo_obra
            ORDER BY ano_referencia, cnpj, tipo_obra
            """,
            list(TIPOS_INVESTIMENTO_EXIBIDOS),
        ).fetchall()
        tipos_completos = con.execute(
            """
            SELECT
                ano_referencia,
                cnpj,
                MAX(NULLIF(TRIM(rotulo_pdd), '')) AS nome,
                COALESCE(NULLIF(TRIM(tipo_obra), ''), '(tipo vazio/nulo)') AS tipo,
                CASE
                    WHEN SUM(qtd_realizados_invalidos) > 0 THEN 'partial_invalid'
                    WHEN SUM(qtd_realizados_nulos) > 0 THEN 'partial_null'
                    WHEN SUM(qtd_realizados_validos) = 0 THEN 'unavailable'
                    ELSE 'valid'
                END AS status_realizado,
                CASE
                    WHEN SUM(qtd_realizados_validos) = 0 THEN NULL
                    ELSE SUM(total_realizado)
                END AS realizado,
                SUM(qtd_realizados_validos) AS qtd_validos,
                SUM(qtd_realizados_nulos) AS qtd_nulos,
                SUM(qtd_realizados_invalidos) AS qtd_invalidos
            FROM marts.perfil_investimentos
            WHERE escopo = 'top10'
              AND ano_referencia BETWEEN 2023 AND 2025
            GROUP BY ano_referencia, cnpj,
                     COALESCE(NULLIF(TRIM(tipo_obra), ''), '(tipo vazio/nulo)')
            ORDER BY ano_referencia, cnpj, tipo
            """
        ).fetchall()
        totais_perfil = con.execute(
            """
            SELECT
                ano_referencia,
                cnpj,
                CASE
                    WHEN SUM(qtd_realizados_invalidos) > 0 THEN 'partial_invalid'
                    WHEN SUM(qtd_realizados_nulos) > 0 THEN 'partial_null'
                    WHEN SUM(qtd_realizados_validos) = 0 THEN 'unavailable'
                    ELSE 'valid'
                END AS status_realizado,
                CASE
                    WHEN SUM(qtd_realizados_invalidos) > 0
                      OR SUM(qtd_realizados_nulos) > 0
                      OR SUM(qtd_realizados_validos) = 0 THEN NULL
                    ELSE SUM(total_realizado)
                END AS realizado
            FROM marts.perfil_investimentos
            WHERE escopo = 'top10'
              AND ano_referencia BETWEEN 2023 AND 2025
            GROUP BY ano_referencia, cnpj
            ORDER BY ano_referencia, cnpj
            """
        ).fetchall()
        categorias_adicionais = con.execute(
            """
            SELECT DISTINCT
                COALESCE(NULLIF(TRIM(tipo_obra), ''), '(tipo vazio/nulo)')
            FROM marts.perfil_investimentos
            WHERE escopo = 'top10'
              AND ano_referencia BETWEEN 2023 AND 2025
              AND COALESCE(NULLIF(TRIM(tipo_obra), ''), '(tipo vazio/nulo)')
                  NOT IN (?, ?, ?)
            ORDER BY 1
            """,
            list(TIPOS_INVESTIMENTO_EXIBIDOS),
        ).fetchall()
        detalhes_financeiros = con.execute(
            """
            SELECT
                cnpj,
                ano_referencia,
                total_planejado,
                status_total_planejado,
                total_realizado,
                status_total_realizado,
                percentual_execucao,
                status_percentual_execucao,
                diferenca_absoluta,
                status_diferenca,
                diferenca_percentual,
                status_diferenca_percentual
            FROM marts.planejado_vs_realizado_distribuidora
            WHERE top10_2025 = TRUE
              AND ano_referencia BETWEEN 2023 AND 2025
            ORDER BY ano_referencia, cnpj
            """
        ).fetchall()
        unidades_consumidoras = con.execute(
            """
            SELECT
                cnpj,
                ano_referencia,
                qtd_uc_dezembro,
                status_cobertura
            FROM marts.ranking_por_uc_top10
            WHERE ano_referencia BETWEEN 2023 AND 2025
            ORDER BY ano_referencia, cnpj
            """
        ).fetchall()
        valores_por_uc = con.execute(
            """
            SELECT
                cnpj,
                ano_referencia,
                investimento_realizado_por_uc,
                status_realizado_por_uc,
                total_realizado,
                status_total_realizado,
                qtd_uc_dezembro,
                status_cobertura
            FROM marts.investimento_por_uc
            WHERE escopo = 'top10'
              AND ano_referencia BETWEEN 2023 AND 2025
            ORDER BY ano_referencia, cnpj
            """
        ).fetchall()
    finally:
        con.close()

    anos_encontrados = {linha[0] for linha in linhas}
    if anos_encontrados != set(ANOS_ANALISE) or len(linhas) != len(ANOS_ANALISE):
        raise RuntimeError(
            "O MART 01 precisa conter exatamente uma linha do escopo top10 "
            "para cada ano de 2023 a 2025."
        )
    if quantidade_coorte != 10:
        raise RuntimeError(
            "A coorte fixa de dezembro de 2025 deve conter dez CNPJs distintos; "
            f"encontrados={quantidade_coorte}."
        )
    if len(distribuidoras) != 10:
        raise RuntimeError(
            "A lista da coorte fixa deve conter dez distribuidoras; "
            f"encontradas={len(distribuidoras)}."
        )
    ranking_por_ano: dict[int, list[tuple[Any, ...]]] = {}
    for linha in ranking:
        ranking_por_ano.setdefault(linha[0], []).append(linha)
    membros_coorte = {linha[1] for linha in distribuidoras}
    if set(ranking_por_ano) != set(ANOS_ANALISE) or any(
        len(linhas_ano) != 10
        or len({linha[1] for linha in linhas_ano}) != 10
        or {linha[1] for linha in linhas_ano} != membros_coorte
        or any(linha[5] is None for linha in linhas_ano)
        or sorted(linha[5] for linha in linhas_ano) != list(range(1, 11))
        for linhas_ano in ranking_por_ano.values()
    ):
        raise RuntimeError(
            "O MART 06 precisa conter dez CNPJs distintos no escopo top10 "
            "e posições de 1 a 10 em cada ano de 2023 a 2025."
        )

    historico = [
        {
            "ano": ano,
            "planejado": planejado,
            "status_planejado": status_planejado,
            "realizado": realizado,
            "status_realizado": status_realizado,
            "qtd_cnpjs": qtd_cnpjs,
        }
        for (
            ano,
            planejado,
            status_planejado,
            realizado,
            status_realizado,
            qtd_cnpjs,
        ) in linhas
    ]
    coorte = [
        {"posicao": posicao, "cnpj": cnpj, "ucs": ucs, "nome": nome}
        for posicao, cnpj, ucs, nome in distribuidoras
    ]
    linhas_ranking = [
        {
            "ano": ano,
            "cnpj": cnpj,
            "nome": nome,
            "realizado": realizado,
            "status_realizado": status_realizado,
            "posicao_ranking": posicao_ranking,
            "planejado": planejado,
            "status_planejado": status_planejado,
            "posicao_coorte": posicao_coorte,
        }
        for (
            ano,
            cnpj,
            nome,
            realizado,
            status_realizado,
            posicao_ranking,
            planejado,
            status_planejado,
            posicao_coorte,
        ) in ranking
    ]
    linhas_tipos = [
        {
            "ano": ano,
            "cnpj": cnpj,
            "nome": nome,
            "tipo": tipo,
            "status_realizado": status,
            "realizado": total,
            "qtd_validos": qtd_validos,
            "qtd_nulos": qtd_nulos,
            "qtd_invalidos": qtd_invalidos,
        }
        for (
            ano,
            cnpj,
            nome,
            tipo,
            status,
            total,
            qtd_validos,
            qtd_nulos,
            qtd_invalidos,
        ) in tipos
    ]
    linhas_tipos_completos = [
        {
            "ano": ano,
            "cnpj": cnpj,
            "nome": nome,
            "tipo": tipo,
            "status_realizado": status,
            "realizado": total,
            "qtd_validos": qtd_validos,
            "qtd_nulos": qtd_nulos,
            "qtd_invalidos": qtd_invalidos,
        }
        for (
            ano,
            cnpj,
            nome,
            tipo,
            status,
            total,
            qtd_validos,
            qtd_nulos,
            qtd_invalidos,
        ) in tipos_completos
    ]
    totais_perfil_linhas = [
        {"ano": ano, "cnpj": cnpj, "status": status, "realizado": total}
        for ano, cnpj, status, total in totais_perfil
    ]
    financeiros = [
        {
            "cnpj": cnpj,
            "ano": ano,
            "planejado": planejado,
            "status_planejado": status_planejado,
            "realizado": realizado,
            "status_realizado": status_realizado,
            "taxa_execucao": taxa,
            "status_taxa_execucao": status_taxa,
            "diferenca_absoluta": diferenca_absoluta,
            "status_diferenca": status_diferenca,
            "diferenca_percentual": diferenca_percentual,
            "status_diferenca_percentual": status_diferenca_percentual,
        }
        for (
            cnpj,
            ano,
            planejado,
            status_planejado,
            realizado,
            status_realizado,
            taxa,
            status_taxa,
            diferenca_absoluta,
            status_diferenca,
            diferenca_percentual,
            status_diferenca_percentual,
        ) in detalhes_financeiros
    ]
    unidades = [
        {
            "cnpj": cnpj,
            "ano": ano,
            "qtd_uc_dezembro": quantidade,
            "status": status,
        }
        for cnpj, ano, quantidade, status in unidades_consumidoras
    ]
    valores_uc = [
        {
            "cnpj": cnpj,
            "ano": ano,
            "valor": valor,
            "status": status,
            "total_realizado": total_realizado,
            "status_total_realizado": status_total_realizado,
            "qtd_uc_dezembro": qtd_uc_dezembro,
            "status_cobertura": status_cobertura,
        }
        for (
            cnpj,
            ano,
            valor,
            status,
            total_realizado,
            status_total_realizado,
            qtd_uc_dezembro,
            status_cobertura,
        ) in valores_por_uc
    ]
    return {
        "historico": historico,
        "quantidade_coorte": quantidade_coorte,
        "coorte": coorte,
        "ranking": linhas_ranking,
        "tipos": linhas_tipos,
        "tipos_completos": linhas_tipos_completos,
        "totais_perfil": totais_perfil_linhas,
        "categorias_adicionais": [linha[0] for linha in categorias_adicionais],
        "detalhes_financeiros": financeiros,
        "unidades_consumidoras": unidades,
        "investimento_por_uc": valores_uc,
    }


@st.cache_data(ttl=300, max_entries=4, show_spinner=False)
def carregar_dados_visao_geral() -> dict[str, Any]:
    """Mantém os indicadores em cache por cinco minutos durante interações."""
    return ler_dados_visao_geral(DB_PATH)


def calcular_taxa_execucao(
    planejado: Decimal | None,
    realizado: Decimal | None,
    status_planejado: str,
    status_realizado: str,
) -> Decimal | None:
    """Calcula realizado/planejado em percentual; indisponível sem base válida."""
    if (
        planejado is None
        or realizado is None
        or planejado == 0
        or status_planejado != "valid"
        or status_realizado != "valid"
    ):
        return None
    return (realizado * Decimal(100) / planejado).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def formatar_reais(valor: Decimal | None) -> str:
    """Formata um valor Decimal no padrão monetário brasileiro."""
    if valor is None:
        return "Não disponível"
    formatado = f"{valor:,.2f}"
    formatado = formatado.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {formatado}"


def formatar_valor_validado(valor: Decimal | None, status: str | None) -> str:
    """Formata apenas valores válidos e distingue indisponibilidade de zero."""
    if valor is None or status != "valid":
        return "Não disponível"
    return formatar_reais(valor)
