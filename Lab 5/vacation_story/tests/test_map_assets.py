"""Mapping code/icons are project-local even though street tiles are online."""
import re

from vacation_story import create_app
from vacation_story.config import load_config
from vacation_story.pipeline import FakePipeline


def test_leaflet_is_served_locally_with_its_css_images(tmp_path):
    config = load_config()
    config['storage']['runtime_dir'] = str(tmp_path)
    client = create_app(config, pipeline=FakePipeline()).test_client()
    page = client.get('/')
    assert page.status_code == 200
    assert b'/static/vendor/leaflet/leaflet.js' in page.data
    assert b'/static/vendor/leaflet/leaflet.css' in page.data
    assert b'https://unpkg.com' not in page.data
    base = '/static/vendor/leaflet/'
    assert client.get(base + 'leaflet.js').status_code == 200
    css = client.get(base + 'leaflet.css')
    assert css.status_code == 200
    for name in re.findall(r'url\((images/[^)]+)\)', css.data.decode()):
        image = client.get(base + name)
        assert image.status_code == 200
        assert image.data.startswith(b'\x89PNG')
    assert client.get(base + 'LICENSE.txt').status_code == 200
