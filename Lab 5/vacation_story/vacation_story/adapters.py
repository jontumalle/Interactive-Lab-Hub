"""Local-only Ollama transport and Piper WAV adapter."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import wave


class OllamaAdapter:
    def __init__(self, settings: dict):
        self.settings = settings

    def generate(self, messages: list[dict], schema: dict, image_path: str | None = None) -> dict:
        messages = [dict(message) for message in messages]
        if image_path:
            messages[-1]['images'] = [base64.b64encode(Path(image_path).read_bytes()).decode('ascii')]
        settings = self.settings
        payload = dict(model=settings['model'], messages=messages, stream=False, think=False,
                       format=schema, options=dict(num_ctx=settings['context_length'],
                       num_predict=settings['max_output_tokens'], temperature=settings['temperature']))
        request = Request(settings['base_url'].rstrip('/') + '/api/chat',
                          data=json.dumps(payload).encode('utf-8'),
                          headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=settings['timeout_seconds']) as response:
                data = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Ollama returned HTTP {error.code}. Check the local service and installed model, then retry.') from error
        except (URLError, TimeoutError, OSError) as error:
            raise RuntimeError('Ollama could not finish the request. Check the local service and installed model, then retry.') from error
        if data.get('error'):
            raise RuntimeError('Ollama reported an error. Check the local service and installed model, then retry.')
        try:
            return json.loads(data['message']['content'])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError('Ollama returned an invalid JSON response. Retry this stage.') from error


def usable_wav(path: str | Path) -> bool:
    try:
        with wave.open(str(path), 'rb') as audio:
            return audio.getnframes() > 0 and audio.getframerate() > 0
    except (OSError, EOFError, wave.Error):
        return False


class PiperNarrator:
    def __init__(self, settings: dict):
        self.settings = settings

    def narrate(self, text: str, target: Path) -> str:
        settings = self.settings
        voice = Path(settings['voice_path'])
        if not voice.is_file() or not Path(str(voice) + '.json').is_file():
            raise RuntimeError('The configured Piper voice and matching JSON configuration are required.')
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=target.parent, suffix='.wav')
        os.close(descriptor)
        try:
            try:
                subprocess.run([settings['executable'], '--model', str(voice), '--output-file', temporary],
                               input=text, text=True, encoding='utf-8', check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               timeout=settings['timeout_seconds'])
            except FileNotFoundError as error:
                raise RuntimeError('Project Piper is missing. Run bash setup.sh, then retry narration.') from error
            except subprocess.TimeoutExpired as error:
                raise RuntimeError('Piper timed out. Retry narration; increase narration.timeout_seconds if needed.') from error
            except subprocess.CalledProcessError as error:
                detail = (error.stderr or '').strip().splitlines()
                explanation = detail[-1][:500] if detail else f'exit code {error.returncode}'
                raise RuntimeError(f'Piper could not create audio: {explanation}. Retry narration.') from error
            if not usable_wav(temporary):
                raise RuntimeError('Piper did not produce a usable WAV file.')
            os.replace(temporary, target)
            return str(target.resolve())
        finally:
            Path(temporary).unlink(missing_ok=True)
