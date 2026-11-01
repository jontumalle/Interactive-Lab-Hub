"""Guard missing setup before generation; repair audio without model calls."""
from copy import deepcopy
import json
from pathlib import Path
import wave

import pytest

from vacation_story import create_app
from vacation_story.config import load_config, PROJECT_ROOT
from vacation_story.pipeline import FakePipeline, StoryPipeline


def write_wav(target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), 'wb') as audio:
        audio.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        audio.writeframes(b'\x00\x00' * 30)
    return str(target)


def test_missing_local_voice_blocks_startup_and_job_before_generation(tmp_path, monkeypatch, capsys):
    from vacation_story import __main__ as launcher
    config = load_config()
    config['storage']['runtime_dir'] = str(tmp_path)
    config['narration']['voice_path'] = str(PROJECT_ROOT / 'voices/missing-test-voice.onnx')
    monkeypatch.setattr(launcher, 'load_config', lambda: config)
    monkeypatch.setattr(launcher, 'create_app', lambda *_: pytest.fail('Server must not start with missing narration setup'))
    monkeypatch.setattr('sys.argv', ['vacation_story'])
    with pytest.raises(SystemExit) as result:
        launcher.main()
    assert result.value.code == 1
    assert 'setup.sh' in capsys.readouterr().err
    app = create_app(config)
    store = app.extensions['trip_store']
    trip = store.create('Missing setup')
    fixture = json.loads((Path(__file__).parent / 'fixtures/photo-input.json').read_text())
    trip['photos'] = [fixture]
    store.save(trip)
    response = app.test_client().post(f"/api/trips/{trip['id']}/process")
    assert response.status_code == 503
    assert response.json['error']['code'] == 'narration_not_ready'
    assert store.get(trip['id'])['status']['state'] == 'collecting'
    assert app.extensions['worker'].thread is None


def test_narration_setup_rejects_external_project_dependencies(tmp_path):
    from vacation_story.narration import setup_problem
    config = load_config()['narration']
    config['executable'] = str(tmp_path / 'other-project/piper')
    assert 'inside this project' in setup_problem(config)


def test_audio_only_retry_preserves_story_and_valid_wavs_and_explains_failures(tmp_path):
    class NoModel:
        def generate(self, *_args, **_kwargs):
            pytest.fail('Narration repair must never call the language model')

    class Narrator:
        texts = []
        fail_once = True

        def narrate(self, text, target):
            self.texts.append(text)
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError('Voice synthesis failed. Retry narration.')
            return write_wav(target)

    config = load_config()
    config['storage']['runtime_dir'] = str(tmp_path)
    narrator = Narrator()
    pipeline = StoryPipeline(config, model=NoModel(), narrator=narrator)
    app = create_app(config, pipeline=pipeline)
    store, worker = app.extensions['trip_store'], app.extensions['worker']
    trip = store.create('Narration repair')
    trip['photos'] = [json.loads((Path(__file__).parent / 'fixtures/photo-input.json').read_text())]
    trip['story'] = FakePipeline().run(trip, str(store.directory(trip['id'])), lambda _: None)
    before = deepcopy(trip['story'])
    opening = write_wav(store.directory(trip['id']) / 'narration/0000-opening.wav')
    original_bytes = Path(opening).read_bytes()
    trip['story']['opening']['audio_path'] = opening
    trip['status'].update(state='ready', total=6, completed=6)
    photo_id = trip['photos'][0]['id']
    trip['checkpoints'] = [dict(stage=stage, photo_id=photo_id if stage != 'framing' else None, result={})
                           for stage in ('observe', 'synthesize', 'chapter', 'framing')]
    trip['checkpoints'] += [dict(stage='narration', photo_id=None, result=dict(segment='opening', available=True, audio_path=opening)),
                           dict(stage='narration', photo_id=photo_id, result=dict(segment='chapter', available=False, audio_path=None)),
                           dict(stage='narration', photo_id=None, result=dict(segment='closing', available=False, audio_path=None))]
    store.save(trip)
    client = app.test_client()
    base = f"/api/trips/{trip['id']}"
    try:
        assert client.post(base + '/narration/retry').status_code == 202
        worker.queue.join()
        partial = client.get(base + '/story').json
        assert partial['narration'] == 'partial'
        assert partial['chapters'][0]['audio_error'] == 'Voice synthesis failed. Retry narration.'
        failed = [item for item in store.get(trip['id'])['checkpoints']
                  if item['stage'] == 'narration' and item['photo_id'] == photo_id][0]
        assert failed['result']['error'] == partial['chapters'][0]['audio_error']
        assert client.post(base + '/narration/retry').status_code == 202
        worker.queue.join()
        ready = client.get(base + '/story').json
        assert ready['narration'] == 'available'
        assert client.get(base + '/status').json['total'] == 6  # Four saved model stages + moment/day audio; no unused opening/closing.
        assert ready['chapters'][0]['audio_error'] is None
        assert narrator.texts == [before['chapters'][0]['narrative'], before['days'][0]['narrative'], before['chapters'][0]['narrative']]
        assert ready['opening']['text'] == before['opening']['text']
        assert ready['chapters'][0]['narrative'] == before['chapters'][0]['narrative']
        assert ready['closing']['text'] == before['closing']['text']
        assert Path(opening).read_bytes() == original_bytes
        audio = client.get(ready['chapters'][0]['audio_url'])
        assert audio.status_code == 200 and audio.data.startswith(b'RIFF')
        assert 'audio_path' not in ready['chapters'][0]
    finally:
        worker.close()
