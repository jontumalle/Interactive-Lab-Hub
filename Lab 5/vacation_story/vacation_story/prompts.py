"""Read editable model instructions once at the start of every job."""
import json
from pathlib import Path
from string import Template

STAGES = ('observe', 'synthesize', 'outline', 'chapter', 'framing', 'day')


def load_prompts(directory: str) -> dict[str, tuple[str, str]]:
    prompts = {}
    for stage in STAGES:
        content = (Path(directory) / f'{stage}.txt').read_text(encoding='utf-8')
        if not content.startswith('SYSTEM\n') or content.count('\nUSER\n') != 1:
            raise ValueError(f'{stage}.txt must contain standalone SYSTEM and USER sections.')
        system, user = content[len('SYSTEM\n'):].split('\nUSER\n')
        if not system.strip() or not user.strip():
            raise ValueError(f'{stage}.txt has an empty instruction section.')
        prompts[stage] = (system.strip(), user.strip())
    return prompts


def messages_for(prompt: tuple[str, str], payload: dict | None = None) -> list[dict]:
    system, user = prompt
    if payload is not None:
        user = Template(user).substitute(input_json=json.dumps(payload, ensure_ascii=False))
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
