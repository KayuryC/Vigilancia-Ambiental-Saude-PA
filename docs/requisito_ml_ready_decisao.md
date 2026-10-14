# Documentação da Base ML-Ready e Suporte à Decisão (Requisitos 5 e 6)

Data de geração: 14/10/2026 19:18:42 UTC

## 1. Especificação Formal da Modelagem (Requisito 5)

| Elemento | Especificação Documentada |
| :--- | :--- |
| **Decisor** | Secretaria de Estado de Saúde Pública do Pará (SESPA) |
| **Ação Concreta** | Envio preventivo de Kits de Insumos Respiratórios (cilindros de oxigênio e broncodilatadores) antes do ápice da estiagem |
| **Label ($Y$)** | $1$ (Risco de Sobrecarga Hospitalar) se a taxa no próximo mês for $\ge$ percentil 75 histórico (47.92 intern/100k hab); $0$ caso contrário |
| **Regra de Rotulagem** | `label_sobrecarga_proximo_mes = (taxa_internacao_futura >= limiar_p75)` calculada via `shift(-1)` temporal |
| **Coorte** | Todos os 144 municípios do Pará em meses com histórico completo e horizonte futuro observável |
| **Ponto de Corte ($t_0$)** | Último dia de cada mês calendário $m$ (instante em que a decisão de despacho logístico é congelada) |
| **Janela de Observação** | Período estritamente anterior ou igual a $t_0$ (features de queimadas, internações e dados censitários até o mês $m$) |
| **Janela de Predição** | Mês imediatamente posterior $m + 1$ (horizonte de 30 dias à frente para atuação da saúde pública) |
| **Split Adotado** | **Temporal Estrito:** Treino = Janeiro a Agosto de 2023; Teste = Setembro a Novembro de 2023 (evita data leakage sazonal) |
| **Baseline** | Modelo Trivial de Regra: Prever alerta ($1$) se o município teve focos no mês $t_0$ durante o período de estiagem |
| **Métrica Principal** | **$F_2$-Score e Recall:** Em saúde pública, minimizar Falsos Negativos (deixar um município desabastecido) tem prioridade sobre Falsos Positivos |

---

## 2. Checklist Anti-Vazamento (Zero Data Leakage)

- [x] **Toda feature existia antes de $t_0$?**  
  *Sim. Nenhuma variável agregada utiliza dados do mês $m+1$. Todas as covariáveis derivam exclusivamente do histórico do mês $m$ ou de lags anteriores.*
- [x] **As agregações foram calculadas apenas com dados anteriores a $t_0$?**  
  *Sim. Os agregados mensais e lags foram calculados de forma causal estrita.*
- [x] **O split respeita tempo e grupo?**  
  *Sim. O split é puramente cronológico (Treino: Jan-Ago / Teste: Set-Nov). O futuro não vazou para o treino.*
- [x] **Scalers, encoders e modelos foram ajustados somente no treino?**  
  *Sim. O modelo Random Forest foi ajustado (fit) apenas nos meses de Jan-Ago e avaliado nos meses subsequentes.*
- [x] **Métricas honestas e sem overfitting:**  
  *As métricas refletem desempenho generalizável no período de seca.*

---

## 3. Avaliação Comparativa: Baseline vs. Modelo

| Modelo | Recall (Sensibilidade) | Precisão | $F_2$-Score |
| :--- | :---: | :---: | :---: |
| **Baseline Trivial (Regra)** | 88.29% | 24.32% | 57.85% |
| **Modelo Random Forest (Calibrado)** | **80.18%** | **78.76%** | **79.89%** |

### Matriz de Confusão no Teste (Limiar = 0.4):
* **Verdadeiros Positivos (TP):** 89 municípios sob risco identificados a tempo.
* **Falsos Negativos (FN):** 22 municípios críticos que deixaram de ser alertados.
* **Falsos Positivos (FP):** 24 municípios alertados preventivamente sem sobrecarga severa.
* **Verdadeiros Negativos (TN):** 297 municípios corretamente mantidos em monitoramento de rotina.

---

## 4. Análise Econômico-Sanitária de Decisão (Requisito 6)

* **Custo do Falso Positivo (FP):** R$ 3,500.00 por município (custo logístico de remanejamento fluvial/terrestre de kits de insumos estocáveis).
* **Custo do Falso Negativo (FN):** R$ 45,000.00 por município (resgate em UTI aérea de emergência, leito intensivo e risco iminente de óbito evitável).
* **Justificativa do Limiar (0.4):** Como o custo de um falso negativo é mais de 12 vezes superior ao de um falso positivo, o limiar de decisão foi calibrado para priorizar o **Recall (80.18%)**, garantindo cobertura protetiva máxima à população vulnerável.

---

## 5. A Frase de Decisão do Projeto (Template Oficial)
> *"Cruzando as bases do **INPE (Focos de Calor)**, **DataSUS (Internações Respiratórias)** e **IBGE (População do Censo 2022)**, identificamos os municípios com alto risco de sobrecarga hospitalar. Recomendamos que a **Secretaria de Estado de Saúde Pública do Pará (SESPA)** envie **Kits Preventivos de Insumos Respiratórios** nos próximos **30 dias**, priorizando os **municípios com risco $\ge 70\%$**. Se agir, o ganho esperado é a **garantia de atendimento de emergência a 89 municípios críticos**; se errarmos, o custo de um falso positivo é de **R$ 3.500,00** em logística estocável, versus o risco inaceitável de desabastecimento de **R$ 45.000,00** por caso negligenciado."*
