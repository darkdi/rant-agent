"""Explicitly register or download the optional built-in Qwen model."""
import argparse
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = 'mlx-community/Qwen3.5-9B-4bit'


def validate(path):
    if not (path / 'config.json').is_file() or not (path / 'tokenizer_config.json').is_file():
        raise ValueError('The folder must contain config.json and tokenizer_config.json.')
    index = path / 'model.safetensors.index.json'
    weights = set(json.loads(index.read_text()).get('weight_map', {}).values()) if index.exists() else {p.name for p in path.glob('*.safetensors')}
    if not weights or any(not (path / name).resolve().is_relative_to(path) or not (path / name).is_file() for name in weights):
        raise ValueError('Some model weights are missing. Finish the download first.')


def main():
    parser = argparse.ArgumentParser(description='Configure Qwen3.5-9B-4bit for Apple Silicon. Downloads only with --download.')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--path', type=Path, help='Use an existing MLX Qwen3.5-9B-4bit folder.')
    source.add_argument('--download', action='store_true', help='Download several GB from Hugging Face.')
    parser.add_argument('--directory', type=Path, default=Path.home() / 'Models/Qwen3.5-9B-4bit')
    parser.add_argument('--replace', action='store_true', help='Replace existing local model settings.')
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        parser.exit(1, 'Built-in MLX requires Apple Silicon. Use Ollama or an API on other computers.\n')
    config = ROOT / 'local-assistant/model-9b.json'
    if config.exists() and not args.replace:
        parser.exit(1, 'Model settings already exist. Use --replace to change the configured model.\n')
    path = (args.path or args.directory).expanduser().resolve()
    if args.download:
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            parser.exit(1, 'First run .venv/bin/pip install -r requirements-mlx.txt\n')
        print(f'Downloading {REPO} to {path}. Model license: Apache-2.0.', flush=True)
        snapshot_download(REPO, local_dir=path, allow_patterns=['*.json', '*.safetensors', '*.txt', '*.jinja', '*.model', 'README.md', 'LICENSE*'])
    validate(path)
    config.write_text(json.dumps({'path': str(path), 'repo': REPO, 'revision': 'local'}, indent=2) + '\n')
    config.chmod(0o600)
    print('Model configured. Install requirements-mlx.txt, then restart Rant. The first message loads the weights.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
