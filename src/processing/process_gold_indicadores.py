"""
Processamento Gold: Indicadores Analíticos e Normalizados de Vigilância em Saúde.
Atende ao Requisito 3:
- Granularidade declarada: 'Uma linha por município por mês do estado do Pará com indicadores analíticos e taxas normalizadas'.
- Chave primária verificada: 'codigo_ibge' + 'ano_mes' (sem duplicatas).
- Sem limpeza de dados brutos (se precisou limpar aqui, a Silver falhou).
- Normalização de indicadores por 100 mil habitantes com dados do Censo 2022.
- Engenharia de features temporais (Lags) estritamente causais (sem vazamento de dados).
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SILVER_DIR = Path("data/silver")
GOLD_DIR = Path("data/gold")


class GoldIndicadoresProcessor:
    """Calcula taxas epidemiológicas, indicadores de impacto ambiental e features temporais causais."""

    GRANULARIDADE = "Uma linha por município por mês do estado do Pará com indicadores analíticos e taxas normalizadas"
    PRIMARY_KEYS = ["codigo_ibge", "ano_mes"]

    def __init__(self, silver_dir: Path = SILVER_DIR, gold_dir: Path = GOLD_DIR):
        self.silver_dir = silver_dir
        self.gold_dir = gold_dir

    def load_silver_panel(self) -> pd.DataFrame:
        """Carrega a base unificada limpa da camada Silver."""
        file_path = self.silver_dir / "silver_painel_mensal_pa.parquet"
        if not file_path.exists():
            raise FileNotFoundError(f"Painel Silver não encontrado em: {file_path}")
        logger.info(f"Carregando painel Silver: {file_path}")
        return pd.read_parquet(file_path)

    def compute_indicators(self, df_silver: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula taxas normalizadas e métricas analíticas.
        Garante que nenhuma limpeza de dados seja feita (regra da camada Gold).
        """
        logger.info(f"Declarando granularidade: '{self.GRANULARIDADE}'")
        df = df_silver.copy()

        # Ordenação temporal estrita por município para cálculo seguro de defasagens (lags)
        df.sort_values(by=["codigo_ibge", "ano_mes"], inplace=True)

        # 1. Indicadores Normalizados pela População (Censo 2022)
        pop = df["populacao_censo_2022"].replace(0, np.nan)
        df["taxa_internacao_100k"] = (df["total_internacoes"] / pop * 100000.0).round(2).fillna(0.0)
        df["focos_por_10k_hab"] = (df["total_focos_calor"] / pop * 10000.0).round(2).fillna(0.0)
        df["taxa_internacao_infantil_100k"] = (df["internacoes_infantis"] / pop * 100000.0).round(2).fillna(0.0)
        df["taxa_internacao_idosos_100k"] = (df["internacoes_idosos"] / pop * 100000.0).round(2).fillna(0.0)

        # Custo médio por internação no SUS
        df["custo_medio_internacao"] = np.where(
            df["total_internacoes"] > 0,
            (df["custo_total_sus"] / df["total_internacoes"]).round(2),
            0.0
        )

        # 2. Definição Sazonal da Amazônia Legal
        # Mês numérico
        df["mes_num"] = df["ano_mes"].str[-2:].astype(int)
        # Período de estiagem no Pará: meses 7 a 11 (julho a novembro)
        df["periodo_estiagem"] = df["mes_num"].between(7, 11).astype(int)

        # 3. Features Temporais Históricas (Lag 1 Mês) — Garantia Anti-Vazamento:
        # O conhecimento sobre queimadas e internações no mês anterior (t-1)
        df["focos_lag_1m"] = df.groupby("codigo_ibge")["total_focos_calor"].shift(1).fillna(0)
        df["internacoes_lag_1m"] = df.groupby("codigo_ibge")["total_internacoes"].shift(1).fillna(0)
        df["taxa_internacao_lag_1m"] = df.groupby("codigo_ibge")["taxa_internacao_100k"].shift(1).fillna(0.0)

        # 4. Prova com código de ausência de duplicatas na PK composta
        duplicatas_pk = df.duplicated(subset=self.PRIMARY_KEYS).sum()
        assert duplicatas_pk == 0, f"Falha de integridade: existem {duplicatas_pk} duplicatas na PK composta!"
        logger.info(f"✅ Chave Primária composta {self.PRIMARY_KEYS} verificada: 0 duplicatas encontradas.")

        # Metadados de linhagem Gold
        df["gold_processed_at"] = datetime.now(timezone.utc).isoformat()
        return df

    def execute(self) -> Path:
        """Executa o processamento e persiste a tabela na camada Gold."""
        df_silver = self.load_silver_panel()
        df_gold = self.compute_indicators(df_silver)

        self.gold_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.gold_dir / "gold_painel_indicadores_pa.parquet"
        df_gold.to_parquet(output_path, index=False)

        logger.info(f"✅ Camada Gold gerada com sucesso em: {output_path} ({len(df_gold)} registros)")
        return output_path


if __name__ == "__main__":
    processor = GoldIndicadoresProcessor()
    processor.execute()
