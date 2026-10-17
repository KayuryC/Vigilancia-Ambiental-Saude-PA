# Documentação da Base ML-Ready e Suporte à Decisão (Requisitos 5 e 6)

Data de geração: 17/10/2026 12:08:19 UTC  
Revisão e Auditoria Técnica: 16/10/2026 (seções 6 e 7 elaboradas por Fernando Fonseca e incorporadas ao gerador).

> Este arquivo é **gerado** por `src/processing/process_gold_ml_ready.py`. Para alterar o texto, edite o gerador.

---

## 1. Especificação Formal da Modelagem (Requisito 5)

| Elemento | Especificação Documentada |
| :--- | :--- |
| **Decisor** | Secretaria de Estado de Saúde Pública do Pará (SESPA) |
| **Ação Concreta** | Envio preventivo de Kits de Insumos Respiratórios (cilindros de oxigênio e broncodilatadores) |
| **Label ($Y$)** | $1$ (risco de sobrecarga por SRAG) se a taxa de casos hospitalizados de SRAG no mês seguinte for $\ge$ 4,92 casos/100 mil hab (percentil 75 da taxa futura **calculado só com o período de treino**); $0$ caso contrário |
| **Regra de Rotulagem** | `label_sobrecarga_proximo_mes = (taxa_internacao_futura >= limiar_p75_treino)`, com `taxa_internacao_futura` obtida por `shift(-1)` dentro de cada município |
| **Coorte** | Os 144 municípios do Pará, em todos os meses com mês seguinte observável (dez/2023 não tem rótulo e fica fora) |
| **Ponto de Corte ($t_0$)** | Fim de cada mês $m$: instante em que as features são congeladas |
| **Janela de Observação** | Meses $\le m$ (focos de calor, casos de SRAG e população do Censo 2022) |
| **Janela de Predição** | Mês $m+1$ |
| **Split Adotado** | **Temporal:** treino com $t_0$ de jan a ago/2023; teste com $t_0$ de set a nov/2023. Limiar de decisão escolhido por validação cronológica dentro do treino |
| **Baselines** | Não alertar ninguém; alertar todos; regra de focos na estiagem; persistência (taxa atual já acima do limiar); Random Forest só com população; Random Forest sem focos de calor |
| **Métrica Principal** | **Custo esperado total (R$)** com a matriz de custos da seção 4. Recall, precisão e $F_2$ são métricas de apoio. Com apenas 14,1% de positivos no teste, acurácia seria enganosa |

---

## 2. Checklist Anti-Vazamento

- [x] **Toda feature existia antes de $t_0$?**  
  *Sim. Nenhuma variável usa dados do mês $m+1$. Todas as covariáveis vêm do mês $m$ ou de lags anteriores ($m-1$), calculados por `groupby('codigo_ibge').shift(1)`.*
- [x] **As agregações foram calculadas apenas com dados anteriores a $t_0$?**  
  *Sim para as features. O limiar do rótulo (percentil 75) é calculado apenas com linhas do período de treino. O limiar de decisão é escolhido por validação cronológica dentro do treino, ajustando o modelo só com meses anteriores ao mês validado.*
- [ ] **O split respeita tempo e grupo?**  
  *Respeita o tempo. **Não separa por grupo, de propósito:** os mesmos municípios aparecem no treino e no teste, porque o uso real é prever o mês seguinte dos mesmos municípios. Efeito colateral: o modelo pode aprender características fixas de cada município (como a população). Por isso o modelo só com população está na comparação da seção 3.*
- [x] **Scalers, encoders e imputadores foram ajustados somente no treino?**  
  *Não há scaler nem encoder (Random Forest). Não há imputação estatística: município sem notificação no mês tem 0 casos (regra de negócio da Silver). O modelo e o limiar de decisão são ajustados somente com dados de treino.*
- [x] **Métrica alta demais?**  
  *Não: recall 82,0% e precisão 26,3%. A amostra é pequena (teste: 61 positivos em 432 linhas), então as diferenças entre estratégias têm incerteza grande.*

---

## 3. Avaliação Comparativa (conjunto de teste, set a nov/2023)

| Estratégia | Alertas | Recall | Precisão | $F_2$ | FP | FN | Custo esperado |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | ---: |
| Não alertar ninguém | 0 | 0,0% | 0,0% | 0,0% | 0 | 61 | R$ 2.745.000 |
| Alertar todos | 432 | 100,0% | 14,1% | 45,1% | 371 | 0 | R$ 1.298.500 |
| Regra: foco de calor na estiagem (baseline original) | 403 | 96,7% | 14,6% | 45,6% | 344 | 2 | R$ 1.294.000 |
| Persistência: taxa atual já acima do limiar | 71 | 54,1% | 46,5% | 52,4% | 38 | 28 | R$ 1.393.000 |
| Random Forest só com população | 345 | 93,4% | 16,5% | 48,4% | 288 | 4 | R$ 1.188.000 |
| Random Forest sem focos de calor | 274 | 91,8% | 20,4% | 54,1% | 218 | 5 | R$ 988.000 |
| **Random Forest completo** | 190 | 82,0% | 26,3% | 57,6% | 140 | 11 | R$ 985.000 |

Estratégia de menor custo no teste: **Random Forest completo** (R$ 985.000).

O Random Forest completo teve custo R$ 985.000, **menor** que o da melhor referência (Random Forest só com população: R$ 1.188.000): diferença de R$ 203.000 (17,1%). Com apenas 61 positivos no teste, a evidência é modesta.

### 3.1. Matriz de confusão do Random Forest completo (limiar = 0,10)
* **Verdadeiros Positivos (TP):** 50 municípios-mês com sobrecarga alertados.
* **Falsos Negativos (FN):** 11 municípios-mês com sobrecarga que não foram alertados.
* **Falsos Positivos (FP):** 140 municípios-mês alertados sem sobrecarga.
* **Verdadeiros Negativos (TN):** 231 municípios-mês corretamente mantidos em rotina.

### 3.2. Os focos de calor ajudam a prever?
* Correlação de Pearson entre focos de calor e casos de SRAG no mesmo município-mês: **-0,043**.
* Importância somada das variáveis de focos de calor no Random Forest completo: **9,1%**.
* Variáveis mais importantes: `taxa_internacao_100k` (42,6%); `taxa_internacao_lag_1m` (19,0%); `internacoes_infantis` (10,1%); `internacoes_idosos` (8,5%).
* Retirar os focos de calor aumenta o custo em apenas R$ 3.000 (sem focos: R$ 988.000; com focos: R$ 985.000), menos que o custo de um único falso negativo (R$ 45.000): diferença indistinguível de ruído. **Neste recorte, os focos de calor não agregaram poder preditivo mensurável.**
* Modelo só com população: custo R$ 1.188.000, recall 93,4%, precisão 16,5%.

### 3.3. Qualidade do rótulo
* Média de 2,5 casos por município-mês; 56,7% dos município-mês têm zero casos.
* 19,7% dos positivos do teste têm no máximo 1 caso no mês seguinte: com contagens tão pequenas, a taxa por 100 mil é instável e o rótulo mistura sinal e ruído.

---

## 4. Análise Econômico-Sanitária de Decisão (Requisito 6)

* **Custo do Falso Positivo (FP):** R$ 3.500 por município-mês (logística de envio de kits).
* **Custo do Falso Negativo (FN):** R$ 45.000 por município-mês (resgate, leito intensivo, risco de óbito evitável).
* **Estes valores são premissas do grupo, sem fonte pública.** Devem ser substituídos por valores fornecidos pela SESPA antes de qualquer uso real.
* **Como o limiar foi escolhido:** menor custo esperado em validação cronológica dentro do treino (últimos 3 meses do treino, 432 linhas), sem olhar o teste. Resultado: **0,10**. Referência teórica para probabilidades calibradas: $c_{FP}/(c_{FP}+c_{FN})$ = 0,072. As probabilidades do Random Forest **não são calibradas**, por isso o limiar foi escolhido empiricamente.

### 4.1. Sensibilidade à premissa de custo

| Razão FN/FP | Estratégia de menor custo no teste | Custo | Custo do Random Forest completo |
| :---: | :--- | ---: | ---: |
| 1 | Não alertar ninguém | R$ 213.500 | R$ 528.500 |
| 3 | Persistência: taxa atual já acima do limiar | R$ 427.000 | R$ 605.500 |
| 5 | Persistência: taxa atual já acima do limiar | R$ 623.000 | R$ 682.500 |
| 10 | Random Forest completo | R$ 875.000 | R$ 875.000 |
| 12,9 (premissa atual) | Random Forest completo | R$ 985.000 | R$ 985.000 |
| 20 | Random Forest sem focos de calor | R$ 1.113.000 | R$ 1.260.000 |
| 30 | Random Forest sem focos de calor | R$ 1.288.000 | R$ 1.645.000 |

O Random Forest completo é a estratégia de menor custo apenas nas razões FN/FP de 10 e 12,9; nas demais razões testadas, outra estratégia custa menos. **A conclusão depende da premissa de custo: os valores reais da SESPA precisam ser obtidos antes de qualquer decisão.**

Os limiares dos modelos foram mantidos como escolhidos com a premissa atual; a tabela mostra quão frágil é a conclusão se a razão de custos for outra.

---

## 5. A Frase de Decisão do Projeto

> *"Cruzando as bases do **INPE (focos de calor)**, **OpenDataSUS (SRAG hospitalizado)** e **IBGE (população do Censo 2022)**, identificamos que o risco de sobrecarga por SRAG no mês seguinte é previsto principalmente pelo histórico recente de casos de cada município (importância somada de 61,6%, contra 9,1% dos focos de calor), e os focos de calor não agregaram poder preditivo neste recorte (Pará, 2023). Recomendamos que a **Secretaria de Estado de Saúde Pública do Pará (SESPA)** envie **kits preventivos de insumos respiratórios** nos próximos **30 dias**, priorizando os **60 municípios com score $\ge$ 0,10 em nov/2023**. Se agir, o ganho esperado é reduzir o custo esperado em R$ 1.760.000 frente a não agir (de R$ 2.745.000 para R$ 985.000 no teste) e em R$ 313.500 (24,1%) frente a alertar todos os municípios; se errarmos, cada alerta falso custa R$ 3.500 e cada município com sobrecarga não alertado custa R$ 45.000 (premissas do grupo)."*

---

## 6. Limitações dos Dados e Suposições do Modelo (Requisito 6)

Conforme exigido pelas diretrizes de integridade analítica, explicitamos as fronteiras de inferência do pipeline:

### 6.1. O que os dados NÃO permitem afirmar:
1. **Não comprovam causalidade:** o cruzamento mede associação e antecedência temporal no grão municipal, sem rastrear exposição individual à fumaça. Neste recorte, nem a associação estatística aparece (correlação de -0,043).
2. **Subnotificação e atraso no registro:** casos de municípios remotos podem ser digitados no SIVEP-Gripe com atraso, mascarando a velocidade real da sobrecarga. O campo de evolução do caso também pode estar incompleto para casos recentes.
3. **Fatores meteorológicos mediadores:** não há variáveis de dispersão atmosférica (ventos e precipitação do INMET). Uma queimada em município vizinho pode projetar fumaça sobre outro município.
4. **Um único ano e teste curto:** os dados cobrem apenas 2023 e o teste tem 3 meses (61 positivos). 74,0% dos focos do ano ocorrem nos meses de teste, ou seja, o treino vê pouco da estação de queimadas e não há como aprender a resposta sazonal com um ano só.
5. **SRAG não é toda internação respiratória:** o SIVEP-Gripe registra casos de Síndrome Respiratória Aguda Grave notificados (hospitalizados ou óbitos), não todas as internações por doenças respiratórias.
6. **Contagens pequenas:** média de 2,5 casos por município-mês e 56,7% de células vazias tornam a taxa por 100 mil instável, principalmente nos municípios pequenos.
7. **Custos são premissas:** os valores de FP e FN não têm fonte pública (ver seção 4 e a sensibilidade em 4.1).
8. **Residência não é local de atendimento:** os casos são atribuídos ao município de residência; pacientes de municípios sem hospital são atendidos em municípios vizinhos, onde a pressão assistencial efetiva ocorre.

### 6.2. O que seria necessário para afirmar com precisão diagnóstica:
* Dados de material particulado (PM2.5 e PM10) e de vento e precipitação do INMET/IBAMA.
* Dados de atenção primária (e-SUS / UBS), cobrindo atendimentos leves que antecedem a internação.
* Vários anos de dados (INPE e SIVEP-Gripe têm séries desde 2019) para treinar com ciclos sazonais completos e testar em um ano inteiro.
* Custos reais de remanejamento e de internação fornecidos pela SESPA.

---

## 7. Guia Operacional de Decisão Linha a Linha (Requisito 6)

A tabela `gold_recomendacao_decisao_sespa.parquet` deve ser lida pelo gestor de logística da SESPA da seguinte forma:

1. **`codigo_ibge` e `nome_municipio`:** identificação geográfica do destino da remessa.
2. **`ano_mes_t0`:** mês de corte. A remessa deve ser executada nos primeiros 5 dias úteis após $t_0$.
3. **`probabilidade_risco`:** score do Random Forest. **Não é uma probabilidade calibrada:** serve para ordenar municípios e comparar com o limiar, não para ser lido como "chance de X%".
4. **`decisao_recomendada`:**
   * **Score $\ge$ 0,70 (Alerta Alto):** despacho imediato de kit completo (oxigênio medicinal, concentradores e broncodilatadores) por transporte prioritário.
   * **0,10 $\le$ Score $<$ 0,70 (Alerta Médio):** reforço preventivo de estoque de medicamentos e sobreaviso à equipe médica regional.
   * **Score $<$ 0,10 (Monitoramento de Rotina):** sem envio extra; abastecimento padrão.
5. **`limiar_adotado`:** limiar de decisão escolhido por custo na validação cronológica (constante em todas as linhas).
