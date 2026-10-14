"""
Módulo de Quarentena de Dados.
Requisito 2:
- Registros e arquivos problemáticos vão para área separada, com o motivo registrado.
- O job não pode quebrar por causa de dado sujo — e nada pode sumir sem rastro.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union
import pandas as pd


QUARANTINE_DIR = Path("data/quarantine")


def send_to_quarantine(
    records: Union[List[Dict[str, Any]], pd.DataFrame],
    source_system: str,
    reason: str,
    target_dir: Path = QUARANTINE_DIR
) -> Path:
    """
    Envia registros problemáticos para a pasta de quarentena correspondente,
    registrando carimbo de tempo e o motivo da rejeição.
    """
    if isinstance(records, pd.DataFrame):
        records_list = records.to_dict(orient="records")
    else:
        records_list = records

    if not records_list:
        return target_dir

    dest_dir = target_dir / source_system.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sanitized_reason = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)[:40]
    filename = f"quarantine_{timestamp_str}_{sanitized_reason}.jsonl"
    file_path = dest_dir / filename

    quarantine_payload = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for rec in records_list:
        quarantine_payload.append({
            "quarantine_timestamp": now_iso,
            "quarantine_reason": reason,
            "source_system": source_system,
            "raw_record": rec
        })

    with open(file_path, "w", encoding="utf-8") as f:
        for entry in quarantine_payload:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"⚠️  [QUARENTENA] {len(quarantine_payload)} registro(s) enviados para: {file_path} (Motivo: {reason})")
    return file_path
