"""Day grouping, one-WAV-per-day, source coverage, and preserving old moments."""
from copy import deepcopy
import json
from pathlib import Path
import wave

from vacation_story import create_app
from vacation_story.config import load_config
from vacation_story.days import capture_day, group_days
from vacation_story.pipeline import FakePipeline, StoryPipeline
from vacation_story.narration import segments


def photo(index, date, lat=42.35, lon=-71.07):
    return dict(id=f'photo-{index}', submission_order=index, prepared_image_path=f'/fixture/{index}.jpg',
                analysis_image_path=f'/fixture/analysis-{index}.jpg', user_description=f'We remember experience {index}.', vibes=[],
                metadata=dict(captured_at=date, latitude=lat, longitude=lon, place_name=None, embedded_description=None))


def wav(target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), 'wb') as audio:
        audio.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
        audio.writeframes(b'\x00\x00' * 20)
    return str(target)


def test_day_grouping_preserves_camera_date_and_keeps_unknowns_separate():
    photos = [photo(0, '2018-08-24T23:30:00-04:00'), photo(1, '2018-08-25T00:10:00+03:00'),
              photo(2, None, None, None), photo(3, '2018-08-24T12:00:00')]
    moments = [dict(photo_id=p['id'], time=p['metadata']['captured_at']) for p in photos]
    groups = group_days(moments, photos)
    assert [group['date'] for group in groups] == ['2018-08-24', '2018-08-25', None]
    assert groups[0]['moment_ids'] == ['photo-0', 'photo-3']
    assert groups[-1]['id'] == 'undated' and groups[-1]['moment_ids'] == ['photo-2']
    assert capture_day('invalid') is None
    assert capture_day('2018-08-24T23:30:00-04:00') == '2018-08-24'


def test_connected_story_upgrade_adds_days_only_and_reuses_existing_moment_wavs(tmp_path):
    class DayModel:
        calls = []
        def generate(self, messages, schema, image_path=None):
            assert schema['required'] == ['day_title', 'day_narrative']
            payload = json.loads(messages[-1]['content'])
            self.calls.append(payload)
            return dict(day_title='Our day together', day_narrative='We remember this day through the experiences we shared.')

    class Voice:
        texts = []
        def narrate(self, text, target):
            self.texts.append(text)
            return wav(target)

    config = load_config(); config['storage']['runtime_dir'] = str(tmp_path)
    model, voice = DayModel(), Voice()
    app = create_app(config, pipeline=StoryPipeline(config, model=model, narrator=voice))
    store, worker = app.extensions['trip_store'], app.extensions['worker']
    trip = store.create('Three days together')
    trip['photos'] = [photo(0, '2018-08-24T11:00:00'), photo(1, '2018-08-24T19:00:00'),
                      photo(2, '2018-08-25T12:00:00'), photo(3, '2018-08-26T12:00:00', None, None)]
    trip['story'] = FakePipeline().run(trip, str(store.directory(trip['id'])), lambda _: None)
    trip['story'].pop('journey_version'); trip['story'].pop('days')  # Approved v1 journal.
    trip['status'].update(state='ready', total=20, completed=20)
    for moment in trip['story']['chapters']:
        path = wav(store.directory(trip['id']) / 'narration' / f"{moment['photo_id']}.wav")
        moment['audio_path'] = path
        trip['checkpoints'].append(dict(stage='narration', photo_id=moment['photo_id'],
            result=dict(segment='chapter', audio_path=path, available=True)))
    before = deepcopy(trip['story']); store.save(trip)
    client = app.test_client(); base = f"/api/trips/{trip['id']}"
    try:
        assert client.get(base).json['requires_processing']
        assert client.post(base + '/process').status_code == 202
        worker.queue.join()
        result = store.get(trip['id'])
        assert result['status']['state'] == 'ready'
        assert result['job_kind'] == 'days'
        assert [{key: value for key, value in moment.items() if key != 'audio_error'} for moment in result['story']['chapters']] == before['chapters']
        assert result['story']['opening'] == before['opening']
        assert result['story']['closing'] == before['closing']
        assert len(model.calls) == 3 and len(voice.texts) == 3
        assert [call['moment_count'] for call in model.calls] == [2, 1, 1]
        assert result['story']['narration'] == 'available'  # Unplayed opening/closing have no WAV.
        assert len(list(store.directory(trip['id']).glob('trip.before-story-rewrite.*.json'))) == 1
        story = client.get(base + '/story').json
        assert story['journey_version'] == 2 and len(story['days']) == 3
        assert [day['moment_ids'] for day in story['days']] == [['photo-0', 'photo-1'], ['photo-2'], ['photo-3']]
        assert story['moments'][0]['latitude'] == 42.35
        assert story['moments'][-1]['latitude'] is None
        assert story['chapters'] == story['moments']  # Compatibility alias only.
        for day in story['days']:
            response = client.get(day['audio_url'])
            assert response.status_code == 200 and response.data.startswith(b'RIFF')
        assert len(list(segments(result['story']))) == 7  # Four moments and three days.
    finally:
        worker.close()


def test_large_day_considers_every_source_but_saves_one_day_story_and_audio(tmp_path):
    class DayModel:
        seen = []
        def generate(self, messages, schema, image_path=None):
            payload = json.loads(messages[-1]['content'])
            self.seen.extend(memory['owner_note'] for memory in payload['ordered_memories'])
            if len(self.seen) > 12:
                assert payload['previous_day_story']['day_narrative'] == 'Earlier experiences form our day.'
            return dict(day_title='Our day', day_narrative='Earlier experiences form our day.')

    config = load_config(); config['narration']['enabled'] = False
    trip = dict(title='A full day', photos=[photo(i, '2018-08-24T12:00:00') for i in range(15)], checkpoints=[])
    story = FakePipeline().run(trip, str(tmp_path), lambda _: None)
    model = DayModel(); pipeline = StoryPipeline(config, model=model)
    checkpoints = []
    result = pipeline.add_days(trip, story, checkpoints.append)
    assert model.seen == [p['user_description'] for p in trip['photos']]
    assert len(result['days']) == 1 and len(result['days'][0]['moment_ids']) == 15
    assert [item['result']['batch'] for item in checkpoints] == [0, 1]
    assert all(item['photo_id'] is None and item['result']['day_id'] == 'day-2018-08-24' for item in checkpoints)
