"""Bounded outline planning and progress share a single stage-count contract."""
from math import ceil
from .days import day_count, day_generation_count


def outline_batch_size(settings):
    return max(1, min(12, int(settings.get('outline_batch_size', 12))))


def story_step_count(photos, settings):
    count = photos if isinstance(photos, int) else len(photos)
    days = 0 if isinstance(photos, int) else day_count(photos)
    return 4 * count + 1 + ceil(count / outline_batch_size(settings)) + (0 if isinstance(photos, int) else day_generation_count(photos)) + days
