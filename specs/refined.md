# Especificação — Camada REFINED

## Objetivo

Criar as tabelas tipadas `refined.pdd` e `refined.indger_comerciais` a partir das tabelas RAW da ANEEL.

A REFINED mantém todas as distribuidoras e todas as linhas de origem. Não aplica o filtro das 10 maiores distribuidoras, não realiza agregações anuais e não calcula indicadores de investimento por UC.

## Princípios

1. As tabelas RAW são a cópia de referência e não devem ser alteradas ou substituídas por esta etapa.
2. Não excluir linhas automaticamente, inclusive registros duplicados ou registros com valores inválidos.
3. Preservar CNPJs como texto, inclusive zeros à esquerda.
4. Preservar a granularidade original e documentar as chaves como identificadores de negócio, não como garantia de unicidade.
5. Converter apenas campos com tipo e regra de conversão definidos nesta especificação.
6. Manter os valores originais rastreáveis quando houver conversão ou validação que possa falhar.
7. Sinalizar valores inválidos; nunca convertê-los silenciosamente para zero.

## Fontes e destinos

| Origem | Destino | Linhas observadas |
|---|---|---:|
| `raw.pdd` | `refined.pdd` | 5.484 |
| `raw.indger_comerciais` | `refined.indger_comerciais` | 274.114 |

As quantidades acima correspondem à carga observada e devem ser comparadas com a origem em cada execução.

## `refined.pdd`

### Granularidade e chave

Uma linha por registro publicado no PDD.

- Chave de negócio: `_id`.
- Na carga inspecionada, `_id` não é nulo e é único nas 5.484 linhas.
- Validar essa condição em cada carga. Se a fonte futura violar a unicidade, reportar a falha sem excluir linhas automaticamente.

### Tipos e conversões

- `_id`: texto.
- `NumCPFCNPJ`: texto, preservando zeros à esquerda.
- `DatGeracaoConjuntoDados`: timestamp.
- `AnoReferencia`: tipo inteiro apropriado para ano, como `SMALLINT`.
- `VlrTotalRealizado` e `VlrTotalPlanejado`: `DECIMAL(18,2)`.
  - Interpretar a vírgula como separador decimal brasileiro.
  - Valores vazios ou nulos devem resultar em nulo.
  - Valores não conversíveis devem ser sinalizados e permanecer rastreáveis; não convertê-los para zero.
- Demais campos: manter como texto até haver necessidade e regra explícita para convertê-los.

Manter os valores originais dos campos monetários em colunas de auditoria com sufixo `_raw`, ou assegurar sua rastreabilidade por meio da chave `_id` na RAW.

### Tipos de obra e classes

Valores observados em `DscTipoObra`:

- Expansão: 2.567 registros, somadas suas classes.
- Melhoria: 1.547 registros, somadas suas classes.
- Renovação: 1.369 registros, somadas suas classes.
- Obra com Participação Financeira: 1 registro.

Valores observados em `DscTipoObraClasse`:

- vazio;
- Luz Para Todos;
- Obra com Participação Financeira;
- Planejamento Setorial.

Preservar os dois campos sem recodificação nesta etapa. Tipo e classe não são dimensões mutuamente exclusivas: “Obra com Participação Financeira” aparece tanto como tipo quanto como classe. Não somar os dois campos como categorias independentes. Definir regras de agregação nos MARTS após validação semântica, evitando dupla contagem.

## `refined.indger_comerciais`

### Granularidade e chave

Uma linha por registro de distribuidora, município e mês de referência.

- Chave de negócio: `NumCNPJ + CodMunicipioIBGE + DatReferenciaInformada`.
- Essa combinação não garante unicidade. Na carga inspecionada, há 36 linhas excedentes em junho de 2026, distribuídas em 36 chaves repetidas.
- Na carga inspecionada, as duas linhas de cada chave repetida são idênticas em todas as colunas.
- Preservar as linhas repetidas na REFINED. Não aplicar `DISTINCT`, deduplicação ou seleção arbitrária de uma linha.
- Sinalizar ou disponibilizar diagnóstico para chaves repetidas, sem remover linhas.

### Tipos e conversões

- `NumCNPJ`: texto, preservando zeros à esquerda.
- `CodMunicipioIBGE`: texto. Preservar o valor `"0"` encontrado na origem e sinalizá-lo para análise; não completar zeros nem tratá-lo automaticamente como código municipal válido.
- `DatReferenciaInformada`: data.
- `DatGeracaoConjuntoDados`: data.
- `DthCarga`: timestamp.
- `QtdUCAtiva`: inteiro de 64 bits, nulo quando a origem for vazia ou nula.
  - Preservar o texto de origem em coluna de auditoria, como `QtdUCAtiva_raw`, ou manter vínculo rastreável com a RAW.
  - Identificar valores não vazios que não possam ser convertidos como inválidos. Não os converter para zero nem descartar suas linhas.
  - Na carga inspecionada, todos os 274.114 valores são inteiros válidos.
- Manter as demais colunas como texto até que outra conversão seja definida e justificada.

## Distribuidoras e referências ausentes

Não filtrar distribuidoras por posição, quantidade de UCs ou período.

A distribuidora CNPJ `87462750000163` está presente em meses de 2025, mas não possui registros na referência de dezembro de 2025. Ela deve permanecer na REFINED. Para indicadores que usam as UCs de dezembro, sua referência deve ser tratada como indisponível, nunca preenchida com zero.

## Referência anual e relação com os MARTS

Dezembro será a referência de unidades consumidoras para o indicador anual de investimento por UC.

A escolha da referência de dezembro e as agregações anuais pertencem aos MARTS. A REFINED mantém os registros mensais originais, sem somar meses ou calcular investimento por UC.

Se uma distribuidora não tiver registro em dezembro de determinado ano, o valor de UCs usado como denominador deverá ficar nulo/indisponível, com essa situação identificável. Processos posteriores não devem tratar ausência de registro como zero UCs nem dividir por zero.

## Testes de qualidade

### Gerais

- Comparar as contagens de origem e destino, sem perda ou acréscimo de linhas.
- Confirmar a existência das duas tabelas no schema `refined`.
- Confirmar os tipos de dados especificados.
- Confirmar que não foi aplicado filtro de distribuidoras ou top 10.
- Confirmar que os identificadores e valores de origem permanecem rastreáveis.

### PDD

- Validar a quantidade de linhas contra `raw.pdd`.
- Validar `_id` não nulo e único; falhas devem ser reportadas sem exclusão automática.
- Validar as conversões de `AnoReferencia` e `DatGeracaoConjuntoDados`.
- Validar a conversão dos campos monetários para `DECIMAL(18,2)`, incluindo decimal com vírgula.
- Validar que valores monetários inválidos sejam sinalizados e não convertidos para zero.
- Confirmar a preservação dos valores de `DscTipoObra` e `DscTipoObraClasse`.

### INDGER

- Validar a quantidade de linhas contra `raw.indger_comerciais`.
- Validar CNPJs como texto com 14 dígitos na carga inspecionada e preservar zeros à esquerda.
- Validar referências como datas e detectar valores não conversíveis.
- Validar `QtdUCAtiva` como inteiro ou nulo; contabilizar e identificar separadamente valores inválidos.
- Validar que `CodMunicipioIBGE` permaneça como texto e que valores `"0"` sejam sinalizados, sem correção automática.
- Validar duplicidades pela chave de negócio sem exigir unicidade.
- Para a carga inspecionada, confirmar 36 chaves repetidas em junho de 2026, duas linhas idênticas por chave e nenhuma remoção dessas linhas.
- Confirmar que eventuais novas duplicidades sejam reportadas, sem deduplicação automática.

## Fora do escopo

- Selecionar as 10 maiores distribuidoras.
- Agregar valores anuais ou mensais.
- Calcular investimento por UC.
- Somar tipo de obra e classe como categorias independentes.
- Excluir ou corrigir automaticamente registros inválidos, duplicados ou sem referência de dezembro.
- Alterar ou sobrescrever as tabelas RAW.

