"""Cálculos geoespaciais e dicionário de coordenadas das localidades Neoenergia."""

from __future__ import annotations

from geopy.distance import geodesic

from src.utils import sanitize_string

# Coordenadas das principais localidades de operação (lat, lon).
COORDENADAS: dict[str, tuple[float, float]] = {
    "SALVADOR": (-12.9777, -38.5016),
    "FEIRA DE SANTANA": (-12.2664, -38.9663),
    "CAMACARI": (-12.6975, -38.3243),
    "VITORIA DA CONQUISTA": (-14.8615, -40.8442),
    "ILHEUS": (-14.7886, -39.0349),
    "ITABUNA": (-14.7876, -39.2781),
    "RECIFE": (-8.0476, -34.8770),
    "OLINDA": (-8.0089, -34.8553),
    "JABOATAO DOS GUARARAPES": (-8.1120, -35.0140),
    "CARUARU": (-8.2832, -35.9714),
    "PETROLINA": (-9.3891, -40.5028),
    "PAULISTA": (-7.9407, -34.8731),
    "NATAL": (-5.7945, -35.2110),
    "MOSSORO": (-5.1878, -37.3440),
    "PARNAMIRIM": (-5.9156, -35.2628),
    "JOAO PESSOA": (-7.1195, -34.8450),
    "CAMPINA GRANDE": (-7.2214, -35.8831),
    "ARACAJU": (-10.9472, -37.0731),
    "MACEIO": (-9.6498, -35.7089),
    "TERESINA": (-5.0892, -42.8016),
}


def get_coordinates(localidade: object) -> tuple[float, float] | None:
    key = sanitize_string(localidade)
    if not key:
        return None
    if key in COORDENADAS:
        return COORDENADAS[key]
    for city, coords in COORDENADAS.items():
        if key in city or city in key:
            return coords
    return None


def distance_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    return float(geodesic(origin, destination).kilometers)


def find_nearest_locality(
    localidade_origem: object,
    candidatas: list[str],
    raio_max_km: float,
) -> tuple[str, float] | None:
    """Retorna (localidade_candidata, distancia_km) dentro do raio, ou None."""
    origem = get_coordinates(localidade_origem)
    if origem is None:
        return None

    melhor: tuple[str, float] | None = None
    for candidata in candidatas:
        destino = get_coordinates(candidata)
        if destino is None:
            continue
        dist = distance_km(origem, destino)
        if dist <= raio_max_km and (melhor is None or dist < melhor[1]):
            melhor = (candidata, dist)

    return melhor
