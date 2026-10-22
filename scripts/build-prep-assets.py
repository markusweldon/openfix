#!/usr/bin/env python3
"""Rebuild OpenFix's original presentation and diagrams. No network required."""
from pathlib import Path
import math
import textwrap
from xml.sax.saxutils import escape
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.xmlchemy import OxmlElement
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/prep'
DIAGRAMS = OUT / 'diagrams'
OUT.mkdir(parents=True, exist_ok=True)
DIAGRAMS.mkdir(parents=True, exist_ok=True)
BG, BG_END, CARD = '160A2C', '3A185F', '27143F'
MINT, WHITE, MUTED, CORAL, LINE = 'D7B0FF', 'FAF6FF', 'D0C1DF', 'FF96D0', '694789'
CYAN, GRID = '82DDEA', '764396'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'

def txt(x, y, w, h, text, size=30, color=WHITE, bold=False, mono=False):
    return dict(kind='text', x=x, y=y, w=w, h=h, text=text, size=size, color=color, bold=bold, mono=mono)

def rect(x, y, w, h, fill=CARD, stroke=None):
    if stroke is None and fill == CARD:
        stroke = '583474'
    return dict(kind='rect', x=x, y=y, w=w, h=h, fill=fill, stroke=stroke)

def line(x1, y1, x2, y2, color=LINE, arrow=True):
    if arrow and color == MINT:
        color = CYAN
    return dict(kind='line', x1=x1, y1=y1, x2=x2, y2=y2, color=color, arrow=arrow)

def rgb(value):
    return tuple(int(value[i:i+2],16) for i in (0,2,4))

def background_image():
    start, end = rgb(BG), rgb(BG_END)
    strip=Image.new('RGB',(1600,1))
    strip.putdata([tuple(round(a+(b-a)*x/1599) for a,b in zip(start,end)) for x in range(1600)])
    image=strip.resize((1600,900))
    overlay=Image.new('RGBA',image.size,(0,0,0,0));draw=ImageDraw.Draw(overlay)
    # A very quiet perspective floor gives the palette its synthwave character.
    # Keep the texture below the slide's information-bearing area.
    for y in (785,812,850,899):
        draw.line((0,y,1600,y),fill=(*rgb(GRID),48),width=1)
    for x in range(-800,2401,200):
        draw.line((800+(x-800)*.60,770,x,900),fill=(*rgb(GRID),48),width=1)
    return Image.alpha_composite(image.convert('RGBA'),overlay).convert('RGB')

def svg_background():
    rows=[f'<rect width="1600" height="900" fill="url(#synthwave-background)"/>']
    for y in (785,812,850,899):
        rows.append(f'<line x1="0" y1="{y}" x2="1600" y2="{y}" stroke="#{GRID}" stroke-opacity=".19"/>')
    for x in range(-800,2401,200):
        rows.append(f'<line x1="{800+(x-800)*.60}" y1="770" x2="{x}" y2="900" stroke="#{GRID}" stroke-opacity=".19"/>')
    return rows

def ppt_background(slide):
    shape=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,Inches(16),Inches(9))
    shape.fill.gradient()
    shape.fill.gradient_angle=0
    shape.fill.gradient_stops[0].color.rgb=RGBColor.from_string(BG)
    shape.fill.gradient_stops[1].color.rgb=RGBColor.from_string(BG_END)
    shape.line.fill.background()
    segments=[(0,y,1600,y) for y in (785,812,850,899)]
    segments += [(800+(x-800)*.60,770,x,900) for x in range(-800,2401,200)]
    for x,y,xx,yy in segments:
        connector=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x/100),Inches(y/100),Inches(xx/100),Inches(yy/100))
        connector.line.color.rgb=RGBColor.from_string(GRID);connector.line.width=Pt(.6)
        color=connector.line._get_or_add_ln().find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr')
        alpha=OxmlElement('a:alpha');alpha.set('val','19000');color.append(alpha)

def wrap(text, width=43):
    return '\n'.join(textwrap.fill(part, width=width) if part else '' for part in text.split('\n'))

def base(title, subtitle='', number=1, label='CUSTOMER WORKFLOW / VISUAL REFERENCE'):
    s = [rect(0, 0, 1600, 900, BG), rect(70, 62, 42, 7, MINT),
         txt(130, 47, 1300, 36, 'OPENFIX / ' + label, 17, MINT, True),
         txt(70, 125, 1470, 100, title, 56, WHITE, True),
         txt(74, 226, 1430, 75, subtitle, 25, MUTED),
         line(70, 829, 1530, 829, LINE, False),
         txt(73, 850, 1360, 28, 'Independent project • Synthetic practice scenario • No production results claimed', 16, MUTED),
         txt(1450, 845, 90, 35, f'{number:02}', 21, MINT, True)]
    return s

def card(x, y, w, h, kicker, title, body, color=MINT, body_size=28):
    return [rect(x, y, w, h), txt(x+25, y+22, w-50, 35, kicker.upper(), 17, color, True),
            txt(x+25, y+76, w-50, 85, title, 34, WHITE, True),
            txt(x+25, y+177, w-50, h-190, wrap(body, max(16, int((w-50)/(body_size*.55)))), body_size, MUTED)]

def node(x, y, w, h, num, title, sub, accent=MINT):
    return [rect(x, y, w, h), txt(x+20, y+15, 60, 35, num, 22, accent, True),
            txt(x+20, y+58, w-40, 45, title, 24, WHITE, True),
            txt(x+20, y+108, w-40, 62, wrap(sub, max(18,int((w-40)/11))), 20, MUTED)]

def lifecycle(number=3):
    s = base('The complete security loop', 'Evidence, acceptance, verification, and closure are separate decisions.', number)
    xs = [75, 460, 845, 1230]
    data = [('01', 'Inventory + scope', 'Assets, owners, boundaries'), ('02', 'Discover / import', 'Codex Security + scanners'),
            ('03', 'Validate', 'Confirmed / disproved / gaps'), ('04', 'Triage + accept', 'Owner, priority, decision')]
    for x, (n,t,b) in zip(xs,data): s += node(x,320,295,175,n,t,b)
    for a,b in zip(xs,xs[1:]): s.append(line(a+298,407,b-8,407,MINT))
    lower = [('08','Revalidate + close','After normal change controls'), ('07','Human review','Approve the exact artifact'),
             ('06','Verify patch','Security + legitimate behavior'), ('05','Generate patch','Bounded, isolated change')]
    for x, (n,t,b) in zip(xs,lower): s += node(x,580,295,175,n,t,b)
    s += [line(1377,496,1377,573,MINT)]
    for a,b in zip(xs[1:],xs): s.append(line(a-8,667,b+302,667,MINT))
    s += [txt(75,510,1440,50,'Early triage can guide investigation. Failed or incomplete verification returns work to remediation.',21,CORAL)]
    return s

def architecture(number=6):
    s = base('A control plane with clear authority', 'Target architecture: integrate security capabilities without giving one process every permission.',number)
    for y,title,sub in [(310,'Codex Security','Discovery + validation'),(455,'Scanner findings','SARIF / JSON imports'),(600,'Cloud + runtime','Context with asset / version mapping')]:
        s += [rect(70,y,330,110),txt(90,y+16,290,36,title,27,WHITE,True),txt(90,y+61,290,44,sub,18,MUTED)]
        s += [line(404,y+55,510,500,MINT)]
    s += [rect(520,375,410,250),txt(545,402,360,48,'OpenFix',39,WHITE,True),txt(545,465,360,120,'Lifecycle policy\nEvidence + provenance\nReview decisions + audit',27,MUTED)]
    s += [rect(1035,310,485,120),txt(1060,328,435,42,'Isolated executor',31,WHITE,True),txt(1060,379,435,33,'Read source / propose bounded patch',22,MUTED)]
    s += [rect(1035,490,485,120),txt(1060,508,435,42,'Independent verification',31,WHITE,True),txt(1060,559,435,33,'Exact artifact + explicit proof gaps',22,MUTED)]
    s += [line(935,442,1025,370,MINT),line(1278,434,1278,482,MINT),line(1028,550,935,565,MINT)]
    s += [rect(520,700,410,80),txt(545,721,360,38,'Human review',29,MINT,True),line(725,631,725,690,MINT)]
    s += [rect(1035,700,485,80),txt(1060,718,435,43,'Separate publication identity',26,WHITE,True),line(935,740,1025,740,MINT)]
    return s

def current_v1():
    s=base('Current OpenFix v1', 'Implemented path: imported scanner findings to Cursor remediation and downstream PR checks.', 1, 'CURRENT IMPLEMENTATION')
    labels=[('01','Import findings','SARIF / JSON'),('02','Route by policy','Fix / human / noise'),('03','Cursor agent','Generate remediation PR'),('04','Observe PR CI','Tests + scanner jobs'),('05','Human review','Normal merge process')]
    for i,(n,t,b) in enumerate(labels):
        x=65+i*310;s += node(x,350,270,195,n,t,b)
        if i<4:s += [line(x+275,447,x+300,447,MINT)]
    s += [rect(75,620,1450,140),txt(100,643,1390,45,'The refactor adds explicit evidence and decision state across the lifecycle.',29,MINT,True),txt(100,704,1390,40,'Discovery / validation / acceptance / exact-patch verification / review / revalidation / closure',23,MUTED)]
    return s

slides = []
def add(scene, notes): slides.append((scene, notes))

s = base('From security signals\nto reviewed, verified change', 'A customer workflow for OpenFix\nMarkus Weldon • Independent architecture proposal and prototype', 1)
s[3]['h']=160; s[4]['y']=312; s[4]['h']=90
for i,(title,sub) in enumerate([('UNDERSTAND','Scope the customer problem'),('PROVE','Validate evidence and behavior'),('FIX','Review the exact change')]):
    s += card(75+i*510,485,470,280,f'0{i+1}',title,sub,body_size=25)
add(s,'Open with the customer outcome. Explain that this is an independent project, with a tested lifecycle prototype and a proposed integration architecture. Ask permission to use a visual only if useful; a discovery conversation does not need a full presentation.')

s=base('Start with the customer outcome','Let the provided scenario determine the scope. The billing example is only a practice vignette.',2)
for i,(k,t,b) in enumerate([('Problem','Where is work stuck?','Detection noise, investigation, ownership, patch creation, or review?'),('Scope','One service, one issue class','Identify the security owner, service owner, approved data, and success criteria.'),('Value','Measure accepted fixes','Compare end-to-end effort, verified outcomes, review burden, and failure rate.')]):
    s += card(75+i*510,335,470,440,k,t,b)
add(s,'Ask what hurts and who owns the workflow before discussing products. Establish current effort and remediation time. The billing scenario is invented for practice and should never be presented as the actual customer scenario. Avoid invented ROI numbers.')

add(lifecycle(3),'Describe the workflow as a design rather than a rigid OpenAI product sequence. Establish threat context, discover or import candidates, validate, and obtain acceptance before remediation. Early triage can select expensive investigations. Verify the exact patch, review it, use normal merge and deployment controls, then revalidate and close explicitly. Negative and uncertain outcomes are first-class states.')

s=base('Keep these decisions separate','A status label should express the evidence and authority actually present.',4)
rows=[('Candidate','A hypothesis worth investigating'),('Confirmed','Evidence supports the security finding'),('Accepted','A reviewer chooses owner, priority, and remediation scope'),('Verified patch','Agreed checks pass for the exact artifact'),('Closed','Change controls and post-change evidence support closure')]
for i,(a,b) in enumerate(rows):
    y=324+i*88;s += [rect(75,y,1450,70),txt(100,y+16,330,42,a,27,MINT,True),txt(450,y+16,1040,42,b,26,WHITE)]
add(s,'Confidence is separate from severity and business priority. A scanner result or model claim is a candidate until evidence supports it. An accepted finding is a human prioritization and scope decision. Patch creation does not establish verification. Verification does not automatically close a finding.')

s=base('From a signal to an attack path','Hypothetical issue: invoice lookup authenticates a caller but omits tenant ownership.',5)
for i,(t,b) in enumerate([('Attacker input','Invoice identifier'),('Control failure','Lookup omits tenant predicate'),('Supported impact','Another tenant invoice is returned')]):
    s += node(75+i*510,330,470,190,f'0{i+1}',t,b)
    if i<2:s += [line(550+i*510,425,575+i*510,425,MINT)]
s += [rect(75,575,1450,192),txt(100,597,1390,42,'Context informs priority; the code path establishes the flaw.',28,MINT,True),txt(100,654,1390,84,'Cloud exposure: internet-facing asset. Runtime: requests correlated to a known version.\nMapping gaps and unverified exploitation remain visible.',26,MUTED)]
add(s,'Walk through source, failed control, sink, and supported impact. Explain which evidence is executed and which is source-based. Cloud exposure alone is not a vulnerability, and runtime logs must map to the relevant asset and version. Preserve ambiguity rather than escalating a claim beyond its evidence.')

add(architecture(6),'OpenFix owns the lifecycle policy and evidence record. Codex Security can supply discovery and validation; existing scanners remain useful inputs. Cloud and runtime systems contribute approved context. An isolated executor proposes a bounded patch. Verification, human review, and publication use separate authority. This is the target architecture, not a statement that these integrations are all implemented.')

s=base('A useful workflow handles uncertainty','Show the branches as deliberately as the successful fix.',7)
for i,(k,t,b,c) in enumerate([('Evidence supports it','Confirmed','Accept for a bounded remediation after reviewing scope and impact.',MINT),('A control already holds','Disproved','Record the evidence and dismissal reason. Do not spend a patch run.',MINT),('Proof is incomplete','Needs context','Name the missing assumption, test, version mapping, or permission.',CORAL)]):
    s += card(75+i*510,335,470,440,k,t,b,c)
add(s,'A false positive or incomplete validation is a useful output. Source-based analysis can support a finding without runtime reproduction, but execution-dependent uncertainty must remain open. A completed scan can have deferred surfaces and coverage gaps; completion and completeness are different measures.')

s=base('Choose the right capability','Start with native capabilities, then add the customer integration that is actually missing.',8)
rows=[('Defense Factory','Continuous operating model and reference architecture'),('Daybreak','Broader governed cyber-defense stack'),('Codex Security','Code discovery, finding evidence, validation and fixes'),('Promptfoo','AI application evaluation and adversarial behavior testing'),('OpenFix proposal','Customer context, evidence, ownership and change workflow')]
for i,(a,b) in enumerate(rows):
    y=324+i*88;s += [rect(75,y,1450,70),txt(100,y+16,360,42,a,27,MINT,True),txt(485,y+16,1000,42,b,24,WHITE)]
add(s,'Defense Factory describes an operating model; Daybreak is broader than one product. Codex Security Cloud and local workflows have distinct setup and contracts. Promptfoo evaluates AI behavior, including agent tool use; it complements code-security analysis. OpenFix should add a useful customer integration rather than duplicate those products. Sources: https://openai.com/the-defense-factory/ ; https://openai.com/daybreak/ ; https://learn.chatgpt.com/docs/security/setup ; https://www.promptfoo.dev/docs/red-team/agents/ . OpenAI announced a Promptfoo acquisition agreement; do not infer a completed product integration or an interviewer biography from it.')

s=base('Controls travel with the workflow','Assign authority to each action and bind approval to a specific artifact.',9)
rows=[('Read / investigate','Approved source and data; scoped execution'),('Propose a patch','Accepted finding; bounded isolated workspace'),('Verify','Independent result at the exact changed revision'),('Publish / merge','Separate credentials; reviewer and branch protection'),('Deploy / close','Normal change process; post-change evidence')]
for i,(a,b) in enumerate(rows):
    y=324+i*88;s += [rect(75,y,1450,70),txt(100,y+16,360,42,a,27,MINT,True),txt(485,y+16,1000,42,b,25,WHITE)]
add(s,'Distinguish a local command sandbox from isolated execution of arbitrary customer code. Discuss least privilege, data handling, egress, immutable verification inputs, cancellation, auditability, and rollback in terms of the actual customer constraints. Actor labels in the prototype are caller assertions, not authenticated enterprise RBAC.')

s=base('A small pilot with a real decision','Agree the baseline, evidence, owners, and exit criteria before expanding.',10)
for i,(k,t,b) in enumerate([('Baseline','Current workflow','Approved data, labeled examples, reviewer standards, investigator effort.'),('Evaluate','Positive + negative cases','Verified acceptance, false fixes, proof gaps, latency, cost, review time.'),('Decide','Expand, revise, or stop','One service and issue class first. Define the next owner and decision date.')]):
    s += card(75+i*510,335,470,440,k,t,b)
add(s,'Propose a bounded pilot rather than broad autonomous rollout. Include a false positive, missing context, a broken build, a patch that denies all legitimate requests, and a timeout. Agree numerical targets after measuring the baseline. Report sample size and failed attempts; avoid treating replay quality as model quality.')

s=base('What exists, and what changes','The repository should make implementation status easy to inspect.',11)
for i,(k,t,b,c) in enumerate([('Current v1','Remediation orchestrator','SARIF / JSON ingestion, policy routing, Cursor agents, PR CI observation.',MUTED),('Tested prototype','Lifecycle decision gates','Validation, triage, patch identity, verification, review, revalidation, closure.',MINT),('Proposed integration','Full customer workflow','Codex Security adapter, isolated jobs, durable evidence, workbench, publication.',CORAL)]):
    s += card(75+i*510,335,470,440,k,t,b,c)
add(s,'Be candid about what is real. The original code is a useful remediation adapter. The new lifecycle domain and its tests are executable. The complete production integration and workbench are proposed, not delivered. Explain the migration in stages rather than implying that a diagram proves functionality.')

s=base('Separate access, usage, and deployment','Pro familiarization does not establish that every Security surface uses included allowance.',12)
for i,(k,t,b) in enumerate([('Explore locally','ChatGPT sign-in','Learn the native finding, evidence and patch workflow. Confirm access and limits.'),('Cloud scans','Separate billing','Token billing applies to new Cloud scans. Eligible scanning credits may apply; check settings.'),('Customer rollout','Operating requirements','Choose identities, data handling, isolation, budgets, verification and review controls.')]):
    s += card(75+i*510,335,470,440,k,t,b)
add(s,'Local Codex supports ChatGPT sign-in. The current Cloud FAQ excludes newly configured Cloud scans from included plan allowance and describes separate token charges and possible credits. Confirm account-specific settings. Source: https://learn.chatgpt.com/docs/security/faq . No live Codex Security result is claimed by this repository.')

s=base('Leave with a concrete recommendation','A good customer conversation ends with an owned next step and visible uncertainty.',13)
s += [txt(80,340,1430,90,'One service. One issue class. One accountable reviewer.',44,MINT,True)]
for i,(t,b) in enumerate([('Agree the scope','Problem, assets, data, authority'),('Define the proof','Original issue + legitimate behavior'),('Choose the decision','Success measures + expansion gate')]):
    s += card(75+i*510,490,470,280,f'0{i+1}',t,b,body_size=24)
add(s,'Summarize your assumptions and the customer decision you recommend. State the inputs you need, the owner, the expected evidence, the open limitations, and the next decision date. Invite correction. Adapt the proposed workflow to the customer rather than forcing every use case into a prebuilt pipeline.')

s=base('Sources and practical boundaries','Public product documentation supports the workflow; the architecture and scenario are independent.',14)
refs=[('Defense Factory: process and architecture','https://openai.com/the-defense-factory/'),('Daybreak: broader capability stack','https://openai.com/daybreak/'),('Cloud setup and billing boundaries','https://learn.chatgpt.com/docs/security/faq'),('Finding and fix evidence','https://learn.chatgpt.com/docs/security/plugin/fix-findings'),('Promptfoo: adversarial agent evaluation','https://www.promptfoo.dev/docs/red-team/agents/')]
for i,(title,url) in enumerate(refs):
    y=320+i*91;s += [txt(80,y,1400,36,title,25,MINT,True),txt(80,y+38,1420,33,url,19,MUTED)]
add(s,'Use the linked public documentation as the current contract. This deck contains no confidential recruiter messages, customer data, inferred internal roadmaps, or reconstructed interview questions. It is a rehearsal and architecture aid, not a required presentation or evidence of a deployed service.')

s=base('The repo\u2019s next three increments','Make one customer workflow operational before adding a broad product surface.',15)
for i,(k,t,b) in enumerate([('01 / Integrate','Persistent security cases','Wire the case lifecycle into the actual CLI. Preserve evidence, revisions, owners and decisions.'),('02 / Prove','One real capability path','Use a documented Codex Security path. Verify one bounded change and handle failure honestly.'),('03 / Evaluate','Useful review and evidence','Add a workbench over real state. Evaluate agent behavior when needed; expand from measured proof.')]):
    s += card(75+i*510,335,470,440,k,t,b)
add(s,'The next implementation work is integrating the lifecycle into the actual runtime, not adding another disconnected example. First correct readiness semantics for pending/skipped checks, policy errors and corrupt state. Then wire one real capability path with recorded evidence. Keep Cursor behind an executor adapter. Cloud/runtime context and Promptfoo evaluation should be added when they serve the customer use case. The detailed plan and acceptance criteria are in docs/prep/repo-strategy.md; these increments are proposed, not complete.')

s=base('Lead an adaptive working session','No presentation is required. Use a visual only when it helps the customer conversation.',16)
steps=[('01','Frame the problem','Outcome, stakeholders, bottleneck, constraints'),('02','Map the workflow','Assets, tools, versions, evidence and handoffs'),('03','Choose and bound','Smallest useful AI step + identity / data boundaries'),('04','Define a pilot','Proof, baseline, owners, milestones and stop criteria'),('05','Adapt and recommend','Revise assumptions; explain the next decision')]
for i,(n,t,b) in enumerate(steps):
    y=317+i*91;s += [txt(80,y+8,70,50,n,32,MINT,True),txt(175,y+8,570,50,t,29,WHITE,True),txt(770,y+13,720,50,b,24,MUTED)]
add(s,'The supplied exercise assesses discovery, cybersecurity judgment, architecture, execution planning, evidence, business impact, communication and adaptability. Practice these decisions without relying on a running app. Do not assume the scenario is the billing example. If the customer changes a data, identity, tool or rollout constraint, restate the assumption and revise the relevant design. The editable whiteboard and exercise workbook provide a flexible scaffold, not a scripted answer.')

# The core canvases come first; implementation details and examples are references.
slides = [slides[i] for i in [0,1,7,2,5,8,9,15,12,10,14,3,4,6,11,13]]
for number,(scene,_) in enumerate(slides,1):
    for item in scene:
        if item['kind']=='text' and item.get('x')==1450 and item.get('y')==845:
            item['text']=f'{number:02}'

def render_svg(scene, dest):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img">', '<title>OpenFix architecture proposal</title>', f'<defs><linearGradient id="synthwave-background" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#{BG}"/><stop offset="1" stop-color="#{BG_END}"/></linearGradient><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#{CYAN}"/></marker></defs>']
    for item in scene:
        if item['kind']=='rect':
            if item['w']==1600 and item['h']==900:
                out.extend(svg_background());continue
            stroke=f' stroke="#{item["stroke"]}"' if item.get('stroke') else ''
            out.append(f'<rect x="{item["x"]}" y="{item["y"]}" width="{item["w"]}" height="{item["h"]}" rx="12" fill="#{item["fill"]}"{stroke}/>')
        elif item['kind']=='line':
            marker=' marker-end="url(#arrow)"' if item['arrow'] else ''
            out.append(f'<line x1="{item["x1"]}" y1="{item["y1"]}" x2="{item["x2"]}" y2="{item["y2"]}" stroke="#{item["color"]}" stroke-width="3"{marker}/>')
        else:
            family='DejaVu Sans Mono,monospace' if item['mono'] else 'DejaVu Sans,Arial,sans-serif'
            for n,row in enumerate(item['text'].split('\n')):
                y=item['y']+item['size']+n*item['size']*1.26
                out.append(f'<text x="{item["x"]}" y="{y}" fill="#{item["color"]}" font-size="{item["size"]}" font-family="{family}" font-weight="{700 if item["bold"] else 400}">{escape(row)}</text>')
    out.append('</svg>');dest.write_text('\n'.join(out))

def render_png(scene, dest):
    im=background_image();d=ImageDraw.Draw(im)
    for item in scene:
        if item['kind']=='rect':
            if item['w']==1600 and item['h']==900: continue
            d.rounded_rectangle((item['x'],item['y'],item['x']+item['w'],item['y']+item['h']),radius=12,fill='#'+item['fill'],outline='#'+item['stroke'] if item.get('stroke') else None,width=1)
        elif item['kind']=='line':
            x,y,xx,yy=item['x1'],item['y1'],item['x2'],item['y2'];d.line((x,y,xx,yy),fill='#'+item['color'],width=3)
            if item['arrow']:
                angle=math.atan2(yy-y,xx-x);pts=[(xx,yy),(xx-15*math.cos(angle-.4),yy-15*math.sin(angle-.4)),(xx-15*math.cos(angle+.4),yy-15*math.sin(angle+.4))];d.polygon(pts,fill='#'+item['color'])
        else:
            font=ImageFont.truetype(MONO if item['mono'] else BOLD if item['bold'] else FONT,item['size'])
            for n,row in enumerate(item['text'].split('\n')): d.text((item['x'],item['y']+n*item['size']*1.26),row,fill='#'+item['color'],font=font,anchor='lt')
    im.save(dest)

def ppt_scene(prs, scene, notes):
    slide=prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid();slide.background.fill.fore_color.rgb=RGBColor.from_string(BG)
    for item in scene:
        if item['kind']=='rect':
            if item['w']==1600 and item['h']==900:
                ppt_background(slide);continue
            shape=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE if item['w']==1600 else MSO_SHAPE.ROUNDED_RECTANGLE, Inches(item['x']/100), Inches(item['y']/100), Inches(item['w']/100), Inches(item['h']/100))
            shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string(item['fill']);shape.line.fill.background()
            if item.get('stroke'):
                shape.line.color.rgb=RGBColor.from_string(item['stroke']);shape.line.width=Pt(.65)
            try: shape.adjustments[0]=.06
            except (IndexError,ValueError): pass
        elif item['kind']=='line':
            shape=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(item['x1']/100),Inches(item['y1']/100),Inches(item['x2']/100),Inches(item['y2']/100))
            shape.line.color.rgb=RGBColor.from_string(item['color']);shape.line.width=Pt(2)
            if item['arrow']:
                angle=math.degrees(math.atan2(item['y2']-item['y1'],item['x2']-item['x1']))
                tip=slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(item['x2']/100-.07),Inches(item['y2']/100-.07),Inches(.14),Inches(.14))
                tip.rotation=angle+90;tip.fill.solid();tip.fill.fore_color.rgb=RGBColor.from_string(item['color']);tip.line.fill.background()
        else:
            shape=slide.shapes.add_textbox(Inches(item['x']/100),Inches(item['y']/100),Inches(item['w']/100),Inches(item['h']/100))
            frame=shape.text_frame;frame.word_wrap=True
            frame.margin_left=frame.margin_right=frame.margin_top=frame.margin_bottom=0
            for n,row in enumerate(item['text'].split('\n')):
                para=frame.paragraphs[0] if n==0 else frame.add_paragraph();para.text=row
                para.font.name='DejaVu Sans Mono' if item['mono'] else 'DejaVu Sans'
                para.font.size=Pt(item['size']*.72);para.font.bold=item['bold'];para.font.color.rgb=RGBColor.from_string(item['color'])
                para.space_after=Pt(item['size']*.72*.2)
    slide.notes_slide.notes_text_frame.text=notes
    return slide

prs=Presentation();prs.slide_width=Inches(16);prs.slide_height=Inches(9)
prs.core_properties.title='OpenFix — From security signals to reviewed, verified change'
prs.core_properties.author='Markus Weldon';prs.core_properties.subject='Independent customer workflow proposal and lifecycle prototype'
for scene,notes in slides: ppt_scene(prs,scene,notes)
prs.save(OUT/'openfix-customer-workflow.pptx')

for name,scene in [('lifecycle',lifecycle()),('architecture',architecture()),('current-v1',current_v1())]:
    render_svg(scene,DIAGRAMS/f'{name}.svg');render_png(scene,DIAGRAMS/f'{name}.png')
render_png(slides[0][0],OUT/'cover.png')
notes=['# OpenFix talk track\n','This is an original rehearsal aid and independent architecture proposal. Start with discovery and use only the visuals that help.\n']
for i,(scene,note) in enumerate(slides,1):
    title=next(item['text'] for item in scene if item['kind']=='text' and item['size']==56)
    notes += [f'## {i:02}. {title.replace(chr(10), " ")}\n',note+'\n']
(OUT/'talk-track.md').write_text('\n'.join(notes))
print(f'Generated {len(slides)} slides, speaker notes, cover, and three SVG/PNG diagrams in {OUT}')
