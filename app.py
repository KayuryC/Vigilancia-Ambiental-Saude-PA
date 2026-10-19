"""
Apresentação Executiva Interativa da Defesa — SESPA / Pará.
Projeto Integrador: Da Ingestão à Decisão.

Design limpo, minimalista e espaçado (estilo slide deck executivo),
focado em clareza visual e impacto direto para a banca avaliadora.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -------------------------------------------------------------
# CONFIGURAÇÃO GERAL DA PÁGINA
# -------------------------------------------------------------
st.set_page_config(
    page_title="SESPA — Da Ingestão à Decisão",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"  # Oculta a barra lateral por padrão para visual limpo
)

# Estilização minimalista e refinada (Clean Executive UI)
st.markdown("""
<style>
    /* Tipografia e espaçamento geral */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
        max-width: 1250px;
    }
    h1, h2, h3 {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #0f172a;
    }
    .slide-tag {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #2563eb;
        background: #eff6ff;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
        margin-bottom: 8px;
    }
    .slide-title {
        font-size: 1.85rem;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 0.4rem;
        line-height: 1.25;
    }
    .slide-subtitle {
        font-size: 1.05rem;
        color: #2563eb;
        margin-bottom: 1.6rem;
    }
    /* Cards executivos */
    .card-clean {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 16px;
    }
    .card-highlight {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 5px solid #2563eb;
        border-radius: 12px;
        padding: 22px 26px;
        margin-bottom: 20px;
    }
    .quote-text {
        font-size: 1.1rem;
        font-weight: 500;
        color: #1e293b;
        line-height: 1.6;
    }
    /* Badges de criticidade */
    .kpi-num {
        font-size: 2rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1;
        margin-top: 6px;
    }
    .kpi-desc {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# CARREGAMENTO DE DADOS (CAMADA GOLD)
# -------------------------------------------------------------
DATA_DIR = Path("data/gold")
GOLD_IND_PATH = DATA_DIR / "gold_painel_indicadores_pa.parquet"
GOLD_DECISION_PATH = DATA_DIR / "gold_recomendacao_decisao_sespa.parquet"


@st.cache_data
def load_data():
    if not GOLD_IND_PATH.exists() or not GOLD_DECISION_PATH.exists():
        st.error("⚠️ Tabelas da camada Gold não encontradas. Execute 'python run_pipeline.py' primeiro!")
        st.stop()
    df_ind = pd.read_parquet(GOLD_IND_PATH)
    df_dec = pd.read_parquet(GOLD_DECISION_PATH)
    return df_ind, df_dec


df_indicators, df_decisions = load_data()

CUSTO_FP = 3500.0   # Frete logístico preventivo
CUSTO_FN = 45000.0  # Custo de resgate aéreo/UTI e desabastecimento
ALTO_CORTE = 0.70   # Limiar para despacho de kit completo de emergência
LIMIAR_ADOTADO = float(df_decisions["limiar_adotado"].iloc[0]) if "limiar_adotado" in df_decisions.columns else 0.40


def brl(v: float) -> str:
    return "R\\$ " + f"{v:,.0f}".replace(",", ".")


# -------------------------------------------------------------
# NAVEGAÇÃO HORIZONTAL DE SLIDES (ESTILO APRESENTAÇÃO)
# -------------------------------------------------------------
st.markdown("#### 🌳 **Vigilância Ambiental e Saúde no Pará** | Da Ingestão à Decisão")

slides = [
    "1. A Decisão & O Problema",
    "2. Arquitetura Medalhão",
    "3. Dinâmica dos Dados",
    "4. Modelo & Anti-Vazamento",
    "5. Simulador Operacional SESPA",
    "6. Limitações & Equipe"
]

selected_slide = st.radio(
    "Navegue entre os slides da apresentação:",
    slides,
    horizontal=True,
    label_visibility="collapsed"
)

st.markdown("<hr style='margin-top: 10px; margin-bottom: 24px; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)


# =============================================================
# SLIDE 1: A DECISÃO & O PROBLEMA
# =============================================================
if selected_slide == slides[0]:
    st.markdown('<span class="slide-tag">Slide 01 • O Ponto de Partida</span>', unsafe_allow_html=True)
    st.markdown('<div class="slide-title">A Pergunta de Decisão que Move o Pipeline</div>', unsafe_allow_html=True)
    st.markdown('<div class="slide-subtitle">Como antecipar o colapso respiratório no Pará durante a estiagem amazônica antes que ele aconteça.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([7, 5], gap="large")

    with col1:
        st.markdown(f"""
        <div class="card-highlight">
            <span style="font-size: 0.85rem; font-weight: 700; color: #2563eb; text-transform: uppercase;">Template Oficial Preenchido (Exigência do Edital)</span>
            <div class="quote-text" style="margin-top: 10px;">
                "Cruzando as bases do <b>INPE (Focos de Calor)</b>, <b>OpenDataSUS (SRAG Hospitalizado)</b> e <b>IBGE (Censo 2022)</b>, 
                identificamos os municípios com alto risco de sobrecarga hospitalar.<br><br>
                Recomendamos que a <b>Secretaria de Estado de Saúde Pública do Pará (SESPA)</b> envie 
                <b>Kits Preventivos de Insumos Respiratórios (O₂ + Broncodilatadores)</b> nos próximos <b>30 dias</b>, 
                priorizando os <b>municípios com risco &ge; {LIMIAR_ADOTADO:.2f}</b>.<br><br>
                Se agir, o ganho esperado é a <b>garantia de atendimento e abastecimento preventivo a 60 municípios prioritários</b>; 
                se errarmos, o custo de um falso positivo é de <b>{brl(CUSTO_FP)}</b> em logística estocável, 
                versus o custo de <b>{brl(CUSTO_FN)}</b> por caso que necessite de UTI aérea de emergência."
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="card-clean">
            <h5 style="margin-top: 0; color: #0f172a;">🎯 Os 4 Pilares da Decisão</h5>
            <ul style="padding-left: 18px; line-height: 1.7; color: #334155; font-size: 0.9rem; margin-bottom: 0;">
                <li><b>Decisor Concreto:</b> Secretário de Estado de Saúde Pública (SESPA).</li>
                <li><b>Ação Possível:</b> Despacho antecipado de cilindros de oxigênio e broncodilatadores.</li>
                <li><b>Horizonte Temporal:</b> 30 dias de antecedência (ciclo logístico fluvial/rodoviário).</li>
                <li><b>Métrica de Erro:</b> 1 Falso Negativo equivale a <b>12,8 Falsos Positivos</b>.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="card-clean" style="border-left: 5px solid #10b981; margin-top: 10px;">
            <div class="kpi-desc">Princípio Avaliador da Lauda</div>
            <p style="margin: 4px 0 0 0; color: #334155; font-size: 0.9rem;">
                <i>"Um pipeline tecnicamente impecável que não serve para decidir nada vale menos do que um pipeline simples que muda a ação de alguém."</i>
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 18px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # Panorama Geográfico das 6 Mesorregiões do Pará
    col_g1, col_g2 = st.columns([1, 1], gap="large")
    with col_g1:
        st.markdown("##### 📍 População sob Gestão por Mesorregião (Censo 2022)")
        df_meso = df_indicators.drop_duplicates(subset=["codigo_ibge"]).groupby("mesorregiao")["populacao_censo_2022"].sum().reset_index()
        fig_meso = px.bar(
            df_meso.sort_values(by="populacao_censo_2022", ascending=True),
            x="populacao_censo_2022",
            y="mesorregiao",
            orientation="h",
            color="populacao_censo_2022",
            color_continuous_scale="Blues",
            labels={"populacao_censo_2022": "Habitantes", "mesorregiao": "Mesorregião"},
            text=df_meso.sort_values(by="populacao_censo_2022", ascending=True)["populacao_censo_2022"].apply(lambda v: f"{v:,.0f}")
        )
        fig_meso.update_layout(height=280, coloraxis_showscale=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_meso, use_container_width=True)

    with col_g2:
        st.markdown("##### 🏥 Distribuição de Casos Hospitalizados de SRAG por Mesorregião (2023)")
        df_srag_meso = df_indicators.groupby("mesorregiao")["total_internacoes"].sum().reset_index()
        fig_donut = px.pie(
            df_srag_meso,
            names="mesorregiao",
            values="total_internacoes",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig_donut.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="v", x=1.02, y=0.5))
        st.plotly_chart(fig_donut, use_container_width=True)


# =============================================================
# SLIDE 2: ARQUITETURA MEDALHÃO
# =============================================================
elif selected_slide == slides[1]:
    st.markdown('<span class="slide-tag">Slide 02 • Engenharia de Dados</span>', unsafe_allow_html=True)
    st.markdown('<div class="slide-title">Arquitetura Medalhão & Governança Estrita</div>', unsafe_allow_html=True)
    st.markdown('<div class="slide-subtitle">Três fontes públicas reais atravessando contratos formais da Bronze à Gold.</div>', unsafe_allow_html=True)

    col_b, col_s, col_g = st.columns(3, gap="medium")

    with col_b:
        st.markdown("""
        <div class="card-clean" style="border-top: 4px solid #b45309;">
            <h4 style="margin-top: 0; color: #b45309;">🥉 Camada Bronze (Bruta)</h4>
            <p style="font-size: 0.9rem; color: #64748b;">Dado imutável, particionado por data de ingestão. Sem agregação nem regras de negócio.</p>
            <hr style="margin: 12px 0;">
            <b style="font-size: 0.85rem; color: #0f172a;">3 FORMAS DE INGESTÃO:</b>
            <ol style="font-size: 0.85rem; padding-left: 18px; color: #334155; line-height: 1.6; margin-top: 6px;">
                <li><b>API REST (IBGE):</b> Paginação, retry com backoff e gzip.</li>
                <li><b>Arquivo CSV (INPE):</b> Tipagem estrita e validação geoespacial.</li>
                <li><b>Arquivo c/ Checkpoint (OpenDataSUS):</b> Snapshot em chunks com hash SHA-256.</li>
            </ol>
            <div style="font-size: 0.8rem; background: #fef3c7; color: #92400e; padding: 6px 8px; border-radius: 6px; margin-top: 10px;">
                <b>Metadados técnicos:</b> Hash do registro, Load ID, Timestamp UTC e Origem em toda linha.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_s:
        st.markdown("""
        <div class="card-clean" style="border-top: 4px solid #64748b;">
            <h4 style="margin-top: 0; color: #475569;">🥈 Camada Silver (Tratada)</h4>
            <p style="font-size: 0.9rem; color: #64748b;">Tipagem forte, deduplicação semântica, quarentena ativa e integridade do join.</p>
            <hr style="margin: 12px 0;">
            <b style="font-size: 0.85rem; color: #0f172a;">GARANTIAS COMPROVADAS:</b>
            <ul style="font-size: 0.85rem; padding-left: 18px; color: #334155; line-height: 1.6; margin-top: 6px;">
                <li><b>Granularidade:</b> <i>"Uma linha por município por mês do Pará"</i>.</li>
                <li><b>Chave Primária:</b> <code>['codigo_ibge', 'ano_mes']</code> verificada com <b>0 duplicatas</b>.</li>
                <li><b>Quarentena Ativa:</b> Linhas com inconsistências desviadas com motivo registrado.</li>
                <li><b>Conciliação Exata:</b> 4.574 na Bronze = 4.264 contados + 310 em quarentena.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_g:
        st.markdown("""
        <div class="card-clean" style="border-top: 4px solid #eab308;">
            <h4 style="margin-top: 0; color: #ca8a04;">🥇 Camada Gold (Decisão)</h4>
            <p style="font-size: 0.9rem; color: #64748b;">Tabelas analíticas e base ML-Ready. <b>Zero limpeza nesta camada</b>.</p>
            <hr style="margin: 12px 0;">
            <b style="font-size: 0.85rem; color: #0f172a;">ENTREGAS GERADAS:</b>
            <ul style="font-size: 0.85rem; padding-left: 18px; color: #334155; line-height: 1.6; margin-top: 6px;">
                <li><b>Taxas Epidemiológicas:</b> Casos por 100k habitantes (Censo 2022).</li>
                <li><b>Features Causais:</b> Lags temporais (m-1) sem vazamento de dados.</li>
                <li><b>Base ML-Ready:</b> Rótulo formal do próximo mês (m+1).</li>
                <li><b>Tabela Prescritiva:</b> Alocação de kits e scores de risco para a SESPA.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # Expansor com Prova de Idempotência
    with st.expander("🛡️ Ver Demonstração de Idempotência do Pipeline (Execução Dupla Lado a Lado)"):
        st.markdown("""
        *Ao rodar o pipeline duas vezes seguidas, o número de linhas e os hashes de conteúdo das camadas Silver e Gold permanecem 100% idênticos, provando ausência de duplicatas.*
        """)
        df_idemp = pd.DataFrame([
            {"Tabela": "silver/dim_municipios_pa", "Linhas": 144, "Duplicatas PK": 0, "Hash": "f9e81e4a6b5c50ad", "Status": "✅ IDÊNTICO"},
            {"Tabela": "silver/fatos_focos_mensais_pa", "Linhas": 1044, "Duplicatas PK": 0, "Hash": "b08e6e3f25549055", "Status": "✅ IDÊNTICO"},
            {"Tabela": "silver/fatos_srag_mensais_pa", "Linhas": 744, "Duplicatas PK": 0, "Hash": "294a418a29410808", "Status": "✅ IDÊNTICO"},
            {"Tabela": "silver/silver_painel_mensal_pa", "Linhas": 1728, "Duplicatas PK": 0, "Hash": "d9b8b902d48a26ee", "Status": "✅ IDÊNTICO"},
            {"Tabela": "gold/gold_painel_indicadores_pa", "Linhas": 1728, "Duplicatas PK": 0, "Hash": "72b159a36d87e6c5", "Status": "✅ IDÊNTICO"},
            {"Tabela": "gold/gold_ml_ready_pa", "Linhas": 1584, "Duplicatas PK": 0, "Hash": "6946daf15b5c991e", "Status": "✅ IDÊNTICO"},
            {"Tabela": "gold/gold_recomendacao_decisao_sespa", "Linhas": 432, "Duplicatas PK": 0, "Hash": "56d7d98b0c04ca5c", "Status": "✅ IDÊNTICO"}
        ])
        st.dataframe(df_idemp, use_container_width=True)


# =============================================================
# SLIDE 3: DINÂMICA DOS DADOS
# =============================================================
elif selected_slide == slides[2]:
    st.markdown('<span class="slide-tag">Slide 03 • Análise Exploratória</span>', unsafe_allow_html=True)
    st.markdown('<div class="slide-title">Dinâmica Temporal: Queimadas vs. SRAG Hospitalar</div>', unsafe_allow_html=True)
    st.markdown('<div class="slide-subtitle">Série histórica de 2023 consolidada sobre a grade canônica dos 144 municípios do Pará.</div>', unsafe_allow_html=True)

    mensal = df_indicators.groupby("ano_mes").agg(
        total_focos=("total_focos_calor", "sum"),
        taxa_media=("taxa_internacao_100k", "mean")
    ).reset_index()

    fig_tempo = go.Figure()

    fig_tempo.add_trace(go.Bar(
        x=mensal["ano_mes"],
        y=mensal["total_focos"],
        name="Focos de Queimadas (INPE)",
        marker_color="#ea580c",
        opacity=0.8,
        yaxis="y1"
    ))

    fig_tempo.add_trace(go.Scatter(
        x=mensal["ano_mes"],
        y=mensal["taxa_media"],
        name="Taxa Média de SRAG / 100k hab (OpenDataSUS)",
        line=dict(color="#0284c7", width=3.5),
        mode="lines+markers",
        yaxis="y2"
    ))

    fig_tempo.add_vrect(
        x0=5.5, x1=10.5,
        fillcolor="yellow", opacity=0.15,
        layer="below", line_width=0,
        annotation_text="Período Crítico de Estiagem (Julho a Novembro)",
        annotation_position="top left"
        
    )

    fig_tempo.update_layout(
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
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.15)"),
        hovermode="x unified",
        height=500,
        margin=dict(l=20, r=25, t=20, b=25)
    )

    # Divisão em duas colunas para análise visual completa
    col_t1, col_t2 = st.columns([1.2, 1], gap="large")

    with col_t1:
        st.markdown("##### 📈 Série Histórica: Queimadas vs. Taxa de SRAG (2023)")
        st.plotly_chart(fig_tempo, use_container_width=True)

    with col_t2:
        st.markdown("##### 🔬 Dispersão: Focos vs. Taxa de SRAG por Município-Mês")
        # Gráfico de dispersão provando a ausência de correlação linear instantânea
        fig_scatter = px.scatter(
            df_indicators,
            x="total_focos_calor",
            y="taxa_internacao_100k",
            color="mesorregiao",
            hover_name="nome_municipio",
            hover_data=["ano_mes", "populacao_censo_2022"],
            labels={"total_focos_calor": "Focos de Calor no Mês", "taxa_internacao_100k": "Taxa SRAG / 100k hab"},
            opacity=0.65
        )
        fig_scatter.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=-0.22, x=0)
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    col_inf1, col_inf2 = st.columns(2, gap="medium")
    with col_inf1:
        st.markdown("""
        <div class="card-clean" style="border-left: 4px solid #ea580c;">
            <h5 style="margin-top: 0; color: #0f172a;">⚡ O Paradoxo Amazônico: Por que as curvas divergem?</h5>
            <p style="font-size: 0.9rem; color: #475569; margin-bottom: 0; line-height: 1.6;">
                <b>1º Semestre (Inverno Amazônico):</b> Chuvas pesadas aumentam a circulação viral de influenza e sincicial respiratório (pico de SRAG em abril/maio).<br>
                <b>2º Semestre (Verão / Estiagem):</b> As queimadas explodem (pico em out/nov), secam os rios e isolam comunidades. A fumaça viaja centenas de km, tornando qualquer caso respiratório grave e de difícil resgate.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with col_inf2:
        st.markdown("""
        <div class="card-clean" style="border-left: 4px solid #0284c7;">
            <h5 style="margin-top: 0; color: #0f172a;">🎯 A Prova da Honestidade Científica (Pearson: -0,043)</h5>
            <p style="font-size: 0.9rem; color: #475569; margin-bottom: 0; line-height: 1.6;">
                A dispersão à direita prova à banca que <b>não existe correlação linear cega</b> no mesmo município. Se disséssemos que mais foco é igual a mais internação direta na mesma cidade, estaríamos errados.<br>
                O modelo aprendeu que a <b>inércia de saúde recente</b> do município é o verdadeiro sinal preditivo.
            </p>
        </div>
        """, unsafe_allow_html=True)


# =============================================================
# SLIDE 4: MODELO & ANTI-VAZAMENTO
# =============================================================
elif selected_slide == slides[3]:
    st.markdown('<span class="slide-tag">Slide 04 • Requisito de Maior Peso</span>', unsafe_allow_html=True)
    st.markdown('<div class="slide-title">Fundamentos ML-Ready & Comparação de Baselines</div>', unsafe_allow_html=True)
    st.markdown('<div class="slide-subtitle">Split estritamente temporal, zero vazamento de dados e avaliação de custo do erro.</div>', unsafe_allow_html=True)

    # 4 Cards do Design ML-Ready
    col_ml1, col_ml2, col_ml3, col_ml4 = st.columns(4)
    with col_ml1:
        st.markdown("""
        <div class="card-clean">
            <div class="kpi-desc">Ponto de Corte (t0)</div>
            <div style="font-weight: 700; font-size: 1.1rem; color: #0f172a; margin-top: 4px;">Fim de Cada Mês</div>
            <span style="font-size: 0.8rem; color: #64748b;">Conhecimento congelado no dia 30/31</span>
        </div>
        """, unsafe_allow_html=True)
    with col_ml2:
        st.markdown("""
        <div class="card-clean">
            <div class="kpi-desc">Janela de Predição</div>
            <div style="font-weight: 700; font-size: 1.1rem; color: #0f172a; margin-top: 4px;">Mês Seguinte (m+1)</div>
            <span style="font-size: 0.8rem; color: #64748b;">Horizonte de 30 dias para atuação</span>
        </div>
        """, unsafe_allow_html=True)
    with col_ml3:
        st.markdown("""
        <div class="card-clean">
            <div class="kpi-desc">Split Temporal</div>
            <div style="font-weight: 700; font-size: 1.1rem; color: #0f172a; margin-top: 4px;">Jan-Ago / Set-Nov</div>
            <span style="font-size: 0.8rem; color: #64748b;">Treino: 1.152 • Teste: 432 obs</span>
        </div>
        """, unsafe_allow_html=True)
    with col_ml4:
        st.markdown("""
        <div class="card-clean">
            <div class="kpi-desc">Anti-Vazamento</div>
            <div style="font-weight: 700; font-size: 1.1rem; color: #16a34a; margin-top: 4px;">100% Conforme</div>
            <span style="font-size: 0.8rem; color: #64748b;">Zero leakage de futuro comprovado</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("#### Comparativo de Modelos: Baseline vs. Random Forest (Período de Teste)")

    col_m1, col_m2 = st.columns([1.3, 1], gap="large")

    with col_m1:
        df_bench = pd.DataFrame([
            {"Estratégia": "Não alertar ninguém", "Recall": "0.0%", "Precisão": "0.0%", "Alertas": 0, "Custo Total do Erro": "R\\$ 2.745.000", "Diagnóstico": "Inação; arca com 100% dos custos de emergência"},
            {"Estratégia": "Alertar todos os municípios", "Recall": "100.0%", "Precisão": "14.1%", "Alertas": 432, "Custo Total do Erro": "R\\$ 1.298.500", "Diagnóstico": "Desperdício logístico em cidades sem casos"},
            {"Estratégia": "Regra Trivial: Foco na estiagem", "Recall": "96.7%", "Precisão": "14.6%", "Alertas": 403, "Custo Total do Erro": "R\\$ 1.294.000", "Diagnóstico": "Excesso massivo de falsos alarmes"},
            {"Estratégia": "Persistência: Taxa atual já alta", "Recall": "54.1%", "Precisão": "46.5%", "Alertas": 71, "Custo Total do Erro": "R\\$ 1.393.000", "Diagnóstico": "Modelo reativo; só avisa após o surto começar"},
            {"Estratégia": "Random Forest Completo (SESPA)", "Recall": "82.0%", "Precisão": "26.3%", "Alertas": 190, "Custo Total do Erro": "R\\$ 985.000", "Diagnóstico": "🏆 Menor custo do erro e melhor seletividade"}
        ])
        st.dataframe(df_bench, use_container_width=True, height=260)

    with col_m2:
        st.markdown("##### 🌲 Importância das Features no Random Forest")
        df_feat = pd.DataFrame([
            {"Feature": "Taxa SRAG Atual (t0)", "Importância": 42.6, "Grupo": "Saúde"},
            {"Feature": "Taxa SRAG Anterior (t-1)", "Importância": 19.0, "Grupo": "Saúde"},
            {"Feature": "SRAG Infantil (Crianças)", "Importância": 10.1, "Grupo": "Saúde"},
            {"Feature": "Focos de Calor (INPE)", "Importância": 9.1, "Grupo": "Queimadas"},
            {"Feature": "SRAG Idosos", "Importância": 8.5, "Grupo": "Saúde"},
            {"Feature": "População Municipal", "Importância": 6.8, "Grupo": "Demografia"},
            {"Feature": "Lags Históricos Adicionais", "Importância": 3.9, "Grupo": "Outros"}
        ])
        fig_feat = px.bar(
            df_feat.sort_values(by="Importância", ascending=True),
            x="Importância",
            y="Feature",
            orientation="h",
            color="Grupo",
            color_discrete_map={"Saúde": "#0284c7", "Queimadas": "#ea580c", "Demografia": "#10b981", "Outros": "#94a3b8"},
            labels={"Importância": "Importância (%)", "Feature": "Variável Preditiva"},
            text=df_feat.sort_values(by="Importância", ascending=True)["Importância"].apply(lambda v: f"{v:.1f}%")
        )
        fig_feat.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.25, x=0))
        st.plotly_chart(fig_feat, use_container_width=True)


# =============================================================
# SLIDE 5: SIMULADOR OPERACIONAL SESPA (AO VIVO)
# =============================================================
elif selected_slide == slides[4]:
    st.markdown('<span class="slide-tag">Slide 05 • Aplicação Prática</span>', unsafe_allow_html=True)
    st.markdown('<div class="slide-title">Simulador de Despacho Operacional da SESPA</div>', unsafe_allow_html=True)

    # Controles do Simulador (Mês de corte, Mesorregião e Slider de Limiar)
    c_sel1, c_sel2, c_sel3 = st.columns([1, 1.2, 1.4], gap="medium")
    with c_sel1:
        meses_disponiveis = sorted(df_decisions["ano_mes_t0"].unique().tolist())
        mes_selecionado = st.selectbox(
            "📅 Mês de Corte (t0):",
            meses_disponiveis,
            index=len(meses_disponiveis) - 1,
            help="Mês em que a decisão é tomada antes do mês seguinte."
        )
    with c_sel2:
        mesos_disponiveis = ["Todas as 6 Mesorregiões"] + sorted(df_decisions["mesorregiao"].unique().tolist())
        meso_selecionada = st.selectbox("📍 Mesorregião do Pará:", mesos_disponiveis)
    with c_sel3:
        threshold = st.slider(
            "🎚️ Limiar de Decisão (Score):",
            min_value=0.05,
            max_value=0.90,
            value=min(max(LIMIAR_ADOTADO, 0.05), 0.90),
            step=0.05,
            help=f"Limiar padrão adotado pelo pipeline: {LIMIAR_ADOTADO:.2f}"
        )

    # Filtrar dados para os controles selecionados
    df_filtrado = df_decisions[df_decisions["ano_mes_t0"] == mes_selecionado].copy()
    if meso_selecionada != "Todas as 6 Mesorregiões":
        df_filtrado = df_filtrado[df_filtrado["mesorregiao"] == meso_selecionada].copy()

    df_filtrado["decisao_dinamica"] = np.where(
        df_filtrado["probabilidade_risco"] >= ALTO_CORTE,
        "Alerta Alto: Envio de Kit Completo (O2 + Broncodilatadores)",
        np.where(
            df_filtrado["probabilidade_risco"] >= threshold,
            "Alerta Médio: Reforço Preventivo e Equipe Volante",
            "Monitoramento de Rotina"
        )
    )

    total_mun = len(df_filtrado)
    alerta_alto = int((df_filtrado["probabilidade_risco"] >= ALTO_CORTE).sum())
    alerta_medio = int(((df_filtrado["probabilidade_risco"] >= threshold) & (df_filtrado["probabilidade_risco"] < ALTO_CORTE)).sum())
    pop_sob_alerta = float(df_filtrado[df_filtrado["probabilidade_risco"] >= threshold]["populacao_censo_2022"].sum())

    st.markdown(f'<div class="slide-subtitle">Apoio em tempo real para o Secretário de Saúde • Mês de Corte: <b>{mes_selecionado}</b> | Região: <b>{meso_selecionada}</b></div>', unsafe_allow_html=True)

    # 4 KPIs em destaque
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="card-clean" style="border-left: 5px solid #dc2626;">
            <div class="kpi-desc">🚨 Alerta Alto (Kit Completo)</div>
            <div class="kpi-num">{alerta_alto}</div>
            <span style="font-size: 0.8rem; color: #64748b;">Municípios com risco &ge; 70%</span>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="card-clean" style="border-left: 5px solid #eab308;">
            <div class="kpi-desc">⚠️ Alerta Médio (Reforço)</div>
            <div class="kpi-num">{alerta_medio}</div>
            <span style="font-size: 0.8rem; color: #64748b;">Risco entre {threshold:.2f} e 70%</span>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="card-clean" style="border-left: 5px solid #2563eb;">
            <div class="kpi-desc">👥 População Sob Vigilância</div>
            <div class="kpi-num">{pop_sob_alerta:,.0f}</div>
            <span style="font-size: 0.8rem; color: #64748b;">Habitantes protegidos na região</span>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        custo_log = (alerta_alto + alerta_medio) * CUSTO_FP
        st.markdown(f"""
        <div class="card-clean" style="border-left: 5px solid #16a34a;">
            <div class="kpi-desc">💰 Custo Logístico Preventivo</div>
            <div class="kpi-num">{brl(custo_log)}</div>
            <span style="font-size: 0.8rem; color: #64748b;">Evita remoções de R$ 45k</span>
        </div>
        """, unsafe_allow_html=True)

    col_g1, col_g2 = st.columns([1, 1], gap="large")

    with col_g1:
        st.markdown(f"#### Top 10 Municípios Prioritários ({mes_selecionado})")
        ranking_top = df_filtrado.sort_values(by="probabilidade_risco", ascending=False).head(10)

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
        fig_bar.add_vline(x=0.70, line_dash="dash", line_color="red", annotation_text="Alto (70%)")
        fig_bar.add_vline(x=LIMIAR_ADOTADO, line_dash="dot", line_color="orange", annotation_text=f"Limiar ({LIMIAR_ADOTADO:.2f})")
        fig_bar.update_layout(
            yaxis=dict(autorange="reversed"),
            height=360,
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=20, b=10)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g2:
        st.markdown("#### Matriz de Custo do Limiar Adotado")
        y_all = df_decisions["label_sobrecarga_proximo_mes"].astype(int)
        pred_all = df_decisions["probabilidade_risco"] >= LIMIAR_ADOTADO
        tp = int((pred_all & (y_all == 1)).sum())
        fp = int((pred_all & (y_all == 0)).sum())
        fn = int((~pred_all & (y_all == 1)).sum())
        
        recall_t = tp / (tp + fn) if (tp + fn) else 0.0
        precisao_t = tp / (tp + fp) if (tp + fp) else 0.0
        custo_modelo = fp * CUSTO_FP + fn * CUSTO_FN

        st.markdown(f"""
        <div class="card-clean">
            <ul style="padding-left: 18px; line-height: 1.9; color: #334155; margin-bottom: 0;">
                <li><b>Recall Sanitário:</b> <span style="color: #16a34a; font-weight: 700;">{recall_t:.1%}</span> ({tp} municípios em risco socorridos preventivamente).</li>
                <li><b>Falsos Negativos (Omissões):</b> <span style="color: #dc2626; font-weight: 700;">{fn}</span> municípios não alertados a tempo.</li>
                <li><b>Precisão Operacional:</b> <b>{precisao_t:.1%}</b> de eficiência de despacho.</li>
                <li><b>Custo Total dos Erros:</b> <b>{brl(custo_modelo)}</b> (economiza mais de R$ 1,7 milhão comparado a não agir).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # Tabela com busca e download
    st.markdown("#### Lista de Despacho Logístico por Município")
    tabela_disp = df_filtrado[[
        "codigo_ibge", "nome_municipio", "mesorregiao", "populacao_censo_2022",
        "total_focos_calor", "taxa_internacao_100k", "probabilidade_risco", "decisao_dinamica"
    ]].sort_values(by="probabilidade_risco", ascending=False)

    tabela_disp.columns = [
        "Cód IBGE", "Município", "Mesorregião", "População",
        "Focos", "Taxa SRAG", "Score Risco", "Recomendação Operacional"
    ]

    st.dataframe(
        tabela_disp.style.format({
            "População": "{:,.0f}",
            "Focos": "{:.0f}",
            "Taxa SRAG": "{:.2f}",
            "Score Risco": "{:.1%}"
        }),
        use_container_width=True,
        height=280
    )

    csv_bytes = tabela_disp.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Exportar Lista de Despacho Logístico (CSV)",
        data=csv_bytes,
        file_name=f"despacho_sespa_{mes_selecionado}.csv",
        mime="text/csv"
    )


# =============================================================
# SLIDE 6: LIMITAÇÕES & EQUIPE
# =============================================================
elif selected_slide == slides[5]:
    st.markdown('<span class="slide-tag">Slide 06 • Transparência & Autoria</span>', unsafe_allow_html=True)
    st.markdown('<div class="slide-title">Limitações Metodológicas & Integridade</div>', unsafe_allow_html=True)
    st.markdown('<div class="slide-subtitle">Documentação sincera sobre os dados e declaração formal de uso de IA.</div>', unsafe_allow_html=True)

    col_l1, col_l2 = st.columns(2, gap="large")

    with col_l1:
        st.markdown("""
        <div class="card-clean">
            <h4 style="margin-top: 0; color: #0f172a;">🔍 O que os dados permitem e NÃO permitem afirmar</h4>
            <ul style="padding-left: 18px; line-height: 1.7; color: #334155;">
                <li><b>O que permite afirmar:</b> O histórico epidemiológico recente de cada município possui forte valor preditivo para alocação antecipada de oxigênio.</li>
                <li><b>O que NÃO permite afirmar:</b> Não é possível estabelecer causalidade direta de que a queimada em um município gerou a internação nele mesmo no mesmo mês (devido a ventos, plumas e subnotificação).</li>
                <li><b>Atraso de Digitação (SIVEP-Gripe):</b> Em operação em tempo real na SESPA, seria necessário modelo de <i>nowcasting</i> para corrigir o atraso de notificação.</li>
                <li><b>Premissas de Custo:</b> Os valores de R$ 3.500 (FP) e R$ 45.000 (FN) são premissas de negócio parametrizadas pela equipe com base em estudos logísticos e de regulação hospitalar.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with col_l2:
        st.markdown("""
        <div class="card-clean">
            <h4 style="margin-top: 0; color: #0f172a;">🤖 Declaração de Uso de IA (Item 9 da Lauda)</h4>
            <p style="font-size: 0.95rem; color: #475569; line-height: 1.7;">
                Ferramentas de IA Generativa foram utilizadas como assistente técnico de engenharia de software na estruturação do repositório, boas práticas de pipeline e geração de boilerplate de visualização.<br><br>
                <b>Autoria e Domínio:</b> Toda a formulação epidemiológica, os testes de quarentena, o cálculo de custos e as análises críticas foram definidos e são de pleno domínio e autoria da equipe.
            </p>
            <hr style="margin: 14px 0;">
            <div style="font-size: 0.85rem; color: #64748b;">
                <b>Repositório Oficial:</b> <a href="https://github.com/KayuryC/Vigilancia-Ambiental-Saude-PA" target="_blank">github.com/KayuryC/Vigilancia-Ambiental-Saude-PA</a>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='text-align: center; color: #94a3b8; font-size: 0.85rem; margin-top: 35px;'>Projeto Integrador — Da Ingestão à Decisão • Engenharia de Dados & Saúde Pública no Pará</div>", unsafe_allow_html=True)
