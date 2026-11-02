"""Gera um DuckDB mínimo para as consultas do dashboard.

O banco de origem é anexado em modo somente leitura. O artefato resultante
contém apenas tabelas físicas no schema ``marts`` e apenas os anos/escopos
consultados pelas cinco páginas do dashboard.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SOURCE = PROJECT_ROOT / "gridinvest.duckdb"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "deploy" / "gridinvest_dashboard.duckdb"
ANOS = "ano_referencia BETWEEN 2023 AND 2025"
ODBL_URI = "https://opendatacommons.org/licenses/odbl/1-0/"
TABLE_COMMENT = (
    "Contains data derived from ANEEL PDD and INDGER - Dados Comerciais. "
    "Source datasets are identified as ODbL 1.0. License: "
    + ODBL_URI
)


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[str, ...]
    source_query: str


TABLES = (
    TableSpec(
        name="investimentos_anuais",
        columns=(
            "ano_referencia",
            "escopo",
            "total_planejado",
            "status_total_planejado",
            "total_realizado",
            "status_total_realizado",
            "qtd_cnpjs",
        ),
        source_query=f"""
            SELECT ano_referencia, escopo, total_planejado,
                   status_total_planejado, total_realizado,
                   status_total_realizado, qtd_cnpjs
            FROM source_db.marts.investimentos_anuais
            WHERE escopo = 'top10' AND {ANOS}
        """,
    ),
    TableSpec(
        name="cohorte_top10_2025",
        columns=("posicao", "cnpj", "uc_dez_2025"),
        source_query="""
            SELECT posicao, cnpj, uc_dez_2025
            FROM source_db.marts.cohorte_top10_2025
        """,
    ),
    TableSpec(
        name="ranking_investimentos",
        columns=(
            "ano_referencia",
            "cnpj",
            "escopo",
            "medida",
            "valor_investimento",
            "status_valor",
            "rotulo_pdd",
            "rotulo_indger",
            "posicao",
        ),
        source_query=f"""
            SELECT ano_referencia, cnpj, escopo, medida,
                   valor_investimento, status_valor, rotulo_pdd,
                   rotulo_indger, posicao
            FROM source_db.marts.ranking_investimentos
            WHERE escopo = 'top10'
              AND medida IN ('planejado', 'realizado')
              AND {ANOS}
        """,
    ),
    TableSpec(
        name="perfil_investimentos",
        columns=(
            "escopo",
            "cnpj",
            "rotulo_pdd",
            "ano_referencia",
            "tipo_obra",
            "total_realizado",
            "qtd_realizados_validos",
            "qtd_realizados_nulos",
            "qtd_realizados_invalidos",
        ),
        source_query=f"""
            SELECT escopo, cnpj, rotulo_pdd, ano_referencia, tipo_obra,
                   SUM(total_realizado) AS total_realizado,
                   SUM(qtd_realizados_validos) AS qtd_realizados_validos,
                   SUM(qtd_realizados_nulos) AS qtd_realizados_nulos,
                   SUM(qtd_realizados_invalidos) AS qtd_realizados_invalidos
            FROM source_db.marts.perfil_investimentos
            WHERE escopo = 'top10' AND {ANOS}
            GROUP BY escopo, cnpj, rotulo_pdd, ano_referencia, tipo_obra
        """,
    ),
    TableSpec(
        name="planejado_vs_realizado_distribuidora",
        columns=(
            "cnpj",
            "ano_referencia",
            "total_planejado",
            "status_total_planejado",
            "total_realizado",
            "status_total_realizado",
            "percentual_execucao",
            "status_percentual_execucao",
            "diferenca_absoluta",
            "status_diferenca",
            "diferenca_percentual",
            "status_diferenca_percentual",
            "top10_2025",
        ),
        source_query=f"""
            SELECT cnpj, ano_referencia, total_planejado,
                   status_total_planejado, total_realizado,
                   status_total_realizado, percentual_execucao,
                   status_percentual_execucao, diferenca_absoluta,
                   status_diferenca, diferenca_percentual,
                   status_diferenca_percentual, top10_2025
            FROM source_db.marts.planejado_vs_realizado_distribuidora
            WHERE top10_2025 = TRUE AND {ANOS}
        """,
    ),
    TableSpec(
        name="ranking_por_uc_top10",
        columns=("ano_referencia", "cnpj", "qtd_uc_dezembro", "status_cobertura"),
        source_query=f"""
            SELECT ano_referencia, cnpj, qtd_uc_dezembro, status_cobertura
            FROM source_db.marts.ranking_por_uc_top10
            WHERE {ANOS}
        """,
    ),
    TableSpec(
        name="investimento_por_uc",
        columns=(
            "ano_referencia",
            "escopo",
            "cnpj",
            "investimento_realizado_por_uc",
            "status_realizado_por_uc",
            "total_realizado",
            "status_total_realizado",
            "qtd_uc_dezembro",
            "status_cobertura",
        ),
        source_query=f"""
            SELECT ano_referencia, escopo, cnpj,
                   investimento_realizado_por_uc, status_realizado_por_uc,
                   total_realizado, status_total_realizado,
                   qtd_uc_dezembro, status_cobertura
            FROM source_db.marts.investimento_por_uc
            WHERE escopo = 'top10' AND {ANOS}
        """,
    ),
)


def _quoted_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _validate_source_schema(source: Path) -> None:
    with duckdb.connect(str(source), read_only=True) as connection:
        if not duckdb.__version__.startswith("2."):
            raise RuntimeError(
                f"DuckDB 2.x é necessário para gerar o artefato; "
                f"versão ativa: {duckdb.__version__}."
            )

        existing_tables = {
            table
            for schema, table, table_type in connection.execute(
                """
                SELECT table_schema, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'marts'
                """
            ).fetchall()
            if table_type == "BASE TABLE"
        }
        expected_tables = {spec.name for spec in TABLES}
        missing_tables = expected_tables - existing_tables
        if missing_tables:
            raise RuntimeError(
                "Tabelas MARTS obrigatórias ausentes no banco de origem: "
                + ", ".join(sorted(missing_tables))
            )

        for spec in TABLES:
            existing_columns = {
                column
                for (column,) in connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'marts' AND table_name = ?
                    """,
                    [spec.name],
                ).fetchall()
            }
            missing_columns = set(spec.columns) - existing_columns
            if missing_columns:
                raise RuntimeError(
                    f"Colunas esperadas ausentes em marts.{spec.name}: "
                    + ", ".join(sorted(missing_columns))
                )


def _attribution_text() -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""# Atribuição e licença dos dados

Gerado em: {generated}

Este banco derivado contém agregações das seguintes bases públicas da ANEEL:

- [PDD — Plano de Desenvolvimento da Distribuição](https://dadosabertos.aneel.gov.br/dataset/pdd)
- [INDGER — Dados Comerciais](https://dadosabertos.aneel.gov.br/dataset/indger-indicadores-gerenciais-da-distribuicao/resource/fd10c9d4-cb76-4020-a322-e79afb13eaf7)

As páginas das fontes indicam a [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Este banco derivado é disponibilizado sob os termos da ODbL 1.0, incluindo
atribuição e compartilhamento pela mesma licença quando aplicáveis. Consulte o
texto da licença para as condições completas. A atribuição não implica endosso
pela ANEEL.

As sete tabelas do banco também contêm um comentário de metadados com as fontes
e a URI da licença. O artefato contém somente tabelas MARTS, colunas e recortes
usados pelo dashboard; não inclui as camadas RAW ou REFINED.
"""


def build_database(source: Path, output: Path) -> tuple[dict[str, int], Path]:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    notice = output.with_suffix(".ATTRIBUTION.md")

    if not source.is_file():
        raise FileNotFoundError(f"Banco de origem não encontrado: {source}")
    if source == output:
        raise ValueError("O banco de publicação não pode ser o banco de origem.")
    if output.exists() or notice.exists():
        raise FileExistsError(
            f"O artefato ou seu aviso já existe: {output} / {notice}. "
            "Escolha outro caminho para não sobrescrever arquivos."
        )

    _validate_source_schema(source)
    output.parent.mkdir(parents=True, exist_ok=True)

    temp_output = output.with_name(f".{output.stem}.{uuid4().hex}.tmp.duckdb")
    table_counts: dict[str, int] = {}
    connection = duckdb.connect(str(temp_output))
    try:
        source_literal = _quoted_path(source)
        connection.execute(
            f"ATTACH '{source_literal}' AS source_db (READ_ONLY)"
        )
        connection.execute("CREATE SCHEMA marts")

        for spec in TABLES:
            connection.execute(
                f"CREATE TABLE marts.{spec.name} AS {spec.source_query}"
            )
            table_comment = TABLE_COMMENT.replace("'", "''")
            connection.execute(
                f"COMMENT ON TABLE marts.{spec.name} IS '{table_comment}'"
            )
            ordering = ", ".join(spec.columns)
            source_rows = connection.execute(
                f"{spec.source_query} ORDER BY {ordering}"
            ).fetchall()
            published_rows = connection.execute(
                f"SELECT {ordering} FROM marts.{spec.name} ORDER BY {ordering}"
            ).fetchall()
            if source_rows != published_rows:
                raise RuntimeError(
                    f"Conteúdo divergente durante a cópia de marts.{spec.name}."
                )
            table_counts[spec.name] = len(published_rows)

        connection.execute("DETACH source_db")
    except Exception:
        connection.close()
        temp_output.unlink(missing_ok=True)
        temp_output.with_suffix(temp_output.suffix + ".wal").unlink(missing_ok=True)
        raise
    else:
        connection.close()

    temp_output.rename(output)
    notice.write_text(_attribution_text(), encoding="utf-8")

    with duckdb.connect(str(output), read_only=True) as connection:
        tables = connection.execute(
            """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
            """
        ).fetchall()
        expected = {("marts", spec.name, "BASE TABLE") for spec in TABLES}
        if set(tables) != expected:
            raise RuntimeError(
                f"O banco de publicação contém tabelas inesperadas: {tables}"
            )

        comments = connection.execute(
            """
            SELECT table_name, comment
            FROM duckdb_tables()
            WHERE schema_name = 'marts'
            """
        ).fetchall()
        if len(comments) != len(TABLES) or any(
            not comment or ODBL_URI not in comment for _, comment in comments
        ):
            raise RuntimeError(
                "Faltam comentários internos com fontes e licença ODbL nas tabelas."
            )

        forbidden_schemas = connection.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE lower(schema_name) IN ('raw', 'refined')
            """
        ).fetchall()
        if forbidden_schemas:
            raise RuntimeError(
                f"O banco de publicação contém schemas proibidos: {forbidden_schemas}"
            )

    # Executa as mesmas consultas do dashboard nos dois bancos e exige igualdade.
    from dashboard.data import ler_dados_visao_geral

    source_data = ler_dados_visao_geral(source)
    published_data = ler_dados_visao_geral(output)
    if source_data != published_data:
        raise RuntimeError(
            "Os dados retornados ao dashboard diferem entre origem e publicação."
        )

    return table_counts, notice


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera um DuckDB reduzido para o dashboard GridInvest."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    counts, notice = build_database(arguments.source, arguments.output)
    output = arguments.output.expanduser().resolve()
    from dashboard.data import ler_dados_visao_geral

    dashboard_data = ler_dados_visao_geral(output)

    print(f"Banco de publicação: {output}")
    print(f"Tamanho: {output.stat().st_size:,} bytes")
    print("Tabelas e registros:")
    for table, count in counts.items():
        print(f"  marts.{table}: {count:,}")
    print("Comparação das consultas do dashboard: idêntica à origem.")
    print("Totais anuais (coorte top10):")
    for row in dashboard_data["historico"]:
        print(
            f"  {row['ano']}: planejado={row['planejado']} "
            f"({row['status_planejado']}), realizado={row['realizado']} "
            f"({row['status_realizado']})"
        )

    rankings = {}
    for row in dashboard_data["ranking"]:
        rankings[row["ano"]] = rankings.get(row["ano"], 0) + 1
    print("Linhas no ranking financeiro realizado:")
    for year in sorted(rankings):
        print(f"  {year}: {rankings[year]}")

    values_per_uc = dashboard_data["investimento_por_uc"]
    available = sum(
        row["valor"] is not None and row["status"] in {"valid", "zero"}
        for row in values_per_uc
    )
    print(
        f"Investimento por UC: {len(values_per_uc)} linhas; "
        f"{available} valores disponíveis."
    )
    print(f"Atribuição/licença: {notice}")
    print("RAW/REFINED: não incluídos.")


if __name__ == "__main__":
    main()
