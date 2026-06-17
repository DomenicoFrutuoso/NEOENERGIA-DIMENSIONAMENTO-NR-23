"""Core domain: ETL, vinculação geográfica e regras de capacidade das turmas."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.geo import find_nearest_locality
from src.utils import (
    COL_ACAO_RECOMENDADA,
    COL_CODIGO_TURMA,
    COL_DATA_TURMA,
    COL_ID_COLABORADOR,
    COL_LOCALIDADE,
    COL_MOTIVO_PENDENCIA,
    COL_NOME_COLABORADOR,
    COL_STATUS_TURMA,
    COL_VINCULOS,
    HISTORICAL_CUTOFF,
    MAX_VINCULOS,
    MIN_VINCULOS,
    has_vinculo,
    parse_date,
    sanitize_string,
)

ACAO_POR_STATUS = {
    "SEM PARTICIPANTES": "Cancelar Turma ou Remanejar Demanda",
    "ABAIXO DO MÍNIMO": "Consolidar ou Convidar Colaboradores",
    "OK": "Manter Cronograma",
    "PLANEJAR DATA": "Definir Data",
    "ACIMA DO LIMITE": "Dividir Excedente",
}


@dataclass
class EngineResult:
    colaboradores: pd.DataFrame
    turmas: pd.DataFrame
    saneamento_turmas: pd.DataFrame
    vinculacoes: pd.DataFrame
    pendentes: pd.DataFrame
    audit_log: list[str] = field(default_factory=list)


def _status_from_count(count: int, has_date: bool) -> str:
    if count == 0:
        return "SEM PARTICIPANTES"
    if count < MIN_VINCULOS:
        return "ABAIXO DO MÍNIMO"
    if count > MAX_VINCULOS:
        return "ACIMA DO LIMITE"
    return "OK" if has_date else "PLANEJAR DATA"


def _is_historical(row: pd.Series) -> bool:
    data = parse_date(row.get(COL_DATA_TURMA))
    if pd.isna(data):
        return False
    return data < HISTORICAL_CUTOFF


def _prepare_turmas(df: pd.DataFrame) -> pd.DataFrame:
    turmas = df.copy()
    for col in (COL_CODIGO_TURMA, COL_LOCALIDADE, COL_STATUS_TURMA):
        if col not in turmas.columns:
            raise ValueError(f"Coluna obrigatória ausente no cronograma: {col}")
    if COL_DATA_TURMA not in turmas.columns:
        turmas[COL_DATA_TURMA] = pd.NaT
    turmas[COL_VINCULOS] = 0
    turmas["_LOCALIDADE_NORM"] = turmas[COL_LOCALIDADE].apply(sanitize_string)
    turmas["_HISTORICO"] = turmas.apply(_is_historical, axis=1)
    return turmas


def _prepare_colaboradores(df: pd.DataFrame) -> pd.DataFrame:
    cols = df.copy()
    for col in (COL_ID_COLABORADOR, COL_LOCALIDADE):
        if col not in cols.columns:
            raise ValueError(f"Coluna obrigatória ausente no controle nominal: {col}")
    if COL_CODIGO_TURMA not in cols.columns:
        cols[COL_CODIGO_TURMA] = pd.NA
    if COL_NOME_COLABORADOR not in cols.columns:
        cols[COL_NOME_COLABORADOR] = ""
    cols["_LOCALIDADE_NORM"] = cols[COL_LOCALIDADE].apply(sanitize_string)
    return cols


def _count_vinculos(turmas: pd.DataFrame, colaboradores: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for codigo in colaboradores[COL_CODIGO_TURMA].dropna().unique():
        key = str(codigo).strip()
        if key:
            counts[key] = int((colaboradores[COL_CODIGO_TURMA].astype(str).str.strip() == key).sum())
    return counts


def _update_turma_status_inplace(turmas: pd.DataFrame, colaboradores: pd.DataFrame) -> pd.DataFrame:
    counts = _count_vinculos(turmas, colaboradores)
    for idx, row in turmas.iterrows():
        codigo = str(row[COL_CODIGO_TURMA]).strip()
        count = counts.get(codigo, 0)
        has_date = pd.notna(parse_date(row.get(COL_DATA_TURMA)))
        turmas.at[idx, COL_VINCULOS] = count
        turmas.at[idx, COL_STATUS_TURMA] = _status_from_count(count, has_date)
        turmas.at[idx, COL_ACAO_RECOMENDADA] = ACAO_POR_STATUS[turmas.at[idx, COL_STATUS_TURMA]]
    return turmas


def _turmas_com_vaga(turmas: pd.DataFrame) -> pd.DataFrame:
    return turmas[turmas[COL_VINCULOS] < MAX_VINCULOS].copy()


def _find_turma_exata(localidade_norm: str, turmas: pd.DataFrame) -> str | None:
    matches = turmas[turmas["_LOCALIDADE_NORM"] == localidade_norm]
    if matches.empty:
        return None
    ordenadas = matches.sort_values(COL_VINCULOS, ascending=True)
    return str(ordenadas.iloc[0][COL_CODIGO_TURMA]).strip()


def _find_turma_por_proximidade(
    localidade: str,
    turmas: pd.DataFrame,
    raio_max_km: float,
) -> tuple[str, float] | None:
    candidatas = turmas[COL_LOCALIDADE].dropna().astype(str).unique().tolist()
    nearest = find_nearest_locality(localidade, candidatas, raio_max_km)
    if nearest is None:
        return None
    localidade_alvo, distancia = nearest
    alvo_norm = sanitize_string(localidade_alvo)
    matches = turmas[turmas["_LOCALIDADE_NORM"] == alvo_norm].sort_values(COL_VINCULOS)
    if matches.empty:
        return None
    return str(matches.iloc[0][COL_CODIGO_TURMA]).strip(), distancia


def _vincular_colaboradores(
    colaboradores: pd.DataFrame,
    turmas: pd.DataFrame,
    raio_max_km: float,
    audit_log: list[str],
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    saneamento: list[dict] = []
    pendentes: list[dict] = []
    cols = colaboradores.copy()

    turmas = _update_turma_status_inplace(turmas, cols)

    for idx, row in cols.iterrows():
        codigo_atual = row.get(COL_CODIGO_TURMA)
        if pd.notna(codigo_atual) and str(codigo_atual).strip():
            continue

        localidade = row.get(COL_LOCALIDADE)
        if pd.isna(localidade) or not str(localidade).strip():
            pendentes.append(
                {
                    COL_ID_COLABORADOR: row[COL_ID_COLABORADOR],
                    COL_NOME_COLABORADOR: row.get(COL_NOME_COLABORADOR, ""),
                    COL_LOCALIDADE: localidade,
                    COL_MOTIVO_PENDENCIA: "Localidade ausente ou inválida",
                }
            )
            continue

        localidade_norm = row["_LOCALIDADE_NORM"]
        disponiveis = _turmas_com_vaga(turmas)

        codigo_turma = _find_turma_exata(localidade_norm, disponiveis)
        metodo = "MATCH EXATO"
        distancia: float | None = None

        if codigo_turma is None:
            prox = _find_turma_por_proximidade(localidade, disponiveis, raio_max_km)
            if prox is None:
                pendentes.append(
                    {
                        COL_ID_COLABORADOR: row[COL_ID_COLABORADOR],
                        COL_NOME_COLABORADOR: row.get(COL_NOME_COLABORADOR, ""),
                        COL_LOCALIDADE: localidade,
                        COL_MOTIVO_PENDENCIA: f"Sem turma no raio de {raio_max_km:.0f} km",
                    }
                )
                continue
            codigo_turma, distancia = prox
            metodo = "HAVERSINE"

        turma_idx = turmas[turmas[COL_CODIGO_TURMA].astype(str).str.strip() == codigo_turma].index
        if turma_idx.empty:
            pendentes.append(
                {
                    COL_ID_COLABORADOR: row[COL_ID_COLABORADOR],
                    COL_NOME_COLABORADOR: row.get(COL_NOME_COLABORADOR, ""),
                    COL_LOCALIDADE: localidade,
                    COL_MOTIVO_PENDENCIA: "Turma candidata não encontrada após vinculação",
                }
            )
            continue

        t_idx = turma_idx[0]
        if turmas.at[t_idx, "_HISTORICO"]:
            pendentes.append(
                {
                    COL_ID_COLABORADOR: row[COL_ID_COLABORADOR],
                    COL_NOME_COLABORADOR: row.get(COL_NOME_COLABORADOR, ""),
                    COL_LOCALIDADE: localidade,
                    COL_MOTIVO_PENDENCIA: "Turma histórica preservada — vinculação bloqueada",
                }
            )
            audit_log.append(
                f"Preservação histórica: colaborador {row[COL_ID_COLABORADOR]} "
                f"não vinculado à turma {codigo_turma}"
            )
            continue

        vinculos = int(turmas.at[t_idx, COL_VINCULOS])
        if vinculos >= MAX_VINCULOS:
            pendentes.append(
                {
                    COL_ID_COLABORADOR: row[COL_ID_COLABORADOR],
                    COL_NOME_COLABORADOR: row.get(COL_NOME_COLABORADOR, ""),
                    COL_LOCALIDADE: localidade,
                    COL_MOTIVO_PENDENCIA: "Turma atingiu capacidade máxima",
                }
            )
            continue

        cols.at[idx, COL_CODIGO_TURMA] = codigo_turma
        turmas.at[t_idx, COL_VINCULOS] = vinculos + 1
        has_date = pd.notna(parse_date(turmas.at[t_idx, COL_DATA_TURMA]))
        novo_status = _status_from_count(vinculos + 1, has_date)
        turmas.at[t_idx, COL_STATUS_TURMA] = novo_status
        turmas.at[t_idx, COL_ACAO_RECOMENDADA] = ACAO_POR_STATUS[novo_status]

        registro = {
            COL_CODIGO_TURMA: codigo_turma,
            COL_ID_COLABORADOR: row[COL_ID_COLABORADOR],
            COL_LOCALIDADE: localidade,
            "MÉTODO VINCULAÇÃO": metodo,
            "DISTÂNCIA KM": distancia if distancia is not None else 0.0,
            COL_STATUS_TURMA: novo_status,
        }
        saneamento.append(registro)
        audit_log.append(
            f"Vinculado {row[COL_ID_COLABORADOR]} -> turma {codigo_turma} ({metodo})"
        )

    turmas = _update_turma_status_inplace(turmas, cols)
    return cols, saneamento, pendentes


def run_engine(
    controle_nominal: pd.DataFrame,
    cronograma_turmas: pd.DataFrame,
    raio_max_km: float = 50.0,
) -> EngineResult:
    audit_log: list[str] = []
    turmas = _prepare_turmas(cronograma_turmas)
    colaboradores = _prepare_colaboradores(controle_nominal)

    # Preservar vínculos já existentes em turmas históricas
    for idx, row in colaboradores.iterrows():
        codigo = row.get(COL_CODIGO_TURMA)
        if pd.isna(codigo) or not str(codigo).strip():
            continue
        turma_match = turmas[turmas[COL_CODIGO_TURMA].astype(str).str.strip() == str(codigo).strip()]
        if not turma_match.empty and turma_match.iloc[0]["_HISTORICO"]:
            audit_log.append(
                f"Preservado vinculo historico: {row[COL_ID_COLABORADOR]} -> {codigo}"
            )

    colaboradores, saneamento_rows, pendente_rows = _vincular_colaboradores(
        colaboradores, turmas, raio_max_km, audit_log
    )

    turmas_final = turmas.drop(columns=["_LOCALIDADE_NORM", "_HISTORICO"], errors="ignore")
    cols_final = colaboradores.drop(columns=["_LOCALIDADE_NORM"], errors="ignore")

    saneamento_df = pd.DataFrame(saneamento_rows)
    if saneamento_df.empty:
        saneamento_df = pd.DataFrame(
            columns=[
                COL_CODIGO_TURMA,
                COL_ID_COLABORADOR,
                COL_LOCALIDADE,
                "MÉTODO VINCULAÇÃO",
                "DISTÂNCIA KM",
                COL_STATUS_TURMA,
            ]
        )

    pendentes_df = pd.DataFrame(pendente_rows)
    if pendentes_df.empty:
        pendentes_df = pd.DataFrame(
            columns=[COL_ID_COLABORADOR, COL_NOME_COLABORADOR, COL_LOCALIDADE, COL_MOTIVO_PENDENCIA]
        )

    turmas_audit = turmas_final[
        [c for c in turmas_final.columns if not c.startswith("_")]
    ].copy()

    return EngineResult(
        colaboradores=cols_final,
        turmas=turmas_final,
        saneamento_turmas=turmas_audit,
        vinculacoes=saneamento_df,
        pendentes=pendentes_df,
        audit_log=audit_log,
    )


def validate_conservation(
    input_colaboradores: pd.DataFrame,
    result: EngineResult,
) -> tuple[bool, str]:
    total_input = len(input_colaboradores)
    vinculados = int(result.colaboradores[COL_CODIGO_TURMA].apply(has_vinculo).sum())
    pendentes = len(result.pendentes)
    sem_vinculo = int((~result.colaboradores[COL_CODIGO_TURMA].apply(has_vinculo)).sum())
    total_output = vinculados + pendentes

    if sem_vinculo != pendentes:
        return (
            False,
            f"Pendentes inconsistentes: sem vínculo={sem_vinculo}, aba pendentes={pendentes}",
        )
    if total_input != total_output:
        return (
            False,
            f"Conservação violada: entrada={total_input}, "
            f"vinculados={vinculados}, pendentes={pendentes}, soma={total_output}",
        )
    return True, f"Conservação OK: {total_input} colaboradores contabilizados."
