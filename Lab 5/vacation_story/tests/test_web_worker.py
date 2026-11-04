from io import BytesIO
from pathlib import Path
from threading import Event

import pytest

from PIL import Image

from vacation_story import create_app
from vacation_story.config import load_config
from vacation_story.contracts import StageFailure
from vacation_story.pipeline import FakePipeline
from vacation_story.storage import TripStore


def setup_app(tmp_path, pipeline=None):
    config = load_config()
    config['storage']['runtime_dir'] = str(tmp_path)
    return create_app(config, pipeline=pipeline or FakePipeline())


def upload(client, trip_id, metadata=True):
    source = BytesIO()
    exif = Image.Exif()
    if metadata:
        exif[36867] = '2026:10:15 12:30:00'
        exif[36881] = '-04:00'
        exif[270] = 'Lunch at the shore'
        exif[274] = 6
    Image.new('RGB', (2000, 1000), 'blue').save(source, 'JPEG', exif=exif)
    source.seek(0)
    response = client.post(f'/api/trips/{trip_id}/photos', data={'photo': (source, 'phone.jpg')})
    assert response.status_code == 201
    return response.json


def test_photo_metadata_preparation_answers_reload_and_delete(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    trip = client.post('/api/trips', json={'title': 'Coast'}).json
    photo = upload(client, trip['id'])
    assert photo['metadata']['captured_at'] == '2026-10-15T12:30:00-04:00'
    assert photo['user_description'] == 'Lunch at the shore'
    assert 'prepared_image_path' not in photo
    retained = Image.open(BytesIO(client.get(photo['photo_url']).data))
    assert retained.size == (800, 1600)
    assert not retained.getexif()
    response = client.patch(f"/api/trips/{trip['id']}/photos/{photo['id']}", json={
        'metadata': {'place_name': 'Cape May', 'captured_at': '2026-10-15T13:00:00-04:00'},
        'user_description': 'We shared lunch.', 'vibes': ['Relaxed', 'Funny']})
    assert response.status_code == 200
    assert response.json['extracted_metadata']['captured_at'] == photo['metadata']['captured_at']
    reloaded = setup_app(tmp_path).test_client().get(f"/api/trips/{trip['id']}").json['photos'][0]
    assert reloaded['metadata']['place_name'] == 'Cape May'
    assert reloaded['user_description'] == 'We shared lunch.'
    assert client.get(f"/api/trips/{trip['id']}/media/trip.json").status_code == 404
    directory = tmp_path / trip['id']
    assert len(list(directory.rglob('*.jpg'))) == 2
    assert not list(directory.rglob('*.tmp'))
    # An image without capture metadata must not acquire a filesystem timestamp.
    second = upload(client, trip['id'], metadata=False)
    assert second['metadata']['captured_at'] is None
    assert client.delete(f"/api/trips/{trip['id']}").status_code == 204
    assert not directory.exists()


def test_worker_failure_retry_and_resume_after_browser_closes(tmp_path):
    class RetryPipeline:
        calls = 0
        entered = Event()
        release = Event()

        def run(self, trip, output_dir, checkpoint):
            self.calls += 1
            checkpoint.started('observe', trip['photos'][0]['id'])
            if self.calls == 1:
                checkpoint(dict(stage='observe', photo_id=trip['photos'][0]['id'], result={'visible_content': 'Blue'}))
                self.entered.set()
                assert self.release.wait(5)
                raise StageFailure('synthesize', 'Test adapter failed; retry.', trip['photos'][0]['id'])
            assert trip['checkpoints'][0]['stage'] == 'observe'
            return FakePipeline().run(trip, output_dir, checkpoint)

    pipeline = RetryPipeline()
    app = setup_app(tmp_path, pipeline)
    client = app.test_client()
    trip = client.post('/api/trips', json={'title': 'Retry trip'}).json
    photo = upload(client, trip['id'])
    base = f"/api/trips/{trip['id']}"
    worker = app.extensions['worker']
    try:
        assert pipeline.calls == 0  # upload never starts inference
        assert client.post(base + '/process').status_code == 202
        assert pipeline.entered.wait(5)
        assert client.delete(base).status_code == 409
        assert client.post(base + '/process').status_code == 409
        assert client.patch(base + '/photos/' + photo['id'], json={'vibes': []}).status_code == 409
        pipeline.release.set()
        worker.queue.join()
        # New browser connection observes persisted failure, then retries.
        reopened = app.test_client()
        failed = reopened.get(base + '/status').json
        assert failed['state'] == 'failed'
        assert failed['error']['stage'] == 'synthesize'
        assert failed['completed'] == 1
        assert reopened.post(base + '/retry').status_code == 202
        worker.queue.join()
        assert reopened.get(base + '/status').json['state'] == 'ready'
        story = reopened.get(base + '/story').json
        assert story['story_style'] == 'connected_journal'
        assert story['chapters'][0]['photo_id'] == photo['id']
        assert story['chapters'][0]['audio_url'] is None
        assert 'audio_path' not in story['chapters'][0]
        assert pipeline.calls == 2
    finally:
        pipeline.release.set()
        worker.close()


def test_restart_marks_interrupted_job_retryable(tmp_path):
    store = TripStore(tmp_path)
    trip = store.create('Interrupted trip')
    trip['status'].update(state='processing', current_stage='chapter', completed=1, total=7)
    trip['checkpoints'] = [dict(stage='observe', photo_id='photo', result={'visible_content': 'Water'})]
    store.save(trip)
    app = setup_app(tmp_path)
    status = app.test_client().get(f"/api/trips/{trip['id']}/status").json
    assert status['state'] == 'failed'
    assert status['error']['retryable']
    assert TripStore(tmp_path).get(trip['id'])['checkpoints'] == trip['checkpoints']


@pytest.mark.parametrize('start_route', ['/rewrite', '/process'])
def test_story_finalization_reuses_analysis_and_preserves_old_edition(tmp_path, start_route):
    from copy import deepcopy
    import json
    import wave
    from vacation_story.pipeline import StoryPipeline

    config = load_config()
    config['storage']['runtime_dir'] = str(tmp_path)
    entered, release = Event(), Event()
    calls = []

    class JournalModel:
        def generate(self, messages, schema, image_path=None):
            fields = set(schema['required'])
            assert 'visible_content' not in fields and 'grounded_details' not in fields, 'Saved analysis must be reused'
            if 'premise' in fields:
                calls.append('outline')
                entered.set()
                assert release.wait(5)
                return dict(premise='Our coastal stop.', thread='A pause by the shore.', closing_callback='The shore.')
            if 'narrative' in fields:
                calls.append('chapter')
                return dict(title='A pause along the way', narrative='We paused by the shore.', summary='We paused by the shore.')
            if 'day_narrative' in fields:
                calls.append('day')
                return dict(day_title='A coastal day', day_narrative='Our coastal pause brought the day together.')
            calls.append('framing')
            return dict(opening='We paused along the way.', closing='We return to the shore in these memories.')

    class JournalVoice:
        def narrate(self, text, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(target), 'wb') as voice:
                voice.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
                voice.writeframes(b'\x00\x00' * 30)
            return str(target)

    app = create_app(config, pipeline=StoryPipeline(config, model=JournalModel(), narrator=JournalVoice()))
    store, worker = app.extensions['trip_store'], app.extensions['worker']
    trip = store.create('A coastal journey')
    fixture = Path(__file__).parent / 'fixtures/photo-input.json'
    trip['photos'] = [json.loads(fixture.read_text())]
    photo_id = trip['photos'][0]['id']
    trip['story'] = FakePipeline().run(trip, str(store.directory(trip['id'])), lambda _: None)
    trip['story'].pop('story_style')  # An old caption-based result awaiting finalization.
    old_audio = store.directory(trip['id']) / 'narration/0000-opening.wav'
    old_audio.parent.mkdir()
    old_audio.write_bytes(b'old audio retained with the original edition')
    trip['story']['opening']['audio_path'] = str(old_audio)
    trip['checkpoints'] = [dict(stage='observe', photo_id=photo_id, result=dict(visible_content='A shore.', uncertainties=[])),
        dict(stage='synthesize', photo_id=photo_id, result=dict(summary='A coastal pause.', grounded_details=['Shore'], uncertainties=[])),
        dict(stage='chapter', photo_id=photo_id, result=dict(title='Old caption', narrative='A shore.', summary='A shore.'))]
    trip['status'].update(state='ready', completed=7, total=7)
    store.save(trip)
    before = deepcopy(trip)
    client = app.test_client()
    base = f"/api/trips/{trip['id']}"
    try:
        detail = client.get(base).json
        assert detail['requires_processing'] and not detail['story_available']
        assert client.get(base + '/story').status_code == 409
        assert client.post(base + start_route).status_code == 202
        assert entered.wait(5)
        assert client.get(base + '/story').status_code == 409
        assert client.post(base + '/rewrite').status_code == 409
        assert store.get(trip['id'])['story'] == before['story']
        backup = next(store.directory(trip['id']).glob('trip.before-story-rewrite.*.json'))
        assert json.loads(backup.read_text())['story'] == before['story']
        release.set()
        worker.queue.join()
        result = store.get(trip['id'])
        assert result['status']['state'] == 'ready'
        assert result['status']['completed'] == result['status']['total'] == 8
        assert result['photos'] == before['photos']
        assert result['checkpoints'][:2] == before['checkpoints'][:2]
        assert calls == ['outline', 'chapter', 'framing', 'day']
        assert result['story']['story_style'] == 'connected_journal'
        assert '/editions/' in result['story']['days'][0]['audio_path']
        assert Path(result['story']['days'][0]['audio_path']).is_file()
        assert old_audio.read_bytes() == b'old audio retained with the original edition'
        assert client.get(base + '/story').json['story_style'] == 'connected_journal'
        assert client.get(base + '/story').json['edition_id'] == result['edition_id']
        assert not client.get(base).json['requires_processing']
        assert client.get(base).json['story_available']
    finally:
        release.set()
        worker.close()


def test_intermediate_caption_result_is_never_published_as_finished(tmp_path):
    class CaptionPipeline:
        def run(self, trip, output_dir, checkpoint):
            story = FakePipeline().run(trip, output_dir, checkpoint)
            story.pop('story_style')
            return story

    app = setup_app(tmp_path, CaptionPipeline())
    client = app.test_client()
    trip = client.post('/api/trips', json={'title': 'Final story only'}).json
    upload(client, trip['id'])
    base = f"/api/trips/{trip['id']}"
    worker = app.extensions['worker']
    try:
        assert client.post(base + '/process').status_code == 202
        worker.queue.join()
        status = client.get(base + '/status').json
        assert status['state'] == 'failed' and status['error']['retryable']
        assert status['error']['stage'] == 'chapter'
        assert client.get(base + '/story').status_code == 409
        assert not client.get(base).json['story_available']
    finally:
        worker.close()


def test_iphone_style_multiframe_jpeg_keeps_primary_image_and_capture_metadata(tmp_path):
    app = setup_app(tmp_path)
    client = app.test_client()
    trip = client.post('/api/trips', json={'title': 'iPhone JPEG upload'}).json
    source = BytesIO()
    exif = Image.Exif()
    exif[36867] = '2026:11:01 10:30:00'
    exif[36881] = '-05:00'
    exif[274] = 6
    exif[270] = 'Walking together'
    Image.new('RGB', (320, 160), 'red').save(
        source, format='MPO', save_all=True,
        append_images=[Image.new('RGB', (80, 40), 'blue')], exif=exif)
    source.seek(0)
    with Image.open(source) as decoded:
        assert decoded.format == 'MPO' and decoded.n_frames == 2
    source.seek(0)
    response = client.post(f"/api/trips/{trip['id']}/photos",
        data={'photo': (source, 'IMG_4396.jpeg', 'image/jpeg')})
    assert response.status_code == 201
    photo = response.json
    assert photo['metadata']['captured_at'] == '2026-11-01T10:30:00-05:00'
    assert photo['user_description'] == 'Walking together'
    with Image.open(BytesIO(client.get(photo['photo_url']).data)) as retained:
        assert retained.format == 'JPEG'
        assert retained.size == (160, 320)
        assert not retained.getexif()
        red, green, blue = retained.getpixel((80, 160))
        assert red > 200 and green < 30 and blue < 30
    detail = client.get(f"/api/trips/{trip['id']}").json
    assert len(detail['photos']) == 1  # Auxiliary frame must never become a scene.
    assert detail['status']['state'] == 'collecting'
    directory = tmp_path / trip['id']
    assert len(list(directory.rglob('*.jpg'))) == 2  # Prepared + analysis copies.
    assert not list(directory.rglob('*.jpeg'))
    assert not list(directory.rglob('*.mpo'))
