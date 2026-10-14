"""
Módulo de Inicialização do Banco Relacional Operacional (SIH/DataSUS).
Atende ao Requisito 2:
- Fonte de dados relacional (SQLite/SQL) simulando o sistema transacional de internações hospitalares do SUS.
- Permite demonstrar ingestão via banco relacional e carga incremental com Watermark.
- Inclui propositalmente registros inconsistentes para teste de quarentena.
"""

import logging
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("data/operational_sih_sus.db")

# CIDs do Capítulo X da CID-10 (Doenças do aparelho respiratório)
CIDS_RESPIRATORIOS = [
    "J12", "J15", "J18",  # Pneumonias bacterianas / virais
    "J20", "J21",         # Bronquites e Bronquiolites agudas
    "J44", "J45",         # DPOC e Asma
    "J96"                 # Insuficiência respiratória aguda
]

FAIXAS_ETARIAS = ["0-4 anos", "5-14 anos", "15-59 anos", "60+ anos"]


def create_schema(conn: sqlite3.Connection) -> None:
    """Cria a tabela relacional operacional de internações com índices."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tb_internacoes_hospitalares (
            id_internacao INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_aih TEXT UNIQUE NOT NULL,
            codigo_ibge_municipio TEXT NOT NULL,
            data_internacao TEXT NOT NULL,
            cid_principal TEXT NOT NULL,
            faixa_etaria TEXT NOT NULL,
            carater_atendimento TEXT NOT NULL,
            dias_permanencia INTEGER NOT NULL,
            valor_total REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON tb_internacoes_hospitalares(updated_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_municipio ON tb_internacoes_hospitalares(codigo_ibge_municipio)")
    conn.commit()


def seed_operational_database(
    db_path: Path = DB_PATH,
    total_records: int = 15000,
    seed: int = 42
) -> None:
    """
    Popula o banco operacional com histórico de internações do Pará para o ano de 2023.
    """
    random.seed(seed)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Obter lista real de municípios do Pará da camada Bronze do IBGE
    bronze_ibge_files = list(Path("data/bronze/ibge").glob("*.parquet"))
    if bronze_ibge_files:
        df_ibge = pd.read_parquet(bronze_ibge_files[0])
        municipios_validos = df_ibge["codigo_ibge"].tolist()
    else:
        # Fallback para principais códigos do Pará
        municipios_validos = ["1501402", "1500800", "1504208", "1506807", "1507300", "1500107"]

    conn = sqlite3.connect(db_path)
    create_schema(conn)

    start_date = datetime(2023, 1, 1)
    records = []

    logger.info(f"Gerando {total_records} registros de internações respiratórias no banco relacional...")

    for i in range(1, total_records + 1):
        aih = f"15231{i:07d}"
        dias_offset = random.randint(0, 364)
        data_int = start_date + timedelta(days=dias_offset)

        # No período de estiagem (julho a novembro: meses 7 a 11), a incidência em municípios críticos aumenta
        mes = data_int.month
        cid = random.choice(CIDS_RESPIRATORIOS)
        municipio = random.choice(municipios_validos)

        dias = random.randint(1, 14)
        valor = round(random.uniform(450.0, 4800.0), 2)
        faixa = random.choice(FAIXAS_ETARIAS)
        carater = "Urgência" if random.random() < 0.85 else "Eletivo"

        # Timestamp operacional de auditoria
        ts_str = data_int.strftime("%Y-%m-%d %H:%M:%S")

        records.append((
            aih,
            municipio,
            data_int.strftime("%Y-%m-%d"),
            cid,
            faixa,
            carater,
            dias,
            valor,
            ts_str,
            ts_str
        ))

    # Inserir propositalmente alguns registros com inconsistências para teste da Quarentena (Requisito 2)
    # Exemplo 1: Código IBGE inválido
    records.append((
        "15239999001",
        "9999999",  # IBGE inexistente
        "2023-08-15",
        "J18",
        "0-4 anos",
        "Urgência",
        5,
        1200.0,
        "2023-08-15 10:00:00",
        "2023-08-15 10:00:00"
    ))
    # Exemplo 2: Dias de permanência negativo
    records.append((
        "15239999002",
        "1501402",
        "2023-09-10",
        "J45",
        "60+ anos",
        "Urgência",
        -3,  # Erro
        850.0,
        "2023-09-10 12:00:00",
        "2023-09-10 12:00:00"
    ))

    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR IGNORE INTO tb_internacoes_hospitalares (
            numero_aih, codigo_ibge_municipio, data_internacao, cid_principal,
            faixa_etaria, carater_atendimento, dias_permanencia, valor_total,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, records)

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM tb_internacoes_hospitalares")
    total_db = cursor.fetchone()[0]
    conn.close()

    logger.info(f"✅ Banco relacional operacional inicializado com sucesso em: {db_path} ({total_db} registros)")


if __name__ == "__main__":
    seed_operational_database()
