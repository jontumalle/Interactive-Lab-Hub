"""One daemon worker per application; status/checkpoints outlive the browser."""
from copy import deepcopy
import logging
from queue import Queue
from threading import Thread

from .contracts import StageFailure
from .adapters import usable_wav
from .days import daily_story_complete
from .narration import segments

log = logging.getLogger(__name__)


def checkpoint_key(checkpoint):
    return (checkpoint['stage'], checkpoint['photo_id'],
            checkpoint['result'].get('segment') if checkpoint['stage'] == 'narration' else (checkpoint['result'].get('day_id'), checkpoint['result'].get('batch', 0)) if checkpoint['stage'] == 'day' else None)


def prepare_narration_retry(trip):
    trip['job_kind'] = 'narration'
    active = {(segment, photo_id) for segment, photo_id, _, _ in segments(trip['story'])}
    trip['checkpoints'] = [item for item in trip['checkpoints'] if item['stage'] != 'narration'
        or ((item['result'].get('segment'), item['photo_id']) in active
            and item['result'].get('available') and isinstance(item['result'].get('audio_path'), str)
            and usable_wav(item['result']['audio_path']))]
    trip['status'].update(state='queued', current_stage='narration', error=None,
                          completed=len(trip['checkpoints']),
                          total=max(trip['status']['total'], sum(item['stage'] != 'narration' for item in trip['checkpoints']) + sum(1 for _ in segments(trip['story']))))


class JobWorker:
    def __init__(self, store, pipeline, recover_interrupted=True):
        self.store = store
        self.pipeline = pipeline
        self.queue = Queue()
        with store.lock:
            for trip in store.list():
                if recover_interrupted and trip['status']['state'] in ('queued', 'processing'):
                    trip['status'].update(state='failed', error=dict(
                        stage=trip['status']['current_stage'], photo_id=None,
                        message='Processing was interrupted. Retry to reuse completed stages.', retryable=True))
                    store.save(trip)
        self.thread = None

    def enqueue(self, trip_id):
        # Called while the store lock is held after queued state has been persisted.
        if self.thread is None:
            self.thread = Thread(target=self._loop, name='vacation-story-worker', daemon=True)
            self.thread.start()
        self.queue.put(trip_id)

    def _loop(self):
        while True:
            trip_id = self.queue.get()
            try:
                if trip_id is None:
                    return
                self._process(trip_id)
            finally:
                self.queue.task_done()

    def close(self):
        if self.thread is not None:
            self.queue.put(None)
            self.thread.join(timeout=2)

    def _process(self, trip_id):
        store = self.store
        with store.lock:
            trip = store.get(trip_id)
            trip['status'].update(state='processing', error=None)
            store.save(trip)
            snapshot = deepcopy(trip)

        class Persist:
            def started(self, stage, photo_id=None):
                with store.lock:
                    record = store.get(trip_id)
                    record['status']['current_stage'] = stage
                    store.save(record)

            def __call__(self, checkpoint):
                with store.lock:
                    record = store.get(trip_id)
                    key = checkpoint_key(checkpoint)
                    record['checkpoints'] = [item for item in record['checkpoints'] if checkpoint_key(item) != key]
                    record['checkpoints'].append(checkpoint)
                    record['status'].update(current_stage=checkpoint['stage'], completed=len(record['checkpoints']))
                    store.save(record)

        try:
            method = self.pipeline.repair_narration if snapshot.get('job_kind') == 'narration' else self.pipeline.upgrade_days if snapshot.get('job_kind') == 'days' else self.pipeline.run
            output = store.directory(trip_id)
            if snapshot.get('edition_id'):
                output = output / 'editions' / snapshot['edition_id']
            story = method(snapshot, str(output), Persist())
            if not daily_story_complete(story):
                raise StageFailure('chapter', 'The connected story could not be completed. Retry to finish your story.')
            with store.lock:
                trip = store.get(trip_id)
                trip['story'] = story
                trip['status'].update(state='ready', current_stage=None, completed=trip['status']['total'], error=None)
                store.save(trip)
        except Exception as error:
            log.exception('Trip processing failed: %s', trip_id)
            with store.lock:
                trip = store.get(trip_id)
                stage = error.stage if isinstance(error, StageFailure) else trip['status']['current_stage']
                message = str(error) if isinstance(error, StageFailure) else 'Processing failed. Check the server log, then retry.'
                trip['status'].update(state='failed', current_stage=stage, error=dict(stage=stage,
                    photo_id=getattr(error, 'photo_id', None), message=message, retryable=True))
                store.save(trip)
