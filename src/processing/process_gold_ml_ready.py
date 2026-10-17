"""
Processamento Gold: Base ML-Ready e Suporte à Decisão da SESPA.
Atende aos Requisitos 5 e 6:
- Definição formal do Label, Coorte, Janela de Observação (< t0) e Janela de Predição (> t0).
- Limiar do rótulo (percentil 75) calculado SOMENTE com dados do período de treino.
- Split puramente temporal (Treino: Jan-Ago / Teste: Set-Nov), com limiar de decisão escolhido
  por validação cronológica DENTRO do treino (nunca olhando o teste).
- Comparação do modelo com baselines honestos: não alertar, alertar todos, regra de focos,
  persistência (histórico recente de casos) e modelos de ablação (só população, sem focos).
- Matriz de custos (premissas do grupo) e análise de sensibilidade a essas premissas.
- O relatório docs/requisito_ml_ready_decisao.md é GERADO por este arquivo. Para alterar o texto
  do relatório, edite este arquivo (edições feitas direto no .md são sobrescritas a cada execução).
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import fbeta_score, precision_score, recall_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GOLD_DIR = Path("data/gold")
DOCS_DIR = Path("docs")

TRAIN_END = "2023-08"      # último t0 do treino
TEST_START = "2023-09"     # primeiro t0 do teste
LABEL = "label_sobrecarga_proximo_mes"

# Premissas de custo do grupo (NÃO vêm de fonte pública; devem ser substituídas por valores da SESPA).
CUSTO_FP = 3500.0     # alerta desnecessário: logística de envio de kit
CUSTO_FN = 45000.0    # município com sobrecarga sem alerta: resgate, UTI, risco de óbito
MATERIALIDADE = CUSTO_FN   # diferença de custo menor que UM falso negativo equivale a um único caso a mais ou a menos: ruído
ALTO_CORTE = 0.70     # corte operacional de "Alerta Alto" (prioridade de despacho), não ligado a custo
THRESHOLD_GRID = [round(float(t), 2) for t in np.arange(0.05, 0.951, 0.05)]
N_MESES_VALIDACAO = 3

FEATURES_FOCOS = ["total_focos_calor", "focos_por_10k_hab", "focos_lag_1m"]
FEATURES = [
    "populacao_censo_2022",
    "total_focos_calor",
    "focos_por_10k_hab",
    "focos_lag_1m",
    "taxa_internacao_100k",
    "taxa_internacao_lag_1m",
    "internacoes_uti",
    "internacoes_infantis",
    "internacoes_idosos",
    "periodo_estiagem",
]
FEATURES_SEM_FOCOS = [c for c in FEATURES if c not in FEATURES_FOCOS]
FEATURES_SO_POPULACAO = ["populacao_censo_2022"]

N_NAO = "Não alertar ninguém"
N_TODOS = "Alertar todos"
N_REGRA = "Regra: foco de calor na estiagem (baseline original)"
N_PERSIST = "Persistência: taxa atual já acima do limiar"
N_POP = "Random Forest só com população"
N_SEMFOCOS = "Random Forest sem focos de calor"
N_COMPLETO = "Random Forest completo"


def brl(v: float) -> str:
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def pct(v: float) -> str:
    return f"{v:.1%}".replace(".", ",")


def num(v: float, casas: int = 2) -> str:
    return f"{v:.{casas}f}".replace(".", ",")


def fmt_razao(r: float) -> str:
    return f"{r:.0f}" if abs(r - round(r)) < 1e-9 else num(r, 1)


def lista_pt(itens) -> str:
    itens = list(itens)
    return itens[0] if len(itens) == 1 else "; ".join(itens[:-1]) + " e " + itens[-1]


def mes_br(ano_mes: str) -> str:
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    ano, mes = ano_mes.split("-")
    return f"{nomes[int(mes) - 1]}/{ano}"


def metricas(y_true, y_pred) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "f2": float(fbeta_score(y_true, y_pred, beta=2, zero_division=0)),
        "custo": fp * CUSTO_FP + fn * CUSTO_FN,
        "alertas": tp + fp,
    }


class GoldMLReadyProcessor:
    """Gera a base ML-Ready, avalia estratégias e produz a tabela de decisão para a SESPA."""

    GRANULARIDADE = "Uma linha por município por mês de corte (t0)"
    PRIMARY_KEYS = ["codigo_ibge", "ano_mes_t0"]

    def __init__(self, gold_dir: Path = GOLD_DIR, docs_dir: Path = DOCS_DIR):
        self.gold_dir = gold_dir
        self.docs_dir = docs_dir

    # ------------------------------------------------------------------ dados
    def load_gold_indicators(self) -> pd.DataFrame:
        file_path = self.gold_dir / "gold_painel_indicadores_pa.parquet"
        if not file_path.exists():
            raise FileNotFoundError(f"Tabela de indicadores Gold não encontrada em: {file_path}")
        return pd.read_parquet(file_path)

    def build_ml_dataset(self, df_ind: pd.DataFrame):
        """
        Features: somente dados até t0. Label: o que ocorre em t0 + 1.
        O limiar do rótulo (percentil 75 da taxa futura) usa APENAS linhas do período de treino,
        para que nenhuma informação do período de teste influencie a definição do positivo.
        """
        logger.info("Construindo base ML-Ready com janela de predição em t0 + 1 mês...")
        df = df_ind.copy()
        df.sort_values(by=["codigo_ibge", "ano_mes"], inplace=True)

        df["taxa_internacao_futura"] = df.groupby("codigo_ibge")["taxa_internacao_100k"].shift(-1)
        df["total_internacoes_futuras"] = df.groupby("codigo_ibge")["total_internacoes"].shift(-1)

        # O último mês observado não tem rótulo (falta o mês seguinte).
        df_ml = df[df["taxa_internacao_futura"].notna()].copy()

        treino = df_ml["ano_mes"] <= TRAIN_END
        limiar = float(df_ml.loc[treino, "taxa_internacao_futura"].quantile(0.75))
        assert limiar > 0, "Limiar do rótulo é zero: contagens muito esparsas para definir 'sobrecarga'."
        df_ml[LABEL] = (df_ml["taxa_internacao_futura"] >= limiar).astype(int)
        logger.info(f"Limiar do rótulo (p75 da taxa futura, só treino): {limiar:.3f} casos/100 mil hab")

        df_ml.rename(columns={"ano_mes": "ano_mes_t0"}, inplace=True)

        duplicatas = df_ml.duplicated(subset=self.PRIMARY_KEYS).sum()
        assert duplicatas == 0, f"Falha: {duplicatas} duplicatas na chave {self.PRIMARY_KEYS}"
        logger.info(f"✅ Chave Primária {self.PRIMARY_KEYS} verificada na base ML-Ready: 0 duplicatas.")
        return df_ml, limiar

    # ----------------------------------------------------------------- modelos
    @staticmethod
    def _novo_rf() -> RandomForestClassifier:
        return RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    def _escolher_limiar(self, df_train: pd.DataFrame, features: List[str]):
        """
        Escolhe o limiar de decisão que minimiza o custo esperado em validação CRONOLÓGICA dentro do
        treino: para validar o mês v, o modelo é ajustado só com t0 < v (cujos rótulos já eram
        conhecidos). Os últimos N_MESES_VALIDACAO meses do treino servem de validação. O teste não é usado.
        """
        meses = sorted(df_train["ano_mes_t0"].unique())
        ys, ps = [], []
        for v in meses[-N_MESES_VALIDACAO:]:
            tr = df_train[df_train["ano_mes_t0"] < v]
            va = df_train[df_train["ano_mes_t0"] == v]
            if tr[LABEL].nunique() < 2 or va.empty:
                continue
            clf = self._novo_rf().fit(tr[features], tr[LABEL])
            ps.append(clf.predict_proba(va[features])[:, 1])
            ys.append(va[LABEL].to_numpy())
        if not ys:
            return round(CUSTO_FP / (CUSTO_FP + CUSTO_FN), 2), {}, 0
        y, p = np.concatenate(ys), np.concatenate(ps)
        custos = {}
        for t in THRESHOLD_GRID:
            pred = p >= t
            custos[t] = float((pred & (y == 0)).sum() * CUSTO_FP + ((~pred) & (y == 1)).sum() * CUSTO_FN)
        melhor = min(custos, key=lambda t: (custos[t], t))   # empate: prefere o limiar menor
        return melhor, custos, int(len(y))

    def _variante(self, df_train: pd.DataFrame, df_test: pd.DataFrame, features: List[str]) -> Dict:
        limiar, custos_val, n_val = self._escolher_limiar(df_train, features)
        clf = self._novo_rf().fit(df_train[features], df_train[LABEL])
        proba = clf.predict_proba(df_test[features])[:, 1]
        return {"proba": proba, "threshold": limiar, "custos_validacao": custos_val,
                "n_validacao": n_val, "clf": clf, "features": features}

    def train_and_evaluate(self, df_ml: pd.DataFrame, limiar_sobrecarga: float) -> Dict:
        df_train = df_ml[df_ml["ano_mes_t0"] <= TRAIN_END].copy()
        df_test = df_ml[df_ml["ano_mes_t0"] >= TEST_START].copy()
        y_test = df_test[LABEL].to_numpy()
        logger.info(f"Split Temporal: Treino={len(df_train)} registros (Jan-Ago) | Teste={len(df_test)} registros (Set-Nov)")

        preds: Dict[str, np.ndarray] = {
            N_NAO: np.zeros(len(df_test), dtype=int),
            N_TODOS: np.ones(len(df_test), dtype=int),
            N_REGRA: ((df_test["total_focos_calor"] > 0) & (df_test["periodo_estiagem"] == 1)).astype(int).to_numpy(),
            N_PERSIST: (df_test["taxa_internacao_100k"] >= limiar_sobrecarga).astype(int).to_numpy(),
        }
        thresholds: Dict[str, float] = {}
        variantes = {}
        for nome, feats in [(N_POP, FEATURES_SO_POPULACAO), (N_SEMFOCOS, FEATURES_SEM_FOCOS), (N_COMPLETO, FEATURES)]:
            v = self._variante(df_train, df_test, feats)
            variantes[nome] = v
            thresholds[nome] = v["threshold"]
            preds[nome] = (v["proba"] >= v["threshold"]).astype(int)

        estrategias = []
        for nome, yp in preds.items():
            m = metricas(y_test, yp)
            m["nome"] = nome
            m["threshold"] = thresholds.get(nome)
            estrategias.append(m)
            lim = f" limiar={m['threshold']:.2f}" if m["threshold"] is not None else ""
            logger.info(f"   {nome:<55} custo={brl(m['custo']):>14} recall={m['recall']:.2f} precisão={m['precision']:.2f} alertas={m['alertas']}{lim}")

        # Sensibilidade à razão de custos FN/FP (limiares mantidos como escolhidos com as premissas atuais)
        razao_atual = CUSTO_FN / CUSTO_FP
        razoes = sorted({1.0, 3.0, 5.0, 10.0, razao_atual, 20.0, 30.0})
        sens = []
        for r in razoes:
            custos = {e["nome"]: e["fp"] * CUSTO_FP + e["fn"] * r * CUSTO_FP for e in estrategias}
            melhor = min(custos, key=custos.get)
            sens.append({"razao": r, "melhor": melhor, "custo": custos[melhor], "custo_modelo": custos[N_COMPLETO]})

        # Decisão: tabela de teste com o score do modelo completo
        comp = variantes[N_COMPLETO]
        thr = comp["threshold"]
        df_test["probabilidade_risco"] = comp["proba"].round(4)
        alto = max(ALTO_CORTE, thr)
        df_test["decisao_recomendada"] = np.where(
            df_test["probabilidade_risco"] >= alto,
            "Alerta Alto: Envio Imediato de Kit Completo (O2 + Broncodilatadores)",
            np.where(
                df_test["probabilidade_risco"] >= thr,
                "Alerta Médio: Reforço Preventivo e Equipe Volante",
                "Monitoramento de Rotina",
            ),
        )
        df_test["limiar_adotado"] = thr

        # Diagnósticos usados no texto
        imp = dict(zip(FEATURES, comp["clf"].feature_importances_))
        pos_teste = df_test[df_test[LABEL] == 1]
        total_focos_ano = df_ml["total_focos_calor"].sum()
        diag = {
            "corr_focos_casos": float(df_ml["total_focos_calor"].corr(df_ml["total_internacoes"])),
            "importancias": imp,
            "imp_focos": float(sum(imp[c] for c in FEATURES_FOCOS)),
            "media_casos_celula": float(df_ml["total_internacoes"].mean()),
            "pct_celulas_zero": float((df_ml["total_internacoes"] == 0).mean()),
            "pct_positivos_teste_ate_1_caso": float((pos_teste["total_internacoes_futuras"] <= 1).mean()) if len(pos_teste) else float("nan"),
            "pct_focos_no_teste": float(df_ml.loc[df_ml["ano_mes_t0"] >= TEST_START, "total_focos_calor"].sum() / total_focos_ano) if total_focos_ano else float("nan"),
            "n_pos_treino": int(df_train[LABEL].sum()), "n_pos_teste": int(len(pos_teste)),
            "ultimo_mes_teste": str(df_test["ano_mes_t0"].max()),
            "alertas_ultimo_mes": int(((df_test["ano_mes_t0"] == df_test["ano_mes_t0"].max()) & (df_test["probabilidade_risco"] >= thr)).sum()),
            "n_municipios": int(df_ml["codigo_ibge"].nunique()),
        }
        return {
            "df_ml": df_ml, "df_test_decision": df_test, "limiar_sobrecarga": limiar_sobrecarga,
            "threshold_adotado": thr, "alto_corte": alto, "estrategias": estrategias, "sens": sens,
            "custos_validacao": comp["custos_validacao"], "n_validacao": comp["n_validacao"], "diag": diag,
        }

    # ---------------------------------------------------------------- execução
    def execute(self) -> Path:
        df_ind = self.load_gold_indicators()
        df_ml, limiar = self.build_ml_dataset(df_ind)
        res = self.train_and_evaluate(df_ml, limiar)

        ml_path = self.gold_dir / "gold_ml_ready_pa.parquet"
        decision_path = self.gold_dir / "gold_recomendacao_decisao_sespa.parquet"
        res["df_ml"].to_parquet(ml_path, index=False)
        res["df_test_decision"].to_parquet(decision_path, index=False)
        logger.info(f"✅ Base ML-Ready gravada em: {ml_path} ({len(res['df_ml'])} registros)")
        logger.info(f"✅ Tabela de Decisão gravada em: {decision_path} ({len(res['df_test_decision'])} registros)")

        self._generate_ml_report(res)
        return decision_path

    # ----------------------------------------------------------------- relatório
    def _generate_ml_report(self, res: Dict) -> Path:
        est = {e["nome"]: e for e in res["estrategias"]}
        comp, semfocos, pop = est[N_COMPLETO], est[N_SEMFOCOS], est[N_POP]
        d = res["diag"]
        thr = res["threshold_adotado"]
        simples = [N_NAO, N_TODOS, N_REGRA, N_PERSIST, N_POP]   # referências que o modelo completo precisa superar
        melhor_simples = min(simples, key=lambda n: est[n]["custo"])
        melhor_geral = min(est, key=lambda n: est[n]["custo"])
        razao = CUSTO_FN / CUSTO_FP
        report_path = self.docs_dir / "requisito_ml_ready_decisao.md"

        L: List[str] = []
        a = L.append
        a("# Documentação da Base ML-Ready e Suporte à Decisão (Requisitos 5 e 6)")
        a("")
        a(f"Data de geração: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S UTC')}  ")
        a("Revisão e Auditoria Técnica: 16/10/2026 (seções 6 e 7 elaboradas por Fernando Fonseca e incorporadas ao gerador).")
        a("")
        a("> Este arquivo é **gerado** por `src/processing/process_gold_ml_ready.py`. Para alterar o texto, edite o gerador.")
        a("")
        a("---")
        a("")
        a("## 1. Especificação Formal da Modelagem (Requisito 5)")
        a("")
        a("| Elemento | Especificação Documentada |")
        a("| :--- | :--- |")
        a("| **Decisor** | Secretaria de Estado de Saúde Pública do Pará (SESPA) |")
        a("| **Ação Concreta** | Envio preventivo de Kits de Insumos Respiratórios (cilindros de oxigênio e broncodilatadores) |")
        a(f"| **Label ($Y$)** | $1$ (risco de sobrecarga por SRAG) se a taxa de casos hospitalizados de SRAG no mês seguinte for $\\ge$ {num(res['limiar_sobrecarga'], 2)} casos/100 mil hab (percentil 75 da taxa futura **calculado só com o período de treino**); $0$ caso contrário |")
        a("| **Regra de Rotulagem** | `label_sobrecarga_proximo_mes = (taxa_internacao_futura >= limiar_p75_treino)`, com `taxa_internacao_futura` obtida por `shift(-1)` dentro de cada município |")
        a(f"| **Coorte** | Os {d['n_municipios']} municípios do Pará, em todos os meses com mês seguinte observável (dez/2023 não tem rótulo e fica fora) |")
        a("| **Ponto de Corte ($t_0$)** | Fim de cada mês $m$: instante em que as features são congeladas |")
        a("| **Janela de Observação** | Meses $\\le m$ (focos de calor, casos de SRAG e população do Censo 2022) |")
        a("| **Janela de Predição** | Mês $m+1$ |")
        a(f"| **Split Adotado** | **Temporal:** treino com $t_0$ de jan a ago/2023; teste com $t_0$ de set a nov/2023. Limiar de decisão escolhido por validação cronológica dentro do treino |")
        a("| **Baselines** | Não alertar ninguém; alertar todos; regra de focos na estiagem; persistência (taxa atual já acima do limiar); Random Forest só com população; Random Forest sem focos de calor |")
        a(f"| **Métrica Principal** | **Custo esperado total (R$)** com a matriz de custos da seção 4. Recall, precisão e $F_2$ são métricas de apoio. Com apenas {pct(d['n_pos_teste'] / max(len(res['df_test_decision']), 1))} de positivos no teste, acurácia seria enganosa |")
        a("")
        a("---")
        a("")
        a("## 2. Checklist Anti-Vazamento")
        a("")
        a("- [x] **Toda feature existia antes de $t_0$?**  ")
        a("  *Sim. Nenhuma variável usa dados do mês $m+1$. Todas as covariáveis vêm do mês $m$ ou de lags anteriores ($m-1$), calculados por `groupby('codigo_ibge').shift(1)`.*")
        a("- [x] **As agregações foram calculadas apenas com dados anteriores a $t_0$?**  ")
        a("  *Sim para as features. O limiar do rótulo (percentil 75) é calculado apenas com linhas do período de treino. O limiar de decisão é escolhido por validação cronológica dentro do treino, ajustando o modelo só com meses anteriores ao mês validado.*")
        a("- [ ] **O split respeita tempo e grupo?**  ")
        a("  *Respeita o tempo. **Não separa por grupo, de propósito:** os mesmos municípios aparecem no treino e no teste, porque o uso real é prever o mês seguinte dos mesmos municípios. Efeito colateral: o modelo pode aprender características fixas de cada município (como a população). Por isso o modelo só com população está na comparação da seção 3.*")
        a("- [x] **Scalers, encoders e imputadores foram ajustados somente no treino?**  ")
        a("  *Não há scaler nem encoder (Random Forest). Não há imputação estatística: município sem notificação no mês tem 0 casos (regra de negócio da Silver). O modelo e o limiar de decisão são ajustados somente com dados de treino.*")
        if comp["f2"] > 0.85 or (comp["recall"] > 0.9 and comp["precision"] > 0.9):
            a("- [ ] **Métrica alta demais?**  ")
            a(f"  *ATENÇÃO: recall {pct(comp['recall'])} e precisão {pct(comp['precision'])} são altos demais para este problema. Investigar qual coluna pode estar carregando informação do futuro antes de usar este resultado.*")
        else:
            a("- [x] **Métrica alta demais?**  ")
            a(f"  *Não: recall {pct(comp['recall'])} e precisão {pct(comp['precision'])}. A amostra é pequena (teste: {d['n_pos_teste']} positivos em {len(res['df_test_decision'])} linhas), então as diferenças entre estratégias têm incerteza grande.*")
        a("")
        a("---")
        a("")
        a("## 3. Avaliação Comparativa (conjunto de teste, set a nov/2023)")
        a("")
        a("| Estratégia | Alertas | Recall | Precisão | $F_2$ | FP | FN | Custo esperado |")
        a("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | ---: |")
        for e in res["estrategias"]:
            nome = f"**{e['nome']}**" if e["nome"] == N_COMPLETO else e["nome"]
            a(f"| {nome} | {e['alertas']} | {pct(e['recall'])} | {pct(e['precision'])} | {pct(e['f2'])} | {e['fp']} | {e['fn']} | {brl(e['custo'])} |")
        a("")
        a(f"Estratégia de menor custo no teste: **{melhor_geral}** ({brl(est[melhor_geral]['custo'])}).")
        a("")
        dif_ref = est[melhor_simples]["custo"] - comp["custo"]
        if dif_ref >= MATERIALIDADE:
            a(f"O Random Forest completo teve custo {brl(comp['custo'])}, **menor** que o da melhor referência ({melhor_simples}: {brl(est[melhor_simples]['custo'])}): diferença de {brl(dif_ref)} ({pct(dif_ref / est[melhor_simples]['custo'])}). Com apenas {d['n_pos_teste']} positivos no teste, a evidência é modesta.")
        elif dif_ref > 0:
            a(f"O Random Forest completo teve custo {brl(comp['custo'])}, apenas {brl(dif_ref)} abaixo da melhor referência ({melhor_simples}: {brl(est[melhor_simples]['custo'])}). Essa diferença é menor que o custo de um único falso negativo ({brl(CUSTO_FN)}): **empate técnico, indistinguível de ruído**.")
        else:
            a(f"**O Random Forest completo NÃO superou a melhor referência.** Custo do modelo: {brl(comp['custo'])}; custo de \"{melhor_simples}\": {brl(est[melhor_simples]['custo'])}. Com estes dados e este recorte, o modelo não deve ser apresentado como superior.")
        if pop["custo"] <= comp["custo"]:
            a("")
            a(f"**Atenção:** o modelo só com população teve custo igual ou menor ({brl(pop['custo'])}) que o modelo completo ({brl(comp['custo'])}). Isso indica que o modelo está aprendendo principalmente o tamanho do município, e não um sinal adicional das demais variáveis.")
        a("")
        a(f"### 3.1. Matriz de confusão do Random Forest completo (limiar = {num(thr, 2)})")
        a(f"* **Verdadeiros Positivos (TP):** {comp['tp']} municípios-mês com sobrecarga alertados.")
        a(f"* **Falsos Negativos (FN):** {comp['fn']} municípios-mês com sobrecarga que não foram alertados.")
        a(f"* **Falsos Positivos (FP):** {comp['fp']} municípios-mês alertados sem sobrecarga.")
        a(f"* **Verdadeiros Negativos (TN):** {comp['tn']} municípios-mês corretamente mantidos em rotina.")
        a("")
        a("### 3.2. Os focos de calor ajudam a prever?")
        a(f"* Correlação de Pearson entre focos de calor e casos de SRAG no mesmo município-mês: **{num(d['corr_focos_casos'], 3)}**.")
        a(f"* Importância somada das variáveis de focos de calor no Random Forest completo: **{pct(d['imp_focos'])}**.")
        top = sorted(d["importancias"].items(), key=lambda kv: -kv[1])[:4]
        a("* Variáveis mais importantes: " + "; ".join(f"`{k}` ({pct(v)})" for k, v in top) + ".")
        delta = semfocos["custo"] - comp["custo"]
        if delta >= MATERIALIDADE:
            a(f"* Retirar os focos de calor **aumenta** o custo em {brl(delta)} ({semfocos['custo'] / comp['custo'] - 1:.0%}); os focos agregam algum valor preditivo, que deve ser confirmado com mais anos de dados.")
        elif delta > 0:
            a(f"* Retirar os focos de calor aumenta o custo em apenas {brl(delta)} (sem focos: {brl(semfocos['custo'])}; com focos: {brl(comp['custo'])}), menos que o custo de um único falso negativo ({brl(CUSTO_FN)}): diferença indistinguível de ruído. **Neste recorte, os focos de calor não agregaram poder preditivo mensurável.**")
        else:
            a(f"* Retirar os focos de calor **não piora** o custo (sem focos: {brl(semfocos['custo'])}; com focos: {brl(comp['custo'])}). **Neste recorte, os focos de calor não agregaram poder preditivo.**")
        a(f"* Modelo só com população: custo {brl(pop['custo'])}, recall {pct(pop['recall'])}, precisão {pct(pop['precision'])}.")
        a("")
        a("### 3.3. Qualidade do rótulo")
        a(f"* Média de {num(d['media_casos_celula'], 1)} casos por município-mês; {pct(d['pct_celulas_zero'])} dos município-mês têm zero casos.")
        a(f"* {pct(d['pct_positivos_teste_ate_1_caso'])} dos positivos do teste têm no máximo 1 caso no mês seguinte: com contagens tão pequenas, a taxa por 100 mil é instável e o rótulo mistura sinal e ruído.")
        a("")
        a("---")
        a("")
        a("## 4. Análise Econômico-Sanitária de Decisão (Requisito 6)")
        a("")
        a(f"* **Custo do Falso Positivo (FP):** {brl(CUSTO_FP)} por município-mês (logística de envio de kits).")
        a(f"* **Custo do Falso Negativo (FN):** {brl(CUSTO_FN)} por município-mês (resgate, leito intensivo, risco de óbito evitável).")
        a("* **Estes valores são premissas do grupo, sem fonte pública.** Devem ser substituídos por valores fornecidos pela SESPA antes de qualquer uso real.")
        a(f"* **Como o limiar foi escolhido:** menor custo esperado em validação cronológica dentro do treino (últimos {N_MESES_VALIDACAO} meses do treino, {res['n_validacao']} linhas), sem olhar o teste. Resultado: **{num(thr, 2)}**. Referência teórica para probabilidades calibradas: $c_{{FP}}/(c_{{FP}}+c_{{FN}})$ = {num(CUSTO_FP / (CUSTO_FP + CUSTO_FN), 3)}. As probabilidades do Random Forest **não são calibradas**, por isso o limiar foi escolhido empiricamente.")
        a("")
        a("### 4.1. Sensibilidade à premissa de custo")
        a("")
        a("| Razão FN/FP | Estratégia de menor custo no teste | Custo | Custo do Random Forest completo |")
        a("| :---: | :--- | ---: | ---: |")
        for s in res["sens"]:
            marca = " (premissa atual)" if abs(s["razao"] - razao) < 1e-9 else ""
            a(f"| {fmt_razao(s['razao'])}{marca} | {s['melhor']} | {brl(s['custo'])} | {brl(s['custo_modelo'])} |")
        a("")
        vence = [s["razao"] for s in res["sens"] if s["melhor"] == N_COMPLETO]
        if vence:
            a(f"O Random Forest completo é a estratégia de menor custo apenas nas razões FN/FP de {lista_pt([fmt_razao(r) for r in vence])}; nas demais razões testadas, outra estratégia custa menos. **A conclusão depende da premissa de custo: os valores reais da SESPA precisam ser obtidos antes de qualquer decisão.**")
        else:
            a("O Random Forest completo não é a estratégia de menor custo em nenhuma das razões FN/FP testadas. **A conclusão depende da premissa de custo: os valores reais da SESPA precisam ser obtidos antes de qualquer decisão.**")
        a("")
        a("Os limiares dos modelos foram mantidos como escolhidos com a premissa atual; a tabela mostra quão frágil é a conclusão se a razão de custos for outra.")
        a("")
        a("---")
        a("")
        a("## 5. A Frase de Decisão do Projeto")
        a("")
        imp_hist = d["importancias"]["taxa_internacao_100k"] + d["importancias"]["taxa_internacao_lag_1m"]
        if imp_hist > d["imp_focos"]:
            base_achado = f"o risco de sobrecarga por SRAG no mês seguinte é previsto principalmente pelo histórico recente de casos de cada município (importância somada de {pct(imp_hist)}, contra {pct(d['imp_focos'])} dos focos de calor)"
        else:
            base_achado = f"o risco de sobrecarga por SRAG no mês seguinte foi modelado com focos de calor (importância de {pct(d['imp_focos'])}), histórico de casos e população"
        if delta >= MATERIALIDADE:
            achado = f"{base_achado}; retirar os focos de calor aumentaria o custo em {brl(delta)} no teste"
        else:
            achado = f"{base_achado}, e os focos de calor não agregaram poder preditivo neste recorte (Pará, 2023)"
        ganho_vs_nada = est[N_NAO]["custo"] - comp["custo"]
        if ganho_vs_nada > 0:
            ganho = f"reduzir o custo esperado em {brl(ganho_vs_nada)} frente a não agir (de {brl(est[N_NAO]['custo'])} para {brl(comp['custo'])} no teste)"
            ganho_vs_todos = est[N_TODOS]["custo"] - comp["custo"]
            if ganho_vs_todos > 0:
                ganho += f" e em {brl(ganho_vs_todos)} ({pct(ganho_vs_todos / est[N_TODOS]['custo'])}) frente a alertar todos os municípios"
        else:
            ganho = "nenhum ganho demonstrável frente a não agir"
        a(f"> *\"Cruzando as bases do **INPE (focos de calor)**, **OpenDataSUS (SRAG hospitalizado)** e **IBGE (população do Censo 2022)**, identificamos que {achado}. Recomendamos que a **Secretaria de Estado de Saúde Pública do Pará (SESPA)** envie **kits preventivos de insumos respiratórios** nos próximos **30 dias**, priorizando os **{d['alertas_ultimo_mes']} municípios com score $\\ge$ {num(thr, 2)} em {mes_br(d['ultimo_mes_teste'])}**. Se agir, o ganho esperado é {ganho}; se errarmos, cada alerta falso custa {brl(CUSTO_FP)} e cada município com sobrecarga não alertado custa {brl(CUSTO_FN)} (premissas do grupo).\"*")
        a("")
        if dif_ref < MATERIALIDADE:
            if dif_ref > 0:
                a(f"**Ressalva obrigatória:** no teste, o modelo completo ficou apenas {brl(dif_ref)} abaixo da referência \"{melhor_simples}\" (empate técnico). A recomendação acima descreve o uso do score, mas os dados atuais não demonstram vantagem do modelo completo sobre essa referência.")
            else:
                a(f"**Ressalva obrigatória:** no teste, a referência \"{melhor_simples}\" teve custo menor ({brl(est[melhor_simples]['custo'])}) que o modelo completo ({brl(comp['custo'])}). A recomendação acima descreve o uso do score, mas os dados atuais não demonstram que o modelo completo seja a melhor opção.")
            a("")
        a("---")
        a("")
        a("## 6. Limitações dos Dados e Suposições do Modelo (Requisito 6)")
        a("")
        a("Conforme exigido pelas diretrizes de integridade analítica, explicitamos as fronteiras de inferência do pipeline:")
        a("")
        a("### 6.1. O que os dados NÃO permitem afirmar:")
        a(f"1. **Não comprovam causalidade:** o cruzamento mede associação e antecedência temporal no grão municipal, sem rastrear exposição individual à fumaça. Neste recorte, nem a associação estatística aparece (correlação de {num(d['corr_focos_casos'], 3)}).")
        a("2. **Subnotificação e atraso no registro:** casos de municípios remotos podem ser digitados no SIVEP-Gripe com atraso, mascarando a velocidade real da sobrecarga. O campo de evolução do caso também pode estar incompleto para casos recentes.")
        a("3. **Fatores meteorológicos mediadores:** não há variáveis de dispersão atmosférica (ventos e precipitação do INMET). Uma queimada em município vizinho pode projetar fumaça sobre outro município.")
        a(f"4. **Um único ano e teste curto:** os dados cobrem apenas 2023 e o teste tem 3 meses ({d['n_pos_teste']} positivos). {pct(d['pct_focos_no_teste'])} dos focos do ano ocorrem nos meses de teste, ou seja, o treino vê pouco da estação de queimadas e não há como aprender a resposta sazonal com um ano só.")
        a("5. **SRAG não é toda internação respiratória:** o SIVEP-Gripe registra casos de Síndrome Respiratória Aguda Grave notificados (hospitalizados ou óbitos), não todas as internações por doenças respiratórias.")
        a(f"6. **Contagens pequenas:** média de {num(d['media_casos_celula'], 1)} casos por município-mês e {pct(d['pct_celulas_zero'])} de células vazias tornam a taxa por 100 mil instável, principalmente nos municípios pequenos.")
        a("7. **Custos são premissas:** os valores de FP e FN não têm fonte pública (ver seção 4 e a sensibilidade em 4.1).")
        a("8. **Residência não é local de atendimento:** os casos são atribuídos ao município de residência; pacientes de municípios sem hospital são atendidos em municípios vizinhos, onde a pressão assistencial efetiva ocorre.")
        a("")
        a("### 6.2. O que seria necessário para afirmar com precisão diagnóstica:")
        a("* Dados de material particulado (PM2.5 e PM10) e de vento e precipitação do INMET/IBAMA.")
        a("* Dados de atenção primária (e-SUS / UBS), cobrindo atendimentos leves que antecedem a internação.")
        a("* Vários anos de dados (INPE e SIVEP-Gripe têm séries desde 2019) para treinar com ciclos sazonais completos e testar em um ano inteiro.")
        a("* Custos reais de remanejamento e de internação fornecidos pela SESPA.")
        a("")
        a("---")
        a("")
        a("## 7. Guia Operacional de Decisão Linha a Linha (Requisito 6)")
        a("")
        a("A tabela `gold_recomendacao_decisao_sespa.parquet` deve ser lida pelo gestor de logística da SESPA da seguinte forma:")
        a("")
        a("1. **`codigo_ibge` e `nome_municipio`:** identificação geográfica do destino da remessa.")
        a("2. **`ano_mes_t0`:** mês de corte. A remessa deve ser executada nos primeiros 5 dias úteis após $t_0$.")
        a("3. **`probabilidade_risco`:** score do Random Forest. **Não é uma probabilidade calibrada:** serve para ordenar municípios e comparar com o limiar, não para ser lido como \"chance de X%\".")
        a("4. **`decisao_recomendada`:**")
        a(f"   * **Score $\\ge$ {num(res['alto_corte'], 2)} (Alerta Alto):** despacho imediato de kit completo (oxigênio medicinal, concentradores e broncodilatadores) por transporte prioritário.")
        a(f"   * **{num(thr, 2)} $\\le$ Score $<$ {num(res['alto_corte'], 2)} (Alerta Médio):** reforço preventivo de estoque de medicamentos e sobreaviso à equipe médica regional.")
        a(f"   * **Score $<$ {num(thr, 2)} (Monitoramento de Rotina):** sem envio extra; abastecimento padrão.")
        a("5. **`limiar_adotado`:** limiar de decisão escolhido por custo na validação cronológica (constante em todas as linhas).")
        a("")

        self.docs_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(L), encoding="utf-8")
        logger.info(f"📄 Documento formal ML-Ready e Decisão gerado em: {report_path}")
        return report_path


if __name__ == "__main__":
    GoldMLReadyProcessor().execute()
