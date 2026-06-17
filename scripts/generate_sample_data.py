"""Gera planilhas de exemplo para desenvolvimento e testes locais."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils import CONTROLE_NOMINAL_FILE, KNOWLEDGE_BASE_DIR, ensure_directories

ensure_directories()


controle = pd.DataFrame(
    {
        "ID COLABORADOR": [f"COL-{i:04d}" for i in range(1, 46)],
        "NOME": [f"Colaborador {i}" for i in range(1, 46)],
        "LOCALIDADE": (
            ["SALVADOR"] * 8
            + ["RECIFE"] * 7
            + ["NATAL"] * 6
            + ["FEIRA DE SANTANA"] * 5
            + ["CAMACARI"] * 4
            + ["OLINDA"] * 5
            + ["MOSSORO"] * 4
            + ["CARUARU"] * 3
            + ["TERESINA"] * 3
        ),
        "CÓDIGO DA TURMA": [pd.NA] * 45,
    }
)
controle.loc[0, "CÓDIGO DA TURMA"] = "TURMA-HIST-001"

cronograma = pd.DataFrame(
    {
        "CÓDIGO DA TURMA": [
            "TURMA-HIST-001",
            "TURMA-HOJE-001",
            "TURMA-2026-001",
            "TURMA-2026-002",
            "TURMA-2026-003",
            "TURMA-2026-004",
            "TURMA-2026-005",
            "TURMA-2026-006",
        ],
        "LOCALIDADE": [
            "SALVADOR",
            "SALVADOR",
            "SALVADOR",
            "RECIFE",
            "NATAL",
            "FEIRA DE SANTANA",
            "CAMACARI",
            "OLINDA",
        ],
        "DATA": [
            "10/05/2026",
            pd.Timestamp.today().strftime("%d/%m/%Y"),
            "20/07/2026",
            "25/07/2026",
            "01/08/2026",
            "15/08/2026",
            "20/08/2026",
            "05/09/2026",
        ],
        "STATUS DA TURMA": [
            "OK",
            "OK",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
        ],
    }
)

controle_path = KNOWLEDGE_BASE_DIR / CONTROLE_NOMINAL_FILE
cronograma_path = KNOWLEDGE_BASE_DIR / "cronograma_turmas.xlsx"

controle.to_excel(controle_path, index=False, engine="openpyxl")
cronograma.to_excel(cronograma_path, index=False, engine="openpyxl")

print(f"Gerado: {controle_path}")
print(f"Gerado: {cronograma_path}")
