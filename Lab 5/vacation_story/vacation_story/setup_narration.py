"""Explicit online setup; startup and jobs never download voice dependencies."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .config import PROJECT_ROOT, load_config
from .narration import check_narration, setup_problem


def main():
    settings = load_config()['narration']
    if not settings['enabled']:
        print('Narration is explicitly disabled; voice setup skipped.')
        return
    voice = Path(settings['voice_path'])
    voice.resolve().relative_to(PROJECT_ROOT)
    voice.parent.mkdir(parents=True, exist_ok=True)
    if setup_problem(settings):
        # Download both files together, then publish only after the command succeeds.
        with tempfile.TemporaryDirectory(prefix='download-', dir=voice.parent) as temporary:
            subprocess.run([sys.executable, '-m', 'piper.download_voices', voice.stem,
                            '--download-dir', temporary], check=True)
            for suffix in ('', '.json'):
                downloaded = Path(temporary) / (voice.name + suffix)
                if not downloaded.is_file() or not downloaded.stat().st_size:
                    raise RuntimeError('Voice setup did not produce both required files.')
            for suffix in ('', '.json'):
                os.replace(Path(temporary) / (voice.name + suffix), Path(str(voice) + suffix))
    check_narration(settings, smoke=True)
    print('Project-local Piper and English voice verified with real speech synthesis.')


if __name__ == '__main__':
    main()
