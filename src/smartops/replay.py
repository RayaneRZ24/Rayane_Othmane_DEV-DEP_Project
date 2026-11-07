"""One replay owner, monotonic time, atomic cursor updates, and bounded data access."""
import base64
from hashlib import sha256
import hmac
import json
from pathlib import Path
import secrets
from threading import RLock
import time
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from smartops.storage import Alert, ReplayOperation, ReplayRun, RunEvent
from smartops.detection import observe
from smartops.telemetry import Registry


class ReplayError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def fail(status, code, message):
    raise ReplayError(status, code, message)


class ReplayClock:
    def __init__(self, speed, now):
        self.speed, self.last, self.carry = speed, now, 0.0

    def elapsed_samples(self, now):
        self.carry += max(0, now - self.last) * self.speed
        self.last = now
        whole = int(self.carry + 1e-9)
        self.carry -= whole
        return whole


class ReplayManager:
    def __init__(self, engine, root: Path, monotonic=time.monotonic):
        self.engine, self.registry, self.now = engine, Registry(root), monotonic
        self.lock, self.secret = RLock(), secrets.token_bytes(32)
        self.active_id, self.clock, self.cache = None, None, None
        self.recovered = False

    def _get(self, session, identifier):
        run = session.get(ReplayRun, UUID(str(identifier)))
        if run is None:
            fail(404, "RUN_NOT_FOUND", "Exécution introuvable.")
        if str(run.scenario_id) not in self.registry.scenarios:
            fail(503, "SCENARIO_UNAVAILABLE", "Les observations de cette session sont indisponibles.")
        return run

    def _public(self, run):
        scenario = self.registry.scenarios[str(run.scenario_id)]
        return {"id": str(run.id), "scenario_id": str(run.scenario_id), "status": run.status,
                "phase": "pending" if run.cursor_index is None else "replaying",
                "cursor_index": run.cursor_index, "speed": run.speed,
                "start_index": scenario.start_index, "end_index": scenario.end_index,
                "machine_id": scenario.machine_id, "axis": "sample_index",
                "analyzed_index": run.analyzed_index, "detector_name": run.detector_name,
                "detector_version": run.detector_profile.get("version") if run.detector_profile else None,
                "created_at": run.created_at.isoformat()}

    def _event(self, session, run):
        session.flush()
        session.add(RunEvent(run_id=run.id, payload=self._public(run)))

    def recover(self):
        with self.lock:
            if self.recovered:
                return
            with Session(self.engine) as session:
                for run in session.scalars(select(ReplayRun).where(ReplayRun.active_slot == 1)):
                    run.status, run.active_slot = "interrupted", None
                    self._close_alerts(session, run, "interrupted")
                    if str(run.scenario_id) in self.registry.scenarios:
                        self._event(session, run)
                session.commit()
            self.recovered = True

    def interrupt(self):
        with self.lock:
            if not self.recovered:
                return
            try:
                with Session(self.engine) as session:
                    if self.active_id:
                        run = session.get(ReplayRun, self.active_id)
                        if run and run.active_slot == 1:
                            run.status, run.active_slot = "interrupted", None
                            self._close_alerts(session, run, "interrupted")
                            self._event(session, run)
                            session.commit()
            except SQLAlchemyError:
                pass
            self.active_id, self.clock, self.recovered = None, None, False

    def _digest(self, value):
        return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def _existing(self, session, key, digest):
        operation = session.get(ReplayOperation, UUID(str(key)))
        if operation:
            if not hmac.compare_digest(operation.request_hash, digest):
                fail(409, "IDEMPOTENCY_CONFLICT", "Cet identifiant a déjà été utilisé pour une autre opération.")
            return operation.response

    def create(self, key, scenario_id, speed, detector_name="robust-mad-v1"):
        with self.lock:
            self.recover()
            scenario_id = str(scenario_id)
            if scenario_id not in self.registry.scenarios:
                fail(404, "SCENARIO_NOT_FOUND", "Session introuvable.")
            digest = self._digest(["create", scenario_id, speed, detector_name])
            with Session(self.engine) as session:
                previous = self._existing(session, key, digest)
                if previous:
                    return previous, False
                run = ReplayRun(scenario_id=UUID(scenario_id), speed=speed, status="created", detector_name=detector_name)
                session.add(run)
                self._event(session, run)
                result = self._public(run)
                session.add(ReplayOperation(id=UUID(str(key)), request_hash=digest, response=result))
                session.commit()
                return result, True

    def list_runs(self):
        with self.lock:
            self.recover()
            with Session(self.engine) as session:
                runs = session.scalars(select(ReplayRun).order_by(ReplayRun.created_at.desc(), ReplayRun.id).limit(50))
                return [self._public(run) for run in runs if str(run.scenario_id) in self.registry.scenarios]

    def read(self, identifier):
        with self.lock:
            self.recover()
            with Session(self.engine) as session:
                return self._public(self._get(session, identifier))

    def command(self, identifier, key, action):
        with self.lock:
            self.recover()
            digest = self._digest([str(identifier), action])
            with Session(self.engine) as session:
                previous = self._existing(session, key, digest)
                if previous:
                    return previous
            self.tick()
            with Session(self.engine) as session:
                run = self._get(session, identifier)
                state = run.status
                if action in {"start", "resume"}:
                    expected = "created" if action == "start" else "paused"
                    if state != expected:
                        fail(409, "RUN_STATE_CONFLICT", "Cette exécution ne peut pas être démarrée dans son état actuel.")
                    if self.active_id and self.active_id != run.id:
                        fail(409, "RUN_ACTIVE", "Une autre exécution est déjà active.")
                    # Validate/load before making the run active. Keep only one telemetry cache.
                    self._data(run)
                    if action == "start":
                        try:
                            run.detector_profile = self._data(run).fit_detector(self.registry.root, run.detector_name)
                        except (OSError, ValueError, KeyError):
                            fail(503, "REFERENCE_UNAVAILABLE", "La référence d’analyse de cette machine est indisponible.")
                        run.detector_state = {}
                        self.clock = ReplayClock(run.speed, self.now())
                        run.cursor_index = self.registry.scenarios[str(run.scenario_id)].start_index
                        self._analyze(session, run)
                    else:
                        if self.clock is None:
                            fail(409, "RUN_INTERRUPTED", "Cette exécution a été interrompue.")
                        self.clock.last = self.now()
                    run.status, run.active_slot, self.active_id = "running", 1, run.id
                elif action == "pause":
                    if state not in {"running", "paused"}:
                        fail(409, "RUN_STATE_CONFLICT", "Cette exécution ne peut pas être mise en pause.")
                    run.status = "paused"
                elif action == "stop":
                    if state not in {"created", "running", "paused", "stopped"}:
                        fail(409, "RUN_STATE_CONFLICT", "Cette exécution est terminée.")
                    run.status, run.active_slot = "stopped", None
                    self._close_alerts(session, run, "stopped")
                    if self.active_id == run.id:
                        self.active_id, self.clock = None, None
                self._event(session, run)
                result = self._public(run)
                session.add(ReplayOperation(id=UUID(str(key)), request_hash=digest, response=result))
                session.commit()
                return result

    def tick(self):
        with self.lock:
            if not self.recovered or not self.active_id or not self.clock:
                return
            with Session(self.engine) as session:
                run = self._get(session, self.active_id)
                if run.status != "running":
                    return
                delta = self.clock.elapsed_samples(self.now())
                if not delta:
                    return
                end = self.registry.scenarios[str(run.scenario_id)].end_index
                run.cursor_index = min(end, run.cursor_index + delta)
                self._analyze(session, run)
                if run.cursor_index == end:
                    run.status, run.active_slot = "completed", None
                    self._close_alerts(session, run, "completed")
                self._event(session, run)
                session.commit()
                if run.status == "completed":
                    self.active_id, self.clock = None, None

    def _close_alerts(self, session, run, status):
        for alert in session.scalars(select(Alert).where(Alert.run_id == run.id, Alert.status == "active")):
            alert.status, alert.closed_index = status, run.cursor_index

    def _analyze(self, session, run):
        if not run.detector_profile:
            return
        begin = 0 if run.analyzed_index is None else run.analyzed_index + 1
        if begin > run.cursor_index:
            return
        frame = self._data(run).metrics.iloc[begin:run.cursor_index + 1]
        state, transitions = observe(run.detector_profile, run.detector_state, frame)
        active = {str(a.id): a for a in session.scalars(select(Alert).where(Alert.run_id == run.id, Alert.status == "active"))}
        for transition in transitions:
            kind, identifier = transition["kind"], transition["id"]
            if kind == "open":
                alert = Alert(id=UUID(identifier), run_id=run.id, status="active",
                              **{k: v for k, v in transition.items() if k not in {"kind", "id"}})
                session.add(alert)
                active[identifier] = alert
            elif kind == "update":
                alert = active[identifier]
                alert.last_anomalous_index, alert.peak_score = transition["last_anomalous_index"], transition["peak_score"]
            else:
                alert = active.pop(identifier)
                alert.status, alert.closed_index = "recovered", transition["closed_index"]
        run.detector_state, run.analyzed_index = state, run.cursor_index

    def alerts(self, identifier, offset=0, limit=100, resource=None):
        with self.lock:
            self.recover()
            with Session(self.engine) as session:
                run = self._get(session, identifier)
                condition = (Alert.run_id == run.id, Alert.detected_index <= (run.cursor_index if run.cursor_index is not None else -1))
                counts = session.execute(select(Alert.resource, Alert.feature_id, Alert.status, func.count()).where(*condition).group_by(Alert.resource, Alert.feature_id, Alert.status)).all()
                resource_counts = {key: {"total": 0, "active": 0} for key in ("cpu", "memory", "disk", "network")}
                feature_counts = {}
                for component, feature, status, count in counts:
                    resource_counts[component]["total"] += count
                    resource_counts[component]["active"] += count if status == "active" else 0
                    feature_counts[feature] = feature_counts.get(feature, 0) + count
                filtered = (*condition, Alert.resource == resource) if resource else condition
                rows = session.scalars(select(Alert).where(*filtered).order_by(Alert.detected_index.desc(), Alert.feature_id, Alert.id).offset(offset).limit(limit))
                items = [{"id": str(a.id), "feature_id": a.feature_id, "feature_label": a.feature_label,
                          "resource": a.resource, "status": a.status, "start_index": a.start_index,
                          "detected_index": a.detected_index, "last_anomalous_index": a.last_anomalous_index,
                          "closed_index": a.closed_index, "peak_score": a.peak_score, "evidence": a.evidence} for a in rows]
                total = session.scalar(select(func.count()).select_from(Alert).where(*filtered))
                active_count = session.scalar(select(func.count()).select_from(Alert).where(*condition, Alert.status == "active"))
                return {"items": items, "total": total, "active_count": active_count,
                        "resource_counts": resource_counts, "feature_counts": feature_counts,
                        "cursor_index": run.cursor_index, "analyzed_index": run.analyzed_index,
                        "detector_version": run.detector_profile.get("version") if run.detector_profile else None}

    def _data(self, run):
        sid = str(run.scenario_id)
        if self.cache is None or self.cache.scenario.id != sid:
            try:
                self.cache = self.registry.load(sid)
            except (OSError, ValueError, KeyError):
                fail(503, "TELEMETRY_UNAVAILABLE", "Les observations de cette session sont indisponibles.")
        return self.cache

    def _token(self, payload):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw + hmac.digest(self.secret, raw, "sha256")).decode()

    def page(self, identifier, feature, begin, end, limit, token):
        with self.lock:
            self.recover()
            with Session(self.engine) as session:
                run = self._get(session, identifier)
                scope = self._digest([str(identifier), feature, begin, end])
                if feature not in {f["id"] for f in self.registry.scenarios[str(run.scenario_id)].features}:
                    fail(404, "SIGNAL_NOT_FOUND", "Indicateur introuvable.")
                offset = 0
                if run.cursor_index is None:
                    return {"items": [], "effective_to_index": None, "next_cursor": None}
                boundary = min(end if end is not None else run.cursor_index, run.cursor_index)
                start = begin if begin is not None else max(self.registry.scenarios[str(run.scenario_id)].start_index, boundary - 499)
                if token:
                    try:
                        decoded = base64.b64decode(token.encode(), altchars=b"-_", validate=True)
                        raw, signature = decoded[:-32], decoded[-32:]
                        if not hmac.compare_digest(hmac.digest(self.secret, raw, "sha256"), signature):
                            raise ValueError()
                        payload = json.loads(raw)
                        if payload["scope"] != scope or payload["end"] > run.cursor_index:
                            raise ValueError()
                        start, boundary, offset = payload["start"], payload["end"], payload["offset"]
                    except (ValueError, KeyError, TypeError):
                        fail(409, "INVALID_CURSOR", "Cette page n'est plus disponible. Actualisez les observations.")
                if start > boundary:
                    fail(422, "INVALID_WINDOW", "La période demandée est invalide.")
                data = self._data(run)
                items, more = data.metric_page(feature, start, boundary, offset, limit)
                continuation = self._token({"scope": scope, "start": start, "end": boundary, "offset": offset + len(items)}) if more else None
                return {"items": items, "effective_to_index": boundary, "next_cursor": continuation}

    def events(self, identifier, after=None):
        with self.lock:
            self.recover()
            with Session(self.engine) as session:
                run = self._get(session, identifier)
                if after is None:
                    latest = session.scalar(select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run.id)) or 0
                    return [(latest, self._public(run))]
                previous = session.get(RunEvent, after)
                if previous is None or previous.run_id != run.id:
                    fail(409, "INVALID_EVENT_CURSOR", "Actualisez cette exécution pour rétablir la connexion.")
                rows = session.scalars(select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.sequence > after).order_by(RunEvent.sequence).limit(500))
                return [(row.sequence, row.payload) for row in rows]
