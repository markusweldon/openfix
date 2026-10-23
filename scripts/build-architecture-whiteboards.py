#!/usr/bin/env python3
"""Build editable, self-contained Excalidraw architecture discussion canvases.

The original customer-discovery template remains in build-whiteboard.py.
This generator uses only Python's standard library. Native SVG/PNG previews
are exported from these scenes with Excalidraw's exportToSvg/exportToBlob API.
"""
from pathlib import Path
import hashlib
import json
import math
import textwrap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/whiteboards'
BG, PANEL, CARD = '#10071c', '#190e29', '#231337'
WHITE, MUTED, PURPLE = '#fbf7ff', '#d8c9e8', '#e4c7ff'
CYAN, GREEN, PINK, LINE = '#9deeff', '#a5f0cf', '#ffacdd', '#9978b5'
W, H = 1920, 1200


class Canvas:
    def __init__(self, name, number, title, subtitle):
        self.name, self.elements, self.boxes = name, [], {}
        self.panel_ids = set()
        self.text('eyebrow', f'OPENFIX / {number} / REPOSITORY DISCUSSION', 64, 36, 1792, 17, CYAN)
        self.text('title', title, 64, 78, 1792, 46, WHITE)
        self.text('subtitle', subtitle, 66, 143, 1788, 24, MUTED)

    def uid(self, name):
        return hashlib.sha256(f'{self.name}:{name}'.encode()).hexdigest()[:20]

    def base(self, name, kind, x, y, width, height, group=None):
        uid = self.uid(name)
        return dict(id=uid, type=kind, x=x, y=y, width=width, height=height,
                    angle=0, strokeColor=LINE, backgroundColor='transparent',
                    fillStyle='solid', strokeWidth=1.8, strokeStyle='solid',
                    roughness=0.5, opacity=100, groupIds=[self.uid(group)] if group else [],
                    frameId=None, roundness=None, seed=int(uid[:7], 16),
                    version=1, versionNonce=int(uid[7:14], 16), isDeleted=False,
                    boundElements=[], updated=1, link=None, locked=False)

    def rect(self, name, x, y, width, height, fill=CARD, stroke=LINE, group=None, dashed=False):
        element = self.base(name, 'rectangle', x, y, width, height, group)
        element.update(backgroundColor=fill, strokeColor=stroke,
                       strokeStyle='dashed' if dashed else 'solid', roundness={'type': 3})
        self.elements.append(element)
        self.boxes[name] = element
        return element

    def text(self, name, value, x, y, width, size=22, color=WHITE, group=None):
        # Conservative wrapping leaves room for native Arial/Helvetica metrics.
        chars = max(10, math.floor(width / (size * 0.54)))
        rows = [textwrap.fill(row, chars, break_long_words=False, break_on_hyphens=False)
                for row in value.split('\n')]
        value = '\n'.join(rows)
        element = self.base(name, 'text', x, y, width, len(value.split('\n')) * size * 1.28, group)
        element.update(strokeColor=color, fontSize=size, fontFamily=2, text=value,
                       originalText=value, textAlign='left', verticalAlign='top',
                       containerId=None, lineHeight=1.28, autoResize=True)
        self.elements.append(element)
        return element

    def card(self, name, x, y, width, height, title, body='', tag=None,
             accent=PURPLE, fill=CARD, link=None):
        group = name + '-group'
        box = self.rect(name, x, y, width, height, fill=fill, stroke=accent, group=group)
        if link:
            box['link'] = 'https://github.com/markusweldon/openfix/blob/main/' + link
        offset = 22
        if tag:
            t = self.text(name+'-tag', tag.upper(), x+22, y+offset, width-44, 15, accent, group)
            offset += t['height'] + 9
        heading = self.text(name+'-heading', title, x+22, y+offset, width-44, 25, WHITE, group)
        offset += heading['height'] + 14
        if body:
            desc = self.text(name+'-body', body, x+22, y+offset, width-44, 21, MUTED, group)
            offset += desc['height']
        assert offset <= height-14, (self.name, name, offset, height)
        return box

    def panel(self, name, x, y, width, height, title, subtitle='', accent=LINE, dashed=False):
        self.panel_ids.add(self.rect(name, x, y, width, height, fill=PANEL, stroke=accent, dashed=dashed)['id'])
        self.text(name+'-label', title, x+22, y+20, width-44, 20, accent)
        if subtitle:
            self.text(name+'-caption', subtitle, x+22, y+54, width-44, 18, MUTED)

    def arrow(self, name, source, target, source_side='right', target_side='left',
              color=CYAN, route=None, dashed=False):
        a, b = self.boxes[source], self.boxes[target]
        def anchor(box, side):
            return {'left':(box['x']-10, box['y']+box['height']/2),
                    'right':(box['x']+box['width']+10, box['y']+box['height']/2),
                    'top':(box['x']+box['width']/2, box['y']-10),
                    'bottom':(box['x']+box['width']/2, box['y']+box['height']+10)}[side]
        start, end = anchor(a, source_side), anchor(b, target_side)
        points = [start, *(route or []), end]
        x, y = points[0]
        element = self.base(name, 'arrow', x, y,
                            max(p[0] for p in points)-min(p[0] for p in points),
                            max(p[1] for p in points)-min(p[1] for p in points))
        element.update(strokeColor=color, strokeWidth=2.5, roughness=0,
                       strokeStyle='dashed' if dashed else 'solid',
                       points=[[px-x, py-y] for px, py in points],
                       startBinding={'elementId':a['id'], 'focus':0, 'gap':10},
                       endBinding={'elementId':b['id'], 'focus':0, 'gap':10},
                       startArrowhead=None, endArrowhead='arrow',
                       lastCommittedPoint=None, elbowed=False)
        # document() puts connectors above zone backgrounds and below nodes.
        self.elements.append(element)
        for box in (a, b):
            box['boundElements'].append({'id':element['id'], 'type':'arrow'})
        return element

    def footer(self, value, caution):
        self.text('footer-principle', value, 66, 1101, 1788, 23, CYAN)
        self.text('footer-boundary', caution, 66, 1148, 1788, 18, MUTED)

    def document(self):
        return {'type':'excalidraw', 'version':2,
                'source':'https://github.com/markusweldon/openfix',
                'elements':sorted(self.elements,key=lambda e: 0 if e['id'] in self.panel_ids else 1 if e['type']=='arrow' else 2), 'appState':{
                    'viewBackgroundColor':BG, 'gridSize':None,
                    'zoom':{'value':0.65}, 'scrollX':0, 'scrollY':0,
                    'currentItemFontFamily':2, 'exportBackground':True,
                    'exportWithDarkMode':False}, 'files':{}}


def value_board():
    c = Canvas('01-customer-value', '01', 'From security signals to a defensible change',
               'AI can expand investigation and proposals. The harness preserves evidence and keeps consequential decisions explicit.')
    c.panel('foundation', 64, 210, 1792, 110, 'KEEP THE ESTABLISHED FOUNDATION',
            'Scanners and enriched findings  /  asset inventory  /  source control and CI  /  ownership and change control', CYAN)
    xs, width = [64, 524, 984, 1444], 412
    cards = [
        ('inputs', 'Preserve what is known', 'Original reports, producer evidence and customer context travel with the case.', '01 / INTAKE', PURPLE, 'src/workflow/import.mjs'),
        ('gaps', 'Investigate useful gaps', 'Check subject, freshness and conflicts. Reuse matching evidence before adding work.', '02 / EVIDENCE PLAN', PURPLE, 'src/workflow/enrich.mjs'),
        ('ai', 'Bound the AI task', 'An approved host investigates or proposes within the recorded scope and allowed actions.', '03 / AI CONTRIBUTION', CYAN, 'src/workflow/operations.mjs'),
        ('proof', 'Earn a change decision', 'Validate, accept ownership, verify the exact patch, and retain the human review.', '04 / CONTROLLED CHANGE', GREEN, 'src/lifecycle/workflow.mjs'),
    ]
    for x, (name, title, body, tag, color, link) in zip(xs, cards):
        c.card(name, x, 390, width, 250, title, body, tag=tag, accent=color, link=link)
    for a,b in [('inputs','gaps'),('gaps','ai'),('ai','proof')]:c.arrow(a+'-'+b, a, b)
    c.text('case-ribbon', 'ONE PERSISTENT CASE   /   producer + subject + evidence + limitations + decisions + history',
           84, 681, 1752, 24, CYAN)
    for x, name, title, body in [
        (64, 'v1', 'Reduce repeated investigation', 'Hypothesis: less analyst effort through evidence reuse and focused follow-up.'),
        (674, 'v2', 'Make decisions reviewable', 'Expose uncertainty and the reason for each transition, including failed attempts.'),
        (1284, 'v3', 'Protect the business function', 'A fix must address the issue and preserve the behavior customers need.'),
    ]:c.card(name, x, 770, 572, 210, title, body, accent=LINE)
    c.text('measure', 'PILOT MEASURES   Investigation + review time  /  accepted correct fixes  /  regressions  /  cost per accepted outcome',
           84, 1014, 1752, 22, MUTED)
    c.footer('Ask: where does evidence turn into repeated work or a stalled decision today?',
             'Value is a pilot hypothesis. The local core does not run a model; native-host execution and optional Cursor are separate capabilities.')
    return c


def system_board():
    c = Canvas('02-system-boundaries', '02', 'The harness owns decisions; execution crosses a boundary',
               'Keep evidence contracts and lifecycle rules stable while input tools and approved agent hosts change.')
    c.panel('input-zone', 64, 214, 350, 770, 'EXTERNAL INPUTS', 'Treat content as evidence and data.', CYAN)
    c.panel('local-zone', 456, 214, 884, 770, 'IMPLEMENTED LOCAL HARNESS', 'Explicit CLI operations; one persistent security case.', PURPLE)
    c.panel('host-zone', 1382, 214, 474, 770, 'SEPARATE SYSTEMS', 'Execution and change authority live here.', CYAN)
    c.card('reports', 88, 350, 302, 242, 'Findings + enrichment', 'SARIF, GitHub, Snyk and Codex exports. Preserve original producer context.', accent=LINE, link='src/workflow/import.mjs')
    c.card('source', 88, 664, 302, 210, 'Context + source', 'Exact asset / repo / revision joins. Clean pinned code.', accent=LINE, link='src/workflow/enrich.mjs')
    c.card('assess', 488, 350, 360, 216, 'Import + assess', 'Scope, correlate, reuse; retain stale evidence and conflicts.', accent=PURPLE, link='src/workflow/enrich.mjs')
    c.card('ops', 940, 350, 368, 216, 'Decisions + lifecycle', 'Validation, accepted scope, exact-artifact checks and review.', accent=PURPLE, link='src/workflow/operations.mjs')
    c.card('store', 488, 690, 360, 218, 'Durable case store', 'Atomic writes, evidence history and local audit checkpoints.', accent=PURPLE, link='src/workflow/store.mjs')
    c.card('check', 940, 690, 368, 218, 'Scoped checks', 'One reference tenant validator. Local bounded process; no sandbox.', accent=GREEN, link='src/workflow/validation.mjs')
    c.card('agent', 1406, 350, 426, 280, 'Approved agent host', 'Native: operator supplies task packet.\nCursor: explicit execution and draft-publication consent.', accent=CYAN, link='src/workflow/providers.mjs')
    c.card('change', 1406, 724, 426, 184, 'Customer change systems', 'Merge, deploy and post-change observations stay separate.', accent=CYAN)
    c.arrow('reports-assess','reports','assess')
    c.arrow('source-assess','source','assess','right','left',route=[(436,769),(436,458)])
    c.arrow('assess-ops','assess','ops')
    c.arrow('assess-store','assess','store','bottom','top')
    c.arrow('ops-check','ops','check','bottom','top',color=GREEN)['startArrowhead']='arrow'
    c.arrow('ops-store','ops','store','left','right',route=[(894,458),(894,799)],dashed=True)['startArrowhead']='arrow'
    c.arrow('ops-agent','ops','agent')
    c.arrow('agent-evidence','agent','ops','top','top',route=[(1619,326),(1124,326)],dashed=True)
    c.text('return-label','Proposed evidence / change; explicitly record', 947, 292, 823, 18, CYAN)
    c.text('store-label','Read-only view reads the case; it cannot authorize a change.', 488, 938, 820, 18, MUTED)
    c.text('external-proof','Rollout and closure are operator attestations in this local implementation.', 1406, 656, 424, 17, MUTED)
    c.panel('future', 64, 1010, 1792, 65, 'PROPOSED PRODUCTION: authenticated identity / isolated workers / credential + egress broker / trusted evidence ingestion', '', LINE, dashed=True)
    c.footer('A task packet is a scope and evidence contract. It is not credentials or an isolation boundary.',
             'Local actor labels provide attribution, not authenticated RBAC. Reference execution is not network/container isolation. No live Cloud API connector.')
    return c


def approval_board():
    c = Canvas('03-proof-and-approval', '03', 'A plausible patch must earn approval',
               'Read the same issue through evidence, authorization, exact-artifact checks and a human change decision.')
    xs = [64, 524, 984, 1444]
    for x, name, title, body, tag, color in [
        (xs[0], 'evidence', 'Scoped evidence', 'Validate at the immutable finding revision. Retain the method and limitations.', '01 / KNOW THE SUBJECT', PURPLE),
        (xs[1], 'accept', 'Human accepts scope', 'Accountable owner, priority, rationale and current context. Priority grants no authority.', '02 / AUTHORIZE THE WORK', PURPLE),
        (xs[2], 'artifact', 'Record the real change', 'A bounded proposal becomes an actual Git base, head, file set and diff digest.', '03 / EXACT ARTIFACT', CYAN),
        (xs[3], 'checks', 'Check both properties', 'Security behavior AND legitimate behavior, at the exact changed head.', '04 / INDEPENDENT CHECK', GREEN),
    ]:c.card(name, x, 245, 412, 258, title, body, tag, color)
    for a,b in [('evidence','accept'),('accept','artifact'),('artifact','checks')]:c.arrow(a+'-'+b,a,b)
    c.text('uncertainty','Disproved or inconclusive: retain evidence; no remediation authority.', 84, 546, 896, 20, PINK)
    c.text('invalidations','Changed context: reaccept. Changed patch: invalidate prior proof and review.', 84, 995, 1752, 21, CYAN)
    c.card('bad', 64, 640, 534, 260, 'Deny every invoice request', 'Security check: passes\nLegitimate access: FAILS\nApproval blocked; revise the change.', 'FAILED FIX / PRESERVE THE FAILURE', PINK)
    c.card('good', 674, 640, 534, 260, 'Enforce tenant ownership', 'Security check: passes\nLegitimate access: passes\nEligible for exact-artifact review.', 'CORRECTED CHANGE / RECORDED PROOF', GREEN)
    c.card('review', 1284, 640, 572, 260, 'Human reviews the exact hash', 'Reviewer differs from patch author. Approval leaves the case open. Rollout and closure need separate evidence.', '05 / CHANGE DECISION', CYAN)
    c.arrow('check-to-good','checks','good','bottom','top',route=[(1650,602),(941,602)],color=GREEN)
    c.arrow('check-to-bad','checks','bad','bottom','top',route=[(1650,618),(331,618)],color=PINK)
    c.arrow('good-to-review','good','review',color=GREEN)
    c.arrow('bad-to-artifact','bad','artifact','left','top',route=[(30,770),(30,220),(1190,220)],color=PINK,dashed=True)
    c.text('example-scope','REFERENCE CONTRACT   CWE-639 at src/invoices.mjs:3; verification only covers invoice-file changes.', 84, 949, 1752, 23, MUTED)
    c.text('other-cases','Unsupported subjects or missing capability stay inconclusive. Local actor names are assertions; production must authenticate independent roles.',
           84, 1040, 1752, 18, MUTED)
    c.footer('Ask: what must a correct fix preserve, and who can accept the remaining risk?',
             'The issue, failed fix and corrected fix are source/test examples, not an app demonstration. A later empty scan cannot close the case.')
    return c


def validate(doc):
    assert doc['type']=='excalidraw' and doc['version']==2 and doc['files']=={}
    by_id={e['id']:e for e in doc['elements']}
    assert len(by_id)==len(doc['elements']), 'Duplicate element ID'
    arrows=0
    for e in doc['elements']:
        assert not e['isDeleted'] and not e['locked']
        assert e['type'] in {'rectangle','text','arrow'}
        assert 0 <= e['x'] <= W and 0 <= e['y'] <= H
        if e['type']!='arrow':
            assert e['x']+e['width']<=W and e['y']+e['height']<=H, e['id']
        if e['type']=='arrow':
            arrows+=1
            for key in ['startBinding','endBinding']:
                target=by_id[e[key]['elementId']]
                assert {'id':e['id'],'type':'arrow'} in target['boundElements']
    return {'elements':len(by_id),'bound_arrows':arrows,'external_assets':0,'editable':True}


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    for canvas in [value_board(),system_board(),approval_board()]:
        document=canvas.document();result=validate(document)
        target=OUT/(canvas.name+'.excalidraw')
        target.write_text(json.dumps(document,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps({'output':str(target),**result}))
