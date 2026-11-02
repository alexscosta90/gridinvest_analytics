# Dashboard Streamlit

O dashboard compara indicadores de investimento das distribuidoras de energia
elétrica a partir dos dados públicos da ANEEL. As cinco páginas compartilham o
filtro de ano (2023, 2024 e 2025, com 2025 como seleção inicial) e a coorte fixa
dos dez CNPJs com mais unidades consumidoras ativas em dezembro de 2025.
Nomes, rótulos geográficos e logos são associados por CNPJ; marcas repetidas
recebem a UF no rótulo para distinguir concessões.

## Visão Geral

Apresenta um resumo anual da coorte: investimento planejado e realizado, taxa de
execução e quantidade de distribuidoras. O gráfico principal mostra o ranking
financeiro em barras horizontais empilhadas por Expansão, Melhoria e Renovação,
com total realizado e comparação entre as dez empresas. A página também inclui
uma tabela resumida e notas sobre dados adicionais ou divergências de
reconciliação. Os indicadores financeiros vêm de `marts.investimentos_anuais`
(MART 01), o ranking e a coorte de `marts.ranking_investimentos` e
`marts.cohorte_top10_2025` (MART 06), os valores por tipo de
`marts.perfil_investimentos` (MART 08), e os detalhes financeiros e de R$/UC dos
MARTS 04 e 03 (`marts.planejado_vs_realizado_distribuidora` e
`marts.investimento_por_uc`).

## Comparativo Top 10

Compara individualmente as dez distribuidoras da coorte no ano selecionado. Um
gráfico horizontal ordena o investimento realizado por unidade consumidora
(R$/UC); abaixo, cards destacam as três maiores posições financeiras e mostram
as outras sete em formato compacto. Os cards incluem investimento realizado,
posição financeira e da coorte e, nos detalhes expansíveis, valores por tipo,
planejado e realizado, taxa de execução, UCs ativas e R$/UC. Utiliza
`marts.investimento_por_uc` (MART 03),
`marts.planejado_vs_realizado_distribuidora` (MART 04),
`marts.ranking_investimentos` e `marts.cohorte_top10_2025` (MART 06),
`marts.ranking_por_uc_top10` (MART 07) e `marts.perfil_investimentos` (MART 08).

## Investimento por UC

Mostra o investimento realizado por unidade consumidora para cada empresa da
coorte e ajuda a comparar intensidade de investimento e escala de atendimento.
Os KPIs apresentam os maiores e menores valores individuais disponíveis, o
total de UCs ativas em dezembro e o indicador agregado da coorte, calculado
como total realizado dividido pelo total de UCs (não como média dos valores
individuais). A página inclui ranking em barras, gráfico de dispersão entre UCs
e R$/UC, e tabela comparativa com investimento total e posições. Combina
`marts.investimento_por_uc` (MART 03), `marts.ranking_investimentos` (MART 06),
e `marts.ranking_por_uc_top10` (MART 07). Os totais e as unidades são
reconciliados entre os MARTS 03, 06 e 07. Indicadores sem cobertura completa ou
com divergências são apresentados como indisponíveis.

## Planejado x Realizado

Compara os valores planejados e realizados para a coorte fixa no ano escolhido.
Os KPIs mostram os totais planejado e realizado, percentual de execução e
diferença financeira. Um gráfico de colunas agrupadas compara planejado e
realizado por distribuidora; uma tabela apresenta também diferenças absoluta e
percentual e taxa de execução. Usa `marts.investimentos_anuais` (MART 01) e
`marts.planejado_vs_realizado_distribuidora` (MART 04), conferindo a
reconciliação entre os totais anuais e os detalhes por distribuidora.

## Perfil de Investimentos

Examina como o investimento realizado da coorte se distribui por tipo no ano
selecionado e permite consultar a composição de cada distribuidora. Mostra
KPIs de investimento total, Expansão, Melhoria e Renovação; um gráfico de rosca
com a participação por tipo; barras empilhadas por distribuidora; e detalhes
individuais com valores e percentuais. Tipos adicionais são agrupados em
“Outros tipos” nos dados completos e classes não são exibidas. Usa
`marts.perfil_investimentos` (MART 08), o ranking e a coorte do MART 06 e
`marts.investimentos_anuais` (MART 01) para validar os totais. Valores
indisponíveis permanecem identificados como tal, e a página alerta quando os
tipos ou os totais não reconciliam.

## Regras dos indicadores e apresentação

Os escopos nacional e `top10` permanecem separados; os valores nacionais não
são somados aos da coorte. Valores ausentes ou inválidos não são convertidos em
zero. Um zero válido permanece distinto de indisponibilidade. Os valores por
tipo exibidos na Visão Geral são Expansão, Melhoria e Renovação; a página Perfil
de Investimentos também considera tipos adicionais na reconciliação. R$/UC é
uma medida de intensidade de investimento, não de eficiência operacional nem
de valor recebido individualmente pelos consumidores.

`dashboard/metadata.py` registra UF principal e região como referência da
concessão, não como lista completa de municípios atendidos. `dashboard/logos.py`
associa CNPJs aos arquivos em `assets/logos/`; se um logo não estiver presente,
o nome da distribuidora é usado como alternativa. O cabeçalho institucional
compartilhado usa `assets/logos/gridinvest_analytics.png`.

## Acesso ao banco

O dashboard reutiliza `pipeline.db.DB_PATH` e abre o DuckDB em modo somente
leitura. As consultas são carregadas em lote e armazenadas em cache por cinco
minutos. A aplicação não executa ingestões, transformações nem recria MARTS; se
o banco ou uma tabela necessária estiver ausente, mostra uma mensagem sem criar
um banco vazio.

## Execução local

Na raiz do repositório, no terminal:

```powershell
uv run streamlit run dashboard/app.py
```
