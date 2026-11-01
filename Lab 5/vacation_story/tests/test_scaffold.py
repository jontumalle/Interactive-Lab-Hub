import json
from pathlib import Path

from vacation_story import create_app
from vacation_story.config import load_config
from vacation_story.pipeline import FakePipeline
from vacation_story.storage import TripStore

FIXTURES = Path(__file__).parent / "fixtures"


def test_trip_persists_across_app_instances_and_deletes(tmp_path):
    config = load_config()
    config["storage"]["runtime_dir"] = str(tmp_path)
    client = create_app(config).test_client()
    response = client.post("/api/trips", json={"title": "Coastal weekend"})
    assert response.status_code == 201
    trip_id = response.json["id"]
    restarted = create_app(config).test_client()
    assert restarted.get("/api/trips").json["trips"][0]["id"] == trip_id
    assert restarted.get(f"/api/trips/{trip_id}").json["title"] == "Coastal weekend"
    assert restarted.get(f"/api/trips/{trip_id}/status").json["state"] == "collecting"
    # Trip deletion owns all runtime media, not only the JSON record.
    directory = TripStore(tmp_path).directory(trip_id)
    (directory / "photos").mkdir()
    (directory / "photos" / "prepared.jpg").write_bytes(b"placeholder media")
    assert restarted.delete(f"/api/trips/{trip_id}").status_code == 204
    assert not directory.exists()
    assert restarted.get(f"/api/trips/{trip_id}").status_code == 404


def test_fake_pipeline_preserves_photo_association_and_user_text(tmp_path):
    trip = json.loads((FIXTURES / "trip.json").read_text())
    checkpoints = []
    story = FakePipeline().run(trip, str(tmp_path), checkpoints.append)
    assert story["chapters"][0]["photo_id"] == trip["photos"][0]["id"]
    assert story["chapters"][0]["narrative"] == trip["photos"][0]["user_description"]
    assert story["narration"] == "unavailable"
    assert checkpoints[0]["stage"] == "chapter"
    # The fixture paths need not exist: no images, models, or voices are accessed.
    assert not list(tmp_path.iterdir())
