"""Component checks use injected adapters: no models, voices, Flask, or HTTP."""
from copy import deepcopy
import json
from pathlib import Path
import wave

import pytest

from vacation_story.config import load_config
from vacation_story.contracts import StageFailure
from vacation_story.pipeline import StoryPipeline, ordered_photos

FIXTURES = Path(__file__).parent / 'fixtures'


class Model:
    def __init__(self):
        self.calls = []
        self.fail_once = True

    def generate(self, messages, schema, image_path=None):
        fields = set(schema['required'])
        if 'visible_content' in fields:
            stage, result = 'observe', dict(visible_content='A sandy shore.', uncertainties=[])
            # Observation receives the image alone, never private context.
            assert image_path
            assert 'after lunch' not in messages[-1]['content']
        elif 'grounded_details' in fields:
            stage, result = 'synthesize', dict(summary='A coastal stop after lunch.', grounded_details=['Shore'], uncertainties=[])
            assert 'after lunch' in messages[-1]['content']
            assert 'Relaxed' in messages[-1]['content']
            assert 'Corrected coast' in messages[-1]['content']
        elif 'premise' in fields:
            payload = json.loads(messages[-1]['content'])
            assert payload['ordered_moments'][0]['user_context'] == 'We stopped by the coast after lunch.'
            stage, result = 'outline', dict(premise='A coastal journey.', thread='A stop by the coast.', closing_callback='The shore.')
        elif 'narrative' in fields:
            payload = json.loads(messages[-1]['content'])
            assert payload['user_description'] == 'We stopped by the coast after lunch.'
            assert payload['metadata']['place_name'] == 'Corrected coast'
            assert payload['vibes'] == ['Relaxed', 'Awe-inspiring']
            assert 'synthesis' in payload
            stage, result = 'chapter', dict(title='By the coast', narrative='We stopped by the coast after lunch.', summary='A stop after lunch.')
        elif 'day_narrative' in fields:
            stage, result = 'day', dict(day_title='A day by the coast', day_narrative='We paused by the coast after lunch, a memory that joins the day together.')
        else:
            stage, result = 'framing', dict(opening='The sun sets over Buenos Aires.', closing='We board the bus.')
            assert 'chapter_summaries' in messages[-1]['content']
        self.calls.append((stage, image_path))
        if stage == 'chapter' and self.fail_once:
            self.fail_once = False
            raise RuntimeError('Check the local model, then retry.')
        return result


class Narrator:
    def __init__(self):
        self.texts = []

    def narrate(self, text, target):
        self.texts.append(text)
        # Demonstrate a voice failure leaving the chapter readable.
        if len(self.texts) == 2:
            raise RuntimeError('Voice unavailable')
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), 'wb') as audio:
            audio.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
            audio.writeframes(b'\x00\x00' * 20)
        return str(target)


class Persistence:
    def __init__(self, trip, path):
        self.trip, self.path = trip, path
        self.stages = []

    def started(self, stage, photo_id):
        self.stages.append((stage, photo_id))

    def __call__(self, checkpoint):
        self.trip['checkpoints'].append(checkpoint)
        self.path.write_text(json.dumps(self.trip))


def test_staged_trip_failure_retry_and_readable_partial_narration(tmp_path):
    trip = json.loads((FIXTURES / 'trip.json').read_text())
    trip['photos'][0]['metadata']['place_name'] = 'Corrected coast'
    config = load_config()
    model, narrator = Model(), Narrator()
    pipeline = StoryPipeline(config, model=model, narrator=narrator)
    save = Persistence(trip, tmp_path / 'trip.json')
    with pytest.raises(StageFailure) as failure:
        pipeline.run(trip, str(tmp_path), save)
    assert failure.value.stage == 'chapter'
    assert failure.value.photo_id == trip['photos'][0]['id']
    assert [item['stage'] for item in trip['checkpoints']] == ['observe', 'synthesize', 'outline']
    restored = json.loads(save.path.read_text())
    save = Persistence(restored, save.path)
    story = pipeline.run(restored, str(tmp_path), save)
    assert [call[0] for call in model.calls] == ['observe', 'synthesize', 'outline', 'chapter', 'chapter', 'framing', 'day']
    chapter = story['chapters'][0]
    assert chapter['photo_id'] == restored['photos'][0]['id']
    assert chapter['location'] == 'Corrected coast'
    assert chapter['narrative'] == 'We stopped by the coast after lunch.'
    assert narrator.texts == [chapter['narrative'], story['days'][0]['narrative']]
    assert story['narration'] == 'partial'
    assert 'Buenos Aires' not in story['opening']['text']
    assert 'board' not in story['closing']['text']
    assert chapter['audio_path'] is not None
    assert story['days'][0]['audio_path'] is None
    assert len(restored['checkpoints']) == 8
    calls_before = len(model.calls), len(narrator.texts)
    assert pipeline.run(restored, str(tmp_path), save) == story
    assert calls_before == (len(model.calls), len(narrator.texts))
    assert save.stages == [('chapter', restored['photos'][0]['id']), ('framing', None), ('day', None),
                           ('narration', restored['photos'][0]['id']), ('narration', None)]


def test_photo_order_uses_all_comparable_capture_times_otherwise_submission():
    photo = json.loads((FIXTURES / 'photo-input.json').read_text())
    early, late = deepcopy(photo), deepcopy(photo)
    early.update(id='early', submission_order=1)
    late.update(id='late', submission_order=0)
    early['metadata']['captured_at'] = '2026-10-10T10:00:00+02:00'
    late['metadata']['captured_at'] = '2026-10-10T09:00:00+00:00'
    assert [p['id'] for p in ordered_photos([late, early])] == ['early', 'late']
    early['metadata']['captured_at'] = '2026-10-10T10:00:00'
    assert [p['id'] for p in ordered_photos([early, late])] == ['late', 'early']
    early['metadata']['captured_at'] = None
    assert [p['id'] for p in ordered_photos([early, late])] == ['late', 'early']


def test_ollama_transport_encodes_local_image_and_bounded_structured_request(tmp_path, monkeypatch):
    import base64
    import io
    from vacation_story import adapters
    from vacation_story.pipeline import schema_for

    image = tmp_path / 'analysis.jpg'
    image.write_bytes(b'local analysis image')
    config = load_config()['generation']
    response = dict(visible_content='A sandy shore.', uncertainties=[])
    captured = {}

    def local_response(request, timeout):
        captured.update(url=request.full_url, timeout=timeout,
                        payload=json.loads(request.data.decode('utf-8')))
        return io.BytesIO(json.dumps({'message': {'content': json.dumps(response)}}).encode())

    monkeypatch.setattr(adapters, 'urlopen', local_response)
    messages = [{'role': 'system', 'content': 'Observe only visible content.'},
                {'role': 'user', 'content': 'Observe the attached image.'}]
    schema = schema_for('observe')
    result = adapters.OllamaAdapter(config).generate(messages, schema, str(image))
    payload = captured['payload']
    assert result == response
    assert captured['url'] == config['base_url'].rstrip('/') + '/api/chat'
    assert captured['timeout'] == config['timeout_seconds']
    assert payload['think'] is False and payload['stream'] is False
    assert payload['model'] == config['model']
    assert payload['options']['num_ctx'] == config['context_length']
    assert payload['options']['num_predict'] == config['max_output_tokens']
    assert payload['format'] == schema
    assert 'images' not in payload['messages'][0]
    assert payload['messages'][1]['images'] == [base64.b64encode(image.read_bytes()).decode('ascii')]
    assert 'images' not in messages[1]  # Transport must not mutate cached prompt messages.


def test_whole_trip_outline_and_neighbor_context_connect_scenes_in_bounded_batches(tmp_path):
    trip = json.loads((FIXTURES / 'trip.json').read_text())
    original = trip['photos'][0]
    notes = ['We stopped at the shore.', 'We walked along a trail.', 'We shared a meal.']
    trip['photos'] = []
    for index, note in enumerate(notes):
        photo = deepcopy(original)
        photo.update(id=f'photo-{index}', submission_order=index, user_description=note,
                     analysis_image_path=f'photo-{index}.jpg')
        trip['photos'].append(photo)
    config = load_config()
    config['generation']['outline_batch_size'] = 2
    config['narration']['enabled'] = False

    class WholeTripModel:
        def __init__(self):
            self.calls, self.plans, self.scenes = [], [], []

        def generate(self, messages, schema, image_path=None):
            fields = set(schema['required'])
            if 'visible_content' in fields:
                self.calls.append('observe')
                return dict(visible_content='A grounded scene.', uncertainties=[])
            payload = json.loads(messages[-1]['content'])
            if 'grounded_details' in fields:
                self.calls.append('synthesize')
                return dict(summary=payload['user_description'], grounded_details=['A supplied experience.'], uncertainties=[])
            if 'premise' in fields:
                self.calls.append('outline')
                self.plans.append(payload)
                previous = payload['previous_outline']
                premise = (previous['premise'] if previous else '') + ' '.join(item['user_context'] for item in payload['ordered_moments'])
                return dict(premise=premise, thread='Shore, trail, and a meal.', closing_callback='The shore.')
            if 'narrative' in fields:
                self.calls.append('chapter')
                self.scenes.append(payload)
                index = payload['scene_position'] - 1
                assert all(note in payload['trip_outline']['premise'] for note in notes)
                assert payload['scene_count'] == 3
                assert payload['previous_scene'] == (notes[index - 1] if index else None)
                assert (payload['next_moment']['user_context'] if payload['next_moment'] else None) == (notes[index + 1] if index < 2 else None)
                return dict(title=f'Scene {index + 1}', narrative=notes[index], summary=notes[index])
            if 'day_narrative' in fields:
                self.calls.append('day')
                assert len(payload['ordered_memories']) == 3
                return dict(day_title='Undated memories', day_narrative='We remember the shore, the trail, and a shared meal.')
            self.calls.append('framing')
            assert payload['chapter_summaries'] == notes
            assert payload['trip_outline'] == self.scenes[0]['trip_outline']
            return dict(opening='We began at the shore.', closing='We returned to these moments over a shared meal.')

    model = WholeTripModel()
    pipeline = StoryPipeline(config, model=model, narrator=Narrator())
    save = Persistence(trip, tmp_path / 'trip.json')
    story = pipeline.run(trip, str(tmp_path), save)
    assert model.calls == ['observe', 'synthesize'] * 3 + ['outline', 'outline'] + ['chapter'] * 3 + ['framing', 'day']
    assert model.plans[0]['previous_outline'] is None
    assert model.plans[1]['previous_outline']['premise'].startswith(notes[0])
    assert [scene['user_description'] for scene in model.scenes] == notes
    assert all(scene['trip_outline'] == model.scenes[0]['trip_outline'] for scene in model.scenes)
    assert [chapter['photo_id'] for chapter in story['chapters']] == ['photo-0', 'photo-1', 'photo-2']
    assert story['story_style'] == 'connected_journal'
    assert len(trip['checkpoints']) == 17
    before = len(model.calls)
    assert pipeline.run(trip, str(tmp_path), save) == story
    assert len(model.calls) == before
