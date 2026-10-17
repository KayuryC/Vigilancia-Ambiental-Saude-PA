"""
Demonstração de idempotência (Requisito 2 do enunciado).

Executa o pipeline completo DUAS vezes seguidas e mostra, lado a lado, que as camadas
Silver e Gold não mudam nem duplicam: mesmo número de linhas, zero duplicatas na chave
primária e o mesmo hash do conteúdo (ignorando só as colunas de carimbo de tempo, que
mudam a cada execução por definição).

Também mostra que a Bronze do SRAG não ganhou uma segunda carga (checkpoint por hash).

Uso, na raiz do projeto:
    python scripts/demo_idempotencia.py
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Callable, Dict

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

PK = ["codigo_ibge", "ano_mes"]
TABELAS = {
    "silver/dim_municipios_pa": ("data/silver/dim_municipios_pa.parquet", ["codigo_ibge"]),
    "silver/fatos_focos_mensais_pa": ("data/silver/fatos_focos_mensais_pa.parquet", PK),
    "silver/fatos_srag_mensais_pa": ("data/silver/fatos_srag_mensais_pa.parquet", PK),
    "silver/silver_painel_mensal_pa": ("data/silver/silver_painel_mensal_pa.parquet", PK),
    "gold/gold_painel_indicadores_pa": ("data/gold/gold_painel_indicadores_pa.parquet", PK),
    "gold/gold_ml_ready_pa": ("data/gold/gold_ml_ready_pa.parquet", ["codigo_ibge", "ano_mes_t0"]),
    "gold/gold_recomendacao_decisao_sespa": ("data/gold/gold_recomendacao_decisao_sespa.parquet", None),
}


def _colunas_de_tempo(df: pd.DataFrame):
    return [c for c in df.columns if c.endswith("_at") or c.endswith("_timestamp")]


def tirar_foto() -> Dict[str, Dict]:
    foto: Dict[str, Dict] = {}
    for nome, (caminho, pk) in TABELAS.items():
        df = pd.read_parquet(caminho)
        df = df.drop(columns=_colunas_de_tempo(df))
        df = df.sort_values(list(df.columns)).reset_index(drop=True)
        h = hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()[:16]
        foto[nome] = {
            "linhas": len(df),
            "pk_duplicadas": int(df.duplicated(subset=pk).sum()) if pk else 0,
            "hash": h,
        }
    foto["bronze/srag (arquivos de carga)"] = {
        "linhas": len(list(Path("data/bronze/srag").glob("*.parquet"))),
        "pk_duplicadas": 0,
        "hash": "-",
    }
    cp = Path("data/checkpoints/srag_2023.json")
    foto["checkpoint SRAG (load_id)"] = {
        "linhas": "-", "pk_duplicadas": 0,
        "hash": json.loads(cp.read_text(encoding="utf-8"))["load_id"][-8:] if cp.exists() else "-",
    }
    return foto


def main(runner: Callable[[], None] = None) -> int:
    if runner is None:
        from run_pipeline import run_full_pipeline  # importa só aqui para facilitar testes
        runner = run_full_pipeline

    print("\n" + "=" * 78 + "\nEXECUÇÃO 1 de 2\n" + "=" * 78)
    runner()
    foto1 = tirar_foto()

    print("\n" + "=" * 78 + "\nEXECUÇÃO 2 de 2 (mesma fonte, nada novo para ingerir)\n" + "=" * 78)
    runner()
    foto2 = tirar_foto()

    print("\n" + "=" * 78 + "\nCOMPARAÇÃO DAS DUAS EXECUÇÕES\n" + "=" * 78)
    print(f"{'tabela':<42}{'linhas 1':>9}{'linhas 2':>9}{'PK dup':>8}  {'hash 1':<17}{'hash 2':<17}")
    ok = True
    for nome in foto1:
        a, b = foto1[nome], foto2[nome]
        igual = a == b
        ok &= igual and b["pk_duplicadas"] == 0
        print(f"{nome:<42}{str(a['linhas']):>9}{str(b['linhas']):>9}{b['pk_duplicadas']:>8}  {a['hash']:<17}{b['hash']:<17}{'OK' if igual else '<-- DIFERENTE'}")

    print("\n" + ("✅ IDEMPOTENTE: duas execuções seguidas produzem exatamente as mesmas tabelas, sem duplicatas."
                  if ok else "❌ NÃO IDEMPOTENTE: veja as linhas marcadas acima."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
