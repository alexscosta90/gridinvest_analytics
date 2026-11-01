
from pathlib import Path

import duckdb

# Diretório principal do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Caminho do banco de dados local
DB_PATH = BASE_DIR / "gridinvest.duckdb"


def conectar():
    """Abre uma conexão com o banco DuckDB."""
    return duckdb.connect(str(DB_PATH))
