"""Replay locally acquired gameplay through production OCR/capture, off screen.

Usage: python scripts/replay-video-ocr.py MANIFEST --resolution 1920x1080
Manifest clips contain game, path, start, duration, player_voice and manually
reviewed expected/excluded text IDs. Media/indexes stay on the owner's machine.
Only the frame source and audio job sink are replaced: native OneOCR, matching,
confirmation, freshness, deduplication and transcript storage are production.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageOps
from oneocr import OcrEngine
from backend.capture import CaptureService
from backend.config import SettingsStore
from backend.local_game import LocalGameTextIndex
from backend.media_tools import ffmpeg_executable
from backend.models import AppSettings
from backend.storage import TranscriptStore
from backend.windows import WindowInfo
from backend.games import GAME_PROFILES


def prepare_frame(original, resolution, mode='fit'):
    """Keep footage geometry; widening a recording must not stretch its text.

    Fit tests simulate a letterboxed/pillarboxed recording, not native game UI
    reflow. Stretch is retained only for explicitly requested legacy probes.
    """
    if mode == 'fit':
        return ImageOps.pad(original.convert('RGB'), resolution,
                            method=Image.Resampling.LANCZOS, color='black')
    if mode == 'stretch':
        return original.convert('RGB').resize(resolution, Image.Resampling.LANCZOS)
    raise ValueError('aspect_mode must be fit or stretch')


def validate_clip(clip):
    if clip.get('game') not in GAME_PROFILES:
        raise ValueError('Unknown replay game')
    if not 0 < float(clip.get('duration', 0)) <= 120:
        raise ValueError('Review clips in sections of at most 120 seconds')
    if clip.get('aspect_mode', 'fit') not in {'fit', 'stretch'}:
        raise ValueError('aspect_mode must be fit or stretch')
    if not clip.get('expected') and not clip.get('expect_no_lines') and not clip.get('excluded'):
        raise ValueError('Annotate expected IDs or an explicit negative case')
    if clip.get('expect_no_lines') and clip.get('expected'):
        raise ValueError('A negative case cannot also expect lines')
    overrides = clip.get('expected_by_fps', {})
    if not isinstance(overrides, dict) or any(key not in {'2', '4'} or not isinstance(ids, list)
            or not all(isinstance(value, str) and value for value in ids) for key, ids in overrides.items()):
        raise ValueError('Cadence expectations require FPS 2/4 and lists of IDs')
    if clip.get('expect_no_lines') and any(overrides.values()):
        raise ValueError('A negative case cannot also expect lines')


def authored_coverage(records):
    result = {}
    for row in records:
        identity = row['text_id']
        members = row.get('member_text_ids')
        if members is not None:
            prefix, separator, _ = identity.partition(':context-')
            if (not separator or not isinstance(members, list) or len(members) != 2
                    or any(not isinstance(member, str) for member in members) or len(set(members)) != 2
                    or any(not member.startswith(prefix + ':') or member == identity for member in members)):
                raise ValueError('Invalid authored context members')
        result[identity] = members or [identity]
    return result


def validate_result(clip, emitted, scheduled, mapped, fps=2, coverage=None):
    coverage = coverage or {}
    actual = {member for line in emitted for member in coverage.get(line.text_id, [line.text_id])}
    expected = set(clip.get('expected_by_fps', {}).get(str(fps), clip.get('expected', [])))
    assert expected <= actual, f"{clip['name']}: missed {expected-actual}"
    if clip.get('expected_exact'):
        assert actual == expected, f"{clip['name']}: unexpected {actual-expected}"
    if clip.get('expect_no_lines'):
        assert not emitted, f"{clip['name']}: unexpected voice {actual}"
    assert not set(clip.get('excluded', [])) & actual, f"{clip['name']}: false voice {set(clip.get('excluded', [])) & actual}"
    assert all(line.text_id in mapped for line in scheduled)
    assert [line.id for line in scheduled] == [line.id for line in emitted], 'Each accepted line queues its own original asset'
    if 'allowed_channels' in clip:
        assert {line.channel for line in emitted} <= set(clip['allowed_channels'])
    return actual


class ReplayStore(TranscriptStore):
    """Replay uses the production transaction and deterministic close scope."""


def replay(clip, resolution, data_dir, fps=2, catalog_bindings_only=False):
    if catalog_bindings_only:
        # Verify the production OCR/matcher using authored catalog bindings,
        # independently of which voice packs this PC has downloaded. Native
        # audio is neither decoded nor asserted by this explicit test mode.
        game = clip['game']
        relative = Path('languages') / game / clip['source_locale'] if clip.get('source_locale') else Path(game)
        payload = json.loads((data_dir / relative / 'textmap.json').read_text(encoding='utf-8'))
        if game not in {'starrail', 'genshin', 'endfield'}:
            raise ValueError('Catalog-only replay requires an authored RPG dialogue catalog.')
        with tempfile.TemporaryDirectory(prefix='catalog-video-replay-') as temporary:
            target = Path(temporary) / relative
            target.mkdir(parents=True)
            for row in payload['records']:
                if not row.get('audio'):
                    row['audio'] = {'catalog_binding_only': row['text_id']}
            (target / 'textmap.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            result = replay(clip, resolution, Path(temporary), fps)
            result['voice_evidence'] = 'authored catalog bindings; original audio mocked for OCR replay'
            return result
    validate_clip(clip)
    game = clip['game']
    if clip.get('source_locale'):
        from backend.multilingual_index import MultilingualTextIndex
        index = MultilingualTextIndex(game, data_dir / 'languages' / game / clip['source_locale'])
        index.target_locale = clip.get('translation_locale', 'en')
    else:
        index = LocalGameTextIndex(game, data_dir / game)
    index.player_voice = clip.get('player_voice', 'unconfigured')
    assert index.ready and index.audio_count, f'{game}: prepared original-language index required'
    payload = json.loads(index.path.read_text(encoding='utf-8'))
    mapped = {r['text_id'] for r in payload['records'] if r.get('audio')}
    coverage = authored_coverage(payload['records'])
    scheduled, events = [], []
    with tempfile.TemporaryDirectory(prefix='game-video-ocr-') as scratch:
        folder = Path(scratch)
        command = [str(ffmpeg_executable()), '-hide_banner', '-loglevel', 'error',
                   '-threads', '1', '-ss', str(clip.get('start', 0)), '-i', str(Path(clip['path']).resolve()),
                   '-t', str(clip['duration']), '-filter_threads', '1', '-vf', f'fps={fps}',
                   '-threads', '1', str(folder / 'frame-%05d.png')]
        subprocess.run(command, check=True, capture_output=True, timeout=120)
        settings = SettingsStore(folder / 'settings.json')
        settings.save(AppSettings(auto_start=False, stable_frames=2,
                                  **clip.get('settings', {})))
        if game == 'wuwa':
            settings.save(settings.get().model_copy(update={'wuwa_rover_voice': index.player_voice}))
        elif game == 'cyberpunk':
            settings.save(settings.get().model_copy(update={'cyberpunk_v_voice': index.player_voice}))
        elif game == 'nte':
            settings.save(settings.get().model_copy(update={'nte_player_voice': index.player_voice}))
        async def ignore(*_):
            pass
        service = CaptureService(settings, index, None, ReplayStore(folder / 'transcript.db'),
                                 ignore, ignore, ignore, folder / 'audio',
                                 game_indexes={game: index},
                                 game_voice_assets={game: SimpleNamespace(locale=getattr(index, 'source_locale', 'zh-Hans'), has_variant=lambda text_id, *_: text_id in mapped)})
        # Collect original-asset requests; never record sound or write an account.
        service._schedule_line_audio = lambda line, *_args, **_kwargs: scheduled.append(line)
        engine = OcrEngine()
        service._engine = engine
        service._prepare_window_capture = lambda _: None
        window = WindowInfo(0, clip['game'], '', (0, 0, *resolution))
        frame_count = 0
        emitted = []
        origin = datetime.now(timezone.utc)
        try:
            for n, path in enumerate(sorted(folder.glob('frame-*.png'))):
                with Image.open(path) as original:
                    source_resolution = original.size
                    screen = prepare_frame(original, resolution, clip.get('aspect_mode', 'fit'))
                service._capture = lambda bounds: screen.crop((bounds[0], bounds[1], bounds[0]+bounds[2], bounds[1]+bounds[3]))
                # Replay time rather than CPU speed controls freshness/cooldown.
                with patch('backend.capture.time.monotonic', return_value=n / fps), \
                     patch('backend.capture.find_active_game_window', return_value=(GAME_PROFILES[game], window)), \
                     patch('backend.capture.datetime', SimpleNamespace(now=lambda *_: origin + timedelta(seconds=n / fps))):
                    outcome = service._scan_once()
                emitted.extend(outcome.emitted_lines)
                events.extend({'at': n / fps, 'text_id': line.text_id,
                               'authored_ids': coverage.get(line.text_id, [line.text_id]),
                               'ocr': service.snapshot().last_ocr} for line in outcome.emitted_lines)
                frame_count += 1
        finally:
            service._executor.shutdown()
        assert frame_count, 'Replay contains no decoded frames'
        actual = {member for line in emitted for member in coverage.get(line.text_id, [line.text_id])}
        expected = set(clip.get('expected_by_fps', {}).get(str(fps), clip.get('expected', [])))
        result = {'name': clip['name'], 'game': game, 'source_url': clip.get('source_url'),
                'chapter': clip.get('chapter'), 'branch': clip.get('branch'),
                'footage_language': clip.get('footage_language'), 'source_locale': clip.get('source_locale'),
                'translation_locale': clip.get('translation_locale'), 'source_timestamps': clip.get('source_timestamps'),
                'source_resolution': source_resolution, 'resolution': resolution,
                'aspect_mode': clip.get('aspect_mode', 'fit'), 'presentation': clip.get('presentation'),
                'fps': fps, 'frames': frame_count, 'emitted': len(emitted),
                'ids': sorted(actual), 'capture_ids': sorted({line.text_id for line in emitted}),
                'expected': sorted(expected), 'misses': sorted(expected - actual),
                'incorrect': sorted(actual - expected) if clip.get('expected_exact') else sorted(actual & set(clip.get('excluded', []))),
                'events': events, 'channels': sorted({line.channel for line in emitted}), 'passed': False}
        try:
            validate_result(clip, emitted, scheduled, mapped, fps, coverage)
        except AssertionError as error:
            error.replay_report = result
            raise
        result['passed'] = True
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--resolution', default='1920x1080')
    parser.add_argument('--fps', type=int, choices=[2, 4], default=2)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    parser.add_argument('--catalog-bindings-only', action='store_true',
                        help='Check authored subtitle matching with mocked audio, independently of installed voice packs')
    parser.add_argument('--output', type=Path, default=Path('output/video-ocr.json'))
    args = parser.parse_args()
    resolution = tuple(map(int, args.resolution.split('x')))
    assert len(resolution) == 2 and min(resolution) > 0
    results = []
    for clip in json.loads(args.manifest.read_text(encoding='utf-8'))['clips']:
        if clip.get('archived'):
            continue
        try:
            result = replay(clip, resolution, args.data_dir, args.fps, args.catalog_bindings_only)
        except AssertionError as error:
            results.append(getattr(error, 'replay_report', {'name': clip['name'], 'passed': False, 'error': str(error)}))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2), encoding='utf-8')
            raise
        results.append(result)
        print(json.dumps(result), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding='utf-8')
