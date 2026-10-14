"""
Processamento Silver: Dimensão de Municípios do Pará.
Atende ao Requisito 3:
- Granularidade declarada: 'Uma linha por município do estado do Pará'.
- Chave primária declarada e verificada: 'codigo_ibge' (sem duplicatas).
- Tipagem forte, padronização de texto e validação de contratos.
- Deduplicação semântica.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.quarantine import send_to_quarantine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BRONZE_IBGE_DIR = Path("data/bronze/ibge")
SILVER_DIR = Path("data/silver")


class SilverMunicipiosProcessor:
    """Processa a tabela de municípios do IBGE da camada Bronze para a Silver."""

    GRANULARIDADE = "Uma linha por município do estado do Pará"
    PRIMARY_KEY = "codigo_ibge"

    def __init__(self, bronze_dir: Path = BRONZE_IBGE_DIR, silver_dir: Path = SILVER_DIR):
        self.bronze_dir = bronze_dir
        self.silver_dir = silver_dir

    def load_latest_bronze(self) -> pd.DataFrame:
        """Carrega o arquivo mais recente da Bronze do IBGE."""
        files = sorted(self.bronze_dir.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"Nenhum arquivo encontrado em {self.bronze_dir}")
        latest_file = files[-1]
        logger.info(f"Carregando arquivo Bronze: {latest_file}")
        df = pd.read_parquet(latest_file)
        df["bronze_source_file"] = latest_file.name
        return df

    def transform_and_validate(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica padronização, tipagem estrita e validação de contratos.
        Envia registros inconsistentes para quarentena se necessário.
        """
        logger.info(f"Declarando granularidade: '{self.GRANULARIDADE}'")
        df = df_raw.copy()

        # 1. Padronização e tipagem estrita
        df["codigo_ibge"] = df["codigo_ibge"].astype(str).str.strip()
        df["nome_municipio"] = df["nome_municipio"].astype(str).str.strip().str.upper()
        df["uf"] = df["uf"].astype(str).str.strip().str.upper()
        df["mesorregiao"] = df["mesorregiao"].astype(str).str.strip()
        df["microrregiao"] = df["microrregiao"].astype(str).str.strip()
        df["populacao_censo_2022"] = pd.to_numeric(df["populacao_censo_2022"], errors="coerce").fillna(0).astype("int64")

        # 2. Validações de integridade
        mask_ibge_valido = df["codigo_ibge"].str.len() == 7
        mask_uf_valida = df["uf"] == "PA"
        mask_pop_valida = df["populacao_censo_2022"] > 0

        mask_valido = mask_ibge_valido & mask_uf_valida & mask_pop_valida
        df_invalid = df[~mask_valido]

        if not df_invalid.empty:
            logger.warning(f"Enviando {len(df_invalid)} registros inválidos para a Quarentena...")
            send_to_quarantine(
                records=df_invalid,
                source_system="SILVER_IBGE_MUNICIPIOS",
                reason="ibge_ou_uf_ou_populacao_invalida"
            )

        df_valid = df[mask_valido].copy()

        # 3. Deduplicação semântica pela Chave Primária
        total_antes = len(df_valid)
        df_dedup = df_valid.drop_duplicates(subset=[self.PRIMARY_KEY], keep="last")
        duplicatas_removidas = total_antes - len(df_dedup)
        if duplicatas_removidas > 0:
            logger.info(f"Deduplicação: {duplicatas_removidas} registros duplicados na chave '{self.PRIMARY_KEY}' removidos.")

        # 4. Prova com código de ausência de duplicatas na Chave Primária
        num_duplicatas = df_dedup[self.PRIMARY_KEY].duplicated().sum()
        assert num_duplicatas == 0, f"Falha de integridade: existem {num_duplicatas} duplicatas na chave primária!"
        logger.info(f"✅ Chave Primária '{self.PRIMARY_KEY}' verificada: 0 duplicatas encontradas.")

        # 5. Metadados de linhagem da Silver
        df_dedup = df_dedup.copy()
        df_dedup["processed_at"] = datetime.now(timezone.utc).isoformat()

        # Selecionar e ordenar colunas finais do contrato Silver
        colunas_silver = [
            "codigo_ibge",
            "nome_municipio",
            "uf",
            "mesorregiao",
            "microrregiao",
            "populacao_censo_2022",
            "processed_at",
            "bronze_source_file"
        ]
        return df_dedup[colunas_silver]

    def execute(self) -> Path:
        """Executa o processamento completo e grava na camada Silver."""
        df_bronze = self.load_latest_bronze()
        df_silver = self.transform_and_validate(df_bronze)

        self.silver_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.silver_dir / "dim_municipios_pa.parquet"
        df_silver.to_parquet(output_path, index=False)

        logger.info(f"✅ Camada Silver gravada com sucesso em: {output_path} ({len(df_silver)} registros)")
        return output_path


if __name__ == "__main__":
    processor = SilverMunicipiosProcessor()
    processor.execute()
