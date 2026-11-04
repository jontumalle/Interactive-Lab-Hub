"""Resumable local photo-to-story pipeline, independent of Flask and browser URLs."""
from datetime import datetime, timezone
from pathlib import Path
import re

from .adapters import OllamaAdapter, PiperNarrator
from .narration import narrate_story
from .contracts import Pipeline, StageFailure, Story, Trip
from .prompts import load_prompts, messages_for
from .job_steps import outline_batch_size
from .days import group_days

FIELDS = {
    'observe': {'visible_content': 'string', 'uncertainties': 'array'},
    'synthesize': {'summary': 'string', 'grounded_details': 'array', 'uncertainties': 'array'},
    'outline': {'premise': 'string', 'thread': 'string', 'closing_callback': 'string'},
    'chapter': {'title': 'string', 'narrative': 'string', 'summary': 'string'},
    'framing': {'opening': 'string', 'closing': 'string'},
    'day': {'day_title': 'string', 'day_narrative': 'string'},
}


def schema_for(stage: str) -> dict:
    return {'type': 'object', 'properties': {
        name: ({'type': 'string', 'minLength': 1, 'maxLength': 4000} if kind == 'string'
               else {'type': 'array', 'maxItems': 20, 'items': {'type': 'string', 'maxLength': 1000}})
        for name, kind in FIELDS[stage].items()},
        'required': list(FIELDS[stage]), 'additionalProperties': False}


def validate(stage: str, value: dict) -> dict:
    fields = FIELDS[stage]
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f'{stage} returned unexpected fields. Retry this stage.')
    for name, kind in fields.items():
        item = value[name]
        if kind == 'string':
            if not isinstance(item, str) or not item.strip() or len(item) > 4000:
                raise ValueError(f'{stage} returned invalid {name}. Retry this stage.')
        elif not isinstance(item, list) or len(item) > 20 or any(not isinstance(x, str) or len(x) > 1000 for x in item):
            raise ValueError(f'{stage} returned invalid {name}. Retry this stage.')
    return value


def ordered_photos(photos: list[dict]) -> list[dict]:
    submitted = sorted(photos, key=lambda photo: photo['submission_order'])
    try:
        times = [datetime.fromisoformat(photo['metadata']['captured_at']) for photo in submitted]
        if len({stamp.utcoffset() is not None for stamp in times}) > 1:
            return submitted
        comparable = [stamp.astimezone(timezone.utc) if stamp.utcoffset() is not None else stamp for stamp in times]
        return [photo for _, photo in sorted(zip(comparable, submitted), key=lambda item: item[0])]
    except (ValueError, TypeError):
        return submitted


def location_label(metadata: dict) -> str | None:
    if metadata['place_name']:
        return metadata['place_name']
    if metadata['latitude'] is not None and metadata['longitude'] is not None:
        return f"{metadata['latitude']}, {metadata['longitude']}"
    return None


def checkpoint_key(item: dict) -> tuple:
    return (item['stage'], item['photo_id'], item['result'].get('segment') if item['stage'] == 'narration' else (item['result'].get('day_id'), item['result'].get('batch', 0)) if item['stage'] == 'day' else None)


def grounded_framing(framing: dict, title: str, summaries: list[str]) -> dict:
    """Guard new names/numbers while allowing natural connective prose.

    This is a conservative check of specifics, not proof of semantic truth.
    Full-vocabulary overlap previously reduced all new phrasing to captions.
    """
    sources = ' '.join([title, *summaries]).casefold()
    known = set(re.findall(r"[^\W_]+", sources))
    def supported(text):
        if not set(re.findall(r"\d+", text)) <= set(re.findall(r"\d+", sources)):
            return False
        for match in re.finditer(r"\b[A-Z][a-zA-Z’'-]+\b", text):
            prefix = text[:match.start()].rstrip()
            sentence_start = not prefix or prefix.endswith(('.', '!', '?', ':', '\n'))
            if not sentence_start and match.group().casefold() not in known:
                return False
        return True
    if all(supported(framing[key]) for key in ('opening', 'closing')):
        return framing
    return dict(opening=f"{title}. {summaries[0]}",
                closing=f"These are the moments we return to. {summaries[-1]}")


def framing_summaries(summaries, limit=12):
    if len(summaries) <= limit:
        return [summary[:320] for summary in summaries]
    return [summaries[index * (len(summaries) - 1) // (limit - 1)][:320] for index in range(limit)]


class StoryPipeline:
    def __init__(self, config: dict, model=None, narrator=None):
        self.config = config
        self.model = model if model is not None else OllamaAdapter(config['generation'])
        self.narrator = narrator if narrator is not None else PiperNarrator(config['narration'])

    def run(self, trip: Trip, output_dir: str, checkpoint) -> Story:
        try:
            prompts = load_prompts(self.config['generation']['prompts_dir'])
        except (OSError, ValueError) as error:
            raise StageFailure('observe', f'Check the editable prompt files, then retry: {error}') from error
        cache = {checkpoint_key(item): item['result'] for item in trip['checkpoints']}

        def started(stage, photo_id):
            callback = getattr(checkpoint, 'started', None)
            if callback:
                callback(stage, photo_id)

        def persist(stage, photo_id, result):
            item = dict(stage=stage, photo_id=photo_id, result=result)
            checkpoint(item)
            cache[checkpoint_key(item)] = result
            return result

        def generate(stage, photo_id, payload=None, image_path=None):
            key = (stage, photo_id, None)
            if key in cache:
                try:
                    return validate(stage, cache[key])
                except ValueError:
                    pass  # An invalid old checkpoint is recomputed explicitly on retry.
            started(stage, photo_id)
            try:
                result = self.model.generate(messages_for(prompts[stage], payload), schema_for(stage), image_path=image_path)
                result = validate(stage, result)
                if stage == 'framing':
                    result = grounded_framing(result, trip['title'], payload['chapter_summaries'])
            except Exception as error:
                raise StageFailure(stage, str(error) or f'{stage} failed. Check the local model and retry.', photo_id) from error
            return persist(stage, photo_id, result)

        prepared = []
        for photo in ordered_photos(trip['photos']):
            photo_id = photo['id']
            observation = generate('observe', photo_id, image_path=photo['analysis_image_path'])
            synthesis = generate('synthesize', photo_id, dict(observation=observation,
                                 metadata=photo['metadata'], user_description=photo['user_description'], vibes=photo['vibes']))
            prepared.append((photo, synthesis))

        settings = self.config['generation']
        summary_chars = max(80, min(240, int(settings.get('outline_summary_chars', 180))))
        continuity_chars = max(80, min(500, int(settings.get('continuity_summary_chars', 320))))
        batch_size = outline_batch_size(settings)
        outline = None
        for start in range(0, len(prepared), batch_size):
            group = prepared[start:start + batch_size]
            moments = [dict(summary=(photo['user_description'] or synthesis['summary'])[:summary_chars],
                            user_context=photo['user_description'][:summary_chars],
                            place=(photo['metadata']['place_name'] or '')[:80],
                            time=photo['metadata']['captured_at']) for photo, synthesis in group]
            outline = generate('outline', group[-1][0]['id'], dict(trip_title=trip['title'],
                               previous_outline=outline, ordered_moments=moments))
            outline = {key: value[:600] for key, value in outline.items()}

        chapters, summaries = [], []
        for index, (photo, synthesis) in enumerate(prepared):
            next_moment = None
            if index + 1 < len(prepared):
                following, next_synthesis = prepared[index + 1]
                next_moment = dict(summary=(following['user_description'] or next_synthesis['summary'])[:summary_chars],
                                   user_context=following['user_description'][:summary_chars],
                                   place=(following['metadata']['place_name'] or '')[:80])
            scene_facts = dict(summary=(photo['user_description'] or synthesis['summary'])[:600],
                               grounded_details=[detail[:180] for detail in synthesis['grounded_details'][:2]],
                               uncertainties=[detail[:140] for detail in synthesis['uncertainties'][:3]])
            generated = generate('chapter', photo['id'], dict(trip_title=trip['title'], trip_outline=outline,
                                 scene_position=index + 1, scene_count=len(prepared),
                                 previous_scene=summaries[-1][:continuity_chars] if summaries else None,
                                 next_moment=next_moment, synthesis=scene_facts, vibes=photo['vibes'],
                                 metadata=photo['metadata'], user_description=photo['user_description']))
            chapters.append(dict(photo_id=photo['id'], title=generated['title'], narrative=generated['narrative'],
                                 location=location_label(photo['metadata']), time=photo['metadata']['captured_at'], audio_path=None))
            summaries.append(photo['user_description'][:continuity_chars] or generated['summary'])
        framing = generate('framing', None, dict(trip_title=trip['title'], trip_outline=outline,
                                                chapter_summaries=framing_summaries(summaries)))
        story: Story = dict(title=trip['title'], opening=dict(text=framing['opening'], audio_path=None),
                            chapters=chapters, closing=dict(text=framing['closing'], audio_path=None),
                            narration='unavailable', story_style='connected_journal')
        story = self.add_days(trip, story, checkpoint, cache, prompts)
        return narrate_story(story, output_dir, checkpoint, self.config['narration'], self.narrator, cache)

    def add_days(self, trip, story, checkpoint, cache=None, prompts=None):
        cache = cache or {}
        prompts = prompts if prompts is not None else load_prompts(self.config['generation']['prompts_dir'])
        by_photo = {photo['id']: photo for photo in trip['photos']}
        by_moment = {moment['photo_id']: moment for moment in story['chapters']}
        days = []
        for group in group_days(story['chapters'], trip['photos']):
            ids = group['moment_ids']
            result = None
            for batch, start in enumerate(range(0, len(ids), 12)):
                key = ('day', None, (group['id'], batch))
                previous = cache.get(key)
                cached = None
                if previous:
                    try:
                        cached = validate('day', {name: previous[name] for name in FIELDS['day']})
                    except (ValueError, KeyError):
                        pass
                if cached is not None:
                    result = cached
                    continue
                started = getattr(checkpoint, 'started', None)
                if started:
                    started('day', None)
                selected = ids[start:start + 12]
                memories = [dict(owner_note=by_photo[photo_id]['user_description'][:240],
                                 place=by_photo[photo_id]['metadata']['place_name'],
                                 moment=by_moment[photo_id]['narrative'][:240]) for photo_id in selected]
                payload = dict(trip_title=trip['title'], date=group['date'],
                               moment_count=len(ids), previous_day_story=result,
                               ordered_memories=memories)
                try:
                    result = validate('day', self.model.generate(messages_for(prompts['day'], payload), schema_for('day')))
                except Exception as error:
                    raise StageFailure('day', str(error) or 'The day story failed. Retry to finish it.') from error
                checkpoint(dict(stage='day', photo_id=None, result=dict(result, day_id=group['id'], batch=batch)))
            days.append(dict(group, title=result['day_title'], narrative=result['day_narrative'], audio_path=None))
        story['days'] = days
        story['journey_version'] = 2
        return story

    def upgrade_days(self, trip: Trip, output_dir: str, checkpoint) -> Story:
        from copy import deepcopy
        if not trip.get('story'):
            raise StageFailure('day', 'Create the story before preparing its days.')
        cache = {checkpoint_key(item): item['result'] for item in trip['checkpoints']}
        story = self.add_days(trip, deepcopy(trip['story']), checkpoint, cache)
        return narrate_story(story, output_dir, checkpoint, self.config['narration'], self.narrator, cache)

    def repair_narration(self, trip: Trip, output_dir: str, checkpoint) -> Story:
        if not trip.get('story'):
            raise StageFailure('narration', 'Create the story before retrying narration.')
        cache = {checkpoint_key(item): item['result'] for item in trip['checkpoints']}
        return narrate_story(trip['story'], output_dir, checkpoint, self.config['narration'],
                             self.narrator, cache, retry_unavailable=True)



def build_pipeline(config: dict) -> StoryPipeline:
    return StoryPipeline(config)


class FakePipeline:
    """Small development adapter, deliberately independent of real pipeline stages."""
    def run(self, trip: Trip, output_dir: str, checkpoint) -> Story:
        chapters = []
        for photo in sorted(trip['photos'], key=lambda item: item['submission_order']):
            chapter = dict(photo_id=photo['id'], title=f'Moment {len(chapters) + 1}',
                           narrative=photo['user_description'] or 'A moment from our trip.',
                           location=location_label(photo['metadata']), time=photo['metadata']['captured_at'], audio_path=None)
            checkpoint(dict(stage='chapter', photo_id=photo['id'], result=chapter))
            chapters.append(chapter)
        days = [dict(group, title=group['date'] or 'Undated memories',
                     narrative=' '.join(next(chapter['narrative'] for chapter in chapters if chapter['photo_id'] == photo_id) for photo_id in group['moment_ids']),
                     audio_path=None) for group in group_days(chapters, trip['photos'])]
        return dict(title=trip['title'], opening=dict(text='A demo journey in photos.', audio_path=None),
                    chapters=chapters, closing=dict(text='Memories to return to.', audio_path=None), narration='unavailable',
                    story_style='connected_journal', journey_version=2, days=days)


fake_pipeline: Pipeline = FakePipeline()
