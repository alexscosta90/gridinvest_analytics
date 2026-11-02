# GridInvest Analytics

Dashboard para análise de investimentos das distribuidoras de energia elétrica, com dados públicos da ANEEL. O processamento organiza os dados em RAW, REFINED e MARTS; o dashboard consulta os indicadores MARTS.

## Executar localmente

Instale as dependências com `uv sync` e inicie o dashboard:

```powershell
uv run python -m streamlit run dashboard/app.py
```

Sem configuração adicional, o dashboard abre `gridinvest.duckdb` na raiz do projeto. Para preparar o banco independente com apenas os dados necessários às cinco páginas, execute:

```powershell
uv run python scripts/build_dashboard_db.py
```

O banco será salvo em `artifacts/deploy/gridinvest_dashboard.duckdb`. O diretório `artifacts/` é ignorado pelo Git; o banco original não é alterado.

## Configuração do banco

| Variável | Uso |
|---|---|
| `GRIDINVEST_DB_URL` | URL HTTPS do banco de publicação. Quando definida, seleciona o modo remoto e ativa o download para o diretório temporário do sistema, fora do repositório. |
| `GRIDINVEST_DB_SHA256` | SHA-256 hexadecimal esperado, obrigatório junto com `GRIDINVEST_DB_URL`. O arquivo só é disponibilizado se o hash corresponder. |
| `GRIDINVEST_DB_PATH` | Caminho opcional para selecionar outro arquivo DuckDB local. Útil para validar o artefato de publicação antes de hospedá-lo. Não inicia download. |

Se `GRIDINVEST_DB_URL` não estiver definida, o modo local permanece ativo e usa `GRIDINVEST_DB_PATH` quando fornecido; caso contrário, usa `gridinvest.duckdb`. O acesso do dashboard ao DuckDB é somente leitura. Falhas de rede, URL que não seja HTTPS e hash divergente interrompem a carga com uma mensagem explicativa.

### Testar localmente o banco de publicação

Depois de gerar o artefato, selecione-o diretamente por caminho local e inicie o dashboard:

```powershell
$env:GRIDINVEST_DB_PATH = (Resolve-Path .\artifacts\deploy\gridinvest_dashboard.duckdb).Path
uv run python -m streamlit run dashboard/app.py
```

Para voltar ao banco de desenvolvimento, remova a variável e reinicie o comando:

```powershell
Remove-Item Env:GRIDINVEST_DB_PATH
```

## Publicação no Streamlit Community Cloud

1. Gere e valide o banco com `uv run python scripts/build_dashboard_db.py`.
2. Calcule o hash do arquivo aprovado com `Get-FileHash .\artifacts\deploy\gridinvest_dashboard.duckdb -Algorithm SHA256`.
3. Hospede o banco e o aviso de atribuição em um armazenamento HTTPS que permita ao app baixar o arquivo. O banco local de desenvolvimento não deve ser publicado nem adicionado ao Git; o artefato reduzido também permanece fora do repositório.
4. Nas configurações de Secrets do app no Community Cloud, informe as chaves `GRIDINVEST_DB_URL` e `GRIDINVEST_DB_SHA256` com a URL real do artefato hospedado e o hash calculado. Esses nomes de nível raiz ficam disponíveis como variáveis de ambiente no Streamlit.
5. Configure `dashboard/app.py` como arquivo principal e selecione Python 3.12 nas opções avançadas. O projeto requer Python `>=3.12`; o Community Cloud reconhece `uv.lock` e usa esse arquivo para instalar as dependências. No primeiro carregamento, o app baixa o banco, verifica o SHA-256 e consulta o arquivo temporário em modo somente leitura.

Ainda não há URL de publicação configurada neste repositório. Preencha `GRIDINVEST_DB_URL` somente depois de hospedar o artefato aprovado; não coloque credenciais ou URLs privadas no código ou em arquivos versionados.

O banco de publicação contém somente sete tabelas do schema MARTS necessárias ao dashboard; não inclui RAW ou REFINED. Consulte `artifacts/deploy/gridinvest_dashboard.ATTRIBUTION.md` junto ao artefato para as fontes e atribuição dos dados ANEEL.

## Verificações

```powershell
uv run python -m pytest
uv run ruff check .
```
