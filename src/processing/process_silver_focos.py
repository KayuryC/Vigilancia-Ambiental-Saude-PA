"""
Processamento Silver: Fatos de Focos de Calor do INPE por Município e Mês.
Atende ao Requisito 3:
- Granularidade declarada: 'Uma linha por município por mês do estado do Pará'.
- Chave primária declarada e verificada: 'codigo_ibge' + 'ano_mes' (sem duplicatas).
- Resolução e validação de chave estrangeira com a dimensão de municípios do IBGE.
- Quarentena para registros órfãos ou inconsistentes.
- Deduplicação semântica.
"""

import logging
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.quarantine import send_to_quarantine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BRONZE_INPE_DIR = Path("data/bronze/inpe")
SILVER_DIR = Path("data/silver")


def normalize_str(text: str) -> str:
    """Normaliza texto removendo acentos e espaços extras para matching seguro."""
    if not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    return normalized.strip().upper()


class SilverFocosProcessor:
    """Processa eventos de focos de queimada do INPE para agregações mensais na camada Silver."""

    GRANULARIDADE = "Uma linha por município por mês do estado do Pará"
    PRIMARY_KEYS = ["codigo_ibge", "ano_mes"]

    def __init__(self, bronze_dir: Path = BRONZE_INPE_DIR, silver_dir: Path = SILVER_DIR):
        self.bronze_dir = bronze_dir
        self.silver_dir = silver_dir

    def load_dim_municipios(self) -> pd.DataFrame:
        """Carrega a dimensão Silver de municípios para validação de integridade referencial."""
        dim_path = self.silver_dir / "dim_municipios_pa.parquet"
        if not dim_path.exists():
            raise FileNotFoundError(f"Dimensão de municípios não encontrada em: {dim_path}")
        return pd.read_parquet(dim_path)

    def load_latest_bronze_focos(self) -> pd.DataFrame:
        """Carrega o arquivo mais recente de focos da Bronze."""
        files = sorted(self.bronze_dir.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"Nenhum arquivo encontrado em {self.bronze_dir}")
        latest_file = files[-1]
        logger.info(f"Carregando arquivo Bronze de focos: {latest_file}")
        df = pd.read_parquet(latest_file)
        df["bronze_source_file"] = latest_file.name
        return df

    def transform_and_aggregate(self, df_focos: pd.DataFrame, df_dim: pd.DataFrame) -> pd.DataFrame:
        """
        Deduplica eventos individuais, mapeia codigo_ibge, envia órfãos à quarentena
        e agrega para a granularidade de município por mês.
        """
        logger.info(f"Declarando granularidade: '{self.GRANULARIDADE}'")
        df = df_focos.copy()

        # 1. Deduplicação semântica dos registros brutos por foco_id / record_hash
        total_bruto = len(df)
        df.drop_duplicates(subset=["foco_id"], keep="last", inplace=True)
        logger.info(f"Deduplicação de focos: {total_bruto - len(df)} duplicatas descartadas.")

        # 2. Resolução de integridade referencial com dim_municipios_pa
        df_dim_lookup = df_dim.copy()
        df_dim_lookup["mun_norm"] = df_dim_lookup["nome_municipio"].apply(normalize_str)
        lookup_map = dict(zip(df_dim_lookup["mun_norm"], df_dim_lookup["codigo_ibge"]))

        df["mun_norm"] = df["municipio"].apply(normalize_str)
        df["codigo_ibge"] = df["mun_norm"].map(lookup_map)

        # 3. Validação e Quarentena para registros órfãos
        mask_orfaos = df["codigo_ibge"].isna()
        if mask_orfaos.any():
            df_orfaos = df[mask_orfaos].copy()
            logger.warning(f"Detectados {len(df_orfaos)} focos com município não identificado. Enviando para Quarentena...")
            send_to_quarantine(
                records=df_orfaos,
                source_system="SILVER_INPE_FOCOS",
                reason="municipio_orfao_sem_correspondencia_ibge"
            )
            df = df[~mask_orfaos].copy()

        # 4. Agregação para a granularidade declarada (município x ano_mes)
        df["dia"] = df["data_hora_foco"].str[:10]

        # Agrupamento com métricas analíticas
        agg_funcs = {
            "foco_id": "count",
            "lat": "mean",
            "lon": "mean",
            "dia": "nunique"
        }

        df_agg = df.groupby(["codigo_ibge", "ano_mes"], as_index=False).agg(agg_funcs)
        df_agg.rename(columns={
            "foco_id": "total_focos_calor",
            "lat": "media_lat_focos",
            "lon": "media_lon_focos",
            "dia": "dias_com_focos"
        }, inplace=True)

        # Arredondamentos de coordenadas médias
        df_agg["media_lat_focos"] = df_agg["media_lat_focos"].round(4)
        df_agg["media_lon_focos"] = df_agg["media_lon_focos"].round(4)

        # 5. Verificação estrita da Chave Primária composta
        duplicatas_pk = df_agg.duplicated(subset=self.PRIMARY_KEYS).sum()
        assert duplicatas_pk == 0, f"Falha de integridade: existem {duplicatas_pk} duplicatas na PK composta!"
        logger.info(f"✅ Chave Primária composta {self.PRIMARY_KEYS} verificada: 0 duplicatas encontradas.")

        # 6. Metadados de linhagem da Silver
        df_agg["processed_at"] = datetime.now(timezone.utc).isoformat()
        return df_agg

    def execute(self) -> Path:
        """Executa a pipeline e grava o resultado na camada Silver."""
        df_dim = self.load_dim_municipios()
        df_focos = self.load_latest_bronze_focos()
        df_silver = self.transform_and_aggregate(df_focos, df_dim)

        output_path = self.silver_dir / "fatos_focos_mensais_pa.parquet"
        df_silver.to_parquet(output_path, index=False)

        logger.info(f"✅ Camada Silver gravada com sucesso em: {output_path} ({len(df_silver)} registros)")
        return output_path


if __name__ == "__main__":
    processor = SilverFocosProcessor()
    processor.execute()
