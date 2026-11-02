# Especificação — Camada MARTS

## Objetivo

Definir tabelas analíticas para o dashboard do GridInvest Analytics, usando as camadas REFINED do PDD e do INDGER.

O período principal de análise é 2023–2025. A camada MARTS preserva indicadores nacionais e produz sinalização para o grupo fixo das 10 maiores distribuidoras por unidades consumidoras ativas em dezembro de 2025. Não incluir DEC/FEC.

Esta especificação define o grão, as regras de agregação e as validações dos oito artefatos SQL planejados. Não define implementação SQL.

## Fontes e resultados observados

- PDD: 5.484 linhas, anos de referência 2016 a 2030.
- INDGER: 274.114 linhas e 103 CNPJs distintos.
- PDD: 118 CNPJs distintos; 102 coincidem com o INDGER. Há 16 CNPJs somente no PDD e 1 somente no INDGER.
- As datas de dezembro têm 6.240 linhas e 102 distribuidoras em 2023; 6.230 linhas e 102 distribuidoras em 2024; 6.238 linhas e 101 distribuidoras em 2025.
- Não há chaves repetidas por CNPJ, município e referência nos três dezembros analisados. A ausência de dezembro de 2025 da distribuidora CNPJ 87462750000163 deve ser tratada como indisponibilidade, não como zero UCs.
- Todos os 10 CNPJs da coorte têm registro de dezembro nos três anos 2023–2025 e têm correspondência exata no PDD.

### Totais do PDD observados

Valores em reais, agregados por ano e sem JOIN com o INDGER:

| Ano | Linhas | Planejado | Realizado |
|---:|---:|---:|---:|
| 2023 | 381 | R$ 31.522.797.164,57 | R$ 29.000.026.462,95 |
| 2024 | 392 | R$ 36.414.248.927,33 | R$ 33.181.721.110,92 |
| 2025 | 402 | R$ 46.834.210.890,88 | R$ 40.939.987.914,59 |

O PDD também contém anos de referência 2026–2030 com valores planejados e realizado registrado como zero. Esses zeros não representam uma execução anual completa e não devem ser apresentados como resultado realizado anual.

### Coorte fixa do top 10

Ordenar pelo total de QtdUCAtiva em dezembro de 2025, em ordem decrescente, usando CNPJ crescente como desempate determinístico. A coorte observada é:

| Ordem | CNPJ | Rótulo de referência no INDGER | UCs em dez/2025 |
|---:|---|---|---:|
| 1 | 06981180000116 | CEMIG DISTRIBUIÇÃO S.A. | 10.767.051 |
| 2 | 61695227000193 | ELETROPAULO METROPOLITANA ELETRICIDADE DE SÃO PAULO S.A. | 8.680.088 |
| 3 | 15139629000194 | COMPANHIA DE ELETRICIDADE DO ESTADO DA BAHIA | 6.989.298 |
| 4 | 04368898000106 | COPEL DISTRIBUIÇÃO S.A. | 5.409.324 |
| 5 | 33050196000188 | COMPANHIA PAULISTA DE FORÇA E LUZ | 5.145.530 |
| 6 | 60444437000146 | LIGHT SERVIÇOS DE ELETRICIDADE S.A. | 4.686.312 |
| 7 | 07047251000170 | COMPANHIA ENERGÉTICA DO CEARÁ | 4.338.308 |
| 8 | 10835932000108 | COMPANHIA ENERGÉTICA DE PERNAMBUCO | 4.229.463 |
| 9 | 08336783000190 | CELESC DISTRIBUIÇÃO S.A. | 3.589.043 |
| 10 | 01543032000104 | EQUATORIAL GOIÁS DISTRIBUIDORA DE ENERGIA S.A. | 3.583.696 |

Essa coorte fica fixa para comparações históricas do dashboard, mesmo quando a ordem anual ou os valores de UC mudarem. Uma alteração da coorte exige revisão explícita desta especificação.

## Regras comuns

### Preservação e escopos

1. As tabelas base dos MARTS devem conter todas as distribuidoras disponíveis na origem correspondente.
2. O filtro do top 10 é aplicado somente nos indicadores destinados ao dashboard, depois das agregações definidas nesta especificação.
3. Todo indicador deve identificar se representa o universo nacional da fonte ou a coorte fixa top 10.
4. Totais nacionais do PDD incluem todos os CNPJs do PDD. Para indicadores R$/UC, numerador e denominador devem representar o mesmo conjunto de CNPJs com dados correspondentes; expor a cobertura e não rotular uma população parcial como total nacional.
5. Não somar ou comparar como se fossem populações idênticas os CNPJs presentes em somente uma das fontes.

### Identificação de distribuidoras

CNPJ é a chave de relacionamento entre PDD e INDGER, mantido como texto e comparado sem conversão para número. Não relacionar registros pelo nome.

O PDD usa SigAgente, normalmente abreviado, enquanto o INDGER usa NomAgente. Preservar ambos como rótulos de origem. O CNPJ 01543032000104 aparece como Equatorial Goiás no INDGER e como Enel GO no PDD a partir de 2018; no PDD aparece como Celg-D em 2016–2017. Exibir o rótulo INDGER para a coorte atual e manter os nomes PDD como alias de origem. Não inferir equivalência de CNPJs ausentes nem corrigir nomes automaticamente.

### Agregações e JOIN

1. Agregar o PDD separadamente por CNPJ e AnoReferencia antes de qualquer JOIN com o INDGER. Somar cada registro PDD uma vez.
2. Para recortes por tipo, agregar o PDD também por DscTipoObra. O grão fica CNPJ, ano e tipo.
3. Antes de agregar as UCs, validar a unicidade da chave INDGER NumCNPJ + CodMunicipioIBGE + DatReferenciaInformada para as referências de dezembro. Na carga atual, não há duplicidades nos dezembros de 2023, 2024 e 2025.
4. Se houver duplicidade nessa chave, gerar diagnóstico e impedir a agregação das UCs até a revisão dos registros. Não usar SUM(DISTINCT QtdUCAtiva), não escolher uma linha arbitrariamente e não alterar RAW ou REFINED.
5. Agregar INDGER por CNPJ, município e referência de dezembro validada; depois somar os municípios e obter uma linha por CNPJ e ano.
6. Fazer o JOIN entre os resultados já agregados usando CNPJ e ano. A tabela à direita e a tabela à esquerda devem ter no máximo uma linha por CNPJ/ano no grão do indicador.
7. Não unir investimento por empresa diretamente a linhas municipais do INDGER antes de agregar UC.
8. Ausência de dezembro, UCs nulas ou denominador zero tornam R$/UC indisponível. Nunca substituir esses casos por zero artificial.

### Tipos e classes de obra

DscTipoObra contém Expansão, Melhoria, Renovação e Obra com Participação Financeira. DscTipoObraClasse contém valores vazios, Luz Para Todos, Obra com Participação Financeira e Planejamento Setorial.

Tipo e classe são atributos do mesmo registro PDD, não parcelas adicionais de investimento. Os relatórios por tipo e por classe são visões alternativas. Nunca somar os totais de tipo aos totais de classe. O MART por tipo usa somente DscTipoObra. O perfil pode expor o par tipo/classe, deixando claro que totais ou percentuais de dimensões diferentes não devem ser somados entre si.

### Indicador R$/UC

Calcular investimento realizado por UC como a soma de VlrTotalRealizado do ano dividida pela soma de QtdUCAtiva na referência de dezembro do mesmo ano e do mesmo CNPJ.

R$/UC é uma medida de intensidade de investimento em relação à base de UCs. Não é, isoladamente, uma medida de eficiência ou qualidade: diferenças de território, custo, perfil da rede, mix de obras e contexto operacional influenciam o valor.

## MARTs planejados

### 01_investimentos_anuais.sql

- **Objetivo:** apresentar os totais anuais de investimento planejado e realizado, em visão nacional e para a coorte fixa top 10.
- **Granularidade:** ano de referência e escopo; duas linhas de escopo não são aditivas entre si.
- **Campos principais:** ano, escopo, quantidade de registros PDD, CNPJs cobertos, total planejado, total realizado, sinalização de ano realizado completo.
- **Filtros:** foco do dashboard em 2023–2025. Pode manter anos adicionais para análise; identificar 2026–2030 como planejamento com realizado não completo.
- **Cálculo:** somar os valores do PDD por ano antes de cruzar com qualquer dado do INDGER. Top 10 é a soma do subconjunto dos CNPJs fixos.
- **Validações:** contagem e totais devem reconciliar com PDD por ano; comparar os escopos nacional e top 10 sem somá-los; os zeros realizados em 2026–2030 não podem receber rótulo de execução anual completa.

### 02_investimentos_por_tipo.sql

- **Objetivo:** comparar investimento planejado e realizado por categoria de obra.
- **Granularidade:** ano, escopo e DscTipoObra.
- **Campos principais:** ano, escopo, tipo, quantidade de registros, total planejado, total realizado.
- **Filtros:** 2023–2025 como período principal; permitir escopo nacional ou top 10 fixo.
- **Cálculo:** agrupar apenas por DscTipoObra, sem adicionar valores agrupados por DscTipoObraClasse.
- **Validações:** somar as categorias de tipo para reconciliar com o total PDD do mesmo ano e escopo; preservar valores vazios ou tipos novos para análise, sem descartá-los.

### 03_investimento_por_uc.sql

- **Objetivo:** calcular investimento planejado e realizado por UC para cada distribuidora.
- **Granularidade:** CNPJ e ano; uma linha por distribuidora/ano/escopo.
- **Campos principais:** CNPJ, rótulo INDGER, aliases PDD disponíveis, ano, escopo, total realizado, total planejado, UCs de dezembro, realizado por UC, planejado por UC, status de cobertura.
- **Filtros:** 2023–2025; coorte top 10 ou população nacional correspondente.
- **Cálculo:** agregar PDD por CNPJ/ano e INDGER por município/CNPJ/ano de dezembro separadamente; agregar municípios por CNPJ; então fazer JOIN por CNPJ e ano. Dividir somente quando houver referência e UCs maiores que zero.
- **Validações:** verificar unicidade da chave CNPJ/município/referência no INDGER de dezembro antes da soma; duplicidades devem bloquear a agregação e gerar diagnóstico. Ausência ou denominador nulo/zero resulta em indicador nulo/indisponível; conferir unicidade CNPJ/ano em ambos os lados do JOIN e igualdade dos totais PDD antes/depois do JOIN.

### 04_planejado_vs_realizado.sql

- **Objetivo:** mostrar diferenças entre investimento planejado e realizado.
- **Granularidade:** manter saídas separadas: visão por distribuidora com uma linha por CNPJ e ano; visão nacional com uma linha por ano. Não misturar os dois grãos na mesma saída.
- **Campos principais:** visão por distribuidora: CNPJ, rótulo, ano, total planejado, total realizado, diferença absoluta, diferença percentual, status e flag top10_2025. Visão nacional: ano, total planejado, total realizado, diferença absoluta, diferença percentual e status.
- **Filtros:** principal em 2023–2025; não tratar valores realizados zerados em anos futuros como execução completa.
- **Cálculo:** diferença absoluta = realizado menos planejado. Percentual = diferença absoluta dividida pelo planejado, apenas quando planejado for maior que zero.
- **Validações:** não dividir por zero; preservar nulos como indisponíveis; confirmar uma linha por CNPJ/ano na visão por distribuidora e uma por ano na nacional; totais de planejado e realizado devem reconciliar com 01_investimentos_anuais.sql.

### 05_evolucao_investimentos.sql

- **Objetivo:** acompanhar a evolução anual dos investimentos planejados e realizados.
- **Granularidade:** ano e escopo para séries agregadas; CNPJ e ano para séries por distribuidora, sem misturar os dois grãos.
- **Campos principais:** ano, escopo, CNPJ quando aplicável, planejado, realizado, variação absoluta e percentual ano contra ano.
- **Filtros:** exibir 2023–2025; 2022 pode ser usado somente como ano-base para calcular a variação de 2023. Tratar 2026–2030 como planejamento e não como série anual realizada completa.
- **Cálculo:** ordenar anos e calcular a variação contra o ano anterior no mesmo escopo e, quando aplicável, no mesmo CNPJ. Percentual fica indisponível quando o valor-base for nulo ou zero.
- **Validações:** não comparar CNPJs ou escopos diferentes; as somas anuais devem reconciliar com 01_investimentos_anuais.sql.

### 06_ranking_investimentos.sql

- **Objetivo:** classificar distribuidoras por montante de investimento.
- **Granularidade:** ano, CNPJ, escopo e medida ranqueada.
- **Campos principais:** CNPJ, rótulo, ano, total planejado, total realizado, posição por planejado, posição por realizado, flag de pertencimento ao top 10 fixo.
- **Filtros:** manter todos os CNPJs no ranking nacional; permitir recorte da coorte fixa top 10 para o dashboard.
- **Cálculo:** agregar PDD por CNPJ/ano antes de calcular posições. Desempatar posições por CNPJ crescente e registrar qual medida determina o ranking. Não gerar ranking de execução anual completa para 2026–2030.
- **Validações:** posição determinística e sem duplicidade de CNPJ no mesmo ano/escopo/medida; os valores devem reconciliar com o PDD agregado.

### 07_ranking_por_uc.sql

- **Objetivo:** comparar exclusivamente as dez distribuidoras da coorte fixa do dashboard pelo total de UCs ativas em dezembro, mantendo também uma saída nacional auxiliar para diagnóstico.
- **Saídas e granularidade:** `marts.ranking_por_uc_top10`, exatamente uma linha por CNPJ da coorte fixa e ano (30 linhas para 2023–2025); `marts.ranking_por_uc_nacional`, uma linha por CNPJ com dados em dezembro e ano. As saídas são tabelas distintas e não devem ser somadas entre si.
- **Campos principais — top 10:** ano, CNPJ, rótulo INDGER, total de UCs ativas, contagens de municípios/valores válidos/nulos/inválidos, status da cobertura, posição anual dentro da coorte, posição fixa de dezembro de 2025 e variações absoluta e percentual contra o ano anterior.
- **Campos principais — nacional auxiliar:** ano, CNPJ, rótulo INDGER, total de UCs ativas, status da cobertura, posição no ranking nacional, posição fixa de dezembro de 2025 e flag de pertencimento ao top 10.
- **Filtros:** dezembro de 2023, 2024 e 2025. A saída principal contém somente os dez CNPJs persistidos em `marts.cohorte_top10_2025`; a saída auxiliar preserva todos os CNPJs com referência INDGER disponível.
- **Cálculo:** validar antes da agregação a unicidade da chave CNPJ + município + referência. Somar as UCs municipais por CNPJ/ano. Gerar a saída principal a partir da coorte fixa cruzada com os três anos e associar os valores observados; referência ausente permanece indisponível. Calcular posições por UCs decrescentes e CNPJ crescente, separadamente na coorte e no universo nacional. Calcular variações anuais somente entre anos consecutivos e bases válidas; percentual sobre base zero fica indisponível. Ausência de referência, valores nulos ou inválidos nunca se convertem em zero.
- **Validações:** exatamente dez CNPJs distintos por ano na saída principal, iguais à coorte persistida; uma linha por CNPJ/ano em cada saída; duplicidades municipais bloqueiam a execução; posições válidas determinísticas, sem confundir ranking da coorte com ranking nacional; soma de dezembro de 2025 por CNPJ reconcilia com `marts.cohorte_top10_2025`; saída nacional reconcilia com os agregados INDGER; variações respeitam status e continuidade temporal.

### 08_perfil_investimentos.sql

- **Objetivo:** detalhar o perfil de investimentos por distribuidora e composição de obras.
- **Granularidade:** escopo, CNPJ, ano, DscTipoObra e DscTipoObraClasse; cada linha representa uma combinação observada no PDD dentro do escopo.
- **Campos principais:** escopo com valores nacional ou top10, CNPJ, rótulo e alias, ano, tipo, classe, quantidade de registros, total planejado, total realizado, participação sobre o total CNPJ/ano.
- **Filtros:** 2023–2025; disponibilizar visões nacional e top 10 fixo.
- **Cálculo:** agregar cada registro PDD uma vez pelo par tipo/classe; calcular participação usando o total do mesmo CNPJ/ano e escopo. Se nacional e top10 forem armazenados no mesmo MART, produzir ambos os valores em escopo e filtrar somente um escopo em cada consulta do dashboard.
- **Validações:** a soma das combinações tipo/classe deve reconciliar com o total PDD do CNPJ/ano e escopo; percentuais só são calculados com total válido e não zero; ausência de classe deve continuar identificável; consultas do dashboard não podem somar linhas dos escopos nacional e top10 juntos.

## Testes de qualidade dos MARTs

1. Contagens e totais de investimento por ano reconciliam com refined.pdd.
2. Antes de somar UCs por CNPJ, validar a unicidade da chave NumCNPJ + CodMunicipioIBGE + DatReferenciaInformada para dezembro. Para 2023–2025 a carga atual não tem duplicidades; se surgirem, gerar diagnóstico e bloquear a agregação sem modificar RAW/REFINED ou deduplicar arbitrariamente.
3. A agregação de QtdUCAtiva reconcilia com refined.indger_comerciais, limitada às referências de dezembro quando o indicador for anual.
4. Antes de cada JOIN entre fontes, validar no máximo uma linha por CNPJ/ano em cada lado para o grão correspondente.
5. Comparar totais PDD antes e depois dos JOINs; qualquer aumento indica multiplicação e deve falhar a validação.
6. Confirmar que nenhuma linha ou distribuidora foi removida das tabelas-base por aplicação do top 10.
7. Confirmar a associação por CNPJ, sem JOIN por nome; reportar CNPJs sem correspondência em cada fonte.
8. Confirmar cobertura de dezembro, status de UCs nulas e tratamento de referências ausentes como indisponíveis.
9. Confirmar coorte top 10 com exatamente os CNPJs documentados, desempate por CNPJ crescente e ordem por UCs de dezembro de 2025.
10. Confirmar que os zeros realizados de 2026–2030 não aparecem como execução anual completa.
11. Reconciliar valores por DscTipoObra e por tipo/classe como visões separadas; impedir que os totais das duas dimensões sejam somados juntos.
12. Não converter denominadores indisponíveis ou zero em R$/UC igual a zero.
13. Validar que variações percentuais não sejam calculadas com denominador nulo ou zero.

