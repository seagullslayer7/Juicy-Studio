"""Build versioned Windows installer, portable ZIP, source ZIP and checksums."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VERSION = json.loads((ROOT/'release-manifest.json').read_text(encoding='utf-8'))['version']
PAYLOAD_FILES = [
    'config.json',
    'banned_words.txt',
    'banned_phrases.txt',
    'beep.mp3',
    'release-manifest.json',
    'LICENSE',
    'README.md',
    'THIRD-PARTY.md',
    'RELEASE-NOTES.md',
    'JuicyStudio.py',
    'src/JuicyCensorApp.py',
    'src/appearance.py',
    'src/audio_timeline.py',
    'src/audio_waveform.py',
    'src/autocensor.py',
    'src/bootstrap.py',
    'src/editor_project.py',
    'src/editor_ui.py',
    'src/editor_worker.py',
    'src/enhance_cuda.py',
    'src/enhance_face_network.py',
    'src/enhance_framerate.py',
    'src/enhance_networks.py',
    'src/enhance_people.py',
    'src/enhance_quality.py',
    'src/enhance_resolution.py',
    'src/enhance_swinir_network.py',
    'src/enhance_texture.py',
    'src/enhance_ui.py',
    'src/enhance_worker.py',
    'src/help_ui.py',
    'src/install_runtime.py',
    'src/languages.py',
    'src/maintenance_ui.py',
    'src/model_download.py',
    'src/playback_controls.py',
    'src/processing_time.py',
    'src/project_browser.py',
    'src/project_library.py',
    'src/project_session.py',
    'src/runtime_paths.py',
    'src/setup_verify.py',
    'src/setup_wizard.py',
    'src/storage_cleanup.py',
    'src/subtitle_document.py',
    'src/subtitle_encoding.py',
    'src/subtitle_ui.py',
    'src/subtitle_worker.py',
    'src/transcription.py',
    'src/translation.py',
    'src/ui_icons.py',
    'src/video_encoding.py',
    'src/worker.py',
    'src/app_paths.py',
]
PAYLOAD_DIRS = ['assets', 'licenses', 'vendor_wheels', 'bootstrap-tools', 'docs', 'requirements']
SOURCE_EXTRA = ['scripts/JuicyStudio.spec', 'scripts/build_release.py', '.gitignore']

def copy_files(names, destination):
    for name in names:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)


def zip_folder(folder, output, prefix):
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in sorted(folder.rglob('*')):
            private = {'logs', 'cache', 'runtime', 'venv', 'models', 'projects', 'outputs', '.git', 'runtime.local.json', 'appearance.json'}
            if item.is_file() and item.relative_to(folder).parts[0] not in private:
                archive.write(item, str(Path(prefix) / item.relative_to(folder)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiled', type=Path, help='Existing PyInstaller output folder; omit to build')
    parser.add_argument('--iscc', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'release')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    compiled = args.compiled
    if not compiled:
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', str(ROOT/'scripts/JuicyStudio.spec')], cwd=ROOT, check=True)
        compiled = ROOT / 'dist/JuicyStudio'
    payload = output / f'JuicyStudio-{VERSION}-Windows-x64'
    if payload.exists():
        raise SystemExit('Use an empty release output folder to avoid carrying stale files into a release.')
    shutil.copytree(compiled, payload)
    copy_files(PAYLOAD_FILES, payload)
    for name in PAYLOAD_DIRS:
        shutil.copytree(ROOT / name, payload / name)
    # This allowlist intentionally excludes environments, models, caches, local
    # overrides, personal exports, Git metadata and build files.
    zip_folder(payload, output/f'JuicyStudio-{VERSION}-Windows-x64-Portable.zip', payload.name)
    source = output / f'JuicyStudio-{VERSION}-Source'
    source.mkdir()
    copy_files(PAYLOAD_FILES + SOURCE_EXTRA, source)
    for name in PAYLOAD_DIRS + ['installer', 'tests', '.github']:
        shutil.copytree(ROOT/name, source/name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    zip_folder(source, output/f'JuicyStudio-{VERSION}-Source.zip', source.name)
    subprocess.run([str(args.iscc.resolve()), f'/DProductVersion={VERSION}', f'/DPayloadDir={payload}', f'/DReleaseDir={output}',
                    str(ROOT/'installer/JuicyStudio.iss')], check=True, cwd=ROOT)
    files = sorted([*output.glob('*.zip'), *output.glob('*Setup.exe')])
    lines = []
    for file in files:
        with file.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        lines.append(f'{digest}  {file.name}')
    (output/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('Release files created in', output)


if __name__ == '__main__':
    main()
