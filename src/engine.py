"""Core domain: ETL, vinculação geográfica e regras de capacidade das turmas."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.geo import configure_geocoding, distance_between_localities, get_resolver
from src.utils import (
    COL_ACAO_RECOMENDADA,
    COL_CODIGO_TURMA,
    COL_CODIGO_TURMA_NOMINAL,
    COL_DATA_TURMA,
    COL_LOCALIDADE_USADA,
    COL_MOTIVO_PENDENCIA,
    COL_NOME_COMPLETO,
    COL_STATUS_TURMA,
    COL_SUAREA,
    COL_TURMA_LOCALIDADE,
    COL_VINCULOS,
    HISTORICAL_CUTOFF,
    MAX_VINCULOS,
    MIN_VINCULOS,
    STATUS_AGENDADO,
    has_text,
    has_vinculo,
    parse_date,
    reference_tomorrow,
    resolve_localidade_colaborador,
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
    return data.normalize() < HISTORICAL_CUTOFF.normalize()


def _is_elegivel_por_data(row: pd.Series, amanha: pd.Timestamp) -> bool:
    data = parse_date(row.get(COL_DATA_TURMA))
    if pd.isna(data):
        return True
    return data.normalize() >= amanha.normalize()


def _prepare_turmas(df: pd.DataFrame, amanha: pd.Timestamp) -> pd.DataFrame:
    turmas = df.copy()
    for col in (COL_CODIGO_TURMA, COL_TURMA_LOCALIDADE, COL_STATUS_TURMA):
        if col not in turmas.columns:
            raise ValueError(f"Coluna interna ausente após normalização do cronograma: {col}")
    if COL_DATA_TURMA not in turmas.columns:
        turmas[COL_DATA_TURMA] = pd.NaT
    turmas[COL_CODIGO_TURMA] = turmas[COL_CODIGO_TURMA].apply(
        lambda v: str(v).strip() if has_text(v) else pd.NA
    )
    turmas[COL_VINCULOS] = 0
    turmas["_LOCALIDADE_NORM"] = turmas[COL_TURMA_LOCALIDADE].apply(sanitize_string)
    turmas["_STATUS_ENTRADA"] = turmas[COL_STATUS_TURMA].apply(sanitize_string)
    turmas["_HISTORICO"] = turmas.apply(_is_historical, axis=1)
    turmas["_ELEGIVEL_DATA"] = turmas.apply(lambda r: _is_elegivel_por_data(r, amanha), axis=1)
    turmas["_ELEGIVEL_STATUS"] = turmas["_STATUS_ENTRADA"] == STATUS_AGENDADO
    return turmas


def _prepare_colaboradores(df: pd.DataFrame) -> pd.DataFrame:
    cols = df.copy()
    if COL_NOME_COMPLETO not in cols.columns:
        raise ValueError(f"Coluna obrigatória ausente no controle nominal: {COL_NOME_COMPLETO}")
    if COL_CODIGO_TURMA_NOMINAL not in cols.columns:
        cols[COL_CODIGO_TURMA_NOMINAL] = pd.NA
    cols[COL_LOCALIDADE_USADA] = cols.apply(resolve_localidade_colaborador, axis=1)
    cols["_LOCALIDADE_NORM"] = cols[COL_LOCALIDADE_USADA].apply(sanitize_string)
    return cols


def _count_vinculos(turmas: pd.DataFrame, colaboradores: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for codigo in colaboradores[COL_CODIGO_TURMA_NOMINAL].dropna().unique():
        key = str(codigo).strip()
        if key:
            counts[key] = int(
                (colaboradores[COL_CODIGO_TURMA_NOMINAL].astype(str).str.strip() == key).sum()
            )
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
    return turmas[
        (turmas[COL_VINCULOS] < MAX_VINCULOS)
        & (turmas["_ELEGIVEL_DATA"])
        & (turmas["_ELEGIVEL_STATUS"])
        & (~turmas["_HISTORICO"])
    ].copy()


def _find_melhor_turma(
    localidade_colaborador: object,
    turmas: pd.DataFrame,
    raio_max_km: float,
    context_colaborador: object | None = None,
) -> tuple[str, float, str] | None:
    candidatos: list[tuple[str, float, int]] = []

    for _, turma in turmas.iterrows():
        distancia = distance_between_localities(
            localidade_colaborador,
            turma[COL_TURMA_LOCALIDADE],
            context_origem=context_colaborador,
        )
        if distancia is None or distancia > raio_max_km:
            continue
        codigo = str(turma[COL_CODIGO_TURMA]).strip()
        vinculos = int(turma[COL_VINCULOS])
        candidatos.append((codigo, distancia, vinculos))

    if not candidatos:
        return None

    candidatos.sort(key=lambda item: (item[1], item[2]))
    codigo, distancia, _ = candidatos[0]
    if distancia < 0.01:
        metodo = "MATCH EXATO"
    elif get_resolver().use_online:
        metodo = "PROXIMIDADE OSM"
    else:
        metodo = "PROXIMIDADE"
    return codigo, distancia, metodo


def _vincular_colaboradores(
    colaboradores: pd.DataFrame,
    turmas: pd.DataFrame,
    raio_max_km: float,
    amanha: pd.Timestamp,
    audit_log: list[str],
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    saneamento: list[dict] = []
    pendentes: list[dict] = []
    cols = colaboradores.copy()

    turmas = _update_turma_status_inplace(turmas, cols)

    for idx, row in cols.iterrows():
        codigo_atual = row.get(COL_CODIGO_TURMA_NOMINAL)
        if has_vinculo(codigo_atual):
            continue

        localidade = row.get(COL_LOCALIDADE_USADA)
        if not has_text(localidade):
            pendentes.append(
                {
                    COL_NOME_COMPLETO: row[COL_NOME_COMPLETO],
                    COL_LOCALIDADE_USADA: localidade,
                    COL_MOTIVO_PENDENCIA: "Localidade ausente em PCI e SUAREA",
                }
            )
            continue

        disponiveis = _turmas_com_vaga(turmas)
        contexto = row.get(COL_SUAREA) if has_text(row.get(COL_SUAREA)) else None
        melhor = _find_melhor_turma(localidade, disponiveis, raio_max_km, contexto)

        if melhor is None:
            pendentes.append(
                {
                    COL_NOME_COMPLETO: row[COL_NOME_COMPLETO],
                    COL_LOCALIDADE_USADA: localidade,
                    COL_MOTIVO_PENDENCIA: (
                        f"Sem turma AGENDADA futura no raio de {raio_max_km:.0f} km "
                        f"(elegíveis a partir de {amanha.strftime('%d/%m/%Y')})"
                    ),
                }
            )
            continue

        codigo_turma, distancia, metodo = melhor

        turma_idx = turmas[turmas[COL_CODIGO_TURMA].astype(str).str.strip() == codigo_turma].index
        if turma_idx.empty:
            pendentes.append(
                {
                    COL_NOME_COMPLETO: row[COL_NOME_COMPLETO],
                    COL_LOCALIDADE_USADA: localidade,
                    COL_MOTIVO_PENDENCIA: "Turma candidata não encontrada após vinculação",
                }
            )
            continue

        t_idx = turma_idx[0]
        vinculos = int(turmas.at[t_idx, COL_VINCULOS])
        if vinculos >= MAX_VINCULOS:
            pendentes.append(
                {
                    COL_NOME_COMPLETO: row[COL_NOME_COMPLETO],
                    COL_LOCALIDADE_USADA: localidade,
                    COL_MOTIVO_PENDENCIA: "Turma atingiu capacidade máxima",
                }
            )
            continue

        cols.at[idx, COL_CODIGO_TURMA_NOMINAL] = codigo_turma
        turmas.at[t_idx, COL_VINCULOS] = vinculos + 1
        has_date = pd.notna(parse_date(turmas.at[t_idx, COL_DATA_TURMA]))
        novo_status = _status_from_count(vinculos + 1, has_date)
        turmas.at[t_idx, COL_STATUS_TURMA] = novo_status
        turmas.at[t_idx, COL_ACAO_RECOMENDADA] = ACAO_POR_STATUS[novo_status]

        registro = {
            COL_CODIGO_TURMA: codigo_turma,
            COL_NOME_COMPLETO: row[COL_NOME_COMPLETO],
            COL_LOCALIDADE_USADA: localidade,
            COL_TURMA_LOCALIDADE: turmas.at[t_idx, COL_TURMA_LOCALIDADE],
            "MÉTODO VINCULAÇÃO": metodo,
            "DISTÂNCIA KM": round(distancia, 2),
            COL_STATUS_TURMA: novo_status,
        }
        saneamento.append(registro)
        audit_log.append(
            f"Vinculado {row[COL_NOME_COMPLETO]} -> turma {codigo_turma} "
            f"({metodo}, {distancia:.1f} km)"
        )

    turmas = _update_turma_status_inplace(turmas, cols)
    return cols, saneamento, pendentes


def _warmup_geocoding(
    colaboradores: pd.DataFrame,
    turmas: pd.DataFrame,
    use_geocoding: bool,
) -> dict[str, int]:
    localidades: set[str] = set()
    context_map: dict[str, str] = {}

    for _, row in colaboradores.iterrows():
        loc = row.get(COL_LOCALIDADE_USADA)
        if not has_text(loc):
            continue
        texto = str(loc).strip()
        localidades.add(texto)
        if has_text(row.get(COL_SUAREA)):
            context_map[sanitize_string(texto)] = str(row[COL_SUAREA]).strip()

    for valor in turmas[COL_TURMA_LOCALIDADE].dropna():
        if has_text(valor):
            localidades.add(str(valor).strip())

    resolver = configure_geocoding(use_online=use_geocoding)
    return resolver.warmup(localidades, context_map)


def run_engine(
    controle_nominal: pd.DataFrame,
    cronograma_turmas: pd.DataFrame,
    raio_max_km: float = 50.0,
    data_referencia: pd.Timestamp | None = None,
    use_geocoding: bool = True,
) -> EngineResult:
    audit_log: list[str] = []
    amanha = reference_tomorrow(data_referencia)
    turmas = _prepare_turmas(cronograma_turmas, amanha)
    colaboradores = _prepare_colaboradores(controle_nominal)

    geo_stats = _warmup_geocoding(colaboradores, turmas, use_geocoding)
    if use_geocoding:
        audit_log.append(
            "Geocoding OpenStreetMap (gratuito, sem chave de API): "
            f"online={geo_stats.get('online', 0)}, "
            f"cache={geo_stats.get('cache', 0)}, "
            f"estatico={geo_stats.get('static', 0)}, "
            f"falhas={geo_stats.get('failed', 0)}"
        )
    else:
        audit_log.append("Geocoding online desativado: apenas dicionario local e cache")

    audit_log.append("Localidade do colaborador: LOCAL DO BRIGADISTA - PCI, fallback SUAREA")
    audit_log.append(
        f"Filtro de data: apenas turmas com data >= {amanha.strftime('%d/%m/%Y')} "
        f"ou sem data definida"
    )
    audit_log.append(
        f"Filtro de status: apenas turmas com STATUS DA TURMA = {STATUS_AGENDADO}"
    )

    for _, row in colaboradores.iterrows():
        codigo = row.get(COL_CODIGO_TURMA_NOMINAL)
        if not has_vinculo(codigo):
            continue
        turma_match = turmas[turmas[COL_CODIGO_TURMA].astype(str).str.strip() == str(codigo).strip()]
        if not turma_match.empty and turma_match.iloc[0]["_HISTORICO"]:
            audit_log.append(
                f"Preservado vinculo historico: {row[COL_NOME_COMPLETO]} -> {codigo}"
            )

    colaboradores, saneamento_rows, pendente_rows = _vincular_colaboradores(
        colaboradores, turmas, raio_max_km, amanha, audit_log
    )

    turmas_final = turmas.drop(
        columns=["_LOCALIDADE_NORM", "_HISTORICO", "_ELEGIVEL_DATA", "_STATUS_ENTRADA", "_ELEGIVEL_STATUS"],
        errors="ignore",
    )
    cols_final = colaboradores.drop(columns=["_LOCALIDADE_NORM"], errors="ignore")

    saneamento_df = pd.DataFrame(saneamento_rows)
    if saneamento_df.empty:
        saneamento_df = pd.DataFrame(
            columns=[
                COL_CODIGO_TURMA,
                COL_NOME_COMPLETO,
                COL_LOCALIDADE_USADA,
                COL_TURMA_LOCALIDADE,
                "MÉTODO VINCULAÇÃO",
                "DISTÂNCIA KM",
                COL_STATUS_TURMA,
            ]
        )

    pendentes_df = pd.DataFrame(pendente_rows)
    if pendentes_df.empty:
        pendentes_df = pd.DataFrame(
            columns=[COL_NOME_COMPLETO, COL_LOCALIDADE_USADA, COL_MOTIVO_PENDENCIA]
        )

    turmas_audit = turmas_final[[c for c in turmas_final.columns if not c.startswith("_")]].copy()

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
    vinculados = int(result.colaboradores[COL_CODIGO_TURMA_NOMINAL].apply(has_vinculo).sum())
    pendentes = len(result.pendentes)
    sem_vinculo = int((~result.colaboradores[COL_CODIGO_TURMA_NOMINAL].apply(has_vinculo)).sum())
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
