"""Resolução segura do banco usado pelo dashboard.

Por padrão usa o DuckDB local. Em deploy, GRIDINVEST_DB_URL ativa o download
HTTPS e GRIDINVEST_DB_SHA256 valida o artefato antes de disponibilizá-lo.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from pipeline.db import DB_PATH

ENV_DB_URL = "GRIDINVEST_DB_URL"
ENV_DB_SHA256 = "GRIDINVEST_DB_SHA256"
ENV_DB_PATH = "GRIDINVEST_DB_PATH"
DOWNLOAD_TIMEOUT_SECONDS = 60
CHUNK_SIZE = 1024 * 1024


class DatabaseDownloadError(RuntimeError):
    """Falha ao obter ou validar o banco remoto de publicação."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as database_file:
        for chunk in iter(lambda: database_file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_database(url: str, expected_sha256: str) -> Path:
    if not url.lower().startswith("https://"):
        raise DatabaseDownloadError(
            f"{ENV_DB_URL} deve conter uma URL HTTPS para o banco de publicação."
        )
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in expected_sha256
    ):
        raise DatabaseDownloadError(
            f"{ENV_DB_SHA256} deve conter um SHA-256 hexadecimal de 64 caracteres."
        )

    cache_dir = Path(tempfile.gettempdir()) / "gridinvest-analytics" / "database"
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / "gridinvest_dashboard.duckdb"
    partial = cache_dir / "gridinvest_dashboard.duckdb.part"
    expected = expected_sha256.lower()

    if destination.is_file() and _sha256(destination) == expected:
        return destination

    destination.unlink(missing_ok=True)
    partial.unlink(missing_ok=True)
    request = Request(url, headers={"User-Agent": "GridInvest-Analytics/1.0"})
    try:
        with (
            urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response,
            partial.open("wb") as output,
        ):
            while chunk := response.read(CHUNK_SIZE):
                output.write(chunk)
        actual = _sha256(partial)
        if actual != expected:
            raise DatabaseDownloadError(
                "O SHA-256 do banco baixado não corresponde ao valor configurado "
                f"em {ENV_DB_SHA256}. Verifique a URL e o artefato publicado."
            )
        partial.replace(destination)
    except DatabaseDownloadError:
        partial.unlink(missing_ok=True)
        raise
    except (OSError, URLError, TimeoutError) as error:
        partial.unlink(missing_ok=True)
        raise DatabaseDownloadError(
            "Não foi possível baixar o banco de publicação por HTTPS. "
            "Confira a URL, a conexão e a disponibilidade do arquivo."
        ) from error
    return destination


def resolver_caminho_banco(
    *,
    url: str | None = None,
    expected_sha256: str | None = None,
    caminho_local: str | Path = DB_PATH,
) -> Path:
    """Seleciona o banco local ou baixa e valida o banco remoto configurado."""
    configured_url = os.environ.get(ENV_DB_URL) if url is None else url
    if not configured_url:
        override = os.environ.get(ENV_DB_PATH)
        local = Path(override) if override else Path(caminho_local)
        if not local.is_file():
            raise FileNotFoundError(
                f"Banco DuckDB local não encontrado em {local}. "
                "Execute as etapas de dados do projeto, configure "
                f"{ENV_DB_PATH} para selecionar outro arquivo local ou "
                f"{ENV_DB_URL} para usar um banco remoto."
            )
        return local

    configured_hash = (
        os.environ.get(ENV_DB_SHA256) if expected_sha256 is None else expected_sha256
    )
    if not configured_hash:
        raise DatabaseDownloadError(
            f"{ENV_DB_SHA256} é obrigatório quando {ENV_DB_URL} está configurada."
        )
    return _download_database(configured_url, configured_hash)
