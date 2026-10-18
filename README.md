# Projeto Integrador — Da Ingestão à Decisão

## 📌 Contexto e Objetivo
Este projeto implementa um pipeline de dados ponta a ponta construído sobre a **Arquitetura Medalhão (Bronze, Silver e Gold)** com foco na tomada de decisão em políticas públicas de saúde e meio ambiente no estado do **Pará**.

O objetivo é investigar se o histórico de **focos de queimadas (INPE)** e indicadores populacionais (**IBGE**) ajudam a antecipar, no mês seguinte, a sobrecarga hospitalar por **Síndrome Respiratória Aguda Grave, casos hospitalizados (SRAG, OpenDataSUS)** nos municípios do Pará.

**Resultado principal (Pará, 2023):** o histórico recente de casos de cada município prevê a sobrecarga; os focos de calor **não agregaram poder preditivo mensurável**. O resultado, as comparações e as limitações estão em [`docs/requisito_ml_ready_decisao.md`](docs/requisito_ml_ready_decisao.md).

---

## 🎯 Pergunta de Decisão do Projeto (Template Oficial Preenchido)
> *"Cruzando as bases do **INPE (focos de calor)**, **OpenDataSUS (SRAG hospitalizado)** e **IBGE (população do Censo 2022)**, identificamos que o risco de sobrecarga por SRAG no mês seguinte é previsto principalmente pelo histórico recente de casos de cada município (importância somada de 61,6%, contra 9,1% dos focos de calor), e os focos de calor não agregaram poder preditivo neste recorte (Pará, 2023). Recomendamos que a **Secretaria de Estado de Saúde Pública do Pará (SESPA)** envie **kits preventivos de insumos respiratórios** nos próximos **30 dias**, priorizando os **60 municípios com score ≥ 0,10 em nov/2023**. Se agir, o ganho esperado é reduzir o custo esperado em R$ 1.760.000 frente a não agir (de R$ 2.745.000 para R$ 985.000 no teste) e em R$ 313.500 (24,1%) frente a alertar todos os municípios; se errarmos, cada alerta falso custa R$ 3.500 e cada município com sobrecarga não alertado custa R$ 45.000 (premissas do grupo)."*

*Números do teste de set–nov/2023, gerados em `docs/requisito_ml_ready_decisao.md` (podem mudar se o pipeline for reexecutado com outra versão da fonte).*

* **Decisor:** Secretaria de Estado de Saúde Pública do Pará (SESPA).
* **Ação concreta:** Distribuição preventiva de kits de insumos respiratórios (oxigênio e broncodilatadores) antes do ápice da estiagem.
* **Custo do Falso Positivo:** R$ 3.500,00 por município-mês (custo logístico de remanejamento fluvial/terrestre de kits de insumos estocáveis). **Premissa do grupo, sem fonte pública.**
* **Custo do Falso Negativo:** R$ 45.000,00 por município-mês (resgate em UTI aérea de emergência, leito intensivo e risco iminente de óbito evitável). **Premissa do grupo, sem fonte pública;** o relatório traz uma tabela de sensibilidade a essa premissa.
* **Limiar Adotado:** 0,10, escolhido por menor custo esperado em validação cronológica **dentro do treino** (sem olhar o teste). O score do Random Forest **não é calibrado**. No teste (set–nov/2023): recall 82,0%, precisão 26,3% e custo de R$ 985.000, contra R$ 1.298.500 de alertar todos, R$ 1.188.000 do modelo só com população e R$ 988.000 do modelo sem focos de calor. Com 61 positivos no teste, a evidência é modesta e a conclusão depende da premissa de custo.

---

## 🏛️ Arquitetura Medalhão

* **Bronze:** Armazenamento bruto dos dados das 3 fontes públicas (imutável, com metadados técnicos de rastreabilidade: `ingestion_timestamp`, `source_system`, `source_object`, `load_id` e `record_hash` SHA-256).
* **Silver:** Dados tipados, padronizados, com deduplicação exata por hash do registro, tratamento de valores nulos e integridade referencial por código IBGE do município. Os casos de SRAG, que chegam por pessoa, são **agregados por município e mês já na Silver, sem nenhum dado individual**. Registros fora da contagem são direcionados para a **Quarentena**, com o motivo.
* **Gold:** Tabelas analíticas agregadas por município e período temporal (granularidade estrita com PKs verificadas sem duplicatas), taxas normalizadas por 100 mil habitantes, base **ML-Ready** (com garantia anti-vazamento) e tabela prescritiva de decisão.

---

## 📁 Estrutura do Repositório

```text
├── data/                                 # Dados locais (ignorado no Git via .gitignore)
│   ├── bronze/                           # Dados brutos com metadados de ingestão
│   │   ├── ibge/                         # Parquet da API IBGE Localidades/Censo
│   │   ├── inpe/                         # Parquet dos arquivos de Queimadas
│   │   └── srag/                         # Parquet do SRAG (OpenDataSUS), uma carga por snapshot
│   ├── landing/srag/                     # CSV do SRAG baixado da fonte (~300 MB)
│   ├── checkpoints/                      # Checkpoint por hash da ingestão do SRAG
│   ├── silver/                           # Tabelas limpas, integradas e dimensões
│   ├── gold/                             # Tabelas analíticas, ML-Ready e decisão
│   └── quarantine/                       # Isolamento de registros inconsistentes
├── docs/                                 # Documentação técnica completa
│   ├── dicionario_de_dados.md            # Dicionário de dados das tabelas Silver e Gold
│   ├── relatorio_join_silver.md          # Auditoria de integridade do Join (Casados vs Órfãos)
│   └── requisito_ml_ready_decisao.md     # Checklist anti-vazamento, baseline e custos
├── notebooks/                            # Notebooks analíticos executivos
├── scripts/                              # demo_idempotencia.py (duas execuções e comparação)
├── src/                                  # Código-fonte modular do pipeline
│   ├── ingestion/                        # Módulos de ingestão (API REST e arquivos)
│   ├── processing/                       # Transformações Bronze -> Silver -> Gold
│   └── utils/                            # Metadados, hash, quarentena e watermark
├── run_pipeline.py                       # Orquestrador ponta a ponta (1 comando)
├── app.py                                # Dashboard Streamlit (consome a camada Gold)
├── .gitignore                            # Proteção para nunca versionar dados
├── README.md                             # Documentação principal
└── requirements.txt                      # Dependências com versões fixadas
```

---

## 🚀 Como Executar o Pipeline do Zero (Reprodutibilidade)

**Pré-requisito:** Python 3.9 a 3.12 (testado em 3.11 e 3.12). As versões fixadas em `requirements.txt` não têm pacotes prontos para Python 3.13.

1. **Clonar o repositório:**
   ```bash
   git clone https://github.com/KayuryC/Vigilancia-Ambiental-Saude-PA.git
   cd Vigilancia-Ambiental-Saude-PA
   ```

2. **Criar e ativar o ambiente virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # No Windows: .venv\Scripts\activate
   ```

3. **Instalar dependências fixadas:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Executar o pipeline completo (Bronze ➔ Silver ➔ Gold ➔ Decisão):**
   ```bash
   python run_pipeline.py
   ```
   Na primeira execução, o pipeline baixa o CSV do SRAG (~300 MB) para `data/landing/srag/`. Se você já tiver o arquivo `INFLUD23-23-03-2026.csv`, copie-o para essa pasta e o download é pulado.


5. **Demonstrar a idempotência (duas execuções seguidas e comparação das tabelas):**
   ```bash
   python scripts/demo_idempotencia.py
   ```

6. **Abrir o dashboard:**
   ```bash
   streamlit run app.py
   ```

---

## 🛡️ Atendimento aos Requisitos Obrigatórios da Avaliação

1. **Requisito 1 — Fontes e Cruzamento:** 3 bases públicas reais de 3 instituições (IBGE, INPE e Ministério da Saúde/OpenDataSUS), 2 formatos (API REST JSON e arquivos CSV), com chave comum `codigo_ibge` + `ano_mes`. Fontes, URLs, datas de coleta e licenças em [`docs/dicionario_de_dados.md`](docs/dicionario_de_dados.md). Relatório de join auditado em [`docs/relatorio_join_silver.md`](docs/relatorio_join_silver.md).
2. **Requisito 2 — Ingestão:** formas implementadas:
   * **API REST (IBGE):** com retry, backoff exponencial, paginação e descompressão gzip.
   * **Arquivo (INPE):** tipagem estrita, encoding `utf-8` e validação geográfica.
   * **Arquivo com checkpoint (OpenDataSUS, SRAG):** CSV de ~300 MB lido em pedaços (separador `;`, encoding detectado, tudo como texto na Bronze), download com retry e backoff, **checkpoint por hash SHA-256 do arquivo** (reexecutar não cria nova carga), quarentena para linhas malformadas e para registros fora da contagem.
   * **Idempotência demonstrável:** `python scripts/demo_idempotencia.py` executa o pipeline duas vezes e compara linhas, duplicatas na chave e hash do conteúdo de cada tabela Silver e Gold.
   * **Nota de integridade:** a versão inicial do projeto usava um banco relacional alimentado por dados **sintéticos**, e essa fonte foi removida porque o enunciado exige dados reais. O histórico permanece no Git. Não há, hoje, fonte relacional no pipeline.
3. **Requisito 3 — Medalhão:** Camadas Bronze (com metadados e hash SHA-256), Silver (deduplicada, tratada e com chaves primárias verificadas por asserção) e Gold (indicadores e ML-Ready sem limpeza adicional).
4. **Requisito 4 — Reprodutibilidade:** Repositório Git com commits atômicos por processo, sem dados versionados, requirements fixados e dicionário de dados detalhado em [`docs/dicionario_de_dados.md`](docs/dicionario_de_dados.md).
5. **Requisito 5 — Base ML-Ready e Anti-Vazamento:** Split temporal (Jan-Ago vs Set-Nov), baseline trivial implementado, limiar do rótulo calculado só com o treino, sete estratégias comparadas por custo (não alertar, alertar todos, regra de focos, persistência, Random Forest só com população, sem focos de calor e completo), limiar de decisão escolhido por validação cronológica dentro do treino (score do Random Forest **não calibrado**) e checklist anti-vazamento respondido item a item, incluindo o item **não atendido** (o split não separa por grupo, com justificativa), em [`docs/requisito_ml_ready_decisao.md`](docs/requisito_ml_ready_decisao.md).
6. **Requisito 6 — Decisão:** Decisor claro (SESPA), ação prática de envio de insumos, limiar justificado, trade-off explícito de custos de FP vs FN (premissas declaradas, com tabela de sensibilidade) e limitações metodológicas documentadas em [`docs/requisito_ml_ready_decisao.md`](docs/requisito_ml_ready_decisao.md).

---

## 👥 Integrantes da Equipe e Contribuições
* **Fernando Fonseca** ([@fernandofonsecadev](mailto:fernandofonsecadev@gmail.com)) — Auditoria de conformidade com os requisitos, especificação de limitações dos dados, registro de licenças/fontes públicas e guia operacional de decisão.
* **Kayury Carneiro** ([@kayocarneiro77](mailto:kayocarneiro77@gmail.com)) — Engenharia do pipeline medalhão, ingestão de dados, modelagem preditiva ML-Ready e dashboard interativo Streamlit.
* **Nathalia Gomes** ([@naathggg](mailto:naathgg213@gmail.com)) - Migração do pipeline para a base real SRAG (ingestão com checkpoint, Silver agregada sem dados pessoais e quarentena), teste de idempotência e avaliação do modelo (baselines e limiar por custo).

---

## 🤖 Declaração de Uso de IA
Ferramentas de IA generativa foram utilizadas neste projeto. A declaração é feita por integrante, com a ferramenta, a finalidade e os arquivos envolvidos. Todo integrante deve saber explicar qualquer trecho entregue.

* **Nathalia Gomes: Claude (Anthropic).** Usado para auditar o repositório contra o enunciado; escrever a ingestão e a Silver do SRAG (`src/ingestion/ingest_srag_opendatasus.py`, `src/processing/process_silver_srag.py`), o script `scripts/demo_idempotencia.py` e a reescrita do módulo de ML-Ready e decisão (`src/processing/process_gold_ml_ready.py`); e redigir as atualizações de README, dicionário de dados e dashboard desta versão. Os resultados foram reproduzidos pela integrante executando o pipeline com os dados reais.
* **Kayury Carneiro: Antigravity / Gemini (Google) e Claude (Anthropic).** Usado para assistência técnica na refatoração e estilização executiva do dashboard (`app.py`), estruturação modular das camadas Medalhão (`src/ingestion/`, `src/processing/`, `run_pipeline.py`), validação de idempotência, testes de não-vazamento temporal e geração dos gráficos interativos Plotly. Todas as implementações, regras de quarentena, métricas de negócio e lógicas operacionais foram validadas e são de pleno domínio do integrante.
* **Fernando Fonseca:** `[PENDENTE: informar ferramenta, finalidade e arquivos, ou declarar que não usou]`

