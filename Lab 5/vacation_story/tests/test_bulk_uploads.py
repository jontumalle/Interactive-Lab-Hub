"""Exercise the browser's serial batch transport without Chromium or model calls."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_bulk_uploads_preserve_successes_retry_failures_and_stop_after_navigation():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is unavailable for the batch transport check')
    source = Path(__file__).resolve().parent.parent / 'vacation_story/static/uploads.js'
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const { uploadBatch } = context.window.VacationUploads;
(async () => {
  const files = ['first.jpg', 'bad.heic', 'last.jpg'].map(name => ({ name }));
  const requests = [], saved = [], progress = [];
  let active = 0, peak = 0;
  const result = await uploadBatch(files, {
    isCurrent: () => true,
    onProgress: state => progress.push(`${state.index}/${state.total}`),
    onPhoto: photo => saved.push(photo.id),
    submit: async file => {
      requests.push(file.name);
      peak = Math.max(peak, ++active);
      await Promise.resolve();
      active--;
      if (file.name === 'bad.heic') throw new Error('Unsupported image');
      return { id: file.name };
    },
  });
  assert.equal(peak, 1);
  assert.deepEqual(requests, ['first.jpg', 'bad.heic', 'last.jpg']);
  assert.deepEqual(saved, ['first.jpg', 'last.jpg']);
  assert.deepEqual(progress, ['1/3', '2/3', '3/3']);
  assert.equal(result.failures[0].file, files[1]);
  assert.equal(result.failures[0].message, 'Unsupported image');
  const retried = [];
  const retry = await uploadBatch(result.failures.map(item => item.file), {
    isCurrent: () => true, onProgress() {}, onPhoto() {},
    submit: async file => { retried.push(file.name); return { id: file.name }; },
  });
  assert.deepEqual(retried, ['bad.heic']);
  assert.equal(retry.failures.length, 0);
  assert.equal(retry.uploaded.length, 1);
  let current = true, count = 0;
  const cancelled = await uploadBatch(files, {
    isCurrent: () => current, onProgress() {},
    onPhoto() { throw new Error('Must not change the newly selected trip'); },
    submit: async file => { count++; current = false; return { id: file.name }; },
  });
  assert.equal(cancelled.cancelled, true);
  assert.equal(count, 1);
  console.log('Batch upload, partial failure/retry, serial order and navigation checks passed.');
})().catch(error => { console.error(error); process.exit(1); });
'''
    result = subprocess.run([node, '-e', script, str(source)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
