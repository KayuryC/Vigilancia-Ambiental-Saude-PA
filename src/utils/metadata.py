"""
Módulo de Metadados Técnicos Obrigatórios para a Camada Bronze.
Requisito 2:
- Horário de ingestão (ingestion_timestamp)
- Sistema de origem (source_system)
- Objeto de origem (source_object)
- Identificador da carga (load_id)
- Hash do registro (record_hash) para garantia de idempotência e rastreabilidade
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd


def generate_record_hash(record: Dict[str, Any], ignore_keys: Optional[List[str]] = None) -> str:
    """
    Gera um hash SHA-256 determinístico para um registro (dicionário).
    Ignora chaves de metadados técnicos para avaliar apenas os dados brutos da fonte.
    """
    ignore_keys = ignore_keys or [
        "ingestion_timestamp",
        "source_system",
        "source_object",
        "load_id",
        "record_hash"
    ]
    
    cleaned_dict = {
        str(k): str(v)
        for k, v in record.items()
        if k not in ignore_keys
    }
    
    # Ordenar chaves para garantir determinismo no JSON serializado
    serialized = json.dumps(cleaned_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def enrich_bronze_dataframe(
    df: pd.DataFrame,
    source_system: str,
    source_object: str,
    load_id: Optional[str] = None
) -> pd.DataFrame:
    """
    Enriquece um DataFrame com todos os metadados técnicos obrigatórios da camada Bronze.
    """
    if df.empty:
        return df

    # Gerar ID único da carga se não fornecido
    if not load_id:
        load_id = f"LOAD_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    ingestion_ts = datetime.now(timezone.utc).isoformat()

    df = df.copy()

    # Metadados de contexto da ingestão
    df["source_system"] = source_system
    df["source_object"] = source_object
    df["load_id"] = load_id
    df["ingestion_timestamp"] = ingestion_ts

    # Cálculo do hash linha a linha de forma eficiente
    def row_hash(row):
        return generate_record_hash(row.to_dict())

    df["record_hash"] = df.apply(row_hash, axis=1)

    return df
