"""Exercise actual map renderer with stubbed local Leaflet/DOM, no tile network."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_day_map_renderer_and_two_playback_levels():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is not installed')
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run([node, str(root / 'tests/fixtures/day-map-harness.js'), str(root)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
