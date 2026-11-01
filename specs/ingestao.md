
# Especificação — Ingestão PDD

## Objetivo
Carregar os dados públicos do PDD da ANEEL para a camada RAW do DuckDB, preservando os dados originais.

## Origem
- Arquivo: raw/pdd-distribuicao-aneel.csv
- Fonte: Portal de Dados Abertos da ANEEL
- Formato: CSV
- Separador: vírgula (,)
- Codificação de leitura: UTF-8-SIG
- Quantidade inicial observada: 5.484 registros
- Quantidade de colunas: 12

## Destino
- Banco: gridinvest.duckdb
- Schema: raw
- Tabela: pdd

## Colunas esperadas
1. _id
2. DatGeracaoConjuntoDados
3. SigAgente
4. NumCPFCNPJ
5. DscTipoOutorga
6. SigUF
7. DscRegiao
8. AnoReferencia
9. DscTipoObra
10. DscTipoObraClasse
11. VlrTotalRealizado
12. VlrTotalPlanejado

## Regras
1. Não modificar nomes ou valores das colunas.
2. Não eliminar registros ou duplicidades.
3. Carregar inicialmente todas as colunas como VARCHAR.
4. Preservar CNPJ como texto.
5. Não converter valores monetários nesta etapa.
6. Preservar valores vazios e distinguir sua representação original.
7. Reexecutar a ingestão sem duplicar registros.
8. Informar erros caso o arquivo esteja ausente ou inválido.

## Validações
- Comparar o número de linhas do CSV com a tabela RAW.
- Conferir a existência das 12 colunas.
- Verificar os tipos VARCHAR.
- Conferir registros de exemplo.
- Executar a ingestão duas vezes e comparar a contagem.
- Verificar se a leitura preservou os campos vazios.

## Fora do escopo
- Conversão de valores monetários.
- Padronização de distribuidoras.
- Filtros por ano.
- JOIN com INDGER.
- Cálculo de indicadores.
