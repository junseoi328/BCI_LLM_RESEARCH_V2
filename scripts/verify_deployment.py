"""Read deployment identity; optionally run three small, explicit live API checks."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


def fetch(base, path, body=None):
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    request = Request(base.rstrip('/') + path, data=payload, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=65) as response:
        return response.read().decode('utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--live', action='store_true', help='Makes three LLM-backed prediction requests')
    args = parser.parse_args()
    health = json.loads(fetch(args.base_url, '/health'))
    assert health.get('release') == '0.7.0', f"Unexpected release: {health.get('release')}"
    html = fetch(args.base_url, '/speller')
    assert all(token in html for token in ['btnUndo', 'btnDirectCommit', 'bci_draft_v1', 'btnCancel'])
    report = {'url': args.base_url, 'health': health, 'ui_verified': True, 'predictions': []}
    if args.live:
        from app.korean.initials import exact_initial_match, fill_mask_constraint_match, spelled_constraint_match
        cases = [
            {'bci_input': 'ㄷㅇㅈ', 'recent_context': ['혼자 하기 어려워. 도와줄까?']},
            {'bci_input': 'ㅁㅈ', 'spelled_syllables': {'0': '물'}, 'recent_context': ['목이 말라']},
            {'bci_input': 'ㅁㅈ', 'fill_mask_reference_text': '물 줘', 'fill_mask_target_index': 1, 'recent_context': ['물 좀 부탁해']},
        ]
        for case in cases:
            start = time.perf_counter()
            data = json.loads(fetch(args.base_url, '/predict', {**case, 'top_k': 3}))
            texts = [c['text'] for c in data['candidates']]
            assert texts, f"No candidates for smoke case {len(report['predictions']) + 1}"
            assert all(exact_initial_match(text, case['bci_input']) for text in texts)
            if 'spelled_syllables' in case:
                assert data['recovery_mode'] == 'keyword_ae'
                assert all(spelled_constraint_match(text, {0: '물'}) for text in texts)
            if 'fill_mask_target_index' in case:
                assert data['recovery_mode'] == 'fill_mask'
                assert all(fill_mask_constraint_match(text, '물 줘', 1) for text in texts)
            report['predictions'].append({
                'mode': data['recovery_mode'], 'candidate_count': len(texts),
                'elapsed_ms': round((time.perf_counter() - start) * 1000),
                'fallback': data['fallback'], 'warnings': data['warnings'], 'usage': data['usage'],
            })
    target = Path('test-results/deployment_report.json')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
