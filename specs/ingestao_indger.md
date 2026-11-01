
# Especificação — Ingestão INDGER

## Objetivo

Carregar os Dados Comerciais do INDGER, publicados pela
ANEEL, na camada RAW do DuckDB.

## Fonte

- Arquivo: raw/indger-dados-comerciais.csv
- Origem: Portal de Dados Abertos da ANEEL
- Formato: CSV
- Separador: ponto e vírgula (;)
- Codificação de leitura: UTF-8-SIG
- Registros observados: 274.114
- Colunas observadas: 63

## Destino

- Banco: gridinvest.duckdb
- Schema: raw
- Tabela: indger_comerciais

## Regras

1. Preservar todas as linhas do arquivo original.
2. Preservar os nomes originais das 63 colunas.
3. Carregar inicialmente todos os campos como VARCHAR.
4. Preservar CNPJs e códigos IBGE como texto.
5. Não converter números, datas ou valores monetários.
6. Preservar campos vazios como texto vazio.
7. Não eliminar registros duplicados.
8. Não aplicar filtros por empresa, município ou período.
9. Permitir reexecutar sem duplicar registros.
10. Carregar em lotes para controlar o uso de memória.
11. Validar o número de campos de cada registro.
12. Interromper a operação caso sejam encontrados registros inválidos.

## Validações

- Conferir 274.114 registros.
- Conferir 63 colunas.
- Conferir todos os tipos como VARCHAR.
- Comparar contagens entre CSV e DuckDB.
- Verificar CNPJs com zeros iniciais.
- Verificar campos vazios.
- Executar a ingestão duas vezes e confirmar a mesma contagem.
- Em caso de erro, não deixar uma tabela parcialmente carregada.

## Fora do escopo

- Transformações e limpeza dos dados.
- Conversão de QtdUCAtiva para número.
- Agregações por distribuidora.
- Seleção de dezembro de cada ano.
- Identificação e tratamento de duplicidades.
- JOIN com o PDD.
- Cálculo de investimento por UC.

## Decisões técnicas

O arquivo INDGER utiliza ponto e vírgula, diferentemente
do PDD, que utiliza vírgula.

A ingestão deve ser executada em transação e preservar
os dados já existentes caso uma nova carga falhe.

As regras de agregação e relacionamento serão definidas
na camada REFINED.
