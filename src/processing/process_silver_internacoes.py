"""
Processamento Silver: Fatos de Internações Respiratórias do DataSUS por Município e Mês.
Atende ao Requisito 3:
- Granularidade declarada: 'Uma linha por município por mês do estado do Pará'.
- Chave primária declarada e verificada: 'codigo_ibge' + 'ano_mes' (sem duplicatas).
- Resolução e validação de integridade referencial com a dimensão de municípios do IBGE.
- Quarentena para registros órfãos ou inconsistentes.
- Deduplicação semântica por AIH (Autorização de Internação Hospitalar).
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

BRONZE_DATASUS_DIR = Path("data/bronze/datasus")
SILVER_DIR = Path("data/silver")


class SilverInternacoesProcessor:
    """Processa internações hospitalares da Bronze para agregações mensais na camada Silver."""

    GRANULARIDADE = "Uma linha por município por mês do estado do Pará"
    PRIMARY_KEYS = ["codigo_ibge", "ano_mes"]

    def __init__(self, bronze_dir: Path = BRONZE_DATASUS_DIR, silver_dir: Path = SILVER_DIR):
        self.bronze_dir = bronze_dir
        self.silver_dir = silver_dir

    def load_dim_municipios(self) -> pd.DataFrame:
        """Carrega a dimensão Silver de municípios para validação referencial."""
        dim_path = self.silver_dir / "dim_municipios_pa.parquet"
        if not dim_path.exists():
            raise FileNotFoundError(f"Dimensão de municípios não encontrada em: {dim_path}")
        return pd.read_parquet(dim_path)

    def load_all_bronze_internacoes(self) -> pd.DataFrame:
        """Carrega e consolida arquivos de lote da Bronze do DataSUS."""
        files = sorted(self.bronze_dir.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"Nenhum arquivo encontrado em {self.bronze_dir}")

        dfs = []
        for f in files:
            logger.info(f"Carregando lote Bronze DataSUS: {f.name}")
            df_batch = pd.read_parquet(f)
            df_batch["bronze_source_file"] = f.name
            dfs.append(df_batch)

        return pd.concat(dfs, ignore_index=True)

    def transform_and_aggregate(self, df_raw: pd.DataFrame, df_dim: pd.DataFrame) -> pd.DataFrame:
        """
        Deduplica AIHs, valida integridade com municípios do IBGE,
        encaminha órfãos à quarentena e agrega no grão (município x ano_mes).
        """
        logger.info(f"Declarando granularidade: '{self.GRANULARIDADE}'")
        df = df_raw.copy()

        # 1. Deduplicação semântica pela chave do evento (numero_aih)
        total_bruto = len(df)
        df.drop_duplicates(subset=["numero_aih"], keep="last", inplace=True)
        logger.info(f"Deduplicação de AIHs: {total_bruto - len(df)} duplicatas descartadas.")

        # 2. Padronização e tipagem
        df["codigo_ibge"] = df["codigo_ibge_municipio"].astype(str).str.strip()
        df["dias_permanencia"] = pd.to_numeric(df["dias_permanencia"], errors="coerce").fillna(0).astype(int)
        df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0.0).astype(float)
        df["ano_mes"] = df["ano_mes"].astype(str).str.strip()

        # 3. Validação de integridade referencial com dim_municipios_pa
        codigos_validos = set(df_dim["codigo_ibge"])
        mask_orfaos = ~df["codigo_ibge"].isin(codigos_validos)

        if mask_orfaos.any():
            df_orfaos = df[mask_orfaos].copy()
            logger.warning(f"Detectadas {len(df_orfaos)} internações com código IBGE não cadastrado na dimensão. Enviando para Quarentena...")
            send_to_quarantine(
                records=df_orfaos,
                source_system="SILVER_DATASUS_INTERNACOES",
                reason="codigo_ibge_orfao_nao_encontrado_na_dimensao"
            )
            df = df[~mask_orfaos].copy()

        # 4. Criação de métricas booleanas para contagem segmentada
        df["is_urgencia"] = (df["carater_atendimento"] == "Urgência").astype(int)
        df["is_infantil"] = (df["faixa_etaria"] == "0-4 anos").astype(int)
        df["is_idoso"] = (df["faixa_etaria"] == "60+ anos").astype(int)

        # 5. Agregação no grão (codigo_ibge, ano_mes)
        df_agg = df.groupby(["codigo_ibge", "ano_mes"], as_index=False).agg(
            total_internacoes=("numero_aih", "count"),
            total_dias_leito=("dias_permanencia", "sum"),
            media_dias_leito=("dias_permanencia", "mean"),
            custo_total_sus=("valor_total", "sum"),
            internacoes_urgencia=("is_urgencia", "sum"),
            internacoes_infantis=("is_infantil", "sum"),
            internacoes_idosos=("is_idoso", "sum")
        )

        df_agg["media_dias_leito"] = df_agg["media_dias_leito"].round(2)
        df_agg["custo_total_sus"] = df_agg["custo_total_sus"].round(2)

        # 6. Prova com código de unicidade da Chave Primária
        duplicatas_pk = df_agg.duplicated(subset=self.PRIMARY_KEYS).sum()
        assert duplicatas_pk == 0, f"Falha de integridade: existem {duplicatas_pk} duplicatas na PK composta!"
        logger.info(f"✅ Chave Primária composta {self.PRIMARY_KEYS} verificada: 0 duplicatas encontradas.")

        # 7. Metadados de linhagem da Silver
        df_agg["processed_at"] = datetime.now(timezone.utc).isoformat()
        return df_agg

    def execute(self) -> Path:
        """Executa a pipeline e grava o resultado na camada Silver."""
        df_dim = self.load_dim_municipios()
        df_raw = self.load_all_bronze_internacoes()
        df_silver = self.transform_and_aggregate(df_raw, df_dim)

        output_path = self.silver_dir / "fatos_internacoes_mensais_pa.parquet"
        df_silver.to_parquet(output_path, index=False)

        logger.info(f"✅ Camada Silver gravada com sucesso em: {output_path} ({len(df_silver)} registros)")
        return output_path


if __name__ == "__main__":
    processor = SilverInternacoesProcessor()
    processor.execute()
