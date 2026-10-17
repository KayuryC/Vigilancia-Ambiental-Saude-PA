"""
Ingestão Bronze: SRAG (SIVEP-Gripe) 2023 — OpenDataSUS / Ministério da Saúde.

Fonte REAL e pública (substitui a antiga base sintética de internações).
Requisito 2 (Ingestão):
- Arquivo CSV com tratamento explícito de encoding, separador e tipagem:
  separador ';', aspas duplas, e TODAS as colunas lidas como texto, para
  preservar o dado exatamente como veio da fonte (a tipagem forte é da Silver).
- Download com retry e backoff exponencial, gravando em arquivo temporário
  (.part) e conferindo o tamanho recebido, para nunca deixar arquivo pela metade.
- Checkpoint por hash SHA-256 do arquivo: rodar a ingestão duas vezes seguidas
  com o mesmo arquivo NÃO cria uma segunda carga na Bronze (idempotência).
- Quarentena: linhas malformadas do CSV vão para data/quarantine com o motivo.
  O job não quebra por dado sujo e nada some sem rastro.
- Metadados técnicos em todo registro (ingestion_timestamp, source_system,
  source_object, load_id, record_hash) via src.utils.metadata.

Escopo geográfico da ingestão: a Bronze guarda os registros cuja UF de residência
(SG_UF) OU cuja UF de notificação (SG_UF_NOT) é o Pará. É um recorte de escopo de
ingestão (o arquivo nacional tem ~300 MB e dados pessoais de outros estados que o
projeto não precisa guardar), não uma regra de negócio. As contagens lidas e
mantidas são registradas no log e no checkpoint. A decisão de quais registros
entram nas métricas (residência no PA, hospitalizado etc.) é da Silver.

Cada carga é um SNAPSHOT COMPLETO do "banco vivo" do SIVEP-Gripe naquela data
(não um delta). Por isso a Silver lê apenas a carga mais recente.
"""

import codecs
import hashlib
import json
import logging
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.metadata import enrich_bronze_dataframe
from src.utils.quarantine import send_to_quarantine

logger = logging.getLogger(__name__)

# --- Fonte ---------------------------------------------------------------------
SRAG_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2023/INFLUD23-23-03-2026.csv"
# SHA-256 do arquivo conforme baixado em 16/10/2026 (snapshot "Banco vivo 23/03/2026").
# Se o hash for diferente, a ingestão avisa e segue, registrando o hash real nos metadados.
SRAG_SHA256_ESPERADO: Optional[str] = "639b748fb2838336bbaf0882608159790274734b21abdb02b303ee6076bb5e4a"

LANDING_DIR = Path("data/landing/srag")
BRONZE_DIR = Path("data/bronze/srag")
CHECKPOINT_PATH = Path("data/checkpoints/srag_2023.json")

# Colunas sem as quais a Silver não consegue funcionar (contrato mínimo da fonte).
COLUNAS_OBRIGATORIAS = [
    "NU_NOTIFIC", "DT_NOTIFIC", "SG_UF_NOT", "SG_UF", "CO_MUN_RES",
    "HOSPITAL", "NU_IDADE_N", "TP_IDADE", "UTI", "EVOLUCAO",
]


class SRAGIngestor:
    """Baixa o CSV do SRAG, lê em pedaços e grava a Bronze em Parquet."""

    SOURCE_SYSTEM = "OPENDATASUS_SRAG_SIVEP_GRIPE"
    UF_ALVO = "PA"
    CHUNK_ROWS = 50_000

    def __init__(
        self,
        url: str = SRAG_URL,
        landing_dir: Path = LANDING_DIR,
        bronze_dir: Path = BRONZE_DIR,
        checkpoint_path: Path = CHECKPOINT_PATH,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ):
        self.url = url
        self.landing_dir = Path(landing_dir)
        self.bronze_dir = Path(bronze_dir)
        self.checkpoint_path = Path(checkpoint_path)
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    # ------------------------------------------------------------------ download
    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()

    def download(self) -> Path:
        """
        Garante o CSV em data/landing/srag/. Se o arquivo já estiver lá (por
        download anterior ou colocado manualmente), não baixa de novo.
        """
        self.landing_dir.mkdir(parents=True, exist_ok=True)
        dest = self.landing_dir / Path(self.url).name
        if dest.exists():
            logger.info(f"Arquivo já presente em {dest}; download não é necessário.")
            return dest

        tmp = dest.with_suffix(dest.suffix + ".part")
        last_exception: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Baixando SRAG (tentativa {attempt}/{self.max_retries}): {self.url}")
                req = urllib.request.Request(self.url, headers={"User-Agent": "projeto-integrador-pipeline/1.0"})
                written = 0
                with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
                    expected_len = resp.headers.get("Content-Length")
                    for block in iter(lambda: resp.read(1 << 20), b""):
                        out.write(block)
                        written += len(block)
                if expected_len is not None and int(expected_len) != written:
                    raise IOError(f"download incompleto: recebidos {written} de {expected_len} bytes")
                tmp.replace(dest)
                logger.info(f"Download concluído: {dest} ({written / 1e6:.1f} MB)")
                return dest
            except Exception as exc:  # noqa: BLE001 - qualquer falha de rede entra no retry
                last_exception = exc
                logger.warning(f"Falha na tentativa {attempt}: {exc}")
                if tmp.exists():
                    tmp.unlink()
                if attempt < self.max_retries:
                    wait = self.backoff_base ** (attempt - 1)
                    logger.info(f"Aguardando {wait:.1f}s antes de tentar novamente (Backoff)...")
                    time.sleep(wait)
        raise RuntimeError(f"Falha após {self.max_retries} tentativas ao baixar {self.url}. Motivo: {last_exception}")

    # ------------------------------------------------------------------- leitura
    @staticmethod
    def detect_encoding(path: Path) -> str:
        """Testa se o arquivo inteiro é UTF-8 válido; senão assume latin-1. 'utf-8-sig' tolera BOM."""
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            with open(path, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    decoder.decode(block)
                decoder.decode(b"", final=True)
            return "utf-8-sig"
        except UnicodeDecodeError:
            return "latin-1"

    def _read_filtered(self, csv_path: Path, encoding: str) -> Tuple[pd.DataFrame, int, List[Dict]]:
        """
        Lê o CSV em chunks, mantendo só os registros do UF alvo.
        Tenta o engine rápido (C); se houver linha malformada, relê com o engine
        'python', que permite capturar cada linha ruim para a quarentena.
        """
        bad_lines: List[Dict] = []

        def run(engine: str) -> Tuple[pd.DataFrame, int]:
            kwargs = dict(
                sep=";", quotechar='"', dtype=str, na_filter=False,
                encoding=encoding, chunksize=self.CHUNK_ROWS, engine=engine,
            )
            if engine == "python":
                kwargs["on_bad_lines"] = lambda fields: bad_lines.append({"linha_malformada": fields}) or None

            kept: List[pd.DataFrame] = []
            total = 0
            first = True
            for chunk in pd.read_csv(csv_path, **kwargs):
                if first:
                    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in chunk.columns]
                    if faltando:
                        raise ValueError(f"Contrato da fonte quebrado: colunas ausentes no CSV: {faltando}")
                    first = False
                total += len(chunk)
                mask = (chunk["SG_UF"] == self.UF_ALVO) | (chunk["SG_UF_NOT"] == self.UF_ALVO)
                if mask.any():
                    kept.append(chunk[mask])
            if not kept:
                raise ValueError(f"Nenhum registro do UF {self.UF_ALVO} encontrado no arquivo.")
            return pd.concat(kept, ignore_index=True), total

        try:
            df, total = run("c")
        except pd.errors.ParserError as exc:
            logger.warning(f"Linhas malformadas no CSV ({exc}). Relendo com engine 'python' e quarentena...")
            bad_lines.clear()
            df, total = run("python")
        return df, total, bad_lines

    # ------------------------------------------------------------ checkpoint
    def _read_checkpoint(self) -> Optional[Dict]:
        if not self.checkpoint_path.exists():
            return None
        try:
            return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Checkpoint ilegível; será tratado como primeira carga.")
            return None

    def _write_checkpoint(self, payload: Dict) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------- execução
    def run_ingestion(self) -> Path:
        csv_path = self.download()

        sha = self.sha256_file(csv_path)
        logger.info(f"SHA-256 do arquivo de origem: {sha}")
        if SRAG_SHA256_ESPERADO and sha != SRAG_SHA256_ESPERADO:
            logger.warning(
                "Hash diferente do registrado (snapshot de 23/03/2026). O arquivo foi atualizado "
                "ou substituído; seguindo com o arquivo atual e registrando o hash real."
            )

        checkpoint = self._read_checkpoint()
        if checkpoint and checkpoint.get("sha256") == sha and Path(checkpoint.get("bronze_file", "")).exists():
            logger.info(
                f"✅ Snapshot já ingerido (hash idêntico, carga {checkpoint['load_id']}). "
                f"Nenhuma nova carga criada: {checkpoint['bronze_file']}"
            )
            return Path(checkpoint["bronze_file"])

        encoding = self.detect_encoding(csv_path)
        logger.info(f"Encoding detectado: {encoding} | separador ';' | colunas lidas como texto")

        df, total_lido, bad_lines = self._read_filtered(csv_path, encoding)
        logger.info(f"Registros lidos no arquivo (Brasil): {total_lido} | mantidos (residência ou notificação em {self.UF_ALVO}): {len(df)}")

        if bad_lines:
            send_to_quarantine(
                records=bad_lines,
                source_system="BRONZE_SRAG_CSV",
                reason="linha_malformada_no_csv",
            )

        load_id = f"LOAD_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        df = enrich_bronze_dataframe(df, source_system=self.SOURCE_SYSTEM, source_object=self.url, load_id=load_id)
        df["source_file_sha256"] = sha  # adicionado após o hash do registro, para não alterá-lo

        self.bronze_dir.mkdir(parents=True, exist_ok=True)
        data_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        out_path = self.bronze_dir / f"srag_2023_{data_str}_{load_id}.parquet"
        df.to_parquet(out_path, index=False)

        self._write_checkpoint({
            "sha256": sha,
            "load_id": load_id,
            "bronze_file": str(out_path),
            "source_url": self.url,
            "rows_total_file": total_lido,
            "rows_kept_bronze": len(df),
            "rows_malformed_quarantined": len(bad_lines),
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"✅ Ingestão Bronze do SRAG concluída! Salvo em: {out_path} ({len(df)} registros)")
        return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    SRAGIngestor().run_ingestion()
