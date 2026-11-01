/* Browser-only integration check against synthetic API responses. */
(async () => {
  const result = document.createElement('pre'); result.id = 'test-result'; document.body.append(result);
  const $ = id => document.getElementById(id);
  const assert = (value, message) => { if (!value) throw new Error(message); };
  async function until(condition, label) {
    for (let i = 0; i < 200; i++) {
      if (condition()) return;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    throw new Error(`Timed out: ${label}`);
  }
  const submit = id => $(id).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  try {
    await until(() => $('trips').textContent.includes('Your next trip'), 'home');
    $('title').value = 'Weekend <img src=x onerror=alert(1)>';
    submit('create-trip');
    await until(() => !$('trip-view').hidden && !$('upload-form').hidden, 'create trip');
    assert($('trip-title').children.length === 0, 'Trip title must remain plain text');
    const transfer = new DataTransfer();
    transfer.items.add(new File(['fixture'], 'coast.jpg', { type: 'image/jpeg' }));
    transfer.items.add(new File(['fixture2'], 'coast-again.jpg', { type: 'image/jpeg' }));
    assert($('photo-file').multiple, 'Picker permits bulk selection');
    $('photo-file').files = transfer.files;
    submit('upload-form');
    await until(() => !$('photo-editor').hidden, 'photo editor');
    assert(window.fixtureState.uploads === 2, 'Both selected photos uploaded before review');
    assert($('upload-summary').textContent.includes('2 of 2'), 'Batch result displayed');
    assert($('metadata-captured_at').closest('#missing-fields'), 'Missing capture time is requested');
    assert($('metadata-place_name').closest('#correction-fields'), 'Existing place is editable without repeating the question');
    $('description').value = 'We stopped after lunch.';
    const choices = [...document.querySelectorAll('input[name=vibes]')];
    assert(choices.length === 6, 'Exactly six vibe choices');
    choices[0].checked = true; choices[5].checked = true;
    submit('photo-answers');
    await until(() => !$('saved-confirmation').hidden, 'save confirmation');
    assert(window.fixtureState.patch.vibes.join(',') === 'Relaxed,Awe-inspiring', 'Multiple vibes saved');
    assert(window.fixtureState.patch.user_description === 'We stopped after lunch.', 'Context saved');
    $('review-next').click();
    await until(() => !$('photo-editor').hidden, 'review second photo');
    assert($('description').value === '', 'Each photo keeps its own answers');
    $('description').value = 'A second stop.';
    submit('photo-answers');
    await until(() => !$('saved-confirmation').hidden, 'save second photo');
    assert($('review-next').hidden, 'Last photo completes batch review');
    $('add-another').click();
    assert(!$('upload-form').hidden, 'Add another returns to upload');
    $('finish-collection').click();
    await until(() => !$('progress-view').hidden, 'processing view');
    assert($('progress-count').textContent.includes('1 of 12'), 'Progress count displayed');
    // Reopening the hash fetches persisted progress, without starting another job.
    location.hash = '';
    await until(() => !$('home-view').hidden && $('trips').textContent.includes('Weekend'), 'home after close');
    location.hash = `trip=${window.fixtureState.trip.id}`;
    await until(() => !$('progress-view').hidden, 'reopened progress');
    window.fixtureState.ready = true;
    $('check-progress').click();
    await until(() => !$('story-view').hidden, 'ready story');
    assert(window.fixtureState.playCount === 0, 'Narration never starts without gesture');
    assert($('journey-title').children.length === 0, 'Journey title remains plain text');
    assert($('day-list').querySelectorAll('button').length === 1, 'One undated day group is shown honestly');
    assert($('day-moments').querySelectorAll('button').length === 2, 'Both photographs remain accessible');
    assert(!$('map-unavailable').hidden, 'No-GPS fixture has a truthful map fallback without tile requests');
    assert(!$('rewrite-story'), 'Only the finished story is offered');
    $('listen-journey').click();
    await until(() => !$('pause-trip').hidden, 'day narration begins');
    assert($('narration').getAttribute('src') === '/fixture-day.wav', 'Overview uses one day WAV');
    $('pause-trip').click();
    assert($('pause-trip').hidden, 'Pause stops playback');
    $('day-moments').querySelectorAll('button')[1].click();
    assert(!$('moment-panel').hidden && $('moment-narrative').textContent === 'A second stop.', 'Thumbnail opens its own moment');
    assert($('narration').getAttribute('src') === '/fixture-chapter.wav', 'Moment has separate narration');
    $('back-to-day').click();
    assert($('moment-panel').hidden && $('pause-trip').hidden, 'Back returns to the day without autoplay');
    assert($('day-narrative').textContent === 'The day overview tells the memories together.', 'Day narrative stays distinct');
    const playCount = window.fixtureState.playCount;
    window.fixtureState.connected = false;
    window.fixtureState.trip.requires_processing = true;
    window.fixtureState.trip.status = { state: 'ready', current_stage: null, completed: 11, total: 11, error: null };
    location.hash = '';
    await until(() => !$('home-view').hidden, 'home before opening older trip');
    location.hash = `trip=${window.fixtureState.trip.id}`;
    await until(() => !$('progress-view').hidden, 'older trip automatically finishes its story');
    assert(window.fixtureState.preparations === 1 && $('story-view').hidden, 'Intermediate captions remain hidden during preparation');
    window.fixtureState.ready = true;
    $('check-progress').click();
    await until(() => !$('story-view').hidden, 'finished connected story');
    assert(!$('rewrite-story'), 'No separate rewriting action is required');
    assert(window.fixtureState.playCount === playCount, 'Finished journal never starts narration automatically');
    result.textContent = 'PASS: bulk collection, connected journal, itinerary, narration, automatic finalization, and fallback';
  } catch (error) { result.textContent = `FAIL: ${error.stack || error.message}`; }
})();
