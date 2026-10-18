"""
Dashboard Executivo e Apresentação para a Banca — SESPA / Pará.
Projeto Integrador: Da Ingestão à Decisão.

Estruturado no formato de apresentação interativa (Slides / Abas) contendo
integralmente todos os requisitos exigidos pela banca avaliadora:
1. O Problema & Pergunta Oficial de Decisão
2. Arquitetura Medalhão & Governança de Dados
3. Dinâmica Temporal & Cruzamento das Fontes Reais
4. Fundamentos ML-Ready, Checklist Anti-Vazamento e Baselines
5. Painel Operacional SESPA (Simulador de Decisão ao Vivo)
6. Limitações, Uso de IA e Equipe
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -------------------------------------------------------------
# CONFIGURAÇÃO GERAL E ESTILO VISUAL
# -------------------------------------------------------------
st.set_page_config(
    page_title="SESPA — Da Ingestão à Decisão",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS para estética executiva tipo apresentação
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1f3a60;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4a5568;
        margin-bottom: 1.5rem;
    }
    .card-metric {
        background-color: #f8fafc;
        border-left: 5px solid #2563eb;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .badge-alto {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-medio {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-rotina {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .quote-box {
        background-color: #eff6ff;
        border-left: 5px solid #1d4ed8;
        padding: 18px;
        border-radius: 8px;
        font-size: 1.05rem;
        font-style: italic;
        margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

# Caminhos dos dados da Camada Gold
DATA_DIR = Path("data/gold")
GOLD_IND_PATH = DATA_DIR / "gold_painel_indicadores_pa.parquet"
GOLD_DECISION_PATH = DATA_DIR / "gold_recomendacao_decisao_sespa.parquet"


@st.cache_data
def load_data():
    """Carrega as tabelas processadas da Camada Gold."""
    if not GOLD_IND_PATH.exists() or not GOLD_DECISION_PATH.exists():
        st.error("⚠️ Tabelas da camada Gold não encontradas. Execute 'python run_pipeline.py' primeiro!")
        st.stop()

    df_ind = pd.read_parquet(GOLD_IND_PATH)
    df_dec = pd.read_parquet(GOLD_DECISION_PATH)
    return df_ind, df_dec


df_indicators, df_decisions = load_data()

# Premissas econômicas de decisão
CUSTO_FP = 3500.0   # Frete logístico de kit estocável por município
CUSTO_FN = 45000.0  # Custo médio de internação intensiva/UTI aérea e desabastecimento
ALTO_CORTE = 0.70   # Limiar de certeza alta
LIMIAR_ADOTADO = float(df_decisions["limiar_adotado"].iloc[0]) if "limiar_adotado" in df_decisions.columns else 0.40


def brl(v: float) -> str:
    """Formata valor em reais evitando formatação LaTeX acidental."""
    return "R\\$ " + f"{v:,.0f}".replace(",", ".")


# -------------------------------------------------------------
# BARRA LATERAL — MENU DE NAVEGAÇÃO & SIMULADOR
# -------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/fluency/96/hospital.png", width=70)
st.sidebar.markdown("### **SESPA / PA — Defesa do Projeto**")
st.sidebar.markdown("**Da Ingestão à Decisão**")
st.sidebar.caption("Engenharia de Dados em Arquitetura Medalhão")
st.sidebar.markdown("---")

st.sidebar.markdown("#### ⚙️ **Parâmetros da Apresentação**")

# Seletor de Mês de Decisão (t0)
meses_disponiveis = sorted(df_decisions["ano_mes_t0"].unique().tolist())
mes_selecionado = st.sidebar.selectbox(
    "📅 Ponto de Corte Temporal ($t_0$):",
    meses_disponiveis,
    index=len(meses_disponiveis) - 1,
    help="Mês em que o secretário toma a decisão de despacho antes do mês seguinte."
)

# Filtro por Mesorregião
mesos_disponiveis = ["Todas as 6 Mesorregiões"] + sorted(df_decisions["mesorregiao"].unique().tolist())
meso_selecionada = st.sidebar.selectbox("📍 Recorte Geográfico:", mesos_disponiveis)

# Slider Dinâmico de Limiar (Threshold)
threshold = st.sidebar.slider(
    "🎚️ Limiar de Decisão (Score do Modelo):",
    min_value=0.05,
    max_value=0.90,
    value=min(max(LIMIAR_ADOTADO, 0.05), 0.90),
    step=0.05,
    help="Altera a sensibilidade do alerta. O padrão é o limiar de menor custo estimado em validação cronológica."
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Custo Falso Positivo:** {brl(CUSTO_FP)}")
st.sidebar.markdown(f"**Custo Falso Negativo:** {brl(CUSTO_FN)}")
st.sidebar.caption("Razão de severidade: 1 FN equivale ao custo financeiro e sanitário de 12,8 FPs.")

# -------------------------------------------------------------
# PROCESSAMENTO DOS DADOS PARA O RECORTE
# -------------------------------------------------------------
df_filtrado = df_decisions[df_decisions["ano_mes_t0"] == mes_selecionado].copy()

if meso_selecionada != "Todas as 6 Mesorregiões":
    df_filtrado = df_filtrado[df_filtrado["mesorregiao"] == meso_selecionada].copy()

# Recalcular prescrição dinâmica baseada no slider
df_filtrado["decisao_dinamica"] = np.where(
    df_filtrado["probabilidade_risco"] >= ALTO_CORTE,
    "Alerta Alto: Envio Imediato de Kit Completo (O2 + Broncodilatadores)",
    np.where(
        df_filtrado["probabilidade_risco"] >= threshold,
        "Alerta Médio: Reforço Preventivo e Equipe Volante",
        "Monitoramento de Rotina"
    )
)

total_mun = len(df_filtrado)
alerta_alto = (df_filtrado["probabilidade_risco"] >= ALTO_CORTE).sum()
alerta_medio = ((df_filtrado["probabilidade_risco"] >= threshold) & (df_filtrado["probabilidade_risco"] < ALTO_CORTE)).sum()
pop_sob_alerta = df_filtrado[df_filtrado["probabilidade_risco"] >= threshold]["populacao_censo_2022"].sum()

# -------------------------------------------------------------
# CABEÇALHO PRINCIPAL DA APRESENTAÇÃO
# -------------------------------------------------------------
st.markdown('<div class="main-header">🏥 Projeto Integrador: Da Ingestão à Decisão</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Vigilância Epidemiológica e Alocação Preventiva de Insumos Hospitalares no Estado do Pará</div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# NAVEGAÇÃO PRINCIPAL — AS 6 ABAS DA BANCA
# -------------------------------------------------------------
tab_problema, tab_arquitetura, tab_dados, tab_ml, tab_decisao, tab_governanca = st.tabs([
    "🎯 1. O Problema & Pergunta Oficial",
    "🏛️ 2. Arquitetura Medalhão & Governança",
    "📊 3. Dinâmica Temporal & Dados Reais",
    "🧠 4. Fundamentos ML-Ready & Anti-Vazamento",
    "💻 5. Painel Operacional SESPA (Ao Vivo)",
    "🔍 6. Limitações, IA & Equipe"
])

# =============================================================
# TAB 1: O PROBLEMA & PERGUNTA OFICIAL
# =============================================================
with tab_problema:
    st.subheader("1. Contexto do Problema & Formulação da Decisão")
    
    col_prob1, col_prob2 = st.columns([3, 2])
    with col_prob1:
        st.markdown("""
        ### O Desafio de Saúde Pública no Pará
        No segundo semestre de cada ano, o estado do Pará enfrenta o ápice do **período de estiagem amazônica** (julho a novembro), 
        acompanhado pela explosão de focos de queimada e dispersão de material particulado.
        
        * **A Consequência Hospitalar:** Elevação severa de internações por **Síndrome Respiratória Aguda Grave (SRAG)**, 
          atingindo criticamente crianças menores de 5 anos e idosos.
        * **O Gargalo Logístico:** O transporte fluvial e rodoviário na Amazônia exige semanas de planejamento. 
          Reagir apenas após a superlotação hospitalar resulta em **desabastecimento de oxigênio e resgates em UTI aérea de altíssimo custo**.
        """)
        
        st.markdown(f"""
        <div class="quote-box">
            <b>Frase Oficial do Projeto (Template Preenchido com Dados do Pipeline):</b><br>
            "Cruzando as bases do <b>INPE (Focos de Calor)</b>, <b>OpenDataSUS (SRAG Hospitalizado)</b> e <b>IBGE (Censo 2022)</b>, 
            identificamos os municípios com alto risco de sobrecarga hospitalar. 
            Recomendamos que a <b>Secretaria de Estado de Saúde Pública do Pará (SESPA)</b> envie 
            <b>Kits Preventivos de Insumos Respiratórios (O₂ + Broncodilatadores)</b> nos próximos <b>30 dias</b>, 
            priorizando os <b>municípios com risco &ge; {threshold:.2f}</b>. 
            Se agir, o ganho esperado é a <b>garantia de atendimento preventivo aos municípios sob alerta crítico</b>; 
            se errarmos, o custo de um falso positivo é de <b>{brl(CUSTO_FP)}</b> em logística de insumos estocáveis, 
            versus o custo inaceitável de desabastecimento de <b>{brl(CUSTO_FN)}</b> por caso com remoção de emergência."
        </div>
        """, unsafe_allow_html=True)

    with col_prob2:
        st.markdown("### Componentes Exigidos pela Banca")
        st.info(f"""
        * **Decisor Concreto:** Secretário de Estado de Saúde Pública do Pará (SESPA).
        * **Ação Prática:** Despacho antecipado de kits de cilindros de oxigênio e broncodilatadores para hospitais regionais de referência.
        * **Prazo da Ação:** 30 dias de antecedência (ciclo mensal de planejamento).
        * **Custo do Falso Positivo (FP):** {brl(CUSTO_FP)} por município (frete logístico fluvial/terrestre; insumos continuam úteis e estocados).
        * **Custo do Falso Negativo (FN):** {brl(CUSTO_FN)} por caso (resgate em UTI aérea, leito intensivo de emergência e risco de óbito evitável).
        * **Razão Econômica:** 1 FN equivale a **12,8 FPs**, justificando a calibração do modelo voltada a alto Recall.
        """)

# =============================================================
# TAB 2: ARQUITETURA MEDALHÃO & GOVERNANÇA
# =============================================================
with tab_arquitetura:
    st.subheader("2. Arquitetura de Dados Medalhão & Garantias de Governança")
    
    st.markdown("""
    O pipeline foi construído do zero seguindo estritamente as regras de imutabilidade, contratos fortes e rastreabilidade:
    """)
    
    col_arq1, col_arq2, col_arq3 = st.columns(3)
    
    with col_arq1:
        st.markdown("""
        #### 🥉 Camada Bronze (Bruta)
        * **Regra:** Dado imutável, exatamente como veio da fonte. Sem regra de negócio nem agregação.
        * **As 3 Formas de Ingestão:**
          1. **API REST (IBGE):** Paginação, retry com backoff exponencial e descompressão gzip.
          2. **Arquivo (INPE):** Leitura de CSV anual em memória com tipagem estrita e encoding explícito.
          3. **Arquivo com Checkpoint (OpenDataSUS SRAG):** Ingestão em chunks com **checkpoint por hash SHA-256** do arquivo (idempotente).
        * **Metadados Obrigatórios:** `source_system`, `source_object`, `load_id`, `ingestion_timestamp` e `record_hash`.
        """)
        
    with col_arq2:
        st.markdown("""
        #### 🥈 Camada Silver (Tratada)
        * **Regra:** Tipagem forte, padronização, resolução de integridade referencial e contratos declarados.
        * **Granularidade Declarada em 1 Frase:** *"Uma linha por município por mês do estado do Pará"*.
        * **Chave Primária Verificada:** `['codigo_ibge', 'ano_mes']` com asserção formal comprovando **zero duplicatas**.
        * **Quarentena Ativa:** Registros com inconsistências isolados em `data/quarantine/` com motivo explícito.
        * **Conciliação do SRAG:** 4.574 na Bronze = 4.264 contados + 310 em quarentena + 0 duplicatas.
        """)
        
    with col_arq3:
        st.markdown("""
        #### 🥇 Camada Gold (Decisão)
        * **Regra:** Tabelas orientadas à pergunta de negócio. **Proibida qualquer limpeza aqui** (se precisasse limpar, a Silver falhou).
        * **Indicadores:** Taxas normalizadas por 100 mil habitantes com dados do Censo 2022.
        * **Features Causais (Lags):** Variáveis defasadas temporalmente ($m-1$) para impedir vazamento do futuro.
        * **Base ML-Ready:** Rotulagem formal do próximo mês ($m+1$) com $t_0$ no último dia de cada mês.
        * **Tabela de Decisão:** Prescrição operacional com probabilidades e custos associados.
        """)
        
    st.markdown("---")
    st.subheader("🛡️ Demonstração de Idempotência (Exigência Formal da Defesa)")
    st.markdown("""
    O professor exige demonstração de que executar o pipeline duas vezes seguidas **não altera nem duplica nenhum dado na camada final**.
    O script `scripts/demo_idempotencia.py` compara a foto das tabelas lado a lado:
    """)
    
    df_idemp = pd.DataFrame([
        {"Tabela": "silver/dim_municipios_pa", "Linhas (Exec 1)": 144, "Linhas (Exec 2)": 144, "Duplicatas PK": 0, "Hash Conteúdo": "f9e81e4a6b5c50ad", "Status": "✅ IDÊNTICO"},
        {"Tabela": "silver/fatos_focos_mensais_pa", "Linhas (Exec 1)": 1044, "Linhas (Exec 2)": 1044, "Duplicatas PK": 0, "Hash Conteúdo": "b08e6e3f25549055", "Status": "✅ IDÊNTICO"},
        {"Tabela": "silver/fatos_srag_mensais_pa", "Linhas (Exec 1)": 744, "Linhas (Exec 2)": 744, "Duplicatas PK": 0, "Hash Conteúdo": "294a418a29410808", "Status": "✅ IDÊNTICO"},
        {"Tabela": "silver/silver_painel_mensal_pa", "Linhas (Exec 1)": 1728, "Linhas (Exec 2)": 1728, "Duplicatas PK": 0, "Hash Conteúdo": "d9b8b902d48a26ee", "Status": "✅ IDÊNTICO"},
        {"Tabela": "gold/gold_painel_indicadores_pa", "Linhas (Exec 1)": 1728, "Linhas (Exec 2)": 1728, "Duplicatas PK": 0, "Hash Conteúdo": "72b159a36d87e6c5", "Status": "✅ IDÊNTICO"},
        {"Tabela": "gold/gold_ml_ready_pa", "Linhas (Exec 1)": 1584, "Linhas (Exec 2)": 1584, "Duplicatas PK": 0, "Hash Conteúdo": "6946daf15b5c991e", "Status": "✅ IDÊNTICO"},
        {"Tabela": "gold/gold_recomendacao_decisao_sespa", "Linhas (Exec 1)": 432, "Linhas (Exec 2)": 432, "Duplicatas PK": 0, "Hash Conteúdo": "56d7d98b0c04ca5c", "Status": "✅ IDÊNTICO"},
    ])
    st.dataframe(df_idemp, use_container_width=True)

# =============================================================
# TAB 3: DINÂMICA TEMPORAL & DADOS REAIS
# =============================================================
with tab_dados:
    st.subheader("3. Dinâmica Temporal e Cruzamento das 3 Fontes Reais")
    
    st.markdown("""
    O cruzamento estabelece uma **grade canônica contínua de 1.728 registros** (144 municípios × 12 meses do ano de 2023), 
    garantindo que a ausência de casos ou queimadas em dado mês seja registrada como valor zero (e não nulo), sem registros órfãos.
    """)
    
    # Gráfico Temporal Integrado
    df_ind_tempo = df_indicators.copy()
    if meso_selecionada != "Todas as 6 Mesorregiões":
        df_ind_tempo = df_ind_tempo[df_ind_tempo["mesorregiao"] == meso_selecionada]

    mensal = df_ind_tempo.groupby("ano_mes").agg(
        total_focos=("total_focos_calor", "sum"),
        taxa_media=("taxa_internacao_100k", "mean")
    ).reset_index()

    fig_tempo = go.Figure()

    # Barras de Queimadas
    fig_tempo.add_trace(go.Bar(
        x=mensal["ano_mes"],
        y=mensal["total_focos"],
        name="Focos de Queimadas (INPE)",
        marker_color="#ea580c",
        opacity=0.75,
        yaxis="y1"
    ))

    # Linha de SRAG hospitalizado
    fig_tempo.add_trace(go.Scatter(
        x=mensal["ano_mes"],
        y=mensal["taxa_media"],
        name="Taxa de SRAG Hospitalizado / 100k hab (OpenDataSUS)",
        line=dict(color="#0284c7", width=3.5),
        mode="lines+markers",
        yaxis="y2"
    ))

    # Destaque da Estiagem
    fig_tempo.add_vrect(
        x0=5.5, x1=10.5,
        fillcolor="yellow", opacity=0.15,
        layer="below", line_width=0,
        annotation_text="Período Crítico de Estiagem Amazônica (Julho a Novembro)",
        annotation_position="top left"
    )

    fig_tempo.update_layout(
        title=f"Série Temporal Mensal de Queimadas vs. SRAG no Pará — Recorte: {meso_selecionada}",
        xaxis=dict(title="Mês de Competência"),
        yaxis=dict(
            title=dict(text="Total de Focos de Calor (INPE)", font=dict(color="#ea580c")),
            tickfont=dict(color="#ea580c")
        ),
        yaxis2=dict(
            title=dict(text="Taxa Média de SRAG / 100k hab", font=dict(color="#0284c7")),
            tickfont=dict(color="#0284c7"),
            overlaying="y",
            side="right"
        ),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
        hovermode="x unified",
        height=450
    )

    st.plotly_chart(fig_tempo, use_container_width=True)
    
    st.info("""
    **Achado Estatístico Central:** Na análise empírica dos dados de 2023, o pico de queimadas ocorre entre agosto e outubro. 
    Contudo, a sobrecarga de SRAG hospitalizado é mais fortemente explicada pela **inércia epidemiológica local recente** 
    (lags de internação) do que diretamente pela contagem bruta de focos no próprio município no mesmo mês, 
    destacando a necessidade de modelagem preditiva baseada em evidências em vez de regras ingênuas.
    """)

# =============================================================
# TAB 4: FUNDAMENTOS ML-READY & ANTI-VAZAMENTO
# =============================================================
with tab_ml:
    st.subheader("4. Base ML-Ready, Garantias Anti-Vazamento e Comparativo de Baselines")
    st.caption("Requisito 5 da lauda — Componente de maior peso avaliativo.")
    
    col_ml1, col_ml2 = st.columns([3, 2])
    
    with col_ml1:
        st.markdown("### Especificação Formal dos 10 Elementos ML-Ready")
        df_elem = pd.DataFrame([
            {"Elemento": "Label (Y)", "Especificação": "1 (Sobrecarga no próximo mês) se taxa futura >= p75 histórico de treino (4.918/100k hab); 0 caso contrário."},
            {"Elemento": "Regra de Rotulagem", "Especificação": "taxa_internacao_futura = shift(-1) temporal calculada estritamente dentro de cada município."},
            {"Elemento": "Coorte Elegível", "Especificação": "Todos os 144 municípios do Pará em meses com horizonte futuro observável (Jan a Nov)."},
            {"Elemento": "Ponto de Corte (t0)", "Especificação": "Último dia de cada mês calendário m. O conhecimento do modelo é congelado em t0."},
            {"Elemento": "Janela de Observação", "Especificação": "Período estritamente anterior ou igual a t0 (dados censitários, focos e SRAG até mês m)."},
            {"Elemento": "Janela de Predição", "Especificação": "Mês imediatamente subsequente m + 1 (horizonte de 30 dias para atuação sanitária)."},
            {"Elemento": "Split Adotado", "Especificação": "Temporal Cronológico Estrito: Treino = Jan-Ago/2023 (1.152 obs); Teste = Set-Nov/2023 (432 obs)."},
            {"Elemento": "Baselines de Comparação", "Especificação": "5 modelos de referência honestos para balizar o valor agregado da modelagem complexa."},
            {"Elemento": "Métrica Principal", "Especificação": "F2-Score, Recall e Custo Total de Decisão (prioridade em minimizar Falsos Negativos)."},
            {"Elemento": "Limiar Otimizado", "Especificação": "Escolha do limiar por minimização de custo financeiro-sanitário em validação cronológica."}
        ])
        st.dataframe(df_elem, use_container_width=True)

    with col_ml2:
        st.markdown("### Checklist Anti-Vazamento (Zero Data Leakage)")
        st.success("✅ **Toda feature existia antes de $t_0$?** Sim. Nenhuma agregação utiliza dados do mês $m+1$.")
        st.success("✅ **Agregações foram calculadas apenas com dados anteriores a $t_0$?** Sim. Lags calculados causalmente.")
        st.success("✅ **O split respeita tempo e grupo?** Sim. Split puramente temporal (Jan-Ago vs Set-Nov). Futuro não vazou para o treino.")
        st.success("✅ **Scalers, encoders e limiar calculados somente no treino?** Sim. O limiar do percentil 75 foi calculado exclusivamente com os dados de treino.")
        st.success("✅ **Métrica honesta sem comemoração de métrica alta demais?** Sim. O modelo atinge métricas realistas e fundamentadas em dados abertos reais.")

    st.markdown("---")
    st.subheader("⚖️ Comparativo de Desempenho e Custo dos Modelos no Teste (Setembro a Novembro/2023)")
    
    df_bench = pd.DataFrame([
        {"Modelo / Estratégia": "Não alertar ninguém", "Recall": "0.0%", "Precisão": "0.0%", "Alertas Emitidos": 0, "Custo Total do Erro": "R\\$ 2.745.000", "Conceito": "Inação total; sofre 100% dos custos de emergência"},
        {"Modelo / Estratégia": "Alertar todos os municípios", "Recall": "100.0%", "Precisão": "14.1%", "Alertas Emitidos": 432, "Custo Total do Erro": "R\\$ 1.298.500", "Conceito": "Desperdício logístico em massa em municípios sem caso"},
        {"Modelo / Estratégia": "Regra Trivial: Foco na estiagem", "Recall": "96.7%", "Precisão": "14.6%", "Alertas Emitidos": 403, "Custo Total do Erro": "R\\$ 1.294.000", "Conceito": "Dispara alertas falsos quase indiscriminadamente"},
        {"Modelo / Estratégia": "Persistência: Taxa atual já alta", "Recall": "54.1%", "Precisão": "46.5%", "Alertas Emitidos": 71, "Custo Total do Erro": "R\\$ 1.393.000", "Conceito": "Modelo reativo; só avisa quando o surto já começou"},
        {"Modelo / Estratégia": "Random Forest só com População", "Recall": "93.4%", "Precisão": "16.5%", "Alertas Emitidos": 345, "Custo Total do Erro": "R\\$ 1.188.000", "Conceito": "Prioriza cidades populosas sem histórico recente"},
        {"Modelo / Estratégia": "Random Forest sem Focos de Calor", "Recall": "91.8%", "Precisão": "20.4%", "Alertas Emitidos": 274, "Custo Total do Erro": "R\\$ 988.000", "Conceito": "Excelente custo baseado em inércia epidemiológica"},
        {"Modelo / Estratégia": "Random Forest Completo (SESPA)", "Recall": "82.0%", "Precisão": "26.3%", "Alertas Emitidos": 190, "Custo Total do Erro": "R\\$ 985.000", "Conceito": "🏆 Menor custo total e melhor seletividade de alertas"}
    ])
    st.dataframe(df_bench, use_container_width=True)

# =============================================================
# TAB 5: PAINEL OPERACIONAL SESPA (AO VIVO)
# =============================================================
with tab_decisao:
    st.subheader(f"5. Simulador de Decisão Operacional da SESPA — Mês: {mes_selecionado}")
    
    # KPIs da decisão
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    with col_kpi1:
        st.metric(
            label="🚨 Alerta Alto (Kit Completo)",
            value=f"{alerta_alto} municípios",
            delta=f"{(alerta_alto / total_mun * 100):.1f}% do total" if total_mun else "0%"
        )
    with col_kpi2:
        st.metric(
            label="⚠️ Alerta Médio (Reforço Volante)",
            value=f"{alerta_medio} municípios",
            delta=f"{(alerta_medio / total_mun * 100):.1f}% do total" if total_mun else "0%"
        )
    with col_kpi3:
        st.metric(
            label="👥 População Coberta pelo Alerta",
            value=f"{pop_sob_alerta:,.0f}".replace(",", "."),
            delta="Habitantes atendidos"
        )
    with col_kpi4:
        custo_log = (alerta_alto + alerta_medio) * CUSTO_FP
        st.metric(
            label="📦 Custo Logístico Preventivo",
            value=brl(custo_log),
            delta="Logística de insumos estocáveis"
        )
        
    st.markdown("---")
    
    col_graph, col_table = st.columns([1, 1])
    
    with col_graph:
        st.markdown(f"#### Ranking Top 15 Municípios Priorizados ({mes_selecionado})")
        ranking_top = df_filtrado.sort_values(by="probabilidade_risco", ascending=False).head(15)

        fig_bar = px.bar(
            ranking_top,
            x="probabilidade_risco",
            y="nome_municipio",
            orientation="h",
            color="probabilidade_risco",
            color_continuous_scale=["#16a34a", "#eab308", "#dc2626"],
            labels={"probabilidade_risco": "Score de Risco", "nome_municipio": "Município"},
            text=ranking_top["probabilidade_risco"].apply(lambda v: f"{v*100:.1f}%")
        )

        fig_bar.add_vline(x=ALTO_CORTE, line_dash="dash", line_color="red", annotation_text=f"Alerta Alto (>= {ALTO_CORTE:.2f})")
        fig_bar.add_vline(x=threshold, line_dash="dot", line_color="orange", annotation_text=f"Limiar Atual ({threshold:.2f})")

        fig_bar.update_layout(
            yaxis=dict(autorange="reversed"),
            height=480,
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_table:
        st.markdown("#### Matriz de Custo com o Limiar Selecionado")
        y_all = df_decisions["label_sobrecarga_proximo_mes"].astype(int)
        pred_all = df_decisions["probabilidade_risco"] >= threshold
        tp = int((pred_all & (y_all == 1)).sum())
        fp = int((pred_all & (y_all == 0)).sum())
        fn = int((~pred_all & (y_all == 1)).sum())
        tn = int((~pred_all & (y_all == 0)).sum())
        
        recall_t = tp / (tp + fn) if (tp + fn) else 0.0
        precisao_t = tp / (tp + fp) if (tp + fp) else 0.0
        custo_modelo = fp * CUSTO_FP + fn * CUSTO_FN
        
        col_c1, col_c2 = st.columns(2)
        col_c1.metric("Acertos (Verdadeiros Positivos)", f"{tp} municípios")
        col_c2.metric("Omissões (Falsos Negativos)", f"{fn} municípios")
        
        st.info(f"""
        * **Recall no Período de Teste:** **{recall_t:.1%}** (sensibilidade sanitária).
        * **Precisão no Período de Teste:** **{precisao_t:.1%}** (eficiência de gasto).
        * **Custo Total de Erros Estimado:** **{brl(custo_modelo)}** em todo o período de teste.
        * **Comparação:** Uma postura passiva sem modelo custaria **{brl(int((y_all == 1).sum()) * CUSTO_FN)}**.
        """)

    st.markdown("---")
    st.subheader("📋 Tabela Prescritiva de Despacho Logístico da SESPA")
    
    tabela_disp = df_filtrado[[
        "codigo_ibge", "nome_municipio", "mesorregiao", "populacao_censo_2022",
        "total_focos_calor", "taxa_internacao_100k", "probabilidade_risco", "decisao_dinamica"
    ]].sort_values(by="probabilidade_risco", ascending=False)
    
    tabela_disp.columns = [
        "Cód IBGE", "Município", "Mesorregião", "População (2022)",
        "Focos Calor", "Taxa Atual / 100k", "Score Risco", "Recomendação Operacional SESPA"
    ]
    
    st.dataframe(
        tabela_disp.style.format({
            "População (2022)": "{:,.0f}",
            "Focos Calor": "{:.0f}",
            "Taxa Atual / 100k": "{:.2f}",
            "Score Risco": "{:.1%}"
        }),
        use_container_width=True,
        height=320
    )
    
    # Download CSV
    csv_bytes = tabela_disp.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Exportar Lista de Despacho Logístico (CSV Oficial)",
        data=csv_bytes,
        file_name=f"despacho_sespa_{mes_selecionado}.csv",
        mime="text/csv"
    )

# =============================================================
# TAB 6: LIMITAÇÕES, IA & EQUIPE
# =============================================================
with tab_governanca:
    st.subheader("6. Limitações Metodológicas, Declaração de IA e Equipe")
    
    col_gov1, col_gov2 = st.columns(2)
    
    with col_gov1:
        st.markdown("""
        ### Limitações Metodológicas e de Dados (Seção 8 da Lauda)
        * **O que os dados permitem afirmar:**  
          Existe alta previsibilidade de sobrecarga hospitalar a partir do **histórico epidemiológico recente** dos municípios, 
          permitindo orientar a alocação logística antecipada de insumos estocáveis e equipes de saúde.
        * **O que os dados NÃO permitem afirmar:**  
          Não é possível comprovar relação de causa-efeito direta de que a fumaça de um foco de calor em um município específico 
          cause a internação naquele mesmo local no mesmo mês, devido a deslocamento de pluma de vento e subnotificação.
        * **Subnotificação e Atraso do SIVEP-Gripe:**  
          Os microdados de SRAG dependem da digitação das fichas pelos municípios. 
          O uso de dados públicos consolidados mitiga esse efeito para o ano de 2023, mas em operação em tempo real exigiria ajuste de *nowcasting*.
        * **Natureza das Premissas de Custo:**  
          Os valores de R\\$ 3.500 (FP) e R\\$ 45.000 (FN) são premissas de negócio parametrizadas pelo grupo com base em estudos logísticos e de regulação hospitalar.
        """)

    with col_gov2:
        st.markdown("""
        ### Declaração de Uso de Inteligência Artificial (Seção 9 da Lauda)
        Em cumprimento estrito ao item 9 da lauda:
        * **Ferramentas Utilizadas:** Antigravity (Google DeepMind) e modelos de linguagem generativa.
        * **Onde foram utilizadas:**
          1. Estruturação inicial do repositório, boas práticas de arquitetura medalhão e `.gitignore`.
          2. Geração de código boilerplate para requisições de API REST e módulos de metadados técnicos.
          3. Construção dos gráficos interativos em Plotly e layout web no Streamlit.
        * **Domínio e Autoria:** Todas as regras epidemiológicas, filtros de quarentena, premissas de custo e validações de contratos foram definidos, revisados e são de pleno domínio e defesa da equipe.
        
        ---
        ### Repositório e Equipe
        * **Repositório GitHub:** [`KayuryC/Vigilancia-Ambiental-Saude-PA`](https://github.com/KayuryC/Vigilancia-Ambiental-Saude-PA.git)
        * **Membros e Contribuições:** Ver documentação em `README.md` e histórico distribuído de commits.
        """)

st.markdown("---")
st.caption("Projeto Integrador: Da Ingestão à Decisão | Engenharia de Dados & Modelagem Preditiva | Pará, 2026")
