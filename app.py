"""
Dashboard Interativo de Suporte à Decisão — SESPA / Pará.
Atende ao Requisito 6 (A Decisão):
- Interface web interativa em Streamlit consumindo a camada Gold.
- Simulação dinâmica do limiar de corte (Threshold) com cálculo de custos de FP vs FN.
- Filtros por mês de decisão, mesorregião e nível de alerta.
- Visualização temporal interativa (Queimadas INPE vs Internações DataSUS).
- Ranking priorizado de municípios para despacho de kits de oxigênio e broncodilatadores.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="SESPA — Vigilância e Alocação de Insumos Respiratórios",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# -------------------------------------------------------------
# BARRA LATERAL (FILTROS E CONTROLES DE DECISÃO)
# -------------------------------------------------------------
st.sidebar.image("https://raw.githubusercontent.com/KayuryC/Vigilancia-Ambiental-Saude-PA/main/docs/logo_saude.png" if Path("docs/logo_saude.png").exists() else "https://img.icons8.com/fluency/96/hospital.png", width=80)
st.sidebar.title("Controle Operacional SESPA")
st.sidebar.markdown("**Projeto Integrador: Da Ingestão à Decisão**")
st.sidebar.markdown("---")

# Seletor de Mês de Decisão (t0)
meses_disponiveis = sorted(df_decisions["ano_mes_t0"].unique().tolist())
mes_selecionado = st.sidebar.selectbox(
    "📅 Mês de Decisão (t0):",
    meses_disponiveis,
    index=len(meses_disponiveis) - 1
)

# Filtro por Mesorregião
mesos_disponiveis = ["Todas"] + sorted(df_decisions["mesorregiao"].unique().tolist())
meso_selecionada = st.sidebar.selectbox("📍 Mesorregião do Pará:", mesos_disponiveis)

# Slider Dinâmico de Limiar (Threshold)
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Calibração de Decisão")
threshold = st.sidebar.slider(
    "Limiar de Alerta (Probabilidade de Risco):",
    min_value=0.10,
    max_value=0.90,
    value=0.40,
    step=0.05,
    help="Define a probabilidade a partir da qual o município recebe alerta de envio de insumos."
)

st.sidebar.info(
    f"**Limiar Adotado:** {threshold:.2f}\n\n"
    "• Custo Falso Positivo: **R$ 3.500,00**\n"
    "• Custo Falso Negativo: **R$ 45.000,00**\n\n"
    "*O limiar de 0.40 foi escolhido para priorizar o Recall em saúde pública.*"
)

# -------------------------------------------------------------
# PROCESSAMENTO DOS DADOS FILTRADOS
# -------------------------------------------------------------
df_filtrado = df_decisions[df_decisions["ano_mes_t0"] == mes_selecionado].copy()

if meso_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado["mesorregiao"] == meso_selecionada].copy()

# Recalcular prescrição dinâmica baseada no slider de threshold
df_filtrado["decisao_dinamica"] = np.where(
    df_filtrado["probabilidade_risco"] >= 0.70,
    "Alerta Alto: Envio de Kit Completo (O2 + Broncodilatadores)",
    np.where(
        df_filtrado["probabilidade_risco"] >= threshold,
        "Alerta Médio: Reforço Preventivo e Equipe Volante",
        "Monitoramento de Rotina"
    )
)

total_mun = len(df_filtrado)
alerta_alto = (df_filtrado["probabilidade_risco"] >= 0.70).sum()
alerta_medio = ((df_filtrado["probabilidade_risco"] >= threshold) & (df_filtrado["probabilidade_risco"] < 0.70)).sum()
pop_sob_alerta = df_filtrado[df_filtrado["probabilidade_risco"] >= threshold]["populacao_censo_2022"].sum()

# -------------------------------------------------------------
# CABEÇALHO PRINCIPAL
# -------------------------------------------------------------
st.title("🏥 Painel de Vigilância Ambiental e Suporte à Decisão — SESPA")
st.markdown(
    f"### Suporte à Decisão para o Mês de **{mes_selecionado}** | Região: **{meso_selecionada}**"
)

st.markdown(
    """
    > *"Cruzando as bases do **INPE (Focos de Queimada)**, **DataSUS (Internações)** e **IBGE (Censo 2022)**, 
    o pipeline antecipa surtos de insuficiência respiratória na Amazônia e orienta o despacho preventivo de oxigênio e medicamentos."*
    """
)

# -------------------------------------------------------------
# CARDS DE MÉTRICAS (KPIs)
# -------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🚨 Municípios em Alerta Alto",
        value=f"{alerta_alto}",
        delta=f"{(alerta_alto / total_mun * 100):.1f}% do total" if total_mun else "0%"
    )

with col2:
    st.metric(
        label="⚠️ Municípios em Alerta Médio",
        value=f"{alerta_medio}",
        delta=f"{(alerta_medio / total_mun * 100):.1f}% do total" if total_mun else "0%"
    )

with col3:
    st.metric(
        label="👥 População Sob Alerta Ativo",
        value=f"{pop_sob_alerta:,.0f}".replace(",", "."),
        delta="Habitantes protegidos"
    )

with col4:
    custo_prev_estimado = (alerta_alto + alerta_medio) * 3500.0
    st.metric(
        label="💰 Custo Logístico Preventivo",
        value=f"R$ {custo_prev_estimado:,.2f}".replace(",", "."),
        delta="Evita UTI aérea de R$ 45k"
    )

st.markdown("---")

# -------------------------------------------------------------
# GRÁFICOS INTERATIVOS
# -------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Dinâmica Temporal Estadual", "🏆 Ranking de Municípios Críticos", "⚖️ Análise de Custos e Decisão"])

with tab1:
    st.subheader("Evolução Temporal no Pará: Queimadas vs. Taxa de Internações")
    
    # Agregação para o gráfico temporal
    df_ind_tempo = df_indicators.copy()
    if meso_selecionada != "Todas":
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
        marker_color="#e6550d",
        opacity=0.7,
        yaxis="y1"
    ))

    # Linha de Internações
    fig_tempo.add_trace(go.Scatter(
        x=mensal["ano_mes"],
        y=mensal["taxa_media"],
        name="Taxa de Internação / 100k hab (DataSUS)",
        line=dict(color="#1f77b4", width=3.5),
        mode="lines+markers",
        yaxis="y2"
    ))

    fig_tempo.update_layout(
        title="Impacto Sazonal da Estiagem: Disparo de Queimadas e Resposta Hospitalar",
        xaxis=dict(title="Mês de Competência"),
        yaxis=dict(
            title=dict(text="Total de Focos de Queimada", font=dict(color="#e6550d")),
            tickfont=dict(color="#e6550d")
        ),
        yaxis2=dict(
            title=dict(text="Taxa de Internação por 100k hab", font=dict(color="#1f77b4")),
            tickfont=dict(color="#1f77b4"),
            overlaying="y",
            side="right"
        ),
        legend=dict(x=0.01, y=0.99),
        hovermode="x unified",
        height=480
    )

    st.plotly_chart(fig_tempo, use_container_width=True)
    st.caption("Nota: Observe a antecedência dos focos de calor entre agosto e outubro, seguida pelo aumento sistemático da sobrecarga hospitalar.")

with tab2:
    st.subheader(f"Top 15 Municípios com Maior Risco de Sobrecarga ({mes_selecionado})")
    
    ranking_top = df_filtrado.sort_values(by="probabilidade_risco", ascending=False).head(15)

    fig_bar = px.bar(
        ranking_top,
        x="probabilidade_risco",
        y="nome_municipio",
        orientation="h",
        color="probabilidade_risco",
        color_continuous_scale=["#31a354", "#fd8d3c", "#de2d26"],
        labels={"probabilidade_risco": "Probabilidade Estimada de Sobrecarga", "nome_municipio": "Município"},
        text=ranking_top["probabilidade_risco"].apply(lambda v: f"{v*100:.1f}%")
    )

    fig_bar.add_vline(x=0.70, line_dash="dash", line_color="red", annotation_text="Alerta Alto (>= 70%)")
    fig_bar.add_vline(x=threshold, line_dash="dot", line_color="orange", annotation_text=f"Limiar ({threshold:.2f})")

    fig_bar.update_layout(
        yaxis=dict(autorange="reversed"),
        height=520,
        coloraxis_showscale=False
    )

    st.plotly_chart(fig_bar, use_container_width=True)

with tab3:
    st.subheader("Matriz de Trade-Off e Análise de Risco")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            """
            ### Racional do Decisor (SESPA):
            * **Falso Positivo (FP):** Enviar um lote preventivo de cilindros de oxigênio e medicamentos para um município que não atingiu a saturação crítica.  
              *Custo estimado:* **R$ 3.500,00** (frete logístico fluvial/rodoviário). O insumo continua utilizável e estocado.
            * **Falso Negativo (FN):** Deixar de alertar um município que sofreu surto respiratório severo por fumaça.  
              *Custo estimado:* **R$ 45.000,00** por caso (remoção de urgência por UTI aérea, ocupação de leito intensivo e risco inaceitável de óbitos evitáveis).
            """
        )
    with col_b:
        st.info(
            f"""
            ### Efeito do Limiar Escolhido ({threshold:.2f}):
            * Como o custo de um falso negativo é **12,8 vezes maior** que o de um falso positivo, calibrar o modelo para priorizar **Recall (80.18%)** minimiza o risco sanitário e financeiro do estado.
            * Municípios sob vigilância ativa neste corte: **{alerta_alto + alerta_medio}**
            * Municípios mantidos em rotina: **{total_mun - (alerta_alto + alerta_medio)}**
            """
        )

st.markdown("---")

# -------------------------------------------------------------
# TABELA PRESCRITIVA COM DOWNLOAD
# -------------------------------------------------------------
st.subheader("📋 Tabela de Recomendação Operacional para Despacho de Insumos")

tabela_display = df_filtrado[[
    "codigo_ibge",
    "nome_municipio",
    "mesorregiao",
    "populacao_censo_2022",
    "total_focos_calor",
    "taxa_internacao_100k",
    "probabilidade_risco",
    "decisao_dinamica"
]].sort_values(by="probabilidade_risco", ascending=False)

tabela_display.columns = [
    "Cód IBGE", "Município", "Mesorregião", "População (2022)",
    "Focos de Calor", "Taxa Atual / 100k", "Prob. Risco", "Recomendação SESPA"
]

st.dataframe(
    tabela_display.style.format({
        "População (2022)": "{:,.0f}",
        "Focos de Calor": "{:.0f}",
        "Taxa Atual / 100k": "{:.2f}",
        "Prob. Risco": "{:.1%}"
    }),
    use_container_width=True,
    height=350
)

# Botão de Download
csv_data = tabela_display.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Baixar Tabela de Decisão em CSV",
    data=csv_data,
    file_name=f"recomendacao_decisao_sespa_{mes_selecionado}.csv",
    mime="text/csv"
)

st.markdown("---")
st.caption("Projeto Integrador — Da Ingestão à Decisão | Engenharia de Dados com Arquitetura Medalhão (Bronze, Silver, Gold)")
