"""Application-owned day grouping; models never infer dates or photo associations."""
from datetime import datetime


def capture_day(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        # Use the date recorded by the camera/user, retaining its timezone context.
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return None


def group_days(moments, photos):
    by_photo = {photo['id']: photo for photo in photos}
    groups = {}
    for moment in moments:
        photo = by_photo.get(moment['photo_id'])
        date = capture_day(photo['metadata'].get('captured_at')) if photo else capture_day(moment.get('time'))
        day_id = f'day-{date}' if date else 'undated'
        if day_id not in groups:
            groups[day_id] = dict(id=day_id, date=date, moment_ids=[])
        groups[day_id]['moment_ids'].append(moment['photo_id'])
    # Keep day order from the published moment order, but never pretend undated
    # photographs belong to an adjacent known day.
    return [group for key, group in groups.items() if key != 'undated'] + ([groups['undated']] if 'undated' in groups else [])


def day_count(photos):
    return len({capture_day(photo['metadata'].get('captured_at')) for photo in photos})


def daily_story_complete(story):
    if not story or story.get('story_style') != 'connected_journal' or story.get('journey_version') != 2:
        return False
    moments = story.get('chapters', [])
    assigned = [photo_id for day in story.get('days', []) for photo_id in day.get('moment_ids', [])]
    expected = [moment['photo_id'] for moment in moments]
    return bool(moments and story.get('days')) and len(assigned) == len(set(assigned)) and set(assigned) == set(expected)


def day_generation_count(photos, batch_size=12):
    from math import ceil
    counts = {}
    for photo in photos:
        key = capture_day(photo['metadata'].get('captured_at'))
        counts[key] = counts.get(key, 0) + 1
    return sum(ceil(count / batch_size) for count in counts.values())
