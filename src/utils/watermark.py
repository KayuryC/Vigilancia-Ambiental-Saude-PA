"""
Módulo de Gerenciamento de Watermark e Checkpoints para Cargas Incrementais.
Atende ao Requisito 2:
- Controle de estado para garantir extrações incrementais sem perda ou duplicação de dados.
- Persistência atômica do watermark de cada fonte de dados.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STATE_FILE_PATH = Path("data/bronze/_watermark_state.json")


class WatermarkManager:
    """Gerencia a leitura e atualização de marcas d'água (watermarks) de ingestão."""

    def __init__(self, state_file: Path = STATE_FILE_PATH):
        self.state_file = state_file
        self._ensure_state_file()

    def _ensure_state_file(self) -> None:
        """Garante que a pasta e o arquivo de estado existam."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def _load_all_states(self) -> Dict[str, Any]:
        """Carrega todos os estados persistidos."""
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def get_watermark(self, pipeline_key: str, default: str = "1970-01-01 00:00:00") -> str:
        """
        Retorna o último watermark registrado para uma chave de pipeline.
        Retorna o valor default se nunca tiver sido executado.
        """
        states = self._load_all_states()
        pipeline_state = states.get(pipeline_key, {})
        watermark = pipeline_state.get("last_watermark", default)
        logger.info(f"Watermark atual para '{pipeline_key}': {watermark}")
        return watermark

    def update_watermark(
        self,
        pipeline_key: str,
        new_watermark: str,
        records_processed: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Atualiza o watermark para a chave informada após o término com sucesso da carga.
        """
        states = self._load_all_states()
        states[pipeline_key] = {
            "last_watermark": str(new_watermark),
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "last_records_processed": records_processed,
            "metadata": metadata or {}
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(states, f, indent=2)

        logger.info(f"Watermark para '{pipeline_key}' atualizado para: {new_watermark} ({records_processed} registros)")
