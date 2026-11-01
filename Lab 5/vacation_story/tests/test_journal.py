"""Check continuous journey associations without a browser or generated wording."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_journal_scene_model_keeps_the_whole_trip_and_audio_associations():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is unavailable for the journal view-model check')
    source = Path(__file__).resolve().parent.parent / 'vacation_story/static/journal.js'
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const story = {
 title: 'Our <weekend>', opening: {text: 'We began by the shore.', audio_url: '/opening.wav'},
 chapters: [
  {photo_id: 'one', title: 'Along the shore', narrative: 'We stopped after lunch.', location: 'Coast', time: '2026-10-30T13:00:00', photo_url: '/one.jpg', audio_url: '/one.wav'},
  {photo_id: 'two', title: 'A change of pace', narrative: 'The next stop was our picnic.', location: 'Park', time: null, photo_url: '/two.jpg', audio_url: null, audio_error: 'Voice unavailable'},
  {photo_id: 'three', title: 'Looking out', narrative: 'We returned to the water.', location: null, time: null, photo_url: '/three.jpg', audio_url: '/three.wav'}
 ], closing: {text: 'The shore frames our day.', audio_url: '/closing.wav'}, narration: 'partial'
};
const original = JSON.stringify(story);
const scenes = context.window.VacationJournal.scenes(story);
assert.equal(scenes.length, 5);
assert.equal(scenes[0].kind, 'opening');
assert.equal(scenes[0].photo_url, '/one.jpg');
assert.equal(scenes[0].title, 'Our <weekend>');
assert.equal(scenes[1].photo_id, 'one');
assert.equal(scenes[2].photo_id, 'two');
assert.equal(scenes[3].photo_id, 'three');
assert.equal(scenes[2].audio_error, 'Voice unavailable');
assert.equal(scenes[2].location, 'Park');
assert.equal(scenes[3].location, null);
assert.equal(scenes[4].kind, 'closing');
assert.equal(scenes[4].text, story.closing.text);
assert.equal(JSON.stringify(story), original);
console.log('The full ordered journey, original photos, metadata, and audio remain associated.');
'''
    result = subprocess.run([node, '-e', script, str(source)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
