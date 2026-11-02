# Dashboard Streamlit

## Visão Geral

A página inicial compara exclusivamente a coorte fixa dos dez CNPJs com mais
unidades consumidoras ativas em dezembro de 2025. O filtro oferece 2023, 2024 e
2025 e inicia em 2025; a seleção das empresas permanece fixa ao trocar o ano.
Nomes e arquivos de logo são resolvidos por CNPJ. Marcas repetidas recebem a UF
no rótulo dos gráficos para não confundir concessões diferentes.

A hierarquia da home é: título institucional, KPIs, ranking financeiro,
composição por tipo de obra, tabela resumida e notas de metodologia e fonte. O
gráfico de evolução não faz parte da home e o MART 05 permanece intacto.

A home usa um ?nico gr?fico principal de barras horizontais empilhadas,
intitulado Ranking de Investimentos por Distribuidora. As dez empresas s?o
ordenadas pelo total realizado do MART 06; cada barra separa Expans?o, Melhoria
e Renova??o e mostra o total compacto no seu final. Classes n?o s?o exibidas.
O tooltip apresenta valores e participa??es por tipo. As tr?s primeiras
posi??es recebem contorno dourado, sem mudar as cores dos tipos. Um seletor
real?a uma distribuidora sem remover as outras nove. O gr?fico separado de
ranking e o gr?fico de evolu??o n?o fazem parte da home; o MART 05 permanece
intacto. Os KPIs usam ?cones e acentos discretos, e o filtro de ano inicia em
2025.

## Comparativo Top 10

Antes dos cards, a página mostra o gráfico horizontal ?Ranking de investimento por UC?, com os dez CNPJs do MART 06 e valores do MART 03 no ano selecionado. A ordem é decrescente por R$/UC; empates são ordenados por CNPJ e valores indisponíveis ficam ao final. O tooltip agrega valores e contexto dos MARTS 03, 04, 06 e 07. R$/UC indisponível não vira zero; zero válido continua sendo mostrado como zero.

A página Comparativo Top 10 reutiliza os cards expansíveis por distribuidora,
organizados pelo ranking financeiro do ano selecionado. Os três primeiros
aparecem em cards maiores e as posições 4 a 10 em cards compactos. A página
mantém os dez CNPJs da coorte fixa em todos os anos disponíveis.

Cada card apresenta marca, logo quando disponível, UF e região de referência,
investimento realizado, posição financeira e posição fixa da coorte. Em
“Ver detalhes”, apresenta valores realizados por tipo (Expansão, Melhoria e
Renovação), total planejado e realizado, taxa de execução, UCs ativas em
dezembro e investimento realizado por UC. Classes de obra não são exibidas.
Dados indisponíveis são identificados como “Não disponível”. R$/UC é uma medida
de intensidade de investimento, não eficiência operacional nem valor recebido
individualmente por consumidores.

O componente em `dashboard/components.py` recebe os dados carregados em lote e
filtra por CNPJ e ano na aplicação. Não executa uma consulta DuckDB por card.

## Fontes e regras dos indicadores

- KPIs anuais: `marts.investimentos_anuais`, filtrado por `escopo = 'top10'`.
- Ranking financeiro: `marts.ranking_investimentos`, MART 06, filtrado por
  `escopo = 'top10'` e pela medida realizado.
- Tipos: `marts.perfil_investimentos`, MART 08, agregado por CNPJ, ano e tipo;
  classes não são mostradas. A Visão Geral mostra Expansão, Melhoria e Renovação.
- Execução financeira: `marts.planejado_vs_realizado_distribuidora`, MART 04.
- Investimento por UC: `marts.investimento_por_uc`, MART 03.
- Ranking e UCs: MARTS 06 e 07. A coorte persistente vem de
  `marts.cohorte_top10_2025`.

Os escopos nacional e top10 não são combinados. A tabela mantém valores
numéricos ordenáveis; valores indisponíveis aparecem em branco, nunca como zero.
O app alerta sobre categorias adicionais presentes no MART 08 e sobre diferenças
entre os totais por tipo e o total realizado da empresa.

## Geografia e logos

`dashboard/metadata.py` mantém UF principal e região para os dez CNPJs da coorte.
Esse local é uma referência principal da concessão, não a lista completa de
municípios atendidos. `dashboard/logos.py` mapeia CNPJ aos arquivos locais em
`assets/logos/`; quando falta um arquivo, o dashboard mostra o nome sem imagem.

## Acesso ao banco

O caminho do DuckDB é reutilizado de `pipeline.db.DB_PATH`; a conexão é somente
leitura. O dashboard não executa ingestões, transformações nem recria MARTS.
As consultas são carregadas em lote e ficam em cache por cinco minutos. Se o
banco ou alguma tabela necessária estiver ausente, a aplicação exibe uma
mensagem e não cria um banco vazio.

## Execução local

Na raiz do repositório, no terminal do VS Code:

```powershell
uv run streamlit run dashboard/app.py
```

A Visão Geral e o Comparativo Top 10 estão implementados. As demais opções da
navegação permanecem preparadas para etapas futuras.
