"""Helpers de I/O, sanitização de strings e caminhos do projeto."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge-base"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

CONTROLE_NOMINAL_FILE = "nr23_controle_nominal.xlsx"
CRONOGRAMA_TURMAS_FILE = "cronograma_turmas.xlsx"
OUTPUT_FILE = "NR23_SANEADO_2026.xlsx"

COL_CODIGO_TURMA = "CÓDIGO DA TURMA"
COL_LOCALIDADE = "LOCALIDADE"
COL_STATUS_TURMA = "STATUS DA TURMA"
COL_DATA_TURMA = "DATA"
COL_ID_COLABORADOR = "ID COLABORADOR"
COL_NOME_COLABORADOR = "NOME"
COL_ACAO_RECOMENDADA = "AÇÃO RECOMENDADA"
COL_VINCULOS = "VÍNCULOS REAIS"
COL_MOTIVO_PENDENCIA = "MOTIVO PENDÊNCIA"

HISTORICAL_CUTOFF = pd.Timestamp("2026-06-12")
MIN_VINCULOS = 10
MAX_VINCULOS = 20


def sanitize_string(value: object) -> str:
    """Normaliza strings para comparação (trim, upper, sem acentos)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def ensure_directories() -> None:
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_input(path: Path | None, default_name: str) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    return KNOWLEDGE_BASE_DIR / default_name


def resolve_output(path: Path | None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    return OUTPUTS_DIR / OUTPUT_FILE


def load_excel(path: Path, sheet_name: str | int = 0) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")


def save_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def has_vinculo(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return bool(str(value).strip())


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return parsed
