"""Generate 8 hand-curated discovery seeds for InstaClone feed (no video, global trending)."""
import json, pathlib, sys, uuid, shutil
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/home/advaith/Desktop/Advaith/studyreel/backend")

from app.schemas import MicroTopic, Slide, Carousel
from app.renderer.render import render_carousel

# Define 8 curated posts: each with module_name, topics list (dict for MicroTopic), caption, hashtags, cover_slide, likes, views
SEEDS = [
    {
        "module_name": "AI: Attention Mechanism",
        "caption": "Attention is all you need! Transformers weigh every token against every other — no recurrence needed. How does Q·Kᵀ decide what to focus on? Save for your AI exam!",
        "hashtags": ["ai","transformer","attention","machinelearning","deeplearning","exam"],
        "cover_slide": 1,
        "likes": 142, "views": 890,
        "topics": [
            {"header": "Attention Is All You Need", "body": "Transformers weigh every token against every other to capture long-range dependencies without recurrence.", "example": "Spot it: if a model compares every token with every other, it uses attention.", "code_block": None, "language_tag": None},
            {"header": "Q K V in Attention", "body": "Query, Key, Value matrices project tokens; dot-product scores softmaxed to weight Values.", "example": "Self-test: Q asks, K is matched, V is the content returned.", "code_block": "scores = Q @ K.T / sqrt(d)\nweights = softmax(scores)", "language_tag": "python"},
            {"header": "Multi-Head Magic", "body": "Parallel heads learn syntax, semantics, position — then concat and project. More heads, richer view.", "example": "Example: one head tracks syntax while another tracks position.", "code_block": None, "language_tag": None},
        ]
    },
    {
        "module_name": "AI: RAG Grounded LLMs",
        "caption": "Stop hallucinations! RAG grounds LLMs in your own docs — chunk, embed, retrieve, generate with citations. Would you use RAG or fine-tune?",
        "hashtags": ["ai","rag","llm","vectordb","generativeai","studyreel"],
        "cover_slide": 1,
        "likes": 118, "views": 720,
        "topics": [
            {"header": "RAG: Grounded LLMs", "body": "Retrieve relevant docs, then generate — reduces hallucination by grounding answers in real data.", "example": "Spot it: an answer citing your own document likely came from RAG.", "code_block": None, "language_tag": None},
            {"header": "RAG Pipeline", "body": "Chunk → Embed → Vector DB → Top-K retrieve → Prompt + docs → LLM generates cited answer.", "example": "Try it: embed a question, retrieve 5 chunks, then prompt the LLM.", "code_block": "docs = vector_db.search(q_emb, k=5)\nanswer = llm(prompt+docs)", "language_tag": "python"},
            {"header": "When to Use RAG", "body": "Use when knowledge is private, fast-changing, or must be cited. No retraining needed.", "example": "Self-test: private, changing data with citations points to RAG.", "code_block": None, "language_tag": None},
        ]
    },
    {
        "module_name": "EV: BLDC Motor",
        "caption": "Why every EV uses BLDC? High torque, no brushes, precise control via inverter. Save this for Electrical Machines!",
        "hashtags": ["ev","bldc","electricvehicle","motors","engineering"],
        "cover_slide": 1,
        "likes": 105, "views": 640,
        "topics": [
            {"header": "BLDC vs Brushed", "body": "Brushless DC removes mechanical brushes — commutation via electronic inverter, less wear, higher efficiency.", "example": "Spot it: no brushes means an inverter must handle commutation.", "code_block": None, "language_tag": None},
            {"header": "3-Phase Inverter", "body": "6-MOSFET bridge drives 3 phases with PWM. Hall sensors give rotor position for timing.", "example": "Example: six MOSFETs switch in sequence to drive three phases.", "code_block": "pwm = sin(theta) * Vdc\nmosfet = update(pwm, hall)", "language_tag": "python"},
            {"header": "Torque Control", "body": "Field-Oriented Control decouples flux and torque — smooth acceleration, regen braking ready.", "example": "Spot it: smooth EV acceleration with separate flux control is FOC.", "code_block": None, "language_tag": None},
        ]
    },
    {
        "module_name": "EV: Battery BMS",
        "caption": "BMS is the brain of EV batteries — balancing, thermal, SOC. One bad cell can kill range. Know your pack!",
        "hashtags": ["ev","battery","bms","lithium","engineering","tech"],
        "cover_slide": 0,
        "likes": 98, "views": 590,
        "topics": [
            {"header": "Battery Pack 101", "body": "Cells in series raise voltage, parallel raises capacity. 96S = ~400V nominal.", "example": "Example: 96 cells in series give roughly 400 V nominal.", "code_block": None, "language_tag": None},
            {"header": "SOC Estimation", "body": "Coulomb counting + Kalman filter fuses voltage, current, temp for State-of-Charge.", "example": "Spot it: current integrated over time is coulomb counting.", "code_block": "soc += current * dt / capacity\nsoc = kalman(soc, voltage)", "language_tag": "python"},
            {"header": "Cell Balancing", "body": "Passive bleeds high cells via resistors; active shuttles charge. Keeps pack healthy.", "example": "Example: a resistor bleeds charge from the highest cell.", "code_block": None, "language_tag": None},
        ]
    },
    {
        "module_name": "Aero: Lift & Drag",
        "caption": "Lift vs Drag — Bernoulli + Newton together. Why cambered airfoils fly? Save for Aerodynamics!",
        "hashtags": ["aerodynamics","lift","drag","aerospace","physics"],
        "cover_slide": 0,
        "likes": 87, "views": 520,
        "topics": [
            {"header": "Lift Explained", "body": "Faster flow over curved top lowers pressure — pressure diff pushes wing up. Angle of attack adds Newton lift.", "example": "Spot it: faster air over the curved top means lower pressure.", "code_block": None, "language_tag": None},
            {"header": "Drag Types", "body": "Parasite drag from shape + skin friction; induced drag from lift — trade-off at high AoA.", "example": "Example: skin friction on a wing is parasite drag.", "code_block": None, "language_tag": None},
            {"header": "Polar Curve", "body": "Plot Cl vs Cd — best L/D at one AoA. Gliders chase it, fighters exceed it.", "example": "Spot it: the best L/D point is where the polar touches its tangent.", "code_block": "Cl = 2*pi*alpha\nCd = Cd0 + Cl**2/(pi*AR)", "language_tag": "python"},
        ]
    },
    {
        "module_name": "Aero: Takeoff Dynamics",
        "caption": "Takeoff is controlled stall — VR, rotate, V2. How does 300 tons lift off in 40 seconds?",
        "hashtags": ["aerodynamics","takeoff","aviation","flight","physics"],
        "cover_slide": 2,
        "likes": 76, "views": 460,
        "topics": [
            {"header": "V-Speeds", "body": "V1 decide, VR rotate nose up, V2 safety climb. All weight, wind, runway dependent.", "example": "Example: V1 is the speed where a rejected takeoff is still safe.", "code_block": None, "language_tag": None},
            {"header": "Ground Roll", "body": "Thrust > drag + rolling resistance. Flaps increase Cl at low speed, shorten run.", "example": "Spot it: flaps let the wing make lift at a lower ground speed.", "code_block": None, "language_tag": None},
            {"header": "Rotation Physics", "body": "Elevator pitches up, increases AoA, lift exceeds weight — liftoff. Gear retract reduces drag.", "example": "Example: pitching the nose up raises AoA until lift exceeds weight.", "code_block": "L = 0.5*rho*V**2*S*Cl\nif L > W: liftoff", "language_tag": "python"},
        ]
    },
    {
        "module_name": "CS: OS Scheduling",
        "caption": "CPU Scheduling decides who runs next — FCFS vs SJF vs Round Robin. Which starves? Save for OS exam!",
        "hashtags": ["operatingsystem","scheduling","os","computerscience","exam"],
        "cover_slide": 1,
        "likes": 68, "views": 410,
        "topics": [
            {"header": "FCFS & SJF", "body": "FCFS simple but convoy effect. SJF optimal avg wait but needs burst prediction.", "example": "Spot it: a long first job delaying everyone else is the convoy effect.", "code_block": None, "language_tag": None},
            {"header": "Round Robin", "body": "Time slice Q gives fairness. Small Q = responsive but overhead; large Q = FCFS.", "example": "Example: a 4 ms quantum gives each ready process a turn.", "code_block": "while ready:\n  run(p, Q)\n  queue.append(p)", "language_tag": "python"},
            {"header": "Priority & Starvation", "body": "Priority ages waiting jobs to avoid starvation. MLFQ learns burst adaptively.", "example": "Spot it: a low-priority job that never runs is starving.", "code_block": None, "language_tag": None},
        ]
    },
    {
        "module_name": "CS: DBMS Indexing",
        "caption": "Indexing makes DB fast — B+ tree vs Hash. Why does LIKE '%a%' kill your index? Save this!",
        "hashtags": ["dbms","indexing","database","sql","computerscience"],
        "cover_slide": 1,
        "likes": 55, "views": 340,
        "topics": [
            {"header": "Why Index?", "body": "Full scan O(N) vs index O(log N). B+ tree keeps keys sorted for range queries.", "example": "Example: an index turns a full table scan into a tree lookup.", "code_block": None, "language_tag": None},
            {"header": "B+ Tree vs Hash", "body": "B+ tree for range and sort; hash for exact match only. Choose per query.", "example": "Spot it: a range query needs a B+ tree, not a hash index.", "code_block": "CREATE INDEX idx ON t(col);\nSELECT * WHERE col=10", "language_tag": "sql"},
            {"header": "Covering Index", "body": "Include all queried cols in index — query served from index alone, no table lookup.", "example": "Example: SELECT name FROM users uses an index on (name).", "code_block": None, "language_tag": None},
        ]
    },
]

OUT_BASE = pathlib.Path("/tmp/seed_renders")
INSTACLONE_SLIDES = pathlib.Path("/home/advaith/Desktop/Advaith/studyreel/instaclone/data/slides")
INSTACLONE_POSTS = pathlib.Path("/home/advaith/Desktop/Advaith/studyreel/instaclone/data/posts.json")
SEED_JSON = pathlib.Path("/home/advaith/Desktop/Advaith/studyreel/seed/discovery_posts.json")

# Clean old seed renders
import shutil
if OUT_BASE.exists():
    shutil.rmtree(OUT_BASE)
OUT_BASE.mkdir(parents=True, exist_ok=True)

generated = []
now = datetime.now(timezone.utc)
for idx, seed in enumerate(SEEDS):
    # Stagger created_at: newest is idx 0 (now - idx*6h)
    created_at = (now - timedelta(hours=idx*6)).isoformat()
    # Build carousel
    topics = [MicroTopic(**t) for t in seed["topics"]]
    slides = [Slide(slide_type=("mixed" if t.code_block else "text"), index=i, topic=t) for i, t in enumerate(topics)]
    carousel_id = f"seed{idx+1:02d}{uuid.uuid4().hex[:4]}"
    carousel = Carousel(carousel_id=carousel_id, module_name=seed["module_name"], slides=slides)
    out_dir = OUT_BASE / carousel_id
    pngs = render_carousel(carousel, out_dir=out_dir)
    print(f"[{idx+1}/8] {seed['module_name']} -> {len(pngs)} PNGs {out_dir}")

    post_id = carousel_id  # use carousel_id as post_id for seed
    target = INSTACLONE_SLIDES / post_id
    target.mkdir(parents=True, exist_ok=True)
    slides_meta = []
    for i, slide in enumerate(slides):
        fname = f"slide_{i+1:02d}.png"
        src = out_dir / fname
        dst = target / fname
        if src.exists():
            shutil.copy(src, dst)
        slides_meta.append({"slide_number": i+1, "image_path": f"/slides/{post_id}/{fname}", "header": slide.topic.header})

    post = {
        "post_id": post_id,
        "media_id": post_id,
        "slides": slides_meta,
        "caption": seed["caption"],
        "hashtags": seed["hashtags"],
        "cover_slide": seed["cover_slide"],
        "likes": seed["likes"],
        "views": seed["views"],
        "created_at": created_at
    }
    generated.append(post)

# Save seed JSON (versioned source)
SEED_JSON.parent.mkdir(parents=True, exist_ok=True)
SEED_JSON.write_text(json.dumps(generated, indent=2), encoding="utf-8")
print(f"Wrote seed JSON {SEED_JSON} with {len(generated)} posts")

# Merge into posts.json: keep existing user posts, prepend seeds sorted by trending? For now replace with seeds + existing non-seed?
# Load existing
import json as js
existing = []
if INSTACLONE_POSTS.exists():
    try:
        existing = json.loads(INSTACLONE_POSTS.read_text(encoding="utf-8"))
    except:
        existing = []
# Keep only non-seed posts (those whose post_id not starting with seed)
keep = [p for p in existing if not p.get("post_id","").startswith("seed")]
# Combine: seeds + keep, then save sorted by trending later at read, but store as is
combined = generated + keep
INSTACLONE_POSTS.write_text(json.dumps(combined, indent=2), encoding="utf-8")
print(f"Wrote {INSTACLONE_POSTS} total {len(combined)} posts (seeds {len(generated)} + kept {len(keep)})")
# Also copy seed renders to seed/output for versioning?
seed_out = pathlib.Path("/home/advaith/Desktop/Advaith/studyreel/seed/output")
seed_out.mkdir(exist_ok=True)
# copy seed json already, also copy pngs? skip heavy
print("Done")
