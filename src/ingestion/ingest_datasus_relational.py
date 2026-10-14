"""
Módulo de Ingestão: Banco Relacional de Internações do DataSUS (SIH).
Atende ao Requisito 2:
- Ingestão via banco relacional com carga incremental baseada em Watermark (updated_at).
- Validação estrita de integridade clínica e geográfica com desvio para Quarentena.
- Metadados técnicos completos na camada Bronze (timestamp, sistema, objeto, load_id, hash).
- Idempotência demonstrável na extração incremental.
"""

import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.metadata import enrich_bronze_dataframe
from src.utils.quarantine import send_to_quarantine
from src.utils.watermark import WatermarkManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("data/operational_sih_sus.db")
BRONZE_DATASUS_DIR = Path("data/bronze/datasus")
PIPELINE_KEY = "DATASUS_SIH_RELATIONAL"


class DataSUSRelationalIngestor:
    """Coletor incremental por Watermark para banco relacional de internações."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.watermark_mgr = WatermarkManager()

    def fetch_incremental_records(self, watermark: str) -> pd.DataFrame:
        """Extrai apenas registros cujo updated_at seja estritamente superior ao watermark."""
        logger.info(f"Conectando ao banco relacional: {self.db_path}")
        logger.info(f"Buscando novos registros com updated_at > '{watermark}'...")

        conn = sqlite3.connect(self.db_path)
        query = """
            SELECT
                id_internacao,
                numero_aih,
                codigo_ibge_municipio,
                data_internacao,
                cid_principal,
                faixa_etaria,
                carater_atendimento,
                dias_permanencia,
                valor_total,
                created_at,
                updated_at
            FROM tb_internacoes_hospitalares
            WHERE updated_at > ?
            ORDER BY updated_at ASC
        """
        df = pd.read_sql_query(query, conn, params=[watermark])
        conn.close()
        return df

    def run_incremental_ingestion(self) -> Optional[Path]:
        """
        Executa a carga incremental:
        1. Consulta o último watermark gravado.
        2. Extrai novos registros do banco relacional.
        3. Valida integridade e encaminha inconsistências para quarentena.
        4. Enriquece com metadados técnicos Bronze e hash.
        5. Persiste lote na camada Bronze.
        6. Atualiza o watermark.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Banco de dados operacional não encontrado em: {self.db_path}")

        current_watermark = self.watermark_mgr.get_watermark(PIPELINE_KEY)
        df_new = self.fetch_incremental_records(current_watermark)

        if df_new.empty:
            logger.info("⚡ Nenhum novo registro encontrado desde o último watermark. Ingestão idempotente concluída.")
            return None

        logger.info(f"Registros extraídos na carga incremental: {len(df_new)}")

        # --- Validação e Quarentena ---
        # Regras:
        # 1. Dias de permanência não podem ser negativos
        # 2. Código IBGE deve ser válido (7 dígitos e começar com 15 para municípios do Pará)
        # 3. CID não pode ser nulo
        mask_dias_validos = df_new["dias_permanencia"] >= 0
        mask_ibge_valido = df_new["codigo_ibge_municipio"].str.startswith("15") & (df_new["codigo_ibge_municipio"].str.len() == 7)
        mask_cid_valido = df_new["cid_principal"].notna() & (df_new["cid_principal"].str.strip() != "")

        mask_valido = mask_dias_validos & mask_ibge_valido & mask_cid_valido

        df_valid = df_new[mask_valido].copy()
        df_invalid = df_new[~mask_valido].copy()

        if not df_invalid.empty:
            logger.warning(f"Detectados {len(df_invalid)} registros inconsistentes. Enviando para a Quarentena...")
            send_to_quarantine(
                records=df_invalid,
                source_system="DATASUS_SIH_RELATIONAL",
                reason="permanencia_negativa_ou_codigo_ibge_invalido"
            )

        # Padronização temporal
        df_valid["ano_mes"] = pd.to_datetime(df_valid["data_internacao"]).dt.strftime("%Y-%m")

        # Enriquecimento com Metadados Técnicos Obrigatórios da Bronze
        df_bronze = enrich_bronze_dataframe(
            df=df_valid,
            source_system="DATASUS_SIH_RELATIONAL",
            source_object="tb_internacoes_hospitalares"
        )

        BRONZE_DATASUS_DIR.mkdir(parents=True, exist_ok=True)
        hoje_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        load_id = df_bronze["load_id"].iloc[0]
        output_file = BRONZE_DATASUS_DIR / f"internacoes_pa_{hoje_str}_{load_id}.parquet"

        df_bronze.to_parquet(output_file, index=False)
        logger.info(f"✅ Ingestão Bronze DataSUS concluída! Salvo em: {output_file} ({len(df_bronze)} registros)")

        # Atualizar o Watermark para o maior updated_at do lote processado
        max_updated_at = str(df_new["updated_at"].max())
        self.watermark_mgr.update_watermark(
            pipeline_key=PIPELINE_KEY,
            new_watermark=max_updated_at,
            records_processed=len(df_valid),
            metadata={"output_file": str(output_file)}
        )

        return output_file


if __name__ == "__main__":
    ingestor = DataSUSRelationalIngestor()
    ingestor.run_incremental_ingestion()
