import hashlib

import pytest

from dashboard import database


class RespostaFalsa:
    def __init__(self, conteudo: bytes):
        self.conteudo = conteudo
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, tamanho: int) -> bytes:
        trecho = self.conteudo[self.offset : self.offset + tamanho]
        self.offset += len(trecho)
        return trecho


def test_seleciona_banco_local_sem_fazer_download(tmp_path, monkeypatch):
    local = tmp_path / "gridinvest.duckdb"
    local.write_bytes(b"banco local")
    monkeypatch.delenv(database.ENV_DB_URL, raising=False)
    monkeypatch.setattr(
        database,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("download inesperado no modo local"),
    )

    assert database.resolver_caminho_banco(caminho_local=local) == local


def test_seleciona_artefato_local_por_variavel_sem_download(tmp_path, monkeypatch):
    artefato = tmp_path / "gridinvest_dashboard.duckdb"
    artefato.write_bytes(b"artefato local")
    monkeypatch.setenv(database.ENV_DB_PATH, str(artefato))
    monkeypatch.delenv(database.ENV_DB_URL, raising=False)
    monkeypatch.setattr(
        database,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("download inesperado no modo local"),
    )

    assert database.resolver_caminho_banco() == artefato


def test_seleciona_banco_remoto_e_armazena_fora_do_repositorio(
    tmp_path, monkeypatch
):
    conteudo = b"banco de publicacao aprovado"
    digest = hashlib.sha256(conteudo).hexdigest()
    cache_root = tmp_path / "temp"
    monkeypatch.setattr(database.tempfile, "gettempdir", lambda: str(cache_root))
    monkeypatch.setattr(
        database, "urlopen", lambda *_args, **_kwargs: RespostaFalsa(conteudo)
    )

    resultado = database.resolver_caminho_banco(
        url="https://dadosabertos.aneel.gov.br/",
        expected_sha256=digest,
        caminho_local=tmp_path / "gridinvest.duckdb",
    )

    assert resultado.read_bytes() == conteudo
    assert resultado == cache_root / "gridinvest-analytics" / "database" / resultado.name
    assert not resultado.is_relative_to(tmp_path / "repositorio")


def test_valida_sha256_e_rejeita_artefato_diferente(tmp_path, monkeypatch):
    monkeypatch.setattr(database.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        database, "urlopen", lambda *_args, **_kwargs: RespostaFalsa(b"conteudo")
    )

    with pytest.raises(database.DatabaseDownloadError, match="SHA-256"):
        database.resolver_caminho_banco(
            url="https://dadosabertos.aneel.gov.br/",
            expected_sha256="0" * 64,
        )
    assert not list(tmp_path.rglob("*.part"))
    assert not list(tmp_path.rglob("*.duckdb"))


def test_rejeita_url_que_nao_seja_https():
    with pytest.raises(database.DatabaseDownloadError, match="HTTPS"):
        database.resolver_caminho_banco(
            url="http://dadosabertos.aneel.gov.br/",
            expected_sha256="0" * 64,
        )


def test_falha_de_download_apresenta_mensagem_clara(tmp_path, monkeypatch):
    monkeypatch.setattr(database.tempfile, "gettempdir", lambda: str(tmp_path))

    def falhar(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(database, "urlopen", falhar)
    with pytest.raises(database.DatabaseDownloadError, match="Não foi possível baixar"):
        database.resolver_caminho_banco(
            url="https://dadosabertos.aneel.gov.br/",
            expected_sha256="0" * 64,
        )


def test_banco_ausente_no_modo_local_informa_como_configurar(tmp_path):
    with pytest.raises(FileNotFoundError, match=database.ENV_DB_URL):
        database.resolver_caminho_banco(caminho_local=tmp_path / "ausente.duckdb")


def test_modo_remoto_exige_sha256():
    with pytest.raises(database.DatabaseDownloadError, match=database.ENV_DB_SHA256):
        database.resolver_caminho_banco(
            url="https://dadosabertos.aneel.gov.br/", expected_sha256=""
        )


def test_cache_remoto_revalida_hash_e_reutiliza_arquivo(tmp_path, monkeypatch):
    conteudo = b"banco aprovado"
    digest = hashlib.sha256(conteudo).hexdigest()
    monkeypatch.setattr(database.tempfile, "gettempdir", lambda: str(tmp_path))
    chamadas = 0

    def baixar(*_args, **_kwargs):
        nonlocal chamadas
        chamadas += 1
        return RespostaFalsa(conteudo)

    monkeypatch.setattr(database, "urlopen", baixar)
    kwargs = {
        "url": "https://dadosabertos.aneel.gov.br/",
        "expected_sha256": digest,
    }
    primeiro = database.resolver_caminho_banco(**kwargs)
    segundo = database.resolver_caminho_banco(**kwargs)
    assert primeiro == segundo
    assert chamadas == 1
