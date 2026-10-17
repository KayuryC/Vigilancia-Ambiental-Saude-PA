"""
Processamento Silver: casos de SRAG hospitalizados (SIVEP-Gripe / OpenDataSUS)
por município de residência e mês de notificação.

Atende ao Requisito 3:
- Granularidade declarada: 'Uma linha por município (de residência) por mês (de notificação) do Pará'.
- Chave primária declarada e verificada: 'codigo_ibge' + 'ano_mes' (sem duplicatas).
- Integridade referencial com a dimensão de municípios do IBGE (o SRAG usa o código de
  6 dígitos; a dimensão usa 7 — a ligação é feita pelos 6 primeiros dígitos, que são
  únicos entre os 144 municípios do Pará, e isso é verificado em código).
- Quarentena, com motivo, para todo registro que não entra na contagem.

Privacidade (Seção 9 do enunciado): o arquivo de origem tem uma linha por pessoa. A
agregação acontece AQUI, na passagem Bronze -> Silver. A tabela Silver tem apenas
contagens por município e mês, sem nenhum dado individual. A quarentena guarda só um
subconjunto mínimo de colunas (identificador da notificação, datas, UF/município e o
hash que permite achar a linha na Bronze), nunca o registro completo.

Definições de negócio (documentar no dicionário de dados):
- Mês: mês da DATA DE NOTIFICAÇÃO (DT_NOTIFIC), campo obrigatório. É o instante em que
  o caso passa a ser conhecido pelo sistema de vigilância, o que importa para o t0.
- Município: município de RESIDÊNCIA (CO_MUN_RES), por ser o que casa com a população
  do Censo (denominador da taxa) e com a exposição a queimadas.
- Caso contado: HOSPITAL == '1' (hospitalizado). Residentes de outras UFs, casos sem
  residência, sem data válida, não hospitalizados etc. vão para a quarentena.
- internacoes_uti: UTI == '1'. internacoes_infantis: 0 a 4 anos. internacoes_idosos: 60+.
- obitos_srag: EVOLUCAO == '2' (óbito por SRAG).
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.quarantine import send_to_quarantine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BRONZE_SRAG_DIR = Path("data/bronze/srag")
SILVER_DIR = Path("data/silver")

ANO_ALVO = 2023
UF_ALVO = "PA"
QUARANTINE_SOURCE = "SILVER_SRAG"

# Subconjunto mínimo de colunas que vai para a quarentena (sem dado pessoal sensível).
QUARANTINE_COLS = [
    "record_hash", "load_id", "NU_NOTIFIC", "DT_NOTIFIC", "SG_UF_NOT", "SG_UF",
    "CO_MUN_RES", "HOSPITAL", "NU_IDADE_N", "TP_IDADE",
]


class SilverSRAGProcessor:
    """Transforma a Bronze do SRAG em fatos mensais por município na camada Silver."""

    GRANULARIDADE = "Uma linha por município (de residência) por mês (de notificação) do estado do Pará"
    PRIMARY_KEYS = ["codigo_ibge", "ano_mes"]

    def __init__(self, bronze_dir: Path = BRONZE_SRAG_DIR, silver_dir: Path = SILVER_DIR):
        self.bronze_dir = Path(bronze_dir)
        self.silver_dir = Path(silver_dir)

    # ----------------------------------------------------------------- entrada
    def load_dim_municipios(self) -> pd.DataFrame:
        dim_path = self.silver_dir / "dim_municipios_pa.parquet"
        if not dim_path.exists():
            raise FileNotFoundError(f"Dimensão de municípios não encontrada em: {dim_path}")
        return pd.read_parquet(dim_path)

    def load_latest_bronze(self) -> pd.DataFrame:
        """
        Cada arquivo da Bronze é um snapshot COMPLETO do banco vivo. Ler todos somaria
        o mesmo caso várias vezes (ou versões antigas dele), então a Silver usa só a
        carga mais recente. O nome do arquivo contém data e hora da carga, então a
        ordenação alfabética coincide com a ordem cronológica.
        """
        files = sorted(self.bronze_dir.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"Nenhum arquivo encontrado em {self.bronze_dir}")
        latest = files[-1]
        logger.info(f"Carregando snapshot Bronze mais recente do SRAG: {latest.name} (de {len(files)} carga(s) disponíveis)")
        return pd.read_parquet(latest)

    # --------------------------------------------------------------- quarentena
    @staticmethod
    def _slim(df: pd.DataFrame) -> pd.DataFrame:
        return df[[c for c in QUARANTINE_COLS if c in df.columns]]

    def _excluir(self, df: pd.DataFrame, mask: pd.Series, reason: str, stats: Dict[str, int]) -> pd.DataFrame:
        """Envia para a quarentena os registros marcados em `mask` e devolve o restante."""
        n = int(mask.sum())
        if n:
            logger.warning(f"{n} registro(s) fora da contagem — motivo: {reason}. Enviando para a Quarentena...")
            send_to_quarantine(records=self._slim(df[mask]), source_system=QUARANTINE_SOURCE, reason=reason)
            stats[reason] = n
        return df[~mask].copy()

    # ------------------------------------------------------------ transformação
    def transform_and_aggregate(self, df_raw: pd.DataFrame, df_dim: pd.DataFrame) -> pd.DataFrame:
        logger.info(f"Declarando granularidade: '{self.GRANULARIDADE}'")
        stats: Dict[str, int] = {}
        df = df_raw.copy()
        total_bronze = len(df)

        # 1. Deduplicação: só registros idênticos (mesmo hash). Sem correção silenciosa.
        df = df.drop_duplicates(subset=["record_hash"], keep="first")
        duplicatas = total_bronze - len(df)
        logger.info(f"Deduplicação por hash do registro: {duplicatas} duplicata(s) exata(s) descartada(s).")

        # 2. Tipagem forte
        df["dt_notific"] = pd.to_datetime(df["DT_NOTIFIC"], format="ISO8601", errors="coerce", utc=True)
        idade_n = pd.to_numeric(df["NU_IDADE_N"], errors="coerce")
        # TP_IDADE: 1 = dias, 2 = meses, 3 = anos. Dias e meses contam como 0 ano completo.
        df["idade_anos"] = np.where(df["TP_IDADE"] == "3", idade_n, np.where(df["TP_IDADE"].isin(["1", "2"]), 0.0, np.nan))

        # 3. Validações com quarentena (cada registro é excluído por no máximo um motivo)
        df = self._excluir(df, df["dt_notific"].isna(), "dt_notific_invalida", stats)
        df = self._excluir(df, df["dt_notific"].dt.year != ANO_ALVO, f"dt_notific_fora_de_{ANO_ALVO}", stats)
        df = self._excluir(df, df["SG_UF"].str.strip() == "", "residencia_ausente", stats)
        df = self._excluir(df, df["SG_UF"] != UF_ALVO, "residencia_fora_do_para", stats)
        df = self._excluir(df, df["CO_MUN_RES"].str.strip() == "", "municipio_residencia_ausente", stats)

        # 4. Integridade referencial com a dimensão do IBGE (código de 6 -> 7 dígitos)
        codigos7 = df_dim["codigo_ibge"].astype(str).str.strip()
        mapa_6_para_7 = dict(zip(codigos7.str[:6], codigos7))
        assert len(mapa_6_para_7) == len(codigos7), "Os 6 primeiros dígitos do código IBGE não são únicos na dimensão!"
        df = self._excluir(df, ~df["CO_MUN_RES"].str.strip().isin(list(mapa_6_para_7.keys())), "municipio_residencia_orfao", stats)

        df = self._excluir(df, (df["idade_anos"] < 0) | (df["idade_anos"] > 120), "idade_invalida", stats)
        df = self._excluir(df, df["HOSPITAL"] != "1", "nao_hospitalizado", stats)

        # 5. Chaves e métricas do registro
        df["codigo_ibge"] = df["CO_MUN_RES"].str.strip().map(mapa_6_para_7)
        df["ano_mes"] = df["dt_notific"].dt.strftime("%Y-%m")
        df["is_uti"] = (df["UTI"] == "1").astype(int)
        df["is_infantil"] = (df["idade_anos"] <= 4).astype(int)   # idade ausente (NaN) dá False
        df["is_idoso"] = (df["idade_anos"] >= 60).astype(int)
        df["is_obito_srag"] = (df["EVOLUCAO"] == "2").astype(int)

        # 6. Agregação no grão (codigo_ibge, ano_mes) — aqui o dado individual desaparece
        df_agg = df.groupby(self.PRIMARY_KEYS, as_index=False).agg(
            total_internacoes=("record_hash", "count"),
            internacoes_uti=("is_uti", "sum"),
            internacoes_infantis=("is_infantil", "sum"),
            internacoes_idosos=("is_idoso", "sum"),
            obitos_srag=("is_obito_srag", "sum"),
        )
        for col in ["total_internacoes", "internacoes_uti", "internacoes_infantis", "internacoes_idosos", "obitos_srag"]:
            df_agg[col] = df_agg[col].astype("int64")

        # 7. Prova de unicidade da chave primária
        duplicatas_pk = df_agg.duplicated(subset=self.PRIMARY_KEYS).sum()
        assert duplicatas_pk == 0, f"Falha de integridade: existem {duplicatas_pk} duplicatas na PK composta!"
        logger.info(f"✅ Chave Primária composta {self.PRIMARY_KEYS} verificada: 0 duplicatas encontradas.")

        # 8. Conciliação: tudo o que entrou na Silver mais tudo o que foi para a quarentena
        #    mais as duplicatas exatas tem que fechar com o total da Bronze.
        contados = int(df_agg["total_internacoes"].sum())
        excluidos = sum(stats.values())
        assert contados + excluidos + duplicatas == total_bronze, (
            f"Conciliação falhou: {contados} contados + {excluidos} em quarentena + "
            f"{duplicatas} duplicatas != {total_bronze} na Bronze"
        )
        logger.info(
            f"✅ Conciliação: {total_bronze} na Bronze = {contados} contados + {excluidos} em quarentena "
            f"+ {duplicatas} duplicatas exatas."
        )
        for motivo, n in stats.items():
            logger.info(f"   quarentena[{motivo}] = {n}")

        df_agg["processed_at"] = datetime.now(timezone.utc).isoformat()
        return df_agg

    def execute(self) -> Path:
        df_dim = self.load_dim_municipios()
        df_raw = self.load_latest_bronze()
        df_silver = self.transform_and_aggregate(df_raw, df_dim)

        self.silver_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.silver_dir / "fatos_srag_mensais_pa.parquet"
        df_silver.to_parquet(output_path, index=False)
        logger.info(f"✅ Camada Silver gravada com sucesso em: {output_path} ({len(df_silver)} registros)")
        return output_path


if __name__ == "__main__":
    SilverSRAGProcessor().execute()
