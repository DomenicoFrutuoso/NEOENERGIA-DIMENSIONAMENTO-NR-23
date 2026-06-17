"""Geocodificação e distâncias — dicionário local + OpenStreetMap (sem API paga)."""

from __future__ import annotations

import json
from pathlib import Path

from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

from src.utils import KNOWLEDGE_BASE_DIR, has_text, sanitize_string

GEOCACHE_FILE = KNOWLEDGE_BASE_DIR / "geocache.json"
NOMINATIM_USER_AGENT = "nr23-cli-engine-neoenergia/1.0"

# Coordenadas fixas das principais localidades (fallback imediato, sem rede).
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
    "LUIS EDUARDO MAGALHAES": (-12.0863, -45.7831),
    "JUAZEIRO": (-9.4167, -40.5033),
    "BARREIRAS": (-12.1529, -44.9900),
    "ALAGOINHAS": (-12.1360, -38.4203),
    "JEQUIE": (-13.8588, -40.0851),
    "TEIXEIRA DE FREITAS": (-17.5350, -39.7419),
    "SIMOES FILHO": (-12.7869, -38.4039),
    "CANDEIAS": (-12.6719, -38.5475),
    "LAGARTO": (-10.9174, -37.6500),
    "PROPRIA": (-10.2111, -36.8408),
}


def _static_lookup(localidade: object) -> tuple[float, float] | None:
    key = sanitize_string(localidade)
    if not key:
        return None
    if key in COORDENADAS:
        return COORDENADAS[key]
    for city, coords in COORDENADAS.items():
        if key in city or city in key:
            return coords
    return None


class GeocodeResolver:
    """
    Resolve coordenadas por:
    1. Cache em memória / disco
    2. Dicionário local
    3. OpenStreetMap (Nominatim) — gratuito, sem chave de API
    """

    def __init__(self, use_online: bool = True) -> None:
        self.use_online = use_online
        self._memory: dict[str, tuple[float, float]] = {}
        self._disk: dict[str, tuple[float, float]] = {}
        self._geocoder: Nominatim | None = None
        self._geocode_fn = None
        self._load_disk_cache()
        self.stats = {"cache": 0, "static": 0, "online": 0, "failed": 0}

    def _load_disk_cache(self) -> None:
        if not GEOCACHE_FILE.exists():
            return
        try:
            raw = json.loads(GEOCACHE_FILE.read_text(encoding="utf-8"))
            for key, value in raw.items():
                if isinstance(value, list) and len(value) == 2:
                    self._disk[sanitize_string(key)] = (float(value[0]), float(value[1]))
        except (json.JSONDecodeError, OSError, ValueError):
            return

    def _save_disk_cache(self) -> None:
        GEOCACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        merged = {**self._disk, **self._memory}
        serializable = {k: [lat, lon] for k, (lat, lon) in merged.items()}
        GEOCACHE_FILE.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _ensure_geocoder(self) -> None:
        if self._geocoder is None:
            self._geocoder = Nominatim(user_agent=NOMINATIM_USER_AGENT, timeout=10)
            self._geocode_fn = RateLimiter(self._geocoder.geocode, min_delay_seconds=1.1)

    def _build_query(self, localidade: object, context: object | None = None) -> str:
        base = str(localidade).strip()
        if has_text(context) and sanitize_string(context) != sanitize_string(localidade):
            return f"{base}, {str(context).strip()}, Brasil"
        return f"{base}, Brasil"

    def _online_lookup(self, localidade: object, context: object | None = None) -> tuple[float, float] | None:
        self._ensure_geocoder()
        assert self._geocode_fn is not None
        query = self._build_query(localidade, context)
        try:
            result = self._geocode_fn(query, country_codes="br", addressdetails=False)
        except Exception:
            return None
        if result is None:
            return None
        return (float(result.latitude), float(result.longitude))

    def resolve(self, localidade: object, context: object | None = None) -> tuple[float, float] | None:
        key = sanitize_string(localidade)
        if not key:
            return None

        if key in self._memory:
            self.stats["cache"] += 1
            return self._memory[key]
        if key in self._disk:
            coords = self._disk[key]
            self._memory[key] = coords
            self.stats["cache"] += 1
            return coords

        coords = _static_lookup(localidade)
        if coords is not None:
            self._memory[key] = coords
            self.stats["static"] += 1
            return coords

        if self.use_online:
            coords = self._online_lookup(localidade, context)
            if coords is not None:
                self._memory[key] = coords
                self._disk[key] = coords
                self.stats["online"] += 1
                return coords

        self.stats["failed"] += 1
        return None

    def warmup(
        self,
        localidades: set[str],
        context_map: dict[str, str] | None = None,
    ) -> dict[str, int]:
        """Pré-carrega coordenadas das localidades únicas (com barra de progresso implícita)."""
        context_map = context_map or {}
        pending = [loc for loc in sorted(localidades) if has_text(loc)]
        for localidade in pending:
            key = sanitize_string(localidade)
            if key in self._memory or key in self._disk or _static_lookup(localidade):
                continue
            if not self.use_online:
                continue
            self.resolve(localidade, context_map.get(key))
        if self.use_online and self.stats["online"] > 0:
            self._save_disk_cache()
        return dict(self.stats)


_resolver: GeocodeResolver | None = None


def configure_geocoding(use_online: bool = True) -> GeocodeResolver:
    global _resolver
    _resolver = GeocodeResolver(use_online=use_online)
    return _resolver


def get_resolver() -> GeocodeResolver:
    global _resolver
    if _resolver is None:
        _resolver = GeocodeResolver(use_online=True)
    return _resolver


def get_coordinates(localidade: object, context: object | None = None) -> tuple[float, float] | None:
    return get_resolver().resolve(localidade, context)


def distance_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    return float(geodesic(origin, destination).kilometers)


def distance_between_localities(
    origem: object,
    destino: object,
    context_origem: object | None = None,
    context_destino: object | None = None,
) -> float | None:
    coords_origem = get_coordinates(origem, context_origem)
    coords_destino = get_coordinates(destino, context_destino)
    if coords_origem is None or coords_destino is None:
        return None
    return distance_km(coords_origem, coords_destino)


def find_nearest_locality(
    localidade_origem: object,
    candidatas: list[str],
    raio_max_km: float,
    context_origem: object | None = None,
) -> tuple[str, float] | None:
    origem = get_coordinates(localidade_origem, context_origem)
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
