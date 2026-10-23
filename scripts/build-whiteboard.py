#!/usr/bin/env python3
"""Build an editable, self-contained Excalidraw v2 customer-workflow canvas."""
from pathlib import Path
import hashlib
import json
import math
import textwrap

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'docs/prep/customer-workflow.excalidraw'
ELEMENTS = []
BG, PANEL, NOTE = '#10071c', '#160c25', '#231237'
STROKE, LAVENDER, CYAN, WHITE, MUTED = '#9c7abf', '#e4c7ff', '#9deeff', '#ffffff', '#f0e9fc'


def identity(name):
    return hashlib.sha256(name.encode()).hexdigest()[:20]


def base(name, kind, x, y, width, height, group=None):
    return {
        'id': identity(name), 'type': kind, 'x': x, 'y': y,
        'width': width, 'height': height, 'angle': 0,
        'strokeColor': STROKE, 'backgroundColor': 'transparent',
        'fillStyle': 'solid', 'strokeWidth': 2, 'strokeStyle': 'solid',
        'roughness': 0, 'opacity': 100, 'groupIds': [identity(group)] if group else [],
        'frameId': None, 'roundness': None, 'seed': int(identity(name)[:7], 16),
        'version': 1, 'versionNonce': int(identity(name)[7:14], 16),
        'isDeleted': False, 'boundElements': [], 'updated': 1,
        'link': None, 'locked': False,
    }


def rectangle(name, x, y, width, height, fill=PANEL, group=None):
    item = base(name, 'rectangle', x, y, width, height, group)
    item.update(backgroundColor=fill, roundness={'type': 3})
    ELEMENTS.append(item)
    return item


def text(name, value, x, y, width, size=22, color=WHITE, container=None, group=None):
    # Use explicit line breaks so the saved bounding boxes remain predictable.
    chars = max(12, math.floor(width / (size * 0.56)))
    value = '\n'.join(textwrap.fill(row, chars, break_long_words=False,
                                   break_on_hyphens=False) for row in value.split('\n'))
    item = base(name, 'text', x, y, width, len(value.split('\n')) * size * 1.25, group)
    item.update(strokeColor=color, fontSize=size, fontFamily=2,
                text=value, originalText=value, textAlign='left',
                verticalAlign='top', containerId=container['id'] if container else None,
                lineHeight=1.25, autoResize=True)
    ELEMENTS.append(item)
    if container:
        container['boundElements'].append({'id': item['id'], 'type': 'text'})
    return item


def prompt(name, value, x, y, width, height, group):
    box = rectangle(name + '-box', x, y, width, height, NOTE, group)
    item = text(name + '-text', value, x + 20, y + 18, width - 40,
                size=24, color=WHITE, container=box, group=group)
    assert item['height'] <= height - 36, (name, 'prompt exceeds its container')


def area(number, title, subtitle, x, y, width, height):
    group = 'area-' + number
    rectangle(group + '-panel', x, y, width, height, PANEL, group)
    text(group + '-number', number, x + 28, y + 24, 90, 25, CYAN, group=group)
    text(group + '-title', title, x + 28, y + 70, width - 56, 34, LAVENDER, group=group)
    text(group + '-subtitle', subtitle, x + 28, y + 124, width - 56, 22, MUTED, group=group)
    return group


text('title', 'OpenFix 0.2 • Discover the customer workflow', 80, 40, 2280, 44, LAVENDER)
text('subtitle', "Fill from the customer's answers. Choose capabilities after the problem is clear. Revise the design as constraints change.",
     84, 110, 2250, 24, MUTED)

areas = [
    ('01', 'Outcome and people', 'What is worth improving?', 80, [
        'What hurts?\nBusiness consequence: ______',
        'Who is affected?\nSponsor / operator / security / service owner: ______',
        'What would success look like?\nCustomer outcome: ______',
    ]),
    ('02', 'Current workflow and evidence', 'Understand the work already happening.', 860, [
        'What happens today?\nInputs → tools → queues → handoffs: ______',
        'Existing evidence?\nProducer / revision / age / proof: ______',
        'What needs investigation?\nGaps / stale evidence / conflicts / owner: ______',
    ]),
    ('03', 'Smallest useful AI step', 'Select the contribution before the platform.', 1640, [
        'Where does AI add value?\nOne useful task: ______',
        'What already exists?\nNative capability / evidence reuse / integration gap: ______',
        'Who keeps authority?\nDeterministic checks / human decisions: ______',
    ]),
]
for number, title, subtitle, x, prompts in areas:
    group = area(number, title, subtitle, x, 220, 720, 650)
    for index, value in enumerate(prompts):
        prompt(f'{group}-prompt-{index}', value, x + 28, 408 + index * 148, 664, 138, group)

group = area('04', 'Boundaries and failure behavior', 'Draw both the data flow and the authority boundary.', 80, 950, 1110, 610)
for index, value in enumerate([
    'Data and identity\nWhat may leave? Which identity is used? ______',
    'Action authority\nRead / write / publish / merge / deploy: ______',
    'Execution and review\nIsolation / egress / audit / checkpoints: ______',
    'Failure behavior\nUncertainty / cancellation / rollback owner: ______',
]):
    prompt(f'{group}-prompt-{index}', value, 108 + (index % 2) * 530,
           1140 + (index // 2) * 185, 498, 157, group)

group = area('05', 'Pilot and decision', 'A small pilot should lead to an operating decision.', 1250, 950, 1110, 610)
for index, value in enumerate([
    'Evidence and examples\nProof / legitimate behavior / stale or conflicting claims: ______',
    'Measures and baseline\nEffort / accepted outcomes / cost / sample size: ______',
    'Owners and milestones\nWho does what, and by when? ______',
    'Decision gate\nStop / revise / expand one scope dimension: ______',
]):
    prompt(f'{group}-prompt-{index}', value, 1278 + (index % 2) * 530,
           1140 + (index // 2) * 185, 498, 157, group)

text('adaptation', 'Keep visible: assumptions • changed constraints • affected decisions • open questions • next owner',
     84, 1645, 2250, 25, CYAN)
text('provenance', 'Original editable practice template • No fixed customer case • No external assets',
     84, 1700, 2250, 19, MUTED)

document = {
    'type': 'excalidraw', 'version': 2,
    'source': 'https://github.com/markusweldon/openfix',
    'elements': ELEMENTS,
    'appState': {
        'viewBackgroundColor': BG, 'gridSize': None,
        'zoom': {'value': 0.45}, 'scrollX': 0, 'scrollY': 0,
        'currentItemFontFamily': 2, 'exportBackground': True,
    },
    'files': {},
}


def validate(doc):
    assert doc['type'] == 'excalidraw' and doc['version'] == 2
    assert doc['files'] == {}, 'The template must be self-contained'
    ids = [item['id'] for item in doc['elements']]
    assert len(ids) == len(set(ids)), 'Element IDs must be unique'
    by_id = {item['id']: item for item in doc['elements']}
    for item in doc['elements']:
        assert item['type'] in ['rectangle', 'text']
        assert 0 <= item['x'] < 2440 and 0 <= item['y'] < 1760
        assert 0 < item['width'] <= 2280 and item['height'] > 0
        assert item['x'] + item['width'] <= 2440
        assert item['y'] + item['height'] <= 1760
        if item['type'] == 'text' and item['containerId']:
            parent = by_id[item['containerId']]
            assert {'id': item['id'], 'type': 'text'} in parent['boundElements']
            assert parent['x'] <= item['x'] and parent['y'] <= item['y']
            assert item['x'] + item['width'] <= parent['x'] + parent['width']
            assert item['y'] + item['height'] <= parent['y'] + parent['height']
    assert len([item for item in doc['elements'] if item['type'] == 'text' and item['containerId']]) == 17
    return {'elements': len(doc['elements']), 'editable_prompt_containers': 17,
            'canvas_bounds': [2440, 1760], 'external_assets': 0}


if __name__ == '__main__':
    result = validate(document)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    validate(json.loads(TARGET.read_text()))
    print(json.dumps({'output': str(TARGET), **result}))
