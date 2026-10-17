"""
Orquestrador Central do Pipeline: Da Ingestão à Decisão.
Atende ao Requisito 4 (Reprodutibilidade Total):
Executa o fluxo completo de ponta a ponta:
1. Ingestão Bronze (IBGE API, INPE Arquivo CSV/ZIP, OpenDataSUS SRAG Arquivo CSV com checkpoint por hash)
2. Processamento Silver (Deduplicação, Integridade Referencial, Verificação de PKs, Quarentena)
3. Processamento Gold (Taxas Epidemiológicas, Features Causais, Base ML-Ready e Suporte à Decisão SESPA)
"""

import logging
import sys
import time
from pathlib import Path

# Assegurar raiz do projeto no path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.ingest_ibge_api import IBGEIngestor
from src.ingestion.ingest_inpe_queimadas import INPEQueimadasIngestor
from src.ingestion.ingest_srag_opendatasus import SRAGIngestor
from src.processing.process_silver_dim_municipios import SilverMunicipiosProcessor
from src.processing.process_silver_focos import SilverFocosProcessor
from src.processing.process_silver_srag import SilverSRAGProcessor
from src.processing.process_silver_join_integrado import SilverJoinIntegrator
from src.processing.process_gold_indicadores import GoldIndicadoresProcessor
from src.processing.process_gold_ml_ready import GoldMLReadyProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PipelineOrchestrator")


def run_full_pipeline():
    start_time = time.time()
    logger.info("=" * 70)
    logger.info("🚀 INICIANDO EXECUÇÃO COMPLETA DO PIPELINE: DA INGESTÃO À DECISÃO")
    logger.info("=" * 70)

    # -------------------------------------------------------------
    # 1. CAMADA BRONZE (Ingestão das 3 Fontes Públicas Reais: IBGE, INPE, OpenDataSUS)
    # -------------------------------------------------------------
    logger.info("\n[ETAPA 1/3] EXECUTANDO CAMADA BRONZE...")
    
    logger.info("-> 1.1 Ingestão API REST (IBGE Localidades & Censo 2022)...")
    ibge_ingestor = IBGEIngestor()
    ibge_path = ibge_ingestor.run_ingestion()
    logger.info(f"   Bronze IBGE salva em: {ibge_path}")

    logger.info("-> 1.2 Ingestão Arquivo CSV/ZIP (INPE BDQueimadas 2023)...")
    inpe_ingestor = INPEQueimadasIngestor(target_uf="PARÁ")
    inpe_path = inpe_ingestor.process_and_ingest(year=2023)
    logger.info(f"   Bronze INPE salva em: {inpe_path}")

    logger.info("-> 1.3 Ingestão Arquivo CSV (OpenDataSUS SRAG/SIVEP-Gripe 2023, checkpoint por hash)...")
    srag_ingestor = SRAGIngestor()
    srag_bronze_path = srag_ingestor.run_ingestion()
    logger.info(f"   Bronze SRAG salva em: {srag_bronze_path}")

    # -------------------------------------------------------------
    # 2. CAMADA SILVER (Limpeza, Tipagem, Deduplicação e Joins)
    # -------------------------------------------------------------
    logger.info("\n[ETAPA 2/3] EXECUTANDO CAMADA SILVER...")
    
    logger.info("-> 2.1 Processando Dimensão de Municípios do Pará...")
    dim_mun_proc = SilverMunicipiosProcessor()
    dim_path = dim_mun_proc.execute()
    logger.info(f"   Silver Dimensão Municípios salva em: {dim_path}")

    logger.info("-> 2.2 Processando Fatos Mensais de Focos do INPE...")
    focos_proc = SilverFocosProcessor()
    focos_path = focos_proc.execute()
    logger.info(f"   Silver Fatos Focos salva em: {focos_path}")

    logger.info("-> 2.3 Processando Fatos Mensais de SRAG hospitalizado (OpenDataSUS)...")
    srag_proc = SilverSRAGProcessor()
    srag_path = srag_proc.execute()
    logger.info(f"   Silver Fatos SRAG salva em: {srag_path}")

    logger.info("-> 2.4 Executando Join Integrado e Relatório de Auditoria...")
    join_proc = SilverJoinIntegrator()
    join_path = join_proc.execute_join_and_audit()
    logger.info(f"   Silver Painel Integrado salvo em: {join_path}")

    # -------------------------------------------------------------
    # 3. CAMADA GOLD (Indicadores, ML-Ready e Suporte à Decisão)
    # -------------------------------------------------------------
    logger.info("\n[ETAPA 3/3] EXECUTANDO CAMADA GOLD...")
    
    logger.info("-> 3.1 Calculando Indicadores Epidemiológicos e Features Causais...")
    gold_ind_proc = GoldIndicadoresProcessor()
    gold_ind_path = gold_ind_proc.execute()
    logger.info(f"   Gold Indicadores salva em: {gold_ind_path}")

    logger.info("-> 3.2 Gerando Base ML-Ready, Avaliação Anti-Vazamento e Decisão SESPA...")
    gold_ml_proc = GoldMLReadyProcessor()
    decision_path = gold_ml_proc.execute()
    logger.info(f"   Gold Decisão SESPA salva em: {decision_path}")

    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 70)
    logger.info(f"🎉 PIPELINE CONCLUÍDO COM SUCESSO EM {elapsed:.2f} SEGUNDOS!")
    logger.info("=" * 70)


if __name__ == "__main__":
    run_full_pipeline()
