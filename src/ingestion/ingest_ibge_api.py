"""
Módulo de Ingestão: API REST do IBGE.
Atende ao Requisito 2:
- Ingestão via API REST oficial com tratamento de erros, retry com backoff exponencial e timeout.
- Metadados técnicos completos na camada Bronze (timestamp, sistema, objeto, load_id, hash).
- Quarentena para registros malformados ou incompletos.
- Idempotência na persistência.
"""

import gzip
import json
import logging
import time
import urllib.error
import urllib.request
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

# Assegurar que a raiz do projeto esteja no sys.path para importações locais
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.metadata import enrich_bronze_dataframe
from src.utils.quarantine import send_to_quarantine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

UF_PARA_CODE = 15
BRONZE_IBGE_DIR = Path("data/bronze/ibge")


class IBGEIngestor:
    """Coletor robusto para as APIs REST do IBGE."""

    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0, timeout: int = 20):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Projeto-Integrador-Engenharia-Dados/1.0",
            "Accept-Encoding": "gzip",
            "Accept": "application/json"
        }

    def _fetch_url_with_retry(self, url: str) -> Any:
        """
        Executa requisição HTTP GET com tratamento explícito de erros e retry com backoff exponencial.
        """
        delay = 1.0
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Requisitando URL (Tentativa {attempt}/{self.max_retries}): {url}")
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read()
                    if raw[:2] == b"\x1f\x8b":
                        raw = gzip.decompress(raw)
                    return json.loads(raw.decode("utf-8"))

            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception) as exc:
                last_exception = exc
                logger.warning(f"Falha na tentativa {attempt}: {exc}")
                if attempt < self.max_retries:
                    logger.info(f"Aguardando {delay:.1f}s antes de tentar novamente (Backoff)...")
                    time.sleep(delay)
                    delay *= self.backoff_factor

        raise RuntimeError(f"Falha após {self.max_retries} tentativas ao acessar {url}. Motivo: {last_exception}")

    def get_municipios_para(self) -> List[Dict[str, Any]]:
        """Busca a lista de todos os municípios do Pará na API de Localidades."""
        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF_PARA_CODE}/municipios"
        return self._fetch_url_with_retry(url)

    def get_populacao_censo_2022(self) -> Dict[str, int]:
        """
        Busca a população residente do Censo 2022 (Tabela 4714) para todos os municípios do Pará.
        Retorna um dicionário mapeando codigo_ibge -> populacao.
        """
        url = f"https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93?localidades=N6[N3[{UF_PARA_CODE}]]"
        data = self._fetch_url_with_retry(url)
        pop_map = {}

        try:
            series = data[0]["resultados"][0]["series"]
            for item in series:
                cod_ibge = str(item["localidade"]["id"])
                pop_val = item["serie"].get("2022")
                if pop_val and pop_val != "-":
                    pop_map[cod_ibge] = int(pop_val)
                else:
                    pop_map[cod_ibge] = 0
        except (KeyError, IndexError) as exc:
            logger.error(f"Erro ao processar dados de população da API do IBGE: {exc}")

        return pop_map

    def run_ingestion(self, save_partitioned: bool = True) -> Path:
        """
        Executa a ingestão completa da base do IBGE:
        1. Consulta dados cadastrais dos municípios.
        2. Consulta agregados de população.
        3. Valida e envia registros malformados para quarentena.
        4. Enriquece com metadados técnicos Bronze.
        5. Salva na pasta data/bronze/ibge/.
        """
        logger.info("Iniciando ingestão da base IBGE (Municípios e População do Pará)...")
        raw_municipios = self.get_municipios_para()
        pop_map = self.get_populacao_censo_2022()

        valid_records = []
        invalid_records = []

        for item in raw_municipios:
            cod_ibge = str(item.get("id", "")).strip()
            nome = item.get("nome", "").strip()

            # Validação para quarentena: código IBGE deve ter exatamente 7 dígitos numéricos
            if not cod_ibge.isdigit() or len(cod_ibge) != 7 or not nome:
                invalid_records.append(item)
                continue

            populacao = pop_map.get(cod_ibge, 0)
            meso = item.get("microrregiao", {}).get("mesorregiao", {}).get("nome", "Não informado")
            micro = item.get("microrregiao", {}).get("nome", "Não informado")

            valid_records.append({
                "codigo_ibge": cod_ibge,
                "nome_municipio": nome,
                "uf": "PA",
                "mesorregiao": meso,
                "microrregiao": micro,
                "populacao_censo_2022": populacao
            })

        # Encaminhar registros inconsistentes para quarentena se houver
        if invalid_records:
            send_to_quarantine(
                records=invalid_records,
                source_system="IBGE_API",
                reason="codigo_ibge_invalido_ou_nome_ausente"
            )

        df_valid = pd.DataFrame(valid_records)

        # Enriquecimento com Metadados Técnicos Obrigatórios
        df_bronze = enrich_bronze_dataframe(
            df=df_valid,
            source_system="IBGE_API",
            source_object="municipios_populacao_censo2022_pa"
        )

        # Criar diretório de destino
        BRONZE_IBGE_DIR.mkdir(parents=True, exist_ok=True)

        hoje_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        if save_partitioned:
            output_file = BRONZE_IBGE_DIR / f"municipios_pa_{hoje_str}.parquet"
        else:
            output_file = BRONZE_IBGE_DIR / "municipios_pa.parquet"

        df_bronze.to_parquet(output_file, index=False)
        logger.info(f"✅ Ingestão Bronze concluída com sucesso! Salvo em: {output_file} ({len(df_bronze)} registros)")
        return output_file


if __name__ == "__main__":
    ingestor = IBGEIngestor()
    ingestor.run_ingestion()
