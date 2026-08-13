"""Observabilité : traçage des entrées/sorties, latence, erreurs et coût estimé
de chaque étape du pipeline (exigence §5.4). Chaque trace est journalisée en JSONL
(persistant, consultable par le tableau de bord) et conservée en mémoire pour la session.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
TRACE_FILE = LOG_DIR / "traces.jsonl"

# Coût unitaire simulé (Ariary, MGA) par étape utilisant un modèle génératif, à titre
# indicatif. Dans cette implémentation 100% locale (pas d'appel LLM externe), le coût réel
# est nul ; ce champ existe pour montrer où brancher un calcul de coût réel (tokens * prix
# converti en Ariary) si un LLM externe est utilisé à la place des heuristiques locales.
ESTIMATED_COST_PER_STEP = {
    "comprehension": 0.0,
    "diagnostic": 0.0,
    "rag": 0.0,
    "agent_outils": 0.0,
    "sortie_structuree": 0.0,
}


@dataclass
class TraceEvent:
    trace_id: str
    ticket_id: str
    step: str
    timestamp: float
    duration_ms: float
    status: str  # succes | erreur
    input: Any = None
    output: Any = None
    error: str | None = None
    cout_estime_ar: float = 0.0


class Tracer:
    def __init__(self):
        self._events: list[TraceEvent] = []

    @contextmanager
    def step(self, trace_id: str, ticket_id: str, step: str, input_data: Any = None):
        start = time.perf_counter()
        result_holder = {"output": None, "status": "succes", "error": None}
        try:
            yield result_holder
        except Exception as exc:  # noqa: BLE001 - on trace l'erreur puis on relance
            result_holder["status"] = "erreur"
            result_holder["error"] = str(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            event = TraceEvent(
                trace_id=trace_id,
                ticket_id=ticket_id,
                step=step,
                timestamp=time.time(),
                duration_ms=round(duration_ms, 2),
                status=result_holder["status"],
                input=_safe_serialize(input_data),
                output=_safe_serialize(result_holder["output"]),
                error=result_holder["error"],
                cout_estime_ar=ESTIMATED_COST_PER_STEP.get(step, 0.0),
            )
            self._events.append(event)
            self._persist(event)

    def _persist(self, event: TraceEvent):
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False, default=str) + "\n")

    def events_for_ticket(self, ticket_id: str) -> list[TraceEvent]:
        return [e for e in self._events if e.ticket_id == ticket_id]

    def all_events(self) -> list[TraceEvent]:
        return list(self._events)

    @staticmethod
    def load_all_from_disk() -> list[dict]:
        if not TRACE_FILE.exists():
            return []
        events = []
        with open(TRACE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events


def _safe_serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, (str, int, float, bool, list, dict)):
        return obj
    return str(obj)


def new_trace_id() -> str:
    return str(uuid.uuid4())[:8]


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
