"""Narration readiness and repair, independent of model generation."""
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import tempfile

from .adapters import PiperNarrator, usable_wav
from .config import PROJECT_ROOT

log = logging.getLogger(__name__)


def setup_problem(settings: dict) -> str | None:
    if not settings['enabled']:
        return None
    executable = Path(settings['executable'])
    voice = Path(settings['voice_path'])
    for label, path in (('Piper executable', executable), ('English voice', voice)):
        try:
            path.resolve().relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            return f'{label} must be inside this project. Run bash setup.sh.'
        if not path.is_file():
            return f'{label} is missing. Run bash setup.sh from the project folder.'
    if not os.access(executable, os.X_OK):
        return 'The project Piper executable cannot run. Run bash setup.sh.'
    try:
        configuration = json.loads(Path(str(voice) + '.json').read_text(encoding='utf-8'))
        if not isinstance(configuration, dict) or not configuration.get('audio', {}).get('sample_rate'):
            raise ValueError('Invalid voice configuration')
    except (OSError, ValueError, TypeError, AttributeError):
        return 'The voice JSON configuration is missing or invalid. Run bash setup.sh.'
    return None


def check_narration(settings: dict, smoke: bool = False) -> None:
    problem = setup_problem(settings)
    if problem:
        raise RuntimeError(problem)
    if smoke and settings['enabled']:
        # Real synthesis catches broken native/runtime dependencies before serving.
        with tempfile.TemporaryDirectory(prefix='voice-check-', dir=Path(settings['voice_path']).parent) as directory:
            PiperNarrator(settings).narrate('Ready.', Path(directory) / 'ready.wav')


def segments(story):
    if story.get('journey_version') != 2:
        yield 'opening', None, story['opening'], 'text'
    for moment in story['chapters']:
        yield 'chapter', moment['photo_id'], moment, 'narrative'
    if story.get('journey_version') != 2:
        yield 'closing', None, story['closing'], 'text'
    for day in story.get('days', []):
        yield f"day:{day['id']}", None, day, 'narrative'


def narrate_story(story, output_dir, checkpoint, settings, narrator, cache=None, retry_unavailable=False):
    story = deepcopy(story)
    cache = cache or {}
    available = 0
    problem = setup_problem(settings) if isinstance(narrator, PiperNarrator) else None
    for index, (segment, photo_id, record, text_key) in enumerate(segments(story)):
        key = ('narration', photo_id, segment)
        previous = cache.get(key)
        result = None
        if isinstance(previous, dict) and isinstance(previous.get('available'), bool):
            if previous['available'] and isinstance(previous.get('audio_path'), str) and usable_wav(previous['audio_path']):
                result = previous
            elif not previous['available'] and not retry_unavailable and previous.get('audio_path') is None:
                result = previous
        if result is None:
            started = getattr(checkpoint, 'started', None)
            if started:
                started('narration', photo_id)
            audio_path = None
            error_message = None
            if not settings['enabled']:
                error_message = 'Narration is disabled in configuration.'
            else:
                try:
                    if problem:
                        raise RuntimeError(problem)
                    audio_path = narrator.narrate(record[text_key], Path(output_dir) / 'narration' / f'{index:04d}-{segment.replace(":", "-")}.wav')
                except Exception as error:
                    error_message = str(error) or 'Narration failed. Check the server log and retry narration.'
                    log.warning('Narration failed for %s/%s: %s', segment, photo_id, error_message)
            result = dict(segment=segment, audio_path=audio_path, available=audio_path is not None, error=error_message)
            checkpoint(dict(stage='narration', photo_id=photo_id, result=result))
        record['audio_path'] = result.get('audio_path')
        record['audio_error'] = result.get('error') if not result['available'] else None
        if not result['available'] and not record['audio_error']:
            record['audio_error'] = 'Narration was not generated. Retry narration to create this audio.'
        available += int(result['available'])
    count = sum(1 for _ in segments(story))
    story['narration'] = 'available' if available == count else ('partial' if available else 'unavailable')
    return story
