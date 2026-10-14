# Projeto Integrador — Da Ingestão à Decisão

## 📌 Contexto e Objetivo
Este projeto implementa um pipeline de dados ponta a ponta construído sobre a **Arquitetura Medalhão (Bronze, Silver e Gold)** com foco na tomada de decisão em políticas públicas de saúde e meio ambiente no estado do **Pará**.

O objetivo é correlacionar o histórico de **focos de queimadas (INPE)** e indicadores populacionais (**IBGE**) com as **internações por doenças respiratórias (DataSUS)**, permitindo antecipar cenários de sobrecarga hospitalar durante os períodos de estiagem na Amazônia.

---

## 🎯 Pergunta de Decisão do Projeto
> *"Cruzando as bases do **INPE (Focos de Calor)**, **DataSUS (Internações Respiratórias)** e **IBGE (População Municipal)**, identificamos os municípios com maior risco de sobrecarga hospitalar após picos de queimadas. Recomendamos que a **Secretaria de Estado de Saúde Pública do Pará (SESPA)** realize a **alocação antecipada de lotes de medicamentos broncodilatadores, oxigênio e reforço de equipes médicas** nas regiões prioritárias antes do ápice da estiagem, mitigando internações graves e óbitos evitáveis."*

* **Decisor:** Secretaria de Estado de Saúde Pública do Pará (SESPA).
* **Ação concreta:** Distribuição preventiva de insumos respiratórios e ampliação de leitos de retaguarda.
* **Custo do Falso Positivo:** Custo logístico de remanejamento de insumos estocáveis para municípios que não atingiram o limiar crítico.
* **Custo do Falso Negativo:** Desabastecimento de insumos, atraso no atendimento de emergência e sobrecarga da rede hospitalar.

---

## 🏛️ Arquitetura Medalhão

* **Bronze:** Armazenamento bruto dos dados provenientes das fontes públicas (imutável, com metadados técnicos de rastreabilidade: timestamp, sistema de origem, identificador de carga e hash do registro).
* **Silver:** Dados tipados, padronizados, com deduplicação, tratamento de valores nulos e integridade referencial por código IBGE do município. Registros inconsistentes são direcionados para a **Quarentena**.
* **Gold:** Tabelas analíticas agregadas por município e período temporal (granularidade estrita), indicadores normalizados por 100 mil habitantes e dataset pronto para modelagem preditiva (*ML-Ready*).

---

## 📁 Estrutura do Repositório

```text
├── data/                  # Estrutura local de dados (não versionada no Git)
│   ├── bronze/            # Dados brutos com metadados de ingestão
│   ├── silver/            # Dados limpos e padronizados
│   ├── gold/              # Tabelas analíticas e bases ML-Ready
│   └── quarantine/        # Registros que falharam nas regras de validação
├── docs/                  # Dicionário de dados e documentação do projeto
├── notebooks/             # Notebooks de análise exploratória e validação
├── src/                   # Código-fonte modular do pipeline
│   ├── ingestion/         # Módulos de ingestão (API REST, arquivos, banco)
│   ├── processing/        # Transformações Bronze -> Silver -> Gold
│   └── utils/             # Utilitários de hash, logging e metadados
├── .gitignore             # Regras de exclusão de dados e ambiente
├── README.md              # Documentação principal e guia de execução
└── requirements.txt       # Dependências com versões fixadas
```

---

## 🚀 Como Executar

1. **Clonar o repositório:**
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd "Projeto Isaac"
   ```

2. **Criar e ativar o ambiente virtual:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # No Windows: venv\Scripts\activate
   ```

3. **Instalar dependências:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🤖 Declaração de Uso de IA
Ferramentas de Inteligência Artificial Generativa foram utilizadas como assistente de engenharia para estruturação inicial do repositório, boas práticas de pipeline e geração de boilerplate de código. Todo o código, regras de negócio e validações foram revisados e são de pleno domínio da equipe.
