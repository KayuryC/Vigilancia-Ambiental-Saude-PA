# Dicionário de Dados do Projeto (Requisito 4)

Este documento descreve detalhadamente o esquema, tipagem, domínios permitidos, linhagem e semântica de negócio para todas as tabelas das camadas **Silver** e **Gold** do pipeline de dados.

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
* **Descrição:** Visão unificada que integra a dimensão de municípios com as métricas de queimadas do INPE e de internações do DataSUS, com preenchimento semântico de ausências (zeros para meses sem eventos).

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
| `ano_mes_t0` | `string` | `YYYY-MM` (`2023-01` a `2023-11`) | Ponto de corte | Instante em que o conhecimento do decisor é congelado para previsão. |
| `taxa_internacao_futura` | `float64` | Reais $\ge 0.0$ | Observado em $t_0 + 1$ | Taxa epidemiológica real que ocorreu no mês subsequente. |
| `label_sobrecarga_proximo_mes` | `int64` | `0` ou `1` | Regra de rotulagem formal | **Variável Alvo ($Y$):** 1 indica que o município atingirá sobrecarga severa no mês seguinte ($\ge 47.92$ internações/100k hab). |

---

### 2.3. Tabela: `gold_recomendacao_decisao_sespa`
* **Caminho:** `data/gold/gold_recomendacao_decisao_sespa.parquet`
* **Granularidade declarada:** Uma linha por município por mês do período de teste operacional (Setembro a Novembro de 2023).
* **Chave Primária Composta:** `codigo_ibge` + `ano_mes_t0` (Verificada: 0 duplicatas).

| Coluna | Tipo | Domínio Válido | Origem | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `probabilidade_risco` | `float64` | Intervalo `[0.0, 1.0]` | Modelo Random Forest | Probabilidade estimada pelo modelo de o município colapsar no mês seguinte. |
| `decisao_recomendada` | `string` | Categorias prescritivas | Regra de Decisão SESPA | Recomendação acionável de suporte à decisão: *"Alerta Alto: Envio Imediato de Kit Completo"*, *"Alerta Médio"* ou *"Monitoramento de Rotina"*. |
