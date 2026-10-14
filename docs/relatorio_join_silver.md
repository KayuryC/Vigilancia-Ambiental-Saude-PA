# Relatório de Auditoria de Cruzamento das Bases (Requisito 1)

Data de execução: 14/10/2026 18:41:56 UTC

## 1. Definição da Chave de Cruzamento
* **Chave Primária Composta:** `codigo_ibge` (código de 7 dígitos do município) e `ano_mes` (formato YYYY-MM).
* **Entidades Envolvidas:**
  1. **IBGE:** Dimensão canônica dos 144 municípios do Pará e população do Censo 2022.
  2. **INPE (BDQueimadas):** Agregações mensais de focos de queimada.
  3. **DataSUS (SIH):** Agregações mensais de internações por causas respiratórias (CID-10 J00-J99).

---

## 2. Contabilidade do Join (Casados vs. Órfãos)

| Base de Dados | Total Registros | Casados na Grade | Órfãos | % Casamento | Tratamento de Órfãos |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Grade Canônica (IBGE x Meses)** | 1728 | 1728 | 0 | 100.0% | Base canônica estrutural |
| **INPE (Focos Mensais)** | 1044 | 1044 | 0 | 100.0% | Encaminhados à Quarentena |
| **DataSUS (Internações Mensais)** | 1727 | 1727 | 0 | 100.0% | Encaminhados à Quarentena |

---

## 3. Justificativa Técnica do Tratamento dos Dados
1. **Preservação da Grade Canônica:**
   * O pipeline estabeleceu uma grade contínua de 1.728 observações (144 municípios × 12 meses).
   * Municípios que não registraram focos de calor ou internações em determinado mês recebem **valor zero** (e não nulo), refletindo a realidade fática de ausência de eventos no período.
2. **Tratamento de Órfãos:**
   * Qualquer registro de internação ou foco cujo código IBGE não pertença à malha oficial do estado do Pará foi isolado na camada de **Quarentena** (`data/quarantine/`), impedindo corrupção nos cálculos da camada analítica.
3. **Verificação de Duplicatas:**
   * A chave composta `['codigo_ibge', 'ano_mes']` foi testada e possui **zero duplicatas**, assegurando granularidade estrita.
