#!/usr/bin/env python3
"""Rebuild OpenFix's original presentation and diagrams. No network required."""
from pathlib import Path
import math
import sys
import base64
from io import BytesIO
import textwrap
from functools import lru_cache
from xml.sax.saxutils import escape
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.xmlchemy import OxmlElement
from lxml import etree
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/prep'
DIAGRAMS = OUT / 'diagrams'
OUT.mkdir(parents=True, exist_ok=True)
DIAGRAMS.mkdir(parents=True, exist_ok=True)
BG, BG_END, CARD = '10071C', '28103F', '160C25'
MINT, WHITE, MUTED, CORAL, LINE = 'E4C7FF', 'FFFFFF', 'F0E9FC', 'FFACDD', '9C7ABF'
CYAN, GRID, CAPTION = '9DEEFF', '6C3A8A', 'C4B1DB'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'

@lru_cache(maxsize=40)
def measure_font(size, bold=False, mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else FONT, int(size))

def wrap_pixels(value, width, size, bold=False, mono=False):
    font=measure_font(size,bold,mono)
    rows=[]
    for paragraph in value.split('\n'):
        row=''
        for word in paragraph.split():
            candidate=(row+' '+word).strip()
            if row and font.getlength(candidate)>width:
                rows.append(row);row=word
            else:row=candidate
        rows.append(row)
    return '\n'.join(rows)

def txt(x, y, w, h, text, size=30, color=WHITE, bold=False, mono=False, href=None):
    return dict(kind='text', x=x, y=y, w=w, h=h, text=wrap_pixels(text,w,size,bold,mono), size=size, color=color, bold=bold, mono=mono, href=href)

def rect(x, y, w, h, fill=CARD, stroke=None):
    if stroke is None and fill == CARD:
        stroke = LINE
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

def base(title, subtitle='', number=1, label='REPOSITORY WALKTHROUGH / IMPLEMENTATION REFERENCE'):
    s = [rect(0, 0, 1600, 900, BG), rect(70, 62, 42, 7, MINT),
        txt(130, 47, 1300, 36, 'OPENFIX / ' + label, 20, MINT, True),
         txt(70, 125, 1470, 100, title, 56, WHITE, True),
         txt(74, 226, 1430, 90, subtitle, 30, MUTED),
         line(70, 829, 1530, 829, LINE, False),
         txt(73, 850, 1360, 28, 'OpenFix 0.2 • Repository walkthrough / implementation reference', 17, CAPTION),
         txt(1450, 845, 90, 35, f'{number:02}', 21, MINT, True)]
    return s

def card(x, y, w, h, kicker, title, body, color=MINT, body_size=32):
    return [rect(x, y, w, h), txt(x+25, y+22, w-50, 38, kicker.upper(), 20, color, True),
            txt(x+25, y+76, w-50, 92, title, 36, WHITE, True),
            txt(x+25, y+177, w-50, h-190, body, body_size, MUTED)]

def node(x, y, w, h, num, title, sub, accent=MINT):
    return [rect(x, y, w, h), txt(x+20, y+15, 60, 35, num, 22, accent, True),
            txt(x+20, y+58, w-40, 45, title, 24, WHITE, True),
            txt(x+20, y+108, w-40, 66, sub, 23, MUTED)]

def lifecycle(number=6):
    s = base('Each case carries evidence and decisions', 'Implemented local stages preserve evidence and require explicit decisions.', number)
    xs = [75, 460, 845, 1230]
    upper = [('01', 'Import + correlate', 'Keep each source observation'), ('02', 'Enrich + assess', 'Reuse, refresh, resolve gaps'),
             ('03', 'Validate', 'Confirmed / disproved / uncertain'), ('04', 'Accept scope', 'Human owner + priority')]
    lower = [('08', 'Human review', 'Approve the exact patch hash'), ('07', 'Verify patch', 'Security + legitimate behavior'),
             ('06', 'Record exact diff', 'Committed base / head + digest'), ('05', 'Propose change', 'Packet or optional Cursor')]
    for x,(n,t,b) in zip(xs,upper):s += node(x,320,295,182,n,t,b)
    for a,b in zip(xs,xs[1:]):s += [line(a+298,410,b-8,410,MINT)]
    for x,(n,t,b) in zip(xs,lower):s += node(x,580,295,182,n,t,b)
    s += [line(1377,504,1377,573,MINT)]
    for a,b in zip(xs[1:],xs):s += [line(a-8,670,b+302,670,MINT)]
    s += [txt(75,518,1440,52,'Failed checks return to remediation. Merge, deployment and post-change closure remain separate.',24,CORAL)]
    return s

def architecture(number=5):
    s=base('The implemented local architecture','One CLI owns durable cases; adapters and execution profiles have explicit boundaries.',number)
    for y,title,sub in [(315,'Security exports','SARIF + tool JSON'),(465,'Context exports','Repo / asset / revision'),(615,'Customer brief','Scope + people + limits')]:
        s += [rect(70,y,350,116),txt(90,y+16,310,38,title,28,WHITE,True),txt(90,y+63,310,47,sub,23,MUTED),line(424,y+58,510,515,MINT)]
    s += [rect(520,370,460,280),txt(545,397,410,48,'OpenFix local CLI',36,WHITE,True),
          txt(545,467,410,162,'Persistent JSON cases\nEvidence + assessment\nDecision and patch gates\nHash-chained audit',28,MUTED)]
    for y,title,sub in [(315,'Reference checks','Trusted local tenant profile'),(465,'Read-only workbench','Cases, provenance, gaps, gates'),(615,'Agent handoff','Task packets / optional Cursor')]:
        s += [rect(1080,y,450,116),txt(1100,y+16,410,38,title,29,WHITE,True),txt(1100,y+63,410,47,sub,24,MUTED),line(984,515,1070,y+58,MINT)]
    s += [txt(75,771,1440,38,'Local processes and actor labels are implemented. Isolated workers and enterprise authentication are not.',24,CORAL)]
    return s

def current_v1():
    s=base('Legacy Cursor path (v1)','Retained execution integration; OpenFix 0.2 now defaults to persistent local cases.',1,'LEGACY EXECUTOR REFERENCE')
    labels=[('01','Import findings','SARIF / JSON'),('02','Route by policy','Fix / human / noise'),('03','Cursor agent','Generate remediation PR'),('04','Observe PR CI','Tests + scanner jobs'),('05','Human review','Normal merge process')]
    for i,(n,t,b) in enumerate(labels):
        x=65+i*310;s += node(x,350,270,195,n,t,b)
        if i<4:s += [line(x+275,447,x+300,447,MINT)]
    s += [rect(75,620,1450,140),txt(100,643,1390,45,'OpenFix 0.2 adds durable cases, reusable evidence and explicit change gates.',29,MINT,True),txt(100,704,1390,40,'Cursor dispatch is optional. A returned patch still needs exact-artifact verification and human review.',25,MUTED)]
    return s

def rows(scene, values, y=330, step=90, left=370, body_size=29):
    for i,(a,b) in enumerate(values):
        yy=y+i*step
        scene += [rect(75,yy,1450,step-12),txt(98,yy+17,left-28,step-22,a,body_size,MINT,True),txt(105+left,yy+17,1385-left,step-22,b,body_size,WHITE)]
    return scene

def picture(x,y,w,h,path,crop=None):
    return dict(kind='image',x=x,y=y,w=w,h=h,path=str(path),crop=crop)

slides=[]
def add(scene,notes):slides.append((scene,notes))

s=base('Evidence to action.','OpenFix 0.2 • A local security-case workflow\nMarkus Weldon • Repository walkthrough and implementation reference',1,'FINDINGS INTELLIGENCE')
s[3]['h']=130;s[4]['y']=276;s[4]['h']=100
for i,(title,body) in enumerate([('PRESERVE','What security tools already know'),('INVESTIGATE','The gaps that change a decision'),('VERIFY','The exact change and its behavior')]):
    s += card(75+i*510,445,470,320,f'0{i+1}',title,body,body_size=32)
add(s,'Use this as an optional companion while reading the repository and explaining its value. The default CLI persists cases, imports evidence, assesses context, validates supported cases, records acceptance, binds a committed diff, verifies it and records human review. The code and tests include synthetic reports and trusted local fixture checks. There is no live AI execution claim, live scanner integration, merge or deployment to show. The interview is a collaborative working session that requires no prepared presentation. Follow the customer scenario and use a relevant file or diagram only if it helps.')

s=base('What AI adds to a mature security workflow','Keep established DevSecOps controls; add adaptive investigation and proposals behind evidence gates.',2)
for i,(k,t,b) in enumerate([('Mature DevSecOps','Established controls','Scanners, tests, CI policy, ownership and release controls remain the foundation.'),('Potential AI contribution','Adaptive investigation','Reason across code and context. Propose focused checks and bounded changes.'),('OpenFix role','Independent evidence gates','Preserve provenance, expose gaps, verify exact changes and record human decisions.')]):
    s += card(75+i*510,335,470,440,k,t,b,body_size=31)
add(s,'Mature DevSecOps already includes investigation, correlation, risk assessment, automation, testing and human review. The opportunity for AI is flexible reasoning across unfamiliar code and evidence, generating hypotheses, selecting useful follow-up work and proposing changes with less bespoke glue. Those benefits are hypotheses to measure, not properties proven by these fixtures. OpenFix implements the context and decision substrate: preserve what tools already know, expose missing or conflicting evidence, constrain a proposed action and independently verify the exact change. Its portable packets and optional executor can host an AI contribution, but the repository does not currently execute an OpenAI model. Explain value through code boundaries, tests and tradeoffs rather than promising autonomy or replacing CI.')

s=base('Many observations, one persistent case','Implemented adapters normalize source exports while retaining their original evidence.',3)
rows(s,[('SARIF','Rules, locations, tool identity and result properties'),('GHAS + Snyk','Code-scanning alerts and dependency findings'),('Codex Security JSON','Scan findings, manifest, coverage and deferred surfaces'),('Case correlation','Link matching observations; retain each source record'),('Durable local state','JSON records, atomic writes, exclusive lock and audit chain')],y=325,step=90,left=355,body_size=28)
add(s,'Adapters import local SARIF, GitHub code-scanning exports, Snyk JSON and supported Codex Security scan JSON, along with a generic finding envelope. These are file adapters, not live service connectors. Original observations remain linked to artifact digests and source identity. Correlation is deterministic and conservative; it is not a universal semantic deduplication engine. The local store uses atomic replacement, a writer lock and a hash-chained event audit with a state checkpoint. These mechanisms do not provide authenticated multi-tenant storage or an external tamper-proof ledger.')

s=base('Reuse evidence and preserve its authority','The evidence plan says what to reuse, refresh, collect or resolve.',4)
rows(s,[('Subject','Repository, revision and asset must match the case'),('Freshness','Use collection time / expiry; flag stale or unknown dates'),('Provenance','Keep producer, authority, source reference and artifact digest'),('Conflicts','Retain competing current claims; ask for a decision'),('Validation','Producer verdicts stay assertions until explicitly reviewed')],y=325,step=90,left=340,body_size=29)
add(s,'Evidence records preserve upstream assertions separately from local evidence and explicit reviewed adoption of external validation. Context joins require the exact repository, asset and revision. Subject-mismatched evidence cannot silently change current context. The default freshness window is seven days, with explicit expiry supported; missing dates remain unknown and future timestamps are flagged. The freshest record per origin, producer and kind contributes to current assessment. Fresh contradictions remain visible instead of being overwritten by source precedence. The plan can reuse with provenance, refresh or verify, collect, resolve a conflict, or review upstream validation. A new or expired context record invalidates accepted scope where required.')

add(architecture(5),'This diagram describes the implemented local architecture. The default src/openfix.mjs CLI calls the workflow modules and persistent store. File adapters supply findings and context, and a customer brief records goals and boundaries. The same stored cases feed assessment, the read-only HTML workbench and agent task packets. The built-in tenant-isolation profile runs trusted local fixture code only after explicit execution authorization. Its supported subject is CWE-639 at src/invoices.mjs:3; mismatched findings remain inconclusive. Optional Cursor dispatch calls the retained executor bridge. Neither local child-process bounds nor named actor labels are a production isolation or identity boundary. The repository imports supported scan output; it does not invoke a live Codex Security scan.')

add(lifecycle(6),'The path is implemented through the default CLI. Imported evidence is assessed before additional investigation. Validation can confirm, disprove or remain inconclusive. Acceptance records owner, priority, rationale and context. A committed diff is then recorded with exact base, head and digest. A different actor runs the approved verification profile and a reviewer approves the exact patch hash. New context or a replacement patch can invalidate earlier decisions. Review does not merge or deploy. Rollout and closure commands require separate change records, exact deployed revision and post-change evidence; the local reference example stops at approved_for_change.')

s=base('A repository map for the conversation','Follow evidence from source imports through assessment, decisions and executable invariants.',7)
repo='https://github.com/markusweldon/openfix/blob/main/'
for i,(label,path,why) in enumerate([
    ('Import','src/workflow/import.mjs','Keep reports and producer evidence.'),
    ('Assess','src/workflow/enrich.mjs','Check subject, freshness and conflicts.'),
    ('Act','src/workflow/operations.mjs','Accept, verify and review exact changes.'),
    ('Enforce','src/lifecycle/workflow.mjs','Enforce lifecycle and patch identity.'),
    ('Prove','tests/workflow.test.mjs','Test stale context and broken fixes.'),
]):
    y=325+i*91
    s += [rect(75,y,1450,79),txt(98,y+19,175,44,label,30,MINT,True),
          txt(290,y+24,520,40,path,25,CYAN,mono=True,href=repo+path),
          txt(835,y+18,665,60,why,28,WHITE)]
add(s,'Start at src/openfix.mjs for the CLI boundary and src/workflow/store.mjs for persistence. Then follow import.mjs to enrich.mjs to operations.mjs and the lifecycle state machine. The file links open the public repository. Read the tests alongside the implementation: tests/workflow.test.mjs covers workflow behavior, while tests/lifecycle.test.mjs concentrates on decision invariants. src/workflow/report.mjs is the read-only report surface. operations.mjs exports task packets; providers.mjs describes adapters and optional Cursor dispatch. The useful conversation is why these boundaries exist, which customer problem they address and where implementation limits remain. No application or model needs to run during the walkthrough.')

s=base('Read the example as four distinct decisions','Synthetic source fixtures and local checks exercise supported, disproved and uncertain paths.',8)
rows(s,[('Vulnerable lookup','Runtime confirmed → accepted → verified patch → reviewed'),('Protected lookup','Cross-tenant access blocked → disproved → dismissed'),('Dependency issue','No installed validation profile → inconclusive'),('Cloud context','Conflicting service owners → resolve the conflict')],y=333,step=100,left=355,body_size=29)
s += [txt(80,756,1430,48,'Code and tests separate a useful finding, a protected path, missing proof and conflicting context.',25,CYAN)]
add(s,'The synthetic reports produce five observations and four correlated cases. The tenant-isolation profile executes four times: vulnerable baseline, protected baseline, deliberately broken patch and corrected patch. The dependency profile is unavailable, creating a fifth attempted check with an incomplete outcome, not a successful reproduction. The protected case is disproved and dismissed. The cloud owner contradiction remains unresolved. Report the denominator honestly: these reference checks demonstrate workflow mechanics and negative cases, not model performance, generalized vulnerability coverage or a customer ROI result.')

s=base('A false fix reveals the verification contract','Read the deny-all and tenant-scoped changes against security and legitimate-behavior assertions.',9)
for i,(k,t,b,c) in enumerate([('Deliberately bad fix','Deny all requests','Security check: passed\nLegitimate behavior: failed\n\nVerification fails.\nHuman approval is blocked.',CORAL),('Corrected committed diff','Enforce tenant ownership','Security check: passed\nLegitimate behavior: passed\n\nVerification passes.\nReviewer approves the hash.',CYAN)]):
    s += card(75+i*750,335,700,440,k,t,b,c,body_size=31)
add(s,'The reference fixture initially returns another tenant invoice. The first committed patch denies every request. It blocks the attacker but also breaks the legitimate owning tenant, so regression verification fails and the workflow rejects an approval attempt. The corrected committed patch adds the tenant predicate and preserves the legitimate lookup. Both checks pass and the reviewer approves that exact hash. The reference code edit is deterministic; it provides a testable example rather than evidence of model-generated remediation. This is evidence of an important evaluation property: security-only success cannot justify a broken product.')

s=base('Approval belongs to an exact change','A plausible fix description is insufficient evidence for publication.',10)
rows(s,[('Accepted scope','Owner, priority, rationale and context recorded'),('Artifact identity','Real git diff: committed base + head + SHA-256'),('Independent check','Verifier label differs from the patch author'),('Review gate','Passing security + regression checks, exact hash'),('After review','Normal publication, merge and deployment controls')],y=325,step=90,left=360,body_size=29)
add(s,'Patch recording binds a real git diff from the recorded base to a committed head, hashes the binary diff and rejects more than twenty changed files. Verification checks the repository snapshot, exact head and digest before executing the selected profile. The reference verifier permits only invoice-file changes; changes beyond that surface remain incomplete. Missing prerequisites or an artifact mismatch produce an incomplete result rather than success. A local verifier label must differ from the author label. Review requires passing independent verification and the exact patch hash. Labels are audit assertions supplied by the operator, not authenticated identities or a separation-of-duties enforcement boundary. Merge, deployment and post-change closure remain separate decisions.')

s=base('Give agents a bounded security case','Implemented handoffs preserve evidence, scope and expected outputs.',11)
for i,(k,t,b) in enumerate([('Default','Portable task packet','Export case.json and instructions with provenance, gaps and permitted actions.'),('Native guidance','.agents skills','Use the approved security workflow; treat findings and tool output as untrusted data.'),('Optional executor','Cursor dispatch','Actor + execution + draft-PR authorization. Verify and review the returned patch.')]):
    s += card(75+i*510,335,470,440,k,t,b,body_size=31)
add(s,'The agent packet carries the case subject, customer brief, observations, current evidence, gaps, action boundary and expected output contract. Instructions distinguish producer assertions, source analysis and runtime proof, and treat code comments, finding text and tool results as data rather than instructions. Packets are handoff artifacts; they do not themselves invoke an OpenAI model. The repository includes .agents skills for case investigation and patch verification. Optional Cursor dispatch reuses the existing executor, requires accepted scope, --execute, --publish-draft and a named --actor, and is separate from the local reference checks. Returned PRs still need exact-patch import, verification and review.')

s=base('Use native security capabilities','OpenFix complements security capabilities with customer evidence and change decisions.',12)
rows(s,[('Defense Factory','Continuous operating model and reference architecture'),('Daybreak','Broader governed cyber-defense capability stack'),('Codex Security','Native code investigation, evidence, validation and fixes'),('Promptfoo','AI application and agent adversarial evaluation'),('OpenFix 0.2','Local evidence reuse, customer context and exact-change gates')],y=325,step=90,left=355,body_size=28)
add(s,'This alignment uses public descriptions, not a claim about internal OpenAI architecture or an official integration. Start with native Codex Security functionality and use the documented contract of the customer environment. OpenFix imports supported Codex scan JSON; live scanning is outside the implemented local path. Defense Factory describes a continuous operating approach, and Daybreak encompasses a wider stack. Promptfoo helps evaluate AI applications and adversarial agent behavior; it is relevant when a model-driven step exists. Promptfoo execution is not implemented in the repository. ChatGPT Pro familiarization does not establish that every Cloud scan is included; confirm product access and billing separately.')

s=base('What remains for production','Keep the implemented controls and remaining boundaries visible.',13)
for i,(k,t,b,c) in enumerate([('Implemented','Inspectable local controls','Persistent cases, exact joins, freshness checks, artifact binding, named actors and audit history.',MINT),('Still required','Production boundaries','Authenticated identities, isolated workers, egress and secret controls, durable service storage.',CORAL),('Still to prove','Real integrations + scale','Live connectors, model behavior, broader validators, customer-scale evals and operational recovery.',CYAN)]):
    s += card(75+i*510,335,470,440,k,t,b,c,body_size=31)
add(s,'The trusted local reference profile is a bounded child process, not a container, VM or network sandbox for arbitrary customer code. Actor labels do not establish authentication, RBAC or enterprise separation of duties. Hash-chain checking and local file permissions are useful inspectability measures, not externally anchored audit guarantees. The read-only HTML workbench is local and not an authenticated hosted service. File adapters and optional dispatch do not imply live scanner integrations. Before a customer rollout, agree approved data, identity, execution isolation, egress, credentials, retention, cancellation, recovery, observability and budget controls. Production publication authority needs a distinct design.')

s=base('Lead a customer working session','The provided scenario sets the scope. No presentation or advance work is required.',14)
steps=[('01','Discover the problem','Outcome, people, bottleneck, constraints'),('02','Map the evidence','Existing tools, assets, revisions and trusted context'),('03','Choose a useful AI step','Native capability, integration gap and authority'),('04','Plan proof and rollout','Pilot, failure cases, owners and decision gate'),('05','Adapt in real time','Restate changed assumptions and revise the plan')]
for i,(n,t,b) in enumerate(steps):
    y=325+i*90;s += [txt(80,y+8,70,55,n,34,MINT,True),txt(175,y+8,570,55,t,32,WHITE,True),txt(770,y+9,720,78,b,30,MUTED)]
add(s,'Treat this as a collaborative customer working session. The repository is optional supporting evidence for a design discussion. Ask clarifying questions, state assumptions and explain tradeoffs. Discover the current workflow, stakeholders, approved data, constraints and desired business outcome. If new information changes a tool, identity, data or deployment assumption, revise the affected architecture and pilot instead of defending the original design. Use the whiteboard only when it helps. The billing example is an invented practice case and must not be assumed to match the provided customer scenario.')

s=base('A pilot should lead to an operating decision','One service, one issue class and one accountable reviewer; measure the baseline first.',15)
for i,(k,t,b) in enumerate([('Baseline','Know today’s work','Investigation effort, review time, accepted outcomes, delay and existing controls.'),('Evaluate','Include failure paths','Valid, disproved, stale, conflicting and missing proof. Bad fixes, cost and latency.'),('Decide','Expand, revise or stop','Agree evidence, owners, milestones and limits. Expand one scope dimension at a time.')]):
    s += card(75+i*510,335,470,440,k,t,b,body_size=31)
add(s,'Agree the business problem and baseline before setting targets. Measure investigator and reviewer effort, accepted fixes, time to a supported decision, false fixes, proof gaps and operating cost. Include sample size and incomplete attempts. The local reference checks provide no model-quality score or measured ROI. A focused customer pilot should add one approved real source and one useful AI contribution, with labeled positive and negative cases, explicit execution boundaries, failure handling and an accountable reviewer. End with a concrete next owner, evidence requirement, date and stop/revise/expand decision.')

s=base('Sources and evidence boundaries','Public workflow references plus an inspectable, reproducible local implementation.',16)
refs=[('Defense Factory: operating model','https://openai.com/the-defense-factory/'),('Daybreak: broader security stack','https://openai.com/daybreak/'),('Codex Security: finding and fix evidence','https://learn.chatgpt.com/docs/security/plugin/fix-findings'),('Codex Security: access and Cloud billing','https://learn.chatgpt.com/docs/security/faq'),('Promptfoo: agent adversarial evaluation','https://www.promptfoo.dev/docs/red-team/agents/')]
for i,(title,url) in enumerate(refs):
    y=332+i*91;s += [txt(80,y,1400,40,title,30,MINT,True),txt(80,y+42,1420,36,url.removeprefix('https://').removeprefix('www.'),24,CYAN,href=url)]
add(s,'Use current public product documentation as the product contract, and the repository source and tests as the implementation evidence. This deck contains no confidential recruiter correspondence, customer data, inferred internal roadmap or reconstructed interview question. OpenFix is an independent project. Synthetic source fixtures and trusted local checks exercise the workflow. They establish no live security-scan coverage, OpenAI model quality, merge or deployment result. Rebuild commands and detailed evidence live in the repository, outside these presentation slides.')

def image_bytes(item):
    im=Image.open(item['path']).convert('RGB')
    if item.get('crop'):
        x,y,xx,yy=item['crop'];im=im.crop((round(x*im.width),round(y*im.height),round(xx*im.width),round(yy*im.height)))
    im=ImageOps.pad(im,(round(item['w']),round(item['h'])),color='#'+CARD,centering=(.5,.5))
    out=BytesIO();im.save(out,format='PNG');return out.getvalue()

def render_svg(scene, dest):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img">', '<title>OpenFix local workflow</title>', f'<defs><linearGradient id="synthwave-background" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#{BG}"/><stop offset="1" stop-color="#{BG_END}"/></linearGradient><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#{CYAN}"/></marker></defs>']
    for item in scene:
        if item['kind']=='rect':
            if item['w']==1600 and item['h']==900:
                out.extend(svg_background());continue
            stroke=f' stroke="#{item["stroke"]}"' if item.get('stroke') else ''
            out.append(f'<rect x="{item["x"]}" y="{item["y"]}" width="{item["w"]}" height="{item["h"]}" rx="12" fill="#{item["fill"]}"{stroke}/>')
        elif item['kind']=='line':
            marker=' marker-end="url(#arrow)"' if item['arrow'] else ''
            out.append(f'<line x1="{item["x1"]}" y1="{item["y1"]}" x2="{item["x2"]}" y2="{item["y2"]}" stroke="#{item["color"]}" stroke-width="3"{marker}/>')
        elif item['kind']=='image':
            data=base64.b64encode(image_bytes(item)).decode()
            out.append(f'<image x="{item["x"]}" y="{item["y"]}" width="{item["w"]}" height="{item["h"]}" href="data:image/png;base64,{data}"/>')
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
        elif item['kind']=='image':
            im.paste(Image.open(BytesIO(image_bytes(item))),(round(item['x']),round(item['y'])))
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
                shape.line.color.rgb=RGBColor.from_string(item['stroke']);shape.line.width=Pt(1.0)
            try: shape.adjustments[0]=.06
            except (IndexError,ValueError): pass
        elif item['kind']=='line':
            shape=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(item['x1']/100),Inches(item['y1']/100),Inches(item['x2']/100),Inches(item['y2']/100))
            shape.line.color.rgb=RGBColor.from_string(item['color']);shape.line.width=Pt(2)
            if item['arrow']:
                angle=math.degrees(math.atan2(item['y2']-item['y1'],item['x2']-item['x1']))
                tip=slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(item['x2']/100-.07),Inches(item['y2']/100-.07),Inches(.14),Inches(.14))
                tip.rotation=angle+90;tip.fill.solid();tip.fill.fore_color.rgb=RGBColor.from_string(item['color']);tip.line.fill.background()
        elif item['kind']=='image':
            slide.shapes.add_picture(BytesIO(image_bytes(item)),Inches(item['x']/100),Inches(item['y']/100),width=Inches(item['w']/100),height=Inches(item['h']/100))
        else:
            shape=slide.shapes.add_textbox(Inches(item['x']/100),Inches(item['y']/100),Inches(item['w']/100),Inches(item['h']/100))
            frame=shape.text_frame;frame.word_wrap=True
            frame.margin_left=frame.margin_right=frame.margin_top=frame.margin_bottom=0
            for n,row in enumerate(item['text'].split('\n')):
                para=frame.paragraphs[0] if n==0 else frame.add_paragraph();para.text=row
                para.font.name='DejaVu Sans Mono' if item['mono'] else 'DejaVu Sans'
                para.font.size=Pt(item['size']*.72);para.font.bold=item['bold'];para.font.color.rgb=RGBColor.from_string(item['color'])
                para.space_after=Pt(item['size']*.72*.2)
                if item.get('href'):
                    for run in para.runs:
                        run.hyperlink.address=item['href'];run.font.color.rgb=RGBColor.from_string(item['color'])
    slide.notes_slide.notes_text_frame.text=notes
    return slide

prs=Presentation();prs.slide_width=Inches(16);prs.slide_height=Inches(9)
# PowerPoint/LibreOffice can substitute the theme hyperlink colors even when a
# run has an explicit text fill. Keep both visited and unvisited links legible.
for rel in prs.slide_master.part.rels.values():
    if rel.reltype.endswith('/theme'):
        theme=etree.fromstring(rel.target_part.blob)
        for tag,color in [('hlink',CYAN),('folHlink',MINT)]:
            theme_node=theme.find(f'.//{{http://schemas.openxmlformats.org/drawingml/2006/main}}{tag}')
            for child in list(theme_node):theme_node.remove(child)
            fill=etree.SubElement(theme_node,'{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr')
            fill.set('val',color)
        rel.target_part._blob=etree.tostring(theme,xml_declaration=True,encoding='UTF-8',standalone=True)
prs.core_properties.title='OpenFix — From security signals to reviewed, verified change'
prs.core_properties.author='Markus Weldon';prs.core_properties.subject='OpenFix 0.2 repository walkthrough and implementation reference'
for scene,notes in slides: ppt_scene(prs,scene,notes)
prs.save(OUT/'openfix-customer-workflow.pptx')

if '--deck-only' not in sys.argv:
    mermaid = {
        'architecture': """flowchart LR
      A[Security file exports: SARIF GHAS Snyk Codex JSON] --> D[OpenFix local CLI]
      B[Context exports: exact repository asset revision] --> D
      C[Customer brief: outcome scope constraints] --> D
      D <--> E[Persistent JSON cases + evidence + audit]
      D --> F[Trusted local reference checks]
      D --> G[Read-only workbench]
      D --> H[Agent packets / optional Cursor dispatch]
      H --> I[Committed diff + verification + exact-hash review]
      I --> J[Separate publication and deployment controls]
      K[Remaining: isolated workers and enterprise authentication]
    """,
        'lifecycle': """flowchart LR
      A[Import + correlate observations] --> B[Enrich + assess existing evidence]
      B --> C[Validate supported subject]
      C --> D[Accept owner priority and scope]
      C --> Q[Disproved / inconclusive / conflict]
      D --> E[Propose bounded change]
      E --> F[Record committed base head and diff digest]
      F --> G[Verify security + legitimate behavior]
      G -->|Failed or incomplete| E
      G --> H[Human review of exact hash]
      H --> I[Separate publication deployment and closure]
    """,
        'current-v1': """flowchart LR
      A[Legacy v1: import findings] --> B[Policy routing]
      B --> C[Optional Cursor executor]
      C --> D[PR CI observation]
      D --> E[Human review]
      F[OpenFix 0.2 now defaults to persistent local case workflow]
    """,
    }
    mermaid['implemented-workflow'] = mermaid['lifecycle']
    for name, content in mermaid.items():
        (DIAGRAMS/f'{name}.mmd').write_text(content)

    for name,scene in [('lifecycle',lifecycle()),('architecture',architecture()),('implemented-workflow',lifecycle()),('current-v1',current_v1())]:
        render_svg(scene,DIAGRAMS/f'{name}.svg');render_png(scene,DIAGRAMS/f'{name}.png')
render_png(slides[0][0],OUT/'cover.png')
notes=['# OpenFix talk track\n','OpenFix 0.2 repository walkthrough and implementation reference. Use the code, tests and diagrams to explain value and tradeoffs. This optional companion does not require running the application or a live AI service.\n']
for i,(scene,note) in enumerate(slides,1):
    title=next(item['text'] for item in scene if item['kind']=='text' and item['size']==56)
    notes += [f'## {i:02}. {title.replace(chr(10), " ")}\n',note+'\n']
(OUT/'talk-track.md').write_text('\n'.join(notes))
print(f'Generated {len(slides)} slides, speaker notes and cover in {OUT}' + (' (diagram assets preserved)' if '--deck-only' in sys.argv else '; rebuilt four diagram families'))
