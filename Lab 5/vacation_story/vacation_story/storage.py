"""Single-process JSON store. Worker integration must serialize read/modify/write."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import RLock
from uuid import uuid4

from .contracts import Trip


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TripStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.lock = RLock()
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, trip_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", trip_id):
            raise KeyError(trip_id)
        return self.root / trip_id

    def create(self, title: str) -> Trip:
        trip: Trip = dict(schema_version=1, id=uuid4().hex, title=title,
                          photos=[], checkpoints=[], story=None,
                          created_at=now(), updated_at=now(),
                          status=dict(state="collecting", current_stage=None,
                                      completed=0, total=0, error=None))
        self.directory(trip["id"]).mkdir()
        self.save(trip)
        return trip

    def save(self, trip: Trip) -> None:
        directory = self.directory(trip["id"])
        trip["updated_at"] = now()
        fd, temporary = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as target:
                json.dump(trip, target, ensure_ascii=False, indent=2)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, directory / "trip.json")
        finally:
            Path(temporary).unlink(missing_ok=True)

    def get(self, trip_id: str) -> Trip:
        try:
            return json.loads((self.directory(trip_id) / "trip.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise KeyError(trip_id) from None

    def list(self) -> list[Trip]:
        return sorted((self.get(p.parent.name) for p in self.root.glob("*/trip.json")),
                      key=lambda trip: trip["created_at"], reverse=True)

    def delete(self, trip_id: str) -> None:
        self.get(trip_id)
        shutil.rmtree(self.directory(trip_id))
