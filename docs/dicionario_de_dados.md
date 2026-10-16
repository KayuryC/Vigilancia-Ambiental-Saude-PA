# Dicionário de Dados do Projeto (Requisitos 1 e 4)

Este documento descreve detalhadamente as fontes de dados públicas, licenças de uso, URLs de coleta, esquema, tipagem, domínios permitidos, linhagem e semântica de negócio para todas as tabelas das camadas **Silver** e **Gold** do pipeline de dados.

---

## 🌐 0. Registro de Fontes Públicas, Licenças e Coleta (Requisito 1)

Conforme exigido pelas diretrizes do projeto, todas as bases utilizadas são de uso aberto, públicas e suas credenciais de rastreabilidade estão formalizadas abaixo:

| Instituição | Base de Dados | Formato | URL Oficial de Coleta | Licença de Uso | Data de Coleta | Chave Primária / Identificador |
| :--- | :--- | :---: | :--- | :--- | :---: | :--- |
| **IBGE** | Localidades & Censo Demográfico 2022 | API REST (JSON) | `https://servicodados.ibge.gov.br/api/docs` | Dados Abertos Governamentais (Lei 12.527/2011) | 14/10/2026 | `codigo_ibge` (7 dígitos) |
| **INPE** | BDQueimadas (Satélite de Referência) | CSV em ZIP | `https://data.inpe.br/queimadas/dados-abertos/` | Política de Dados Abertos MCTI / INPE (Uso Livre) | 14/10/2026 | `foco_id` / Coordenadas e Data |
| **DataSUS** | Sistema de Informações Hospitalares (SIH) | Banco Relacional SQL | `https://opendatasus.saude.gov.br` | Dados Públicos / Ministério da Saúde | 14/10/2026 | `numero_aih` / `codigo_ibge_municipio` |

---

## 🏛️ 1. Camada Silver (Prata)

### 1.1. Tabela: `dim_municipios_pa`
* **Caminho:** `data/silver/dim_municipios_pa.parquet`
* **Granularidade declarada:** Uma linha por município do estado do Pará.
* **Chave Primária (PK):** `codigo_ibge` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `codigo_ibge` | `string` | 7 dígitos numéricos iniciando em `15` | IBGE (API Localidades) | Código identificador padrão geográfico do município no Brasil. |
| `nome_municipio` | `string` | Nomes em maiúsculas, sem espaços extras | IBGE (API Localidades) | Nome oficial padronizado do município. |
| `uf` | `string` | `"PA"` | IBGE | Sigla da Unidade Federativa (Pará). |
| `mesorregiao` | `string` | Nomes das 6 mesorregiões do Pará | IBGE (API Localidades) | Divisão regional geográfica intermediária do IBGE. |
| `microrregiao` | `string` | Nomes das microrregiões do Pará | IBGE (API Localidades) | Divisão regional detalhada do estado. |
| `populacao_censo_2022` | `int64` | Inteiros $> 0$ | IBGE (Censo Demográfico 2022) | População residente oficial apurada pelo Censo de 2022. |
| `processed_at` | `string` | Timestamp ISO 8601 UTC | Pipeline Silver | Data e hora em que a dimensão foi processada. |
| `bronze_source_file` | `string` | Nome do arquivo `.parquet` da Bronze | Metadados | Arquivo da camada Bronze que originou o registro. |

---

### 1.2. Tabela: `fatos_focos_mensais_pa`
* **Caminho:** `data/silver/fatos_focos_mensais_pa.parquet`
* **Granularidade declarada:** Uma linha por município por mês do estado do Pará.
* **Chave Primária Composta:** `codigo_ibge` + `ano_mes` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `codigo_ibge` | `string` | 7 dígitos iniciando em `15` | INPE / Resolução IBGE | Código IBGE do município associado aos focos. |
| `ano_mes` | `string` | Formato `YYYY-MM` (`2023-01` a `2023-12`) | INPE (BDQueimadas) | Mês de competência dos registros de queimadas. |
| `total_focos_calor` | `int64` | Inteiros $\ge 0$ | INPE (BDQueimadas) | Total de focos de queimada detectados pelo satélite de referência no mês. |
| `media_lat_focos` | `float64` | Latitude entre `[-10.5, 3.5]` | INPE (BDQueimadas) | Latitude média dos focos de queimada no território municipal. |
| `media_lon_focos` | `float64` | Longitude entre `[-60.0, -45.0]` | INPE (BDQueimadas) | Longitude média dos focos de queimada. |
| `dias_com_focos` | `int64` | Inteiros entre `[0, 31]` | INPE (BDQueimadas) | Quantidade de dias distintos no mês em que houve registro de queimada. |
| `processed_at` | `string` | Timestamp ISO 8601 UTC | Pipeline Silver | Carimbo temporal do processamento. |

---

### 1.3. Tabela: `fatos_internacoes_mensais_pa`
* **Caminho:** `data/silver/fatos_internacoes_mensais_pa.parquet`
* **Granularidade declarada:** Uma linha por município por mês do estado do Pará.
* **Chave Primária Composta:** `codigo_ibge` + `ano_mes` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `codigo_ibge` | `string` | 7 dígitos iniciando em `15` | DataSUS (SIH) | Código IBGE do município onde ocorreu a internação. |
| `ano_mes` | `string` | Formato `YYYY-MM` | DataSUS (SIH) | Mês de competência da internação hospitalar. |
| `total_internacoes` | `int64` | Inteiros $\ge 0$ | DataSUS (SIH) | Quantidade total de internações por causas respiratórias (CID-10 J00-J99). |
| `total_dias_leito` | `int64` | Inteiros $\ge 0$ | DataSUS (SIH) | Soma total de dias de ocupação de leitos hospitalares no mês. |
| `media_dias_leito` | `float64` | Reais $\ge 0.0$ | DataSUS (SIH) | Duração média de internação por paciente (em dias). |
| `custo_total_sus` | `float64` | Reais $\ge 0.0$ | DataSUS (SIH) | Valor total repassado pelo SUS pelas internações no mês (R$). |
| `internacoes_urgencia`| `int64`| Inteiros $\ge 0$ | DataSUS (SIH) | Internações respiratórias admitidas em caráter de urgência/emergência. |
| `internacoes_infantis`| `int64`| Inteiros $\ge 0$ | DataSUS (SIH) | Internações na faixa etária vulnerável de 0 a 4 anos. |
| `internacoes_idosos` | `int64` | Inteiros $\ge 0$ | DataSUS (SIH) | Internações na faixa etária vulnerável de 60 anos ou mais. |
| `processed_at` | `string` | Timestamp ISO 8601 UTC | Pipeline Silver | Carimbo temporal do processamento. |

---

### 1.4. Tabela: `silver_painel_mensal_pa`
* **Caminho:** `data/silver/silver_painel_mensal_pa.parquet`
* **Granularidade declarada:** Uma linha por município por mês do estado do Pará (144 municípios × 12 meses = 1.728 linhas canônicas).
* **Chave Primária Composta:** `codigo_ibge` + `ano_mes` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `codigo_ibge` | `string` | 7 dígitos iniciando em `15` | IBGE | Código identificador padrão do município. |
| `nome_municipio` | `string` | Texto padronizado | IBGE | Nome oficial do município no Pará. |
| `uf` | `string` | `"PA"` | IBGE | Unidade Federativa. |
| `mesorregiao` | `string` | Texto | IBGE | Mesorregião geográfica do estado. |
| `microrregiao` | `string` | Texto | IBGE | Microrregião geográfica. |
| `populacao_censo_2022` | `int64` | Inteiros $> 0$ | IBGE | População apurada no Censo Demográfico 2022. |
| `ano_mes` | `string` | `YYYY-MM` (`2023-01` a `2023-12`) | Grade Canônica | Mês de competência temporal. |
| `total_focos_calor` | `int64` | Inteiros $\ge 0$ | INPE | Total de focos de queimada no mês (preenchimento 0 para sem eventos). |
| `media_lat_focos` | `float64` | Intervalo geográfico | INPE | Latitude média dos focos (ou 0.0 se sem focos). |
| `media_lon_focos` | `float64` | Intervalo geográfico | INPE | Longitude média dos focos (ou 0.0 se sem focos). |
| `dias_com_focos` | `int64` | `[0, 31]` | INPE | Dias do mês com pelo menos um foco registrado. |
| `total_internacoes` | `int64` | Inteiros $\ge 0$ | DataSUS | Total de internações hospitalares respiratórias. |
| `total_dias_leito` | `int64` | Inteiros $\ge 0$ | DataSUS | Total de diárias de internação acumuladas. |
| `media_dias_leito` | `float64` | Reais $\ge 0.0$ | DataSUS | Média de dias por paciente internado. |
| `custo_total_sus` | `float64` | Reais $\ge 0.0$ | DataSUS | Custo financeiro total repassado pelo SUS (R$). |
| `internacoes_urgencia`| `int64` | Inteiros $\ge 0$ | DataSUS | Contagem de admissões de urgência. |
| `internacoes_infantis`| `int64` | Inteiros $\ge 0$ | DataSUS | Contagem de crianças (0-4 anos) hospitalizadas. |
| `internacoes_idosos` | `int64` | Inteiros $\ge 0$ | DataSUS | Contagem de idosos (60+ anos) hospitalizados. |
| `processed_at` | `string` | Timestamp ISO 8601 UTC | Pipeline Silver | Data e hora de consolidação do Join. |

---

## 🥇 2. Camada Gold (Ouro)

### 2.1. Tabela: `gold_painel_indicadores_pa`
* **Caminho:** `data/gold/gold_painel_indicadores_pa.parquet`
* **Granularidade declarada:** Uma linha por município por mês do estado do Pará com indicadores analíticos e taxas normalizadas.
* **Chave Primária Composta:** `codigo_ibge` + `ano_mes` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `taxa_internacao_100k` | `float64` | Reais $\ge 0.0$ | Calculado (DataSUS ÷ IBGE) | Taxa de internações respiratórias por 100 mil habitantes no mês. |
| `focos_por_10k_hab` | `float64` | Reais $\ge 0.0$ | Calculado (INPE ÷ IBGE) | Densidade relativa de focos de queimada por 10 mil habitantes. |
| `taxa_internacao_infantil_100k` | `float64` | Reais $\ge 0.0$ | Calculado | Incidência de internações em crianças (0-4 anos) por 100 mil hab. |
| `taxa_internacao_idosos_100k` | `float64` | Reais $\ge 0.0$ | Calculado | Incidência de internações em idosos (60+ anos) por 100 mil hab. |
| `custo_medio_internacao` | `float64` | Reais $\ge 0.0$ | Calculado | Gasto médio hospitalar do SUS por paciente respiratório (R$). |
| `periodo_estiagem` | `int64` | `0` ou `1` | Calendário regional | Flag indicadora do período seco amazônico no Pará (Julho a Novembro = 1). |
| `focos_lag_1m` | `float64` | Inteiros/Reais $\ge 0$ | Calculado (Lag causal) | Volume de queimadas do município no mês anterior ($m-1$). |
| `internacoes_lag_1m` | `float64` | Inteiros/Reais $\ge 0$ | Calculado (Lag causal) | Volume de internações respiratórias no mês anterior ($m-1$). |
| `taxa_internacao_lag_1m` | `float64` | Reais $\ge 0.0$ | Calculado (Lag causal) | Taxa epidemiológica por 100 mil hab do mês anterior ($m-1$). |

---

### 2.2. Tabela: `gold_ml_ready_pa`
* **Caminho:** `data/gold/gold_ml_ready_pa.parquet`
* **Granularidade declarada:** Uma linha por município por mês de corte ($t_0$).
* **Chave Primária Composta:** `codigo_ibge` + `ano_mes_t0` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `codigo_ibge` | `string` | 7 dígitos | IBGE | Código identificador do município. |
| `ano_mes_t0` | `string` | `YYYY-MM` (`2023-01` a `2023-11`) | Ponto de corte | Instante em que o conhecimento do decisor é congelado para previsão. |
| `populacao_censo_2022` | `int64` | Inteiros $> 0$ | Feature Censitária ($< t_0$) | População residente de referência. |
| `total_focos_calor` | `int64` | Inteiros $\ge 0$ | Feature Ambiental ($< t_0$) | Focos observados no mês $t_0$. |
| `focos_por_10k_hab` | `float64` | Reais $\ge 0.0$ | Feature Relativa ($< t_0$) | Densidade de focos por habitante em $t_0$. |
| `focos_lag_1m` | `float64` | Reais $\ge 0.0$ | Feature Histórica ($< t_0$) | Queimadas acumuladas no mês anterior ($t_0 - 1$). |
| `taxa_internacao_100k` | `float64` | Reais $\ge 0.0$ | Feature Epidemiológica ($< t_0$) | Taxa de internações hospitalares em $t_0$. |
| `taxa_internacao_lag_1m` | `float64` | Reais $\ge 0.0$ | Feature Histórica ($< t_0$) | Taxa epidemiológica do mês anterior ($t_0 - 1$). |
| `internacoes_urgencia` | `int64` | Inteiros $\ge 0$ | Feature Hospitalar ($< t_0$) | Atendimentos emergenciais em $t_0$. |
| `internacoes_infantis` | `int64` | Inteiros $\ge 0$ | Feature Vulnerabilidade ($< t_0$) | Admissões infantis em $t_0$. |
| `internacoes_idosos` | `int64` | Inteiros $\ge 0$ | Feature Vulnerabilidade ($< t_0$) | Admissões de idosos em $t_0$. |
| `periodo_estiagem` | `int64` | `0` ou `1` | Feature Sazonal ($< t_0$) | Indicador de seca amazônica no mês $t_0$. |
| `taxa_internacao_futura` | `float64` | Reais $\ge 0.0$ | Observado em $t_0 + 1$ | Taxa epidemiológica real que ocorreu no mês subsequente. |
| `label_sobrecarga_proximo_mes` | `int64` | `0` ou `1` | Regra de rotulagem formal | **Variável Alvo ($Y$):** 1 indica que o município atingirá sobrecarga severa no mês seguinte ($\ge 47.92$ internações/100k hab). |

---

### 2.3. Tabela: `gold_recomendacao_decisao_sespa`
* **Caminho:** `data/gold/gold_recomendacao_decisao_sespa.parquet`
* **Granularidade declarada:** Uma linha por município por mês do período de teste operacional (Setembro a Novembro de 2023).
* **Chave Primária Composta:** `codigo_ibge` + `ano_mes_t0` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `codigo_ibge` | `string` | 7 dígitos | IBGE | Código do município. |
| `nome_municipio` | `string` | Texto padronizado | IBGE | Nome do município para despacho logístico. |
| `mesorregiao` | `string` | Texto | IBGE | Região administrativa da SESPA. |
| `ano_mes_t0` | `string` | `YYYY-MM` | Ponto de corte | Mês de emissão da ordem de remanejamento. |
| `probabilidade_risco` | `float64` | Intervalo `[0.0, 1.0]` | Modelo Random Forest | Probabilidade estimada pelo modelo de o município colapsar no mês seguinte. |
| `decisao_recomendada` | `string` | Categorias prescritivas | Regra de Decisão SESPA | Recomendação acionável de suporte à decisão: *"Alerta Alto: Envio Imediato de Kit Completo"*, *"Alerta Médio"* ou *"Monitoramento de Rotina"*. |
