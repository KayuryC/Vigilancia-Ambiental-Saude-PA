# Projeto Integrador — Da Ingestão à Decisão

## 📌 Contexto e Objetivo
Este projeto implementa um pipeline de dados ponta a ponta construído sobre a **Arquitetura Medalhão (Bronze, Silver e Gold)** com foco na tomada de decisão em políticas públicas de saúde e meio ambiente no estado do **Pará**.

O objetivo é correlacionar o histórico de **focos de queimadas (INPE)** e indicadores populacionais (**IBGE**) com as **internações por doenças respiratórias (DataSUS)**, permitindo antecipar cenários de sobrecarga hospitalar durante os períodos de estiagem na Amazônia.

---

## 🎯 Pergunta de Decisão do Projeto (Template Oficial Preenchido)
> *"Cruzando as bases do **INPE (Focos de Calor)**, **DataSUS (Internações Respiratórias)** e **IBGE (População do Censo 2022)**, identificamos os municípios com alto risco de sobrecarga hospitalar. Recomendamos que a **Secretaria de Estado de Saúde Pública do Pará (SESPA)** envie **Kits Preventivos de Insumos Respiratórios** nos próximos **30 dias**, priorizando os **municípios com risco $\ge 70\%$**. Se agir, o ganho esperado é a **garantia de atendimento de emergência a 89 municípios críticos**; se errarmos, o custo de um falso positivo é de **R$ 3.500,00** em logística estocável, versus o risco inaceitável de desabastecimento de **R$ 45.000,00** por caso negligenciado."*

* **Decisor:** Secretaria de Estado de Saúde Pública do Pará (SESPA).
* **Ação concreta:** Distribuição preventiva de kits de insumos respiratórios (oxigênio e broncodilatadores) antes do ápice da estiagem.
* **Custo do Falso Positivo:** R$ 3.500,00 por município (custo logístico de remanejamento fluvial/terrestre de kits de insumos estocáveis).
* **Custo do Falso Negativo:** R$ 45.000,00 por município (resgate em UTI aérea de emergência, leito intensivo e risco iminente de óbito evitável).
* **Limiar Adotado:** 0.40 calibrado para priorizar o **Recall (80.18%)** e $F_2$-Score (79.89%), dado que o custo de uma falha é 12x mais gravoso à saúde pública.

---

## 🏛️ Arquitetura Medalhão

* **Bronze:** Armazenamento bruto dos dados das 3 fontes públicas (imutável, com metadados técnicos de rastreabilidade: `ingestion_timestamp`, `source_system`, `source_object`, `load_id` e `record_hash` SHA-256).
* **Silver:** Dados tipados, padronizados, com deduplicação semântica, tratamento de valores nulos e integridade referencial por código IBGE do município. Registros inconsistentes são direcionados para a **Quarentena**.
* **Gold:** Tabelas analíticas agregadas por município e período temporal (granularidade estrita com PKs verificadas sem duplicatas), taxas normalizadas por 100 mil habitantes, base **ML-Ready** (com garantia anti-vazamento) e tabela prescritiva de decisão.

---

## 📁 Estrutura do Repositório

```text
├── data/                                 # Dados locais (ignorado no Git via .gitignore)
│   ├── bronze/                           # Dados brutos com metadados de ingestão
│   │   ├── ibge/                         # Parquet da API IBGE Localidades/Censo
│   │   ├── inpe/                         # Parquet dos arquivos de Queimadas
│   │   └── datasus/                      # Parquet do banco relacional de internações
│   ├── silver/                           # Tabelas limpas, integradas e dimensões
│   ├── gold/                             # Tabelas analíticas, ML-Ready e decisão
│   └── quarantine/                       # Isolamento de registros inconsistentes
├── docs/                                 # Documentação técnica completa
│   ├── dicionario_de_dados.md            # Dicionário de dados das tabelas Silver e Gold
│   ├── relatorio_join_silver.md          # Auditoria de integridade do Join (Casados vs Órfãos)
│   └── requisito_ml_ready_decisao.md     # Checklist anti-vazamento, baseline e custos
├── notebooks/                            # Notebooks analíticos executivos
├── src/                                  # Código-fonte modular do pipeline
│   ├── ingestion/                        # Módulos de ingestão (API REST, arquivo, relacional)
│   ├── processing/                       # Transformações Bronze -> Silver -> Gold
│   └── utils/                            # Metadados, hash, quarentena e watermark
├── run_pipeline.py                       # Orquestrador ponta a ponta (1 comando)
├── .gitignore                            # Proteção para nunca versionar dados
├── README.md                             # Documentação principal
└── requirements.txt                      # Dependências com versões fixadas
```

---

## 🚀 Como Executar o Pipeline do Zero (Reprodutibilidade)

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

---

## 🛡️ Atendimento aos Requisitos Obrigatórios da Avaliação

1. **Requisito 1 — Fontes e Cruzamento:** 3 bases públicas reais (IBGE, INPE e DataSUS), 2 formatos distintos (API REST JSON e Arquivo CSV/ZIP), com chave comum `codigo_ibge` + `ano_mes`. Relatório de join auditado em [`docs/relatorio_join_silver.md`](docs/relatorio_join_silver.md).
2. **Requisito 2 — Ingestão:** 3 formas distintas implementadas:
   * **API REST (IBGE):** com retry, backoff exponencial, paginação e descompressão gzip.
   * **Arquivo (INPE):** tipagem estrita, encoding `utf-8` e validação geográfica.
   * **Banco Relacional (DataSUS):** extração incremental via **Watermark** (`updated_at`), com **idempotência comprovada** e **quarentena** ativa em `data/quarantine/`.
3. **Requisito 3 — Medalhão:** Camadas Bronze (com metadados e hash SHA-256), Silver (deduplicada, tratada e com chaves primárias verificadas por asserção) e Gold (indicadores e ML-Ready sem limpeza adicional).
4. **Requisito 4 — Reprodutibilidade:** Repositório Git com commits atômicos por processo, sem dados versionados, requirements fixados e dicionário de dados detalhado em [`docs/dicionario_de_dados.md`](docs/dicionario_de_dados.md).
5. **Requisito 5 — Base ML-Ready e Anti-Vazamento:** Split temporal (Jan-Ago vs Set-Nov), baseline trivial implementado, modelo Random Forest calibrado, e checklist anti-leakage documentado em [`docs/requisito_ml_ready_decisao.md`](docs/requisito_ml_ready_decisao.md).
6. **Requisito 6 — Decisão:** Decisor claro (SESPA), ação prática de envio de insumos, limiar justificado e trade-off explícito de custos de FP vs FN.

---

## 🤖 Declaração de Uso de IA
Ferramentas de Inteligência Artificial Generativa foram utilizadas como assistente técnico de engenharia de software e estruturação do projeto. Todo o código, regras epidemiológicas, validações e decisões foram revisados e são de pleno domínio e autoria da equipe.
