"""
Módulo de Ingestão: Focos de Queimadas do INPE (BDQueimadas).
Atende ao Requisito 2:
- Ingestão por arquivo (CSV extraído de ZIP) com tratamento explícito de encoding, separador e tipagem.
- Filtro e validação geográfica e temporal.
- Encaminhamento de registros malformados/inválidos para a Quarentena.
- Metadados técnicos completos na camada Bronze (timestamp, sistema, objeto, load_id, hash).
- Idempotência na geração dos dados da Bronze.
"""

import io
import logging
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import pandas as pd

# Assegurar raiz no sys.path para importações locais
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.metadata import enrich_bronze_dataframe
from src.utils.quarantine import send_to_quarantine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INPE_BASE_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref"
BRONZE_INPE_DIR = Path("data/bronze/inpe")


class INPEQueimadasIngestor:
    """Coletor e processador de arquivos de focos de queimada do INPE."""

    def __init__(self, target_uf: str = "PARÁ"):
        self.target_uf = target_uf.upper()
        self.headers = {"User-Agent": "Projeto-Integrador-Engenharia-Dados/1.0"}

    def download_year_zip(self, year: int) -> bytes:
        """Faz o download do arquivo ZIP anual do INPE com tratamento de erros."""
        url = f"{INPE_BASE_URL}/focos_br_ref_{year}.zip"
        logger.info(f"Baixando base de focos de calor do INPE para o ano {year}: {url}")
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.URLError as exc:
            logger.error(f"Erro ao baixar arquivo do INPE ({url}): {exc}")
            raise

    def process_and_ingest(self, year: int, zip_bytes: Optional[bytes] = None) -> Path:
        """
        Lê o CSV contido no ZIP, aplica tratamento estrito de tipos,
        separa dados do estado alvo, valida para quarentena e persiste na Bronze.
        """
        if zip_bytes is None:
            zip_bytes = self.download_year_zip(year)

        logger.info("Abrindo arquivo ZIP e processando CSV em memória...")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            csv_filename = z.namelist()[0]
            logger.info(f"Arquivo CSV identificado: {csv_filename}")

            with z.open(csv_filename) as f:
                # Tratamento explícito de separador, encoding e tipagem conforme Requisito 2
                dtype_spec = {
                    "id_bdq": "object",
                    "foco_id": "string",
                    "lat": "float64",
                    "lon": "float64",
                    "pais": "string",
                    "estado": "string",
                    "municipio": "string",
                    "bioma": "string"
                }

                df_raw = pd.read_csv(
                    f,
                    sep=",",
                    encoding="utf-8",
                    dtype=dtype_spec,
                    parse_dates=["data_pas"]
                )

        logger.info(f"Total de registros no Brasil em {year}: {len(df_raw)}")

        # Filtrar pelo estado alvo
        df_uf = df_raw[df_raw["estado"].str.upper() == self.target_uf].copy()
        logger.info(f"Total de registros para {self.target_uf} em {year}: {len(df_uf)}")

        # --- Validação e Quarentena ---
        # Regras de integridade:
        # 1. Coordenadas válidas e dentro dos limites aproximados do Pará (Lat: -10 a 3, Lon: -60 a -45)
        # 2. Data de passagem válida e não nula
        # 3. Município preenchido
        mask_coord_valida = (
            df_uf["lat"].between(-10.5, 3.5) &
            df_uf["lon"].between(-60.0, -45.0)
        )
        mask_data_valida = df_uf["data_pas"].notna()
        mask_municipio_valido = df_uf["municipio"].notna() & (df_uf["municipio"].str.strip() != "")

        mask_valido = mask_coord_valida & mask_data_valida & mask_municipio_valido

        df_valid = df_uf[mask_valido].copy()
        df_invalid = df_uf[~mask_valido].copy()

        if not df_invalid.empty:
            logger.warning(f"Detectados {len(df_invalid)} registros inconsistentes. Enviando para quarentena...")
            send_to_quarantine(
                records=df_invalid,
                source_system="INPE_BDQUEIMADAS",
                reason="coordenada_invalida_ou_data_ausente"
            )

        # Padronizar nomes e colunas para a camada Bronze
        df_valid["data_hora_foco"] = df_valid["data_pas"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df_valid["ano_mes"] = df_valid["data_pas"].dt.strftime("%Y-%m")
        df_valid.drop(columns=["data_pas"], inplace=True)

        # Enriquecimento com Metadados Técnicos Obrigatórios
        df_bronze = enrich_bronze_dataframe(
            df=df_valid,
            source_system="INPE_BDQUEIMADAS",
            source_object=f"focos_{self.target_uf.lower()}_{year}"
        )

        BRONZE_INPE_DIR.mkdir(parents=True, exist_ok=True)
        hoje_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        output_file = BRONZE_INPE_DIR / f"focos_pa_{year}_{hoje_str}.parquet"

        df_bronze.to_parquet(output_file, index=False)
        logger.info(f"✅ Ingestão Bronze do INPE concluída! Salvo em: {output_file} ({len(df_bronze)} registros)")
        return output_file


if __name__ == "__main__":
    ingestor = INPEQueimadasIngestor()
    # Executa ingestão para o ano de 2023
    ingestor.process_and_ingest(year=2023)
