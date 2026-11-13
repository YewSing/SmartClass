"""Build the SmartClass design diagrams as one Lucid Standard Import document (T103).

Run from the repo root:  python docs/diagrams/build_lucid.py
Writes docs/diagrams/smartclass-diagrams.lucid.json, which is imported into Lucidchart
with the Lucid connector (lucid_create_diagram_from_specification, product "lucidchart",
use_assisted_layout false).

The ERD page is read from the backend's SQLAlchemy metadata, the same schema
`alembic upgrade head` builds, so it can be regenerated whenever a migration lands.
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().with_name("smartclass-diagrams.lucid.json")

# Colours: clients blue, backend green, data/external orange, Shino's modules purple.
BLUE, GREEN, ORANGE, PURPLE, GREY, YELLOW = "#DCEBFF", "#E3F4E6", "#FFF1DC", "#EEE3F7", "#F2F3F5", "#FFF8C5"
LINE = {"color": "#3A3F47", "width": 2, "style": "solid"}
DASH = {"color": "#6B7280", "width": 2, "style": "dashed"}
THIN = {"color": "#4B5563", "width": 1, "style": "solid"}
TOP, BOTTOM, LEFT, RIGHT = (0.5, 0), (0.5, 1), (0, 0.5), (1, 0.5)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html(title, body=None, size=14, align="center"):
    """Bold title plus optional body lines. Sizes are canvas px (Lucid's pt renders ~2.2x larger)."""
    t = f"<b>{esc(title)}</b>"
    if body:
        t += "<br>" + "<br>".join(esc(b) for b in body)
    return f'<p style="font-size:{size}px;text-align:{align}">{t}</p>'


def shape(sid, x, y, w, h, text=None, kind="rectangle", fill=None, **extra):
    s = {"id": sid, "type": kind, "boundingBox": {"x": x, "y": y, "w": w, "h": h}}
    if text is not None:
        s["text"] = text
    if fill:
        s["style"] = {"fill": {"type": "color", "color": fill}}
    s.update(extra)
    return s


def container(sid, x, y, w, h, title, fill="#FFFFFF"):
    return {"id": sid, "type": "roundedRectangleContainer", "boundingBox": {"x": x, "y": y, "w": w, "h": h},
            "containerTitle": {"text": title}, "assistedLayout": False,
            "style": {"fill": {"type": "color", "color": fill}, "stroke": {"color": "#9CA3AF", "width": 1, "style": "solid"}}}


_line_no = [0]


def line(a, b, label=None, end="arrow", start="none", stroke=None, pos=0.5, side="top", ends=None, kind=None):
    """A connector from shape a to shape b. `ends` pins both attachment points ((x,y),(x,y)).
    Pinned lines are straight unless kind="elbow"; unpinned lines are elbow smart lines."""
    _line_no[0] += 1
    e1 = {"type": "shapeEndpoint", "style": start, "shapeId": a}
    e2 = {"type": "shapeEndpoint", "style": end, "shapeId": b}
    if ends:
        e1["position"] = {"x": ends[0][0], "y": ends[0][1]}
        e2["position"] = {"x": ends[1][0], "y": ends[1][1]}
    ln = {"id": f"l{_line_no[0]}", "lineType": kind or ("straight" if ends else "elbow"),
          "endpoint1": e1, "endpoint2": e2, "stroke": stroke or LINE}
    if label:
        ln["text"] = [{"text": f'<span style="font-size:12px">{esc(label)}</span>', "position": pos, "side": side}]
    return ln


def title_shape(pid, text, sub=None, w=1800):
    body = f'<p style="font-size:30px;text-align:left"><b>{esc(text)}</b></p>'
    if sub:
        body += f'<p style="font-size:13px;text-align:left">{esc(sub)}</p>'
    return shape(f"{pid}_title", 40, -120, w, 100, body, kind="text")


# ─── 1. System architecture ──────────────────────────────────────────────────

def page_architecture():
    p = "arch"
    S, L = [], []
    S.append(title_shape(p, "SmartClass - System Architecture",
                         "Three clients, one FastAPI backend that holds all rules, PostgreSQL + pgvector, and the simulated UM SPeCTRUM (Moodle)."))
    S.append(container("arch_c1", 40, 40, 460, 920, "Clients", "#F7FAFF"))
    S.append(container("arch_c2", 600, 40, 840, 920, "FastAPI backend (Python, uvicorn :8000)", "#F6FBF7"))
    S.append(container("arch_c3", 1540, 40, 460, 920, "Data and external services", "#FFFBF5"))
    bw, bh = 300, 170
    S.append(shape("arch_student", 120, 140, bw, bh, html("Student app", ["React Native + Expo SDK 54", "Android / iOS (Expo Go)", "attendance, face enrolment,", "AI assistant"]), fill=BLUE))
    S.append(shape("arch_lect", 120, 390, bw, bh, html("Lecturer app", ["same Expo code on phone", "and in a browser (Expo web)", "admin area: browser only"]), fill=BLUE))
    S.append(shape("arch_dev", 120, 640, bw, bh, html("Camera device client", ["Raspberry Pi camera or webcam", "detects faces locally,", "sends only face crops"]), fill=BLUE))
    # Each box sits on the row of the client or external service it talks to, so lines stay short.
    boxes = [
        ("arch_api", 680, 140, "API routers", ["REST + JWT roles", "(student / lecturer / admin)", "WebSocket /ws live events"]),
        ("arch_loops", 1060, 140, "Background loops", ["session scheduler, Moodle sync,", "attendance sync, materials sync,", "low-attendance alert, crop cleanup"]),
        ("arch_att", 680, 390, "Attendance services", ["sessions, 4 statuses, overrides,", "flags, reports, CSV export,", "read interface for Module 7"]),
        ("arch_moodle_cl", 1060, 390, "Moodle client", ["token login, course + enrolment", "sync, mod_attendance write,", "material download"]),
        ("arch_face", 680, 640, "Face services", ["InsightFace buffalo_sc (CPU),", "3-frame voting, card check", "with RapidOCR (local)"]),
        ("arch_kb", 1060, 640, "AI assistant (services/kb)", ["parse, chunk, embed (bge-small),", "hybrid search, cited answers,", "study tools, trends"]),
    ]
    for sid, x, y, t, body in boxes:
        S.append(shape(sid, x, y, bw, bh, html(t, body), fill=GREEN))
    ex = 1620
    S.append(shape("arch_db", ex, 130, bw, 150, html("PostgreSQL 16 + pgvector", ["Docker, port 5433", "21 tables, face + text vectors"]), kind="database", fill=ORANGE))
    S.append(shape("arch_moodle", ex, 350, bw, 150, html("Moodle 4.5 (simulated SPeCTRUM)", ["Docker, own compose file", "accounts, courses, materials,", "mod_attendance"]), fill=ORANGE))
    S.append(shape("arch_llm", ex, 570, bw, 130, html("LLM API", ["OpenAI-compatible", "(DeepSeek or Gemini)"]), kind="cloud", fill=ORANGE))
    S.append(shape("arch_yt", ex, 770, bw, 110, html("YouTube Data API", ["optional video suggestions"]), kind="cloud", fill=ORANGE))
    L += [
        line("arch_student", "arch_api", "HTTPS JSON + WebSocket", ends=(RIGHT, LEFT)),
        line("arch_lect", "arch_api", "same API (phone or browser)", ends=((1, 0.3), (0, 0.85)), pos=0.5, side="bottom"),
        line("arch_dev", "arch_face", "POST /device/faces + key", ends=(RIGHT, LEFT)),
        line("arch_c2", "arch_db", "SQLAlchemy async", stroke=DASH, ends=((1, 0.18), LEFT)),
        line("arch_moodle_cl", "arch_moodle", "web services", ends=(RIGHT, LEFT)),
        line("arch_kb", "arch_llm", "chat", ends=((1, 0.35), LEFT)),
        line("arch_kb", "arch_yt", "search", stroke=DASH, ends=((1, 0.75), LEFT), side="bottom"),
    ]
    S.append(shape("arch_note", 600, 1000, 840, 60,
                   html("All backend parts read and write PostgreSQL (dashed arrow).", None, 13), kind="text"))
    return {"id": p, "title": "1 System Architecture", "shapes": S, "lines": L}


# ─── 2. Module diagram ───────────────────────────────────────────────────────

def page_modules():
    p = "mod"
    S, L = [], []
    S.append(title_shape(p, "SmartClass - Module Diagram",
                         "8 modules from the proposal. Yew Sing builds M1, M3, M4, M8; Shino builds M2, M5, M6, M7. Arrows show what one module uses from another."))
    S.append(container("mod_ys", 40, 40, 780, 580, "Yew Sing (M1, M3, M4, M8)", "#F6FBF7"))
    S.append(container("mod_sh", 1000, 40, 780, 580, "Shino (M2, M5, M6, M7)", "#FAF6FD"))
    w, h = 260, 150
    mods = [
        ("mod_m4", 120, 140, GREEN, "M4 Face Recognition", ["camera devices, recognition,", "flags, feedback events"]),
        ("mod_m3", 480, 140, GREEN, "M3 Attendance Management", ["sessions, statuses, overrides,", "reports, Moodle sync"]),
        ("mod_m1", 120, 380, GREEN, "M1 User Management", ["Moodle login, accounts,", "PDPA consent, face enrolment"]),
        ("mod_m8", 480, 380, GREEN, "M8 AI Learning Assistant", ["cited Q&A over materials,", "study tools, trends"]),
        ("mod_m2", 1080, 140, PURPLE, "M2 Dashboard + Notifications", ["consumes events", "(notify.emit)"]),
        ("mod_m7", 1440, 140, PURPLE, "M7 Learning Analytics", ["reads attendance", "(FR-313 interface)"]),
        ("mod_m6", 1080, 380, PURPLE, "M6 AI Quiz", ["uses retrieval (FR-814);", "quiz lock for chat"]),
        ("mod_m5", 1440, 380, PURPLE, "M5 Classroom Interaction", ["participation", "(UI mock in apps)"]),
    ]
    for sid, x, y, fill, t, b in mods:
        S.append(shape(sid, x, y, w, h, html(t, b), fill=fill))
    S.append(shape("mod_moodle", 300, 740, 260, 150, html("Moodle (SPeCTRUM)", ["accounts, courses,", "materials, attendance"]), kind="database", fill=ORANGE))
    L += [
        line("mod_m4", "mod_m3", "mark Present / Late", ends=(RIGHT, LEFT)),
        line("mod_m1", "mod_m4", "face embeddings", ends=(TOP, BOTTOM), side="middle"),
        line("mod_m1", "mod_m3", "enrolments", ends=((0.8, 0), (0.2, 1)), pos=0.6, side="bottom"),
        line("mod_m3", "mod_m2", "events", stroke=DASH, ends=(RIGHT, LEFT)),
        line("mod_m3", "mod_m7", "read interface", stroke=DASH, ends=((0.7, 0), TOP), kind="elbow", pos=0.5),
        line("mod_m8", "mod_m6", "retrieval API", stroke=DASH, ends=(RIGHT, LEFT)),
        line("mod_m1", "mod_moodle", "login + sync", ends=(BOTTOM, (0.2, 0)), kind="elbow", pos=0.6, side="middle"),
        line("mod_m8", "mod_moodle", "materials", ends=(BOTTOM, (0.8, 0)), kind="elbow", pos=0.6, side="middle"),
        line("mod_m3", "mod_moodle", "attendance sync", ends=((1, 0.8), RIGHT), kind="elbow", pos=0.5, side="middle"),
    ]
    return {"id": p, "title": "2 Module Diagram", "shapes": S, "lines": L}


# ─── 3a/3b. Class diagrams ───────────────────────────────────────────────────

def text_lines(items, w):
    per = max(1, (w - 30) // 10)   # umlClass text is about 10 px per character
    return sum(max(1, math.ceil(len(s) / per)) for s in items)


def uml(sid, x, y, w, title, props, methods=()):
    """Lucid grows a umlClass to fit its text, so size it generously from wrapped line counts."""
    ph = 26 * text_lines(props, w) + 30 if props else 34
    mh = 26 * text_lines(methods, w) + 30 if methods else 34
    h = 44 + ph + mh
    return {"id": sid, "type": "umlClass", "boundingBox": {"x": x, "y": y, "w": w, "h": h},
            "title": title, "properties": list(props), "methods": list(methods),
            "propertiesHeight": round(ph / (ph + mh), 2)}, h


def stack(S, col_x, spec, w, gap):
    for x, items in zip(col_x, spec):
        y = 40
        for sid, t, props, methods in items:
            s, h = uml(sid, x, y, w, t, props, methods)
            S.append(s)
            y += h + gap


def page_class_domain():
    p = "cls"
    S, L = [], []
    S.append(title_shape(p, "SmartClass - Class Diagram (domain model)",
                         "SQLAlchemy models in backend/app/models (main attributes). Lines show multiplicity (many - one)."))
    w = 330
    spec = [
        [("c_audit", "AuditLog", ["+ action: str", "+ target_type, target_id", "+ old_val, new_val", "+ ts: datetime"], []),
         ("c_user", "User", ["+ email: str", "+ role: student|lecturer|admin", "+ status: active|inactive", "+ moodle_user_id: int"], []),
         ("c_student", "Student", ["+ matric_no: str", "+ programme: str", "+ faculty: str"], []),
         ("c_lect", "Lecturer", ["+ staff_id: str", "+ dept: str"], [])],
        [("c_course", "Course", ["+ code: str", "+ name: str", "+ moodle_course_id: int"], []),
         ("c_occ", "ClassOccurrence", ["+ type: LECTURE|TUTORIAL", "+ day_of_week: str", "+ start_time, end_time", "+ room: str"], []),
         ("c_enrol", "Enrollment", ["+ student_id", "+ occurrence_id"], []),
         ("c_cam", "Camera", ["+ device_id: str", "+ room: str", "+ key_hash: str", "+ last_heartbeat_at"], [])],
        [("c_sess", "AttendanceSession", ["+ status: scheduled|open|closed|", "  needs_confirmation|cancelled", "+ starts_at, ends_at", "+ source: schedule|manual", "+ moodle_sync_status: pending|", "  synced|failed|conflict"], []),
         ("c_rec", "AttendanceRecord", ["+ status: present|late|", "  absent|excused", "+ detected_at", "+ source: student_flag|null", "+ override_by: User"], []),
         ("c_flag", "AttendanceFlag", ["+ status: pending|confirmed|", "  rejected", "+ reject_reason: str"], []),
         ("c_unm", "UnmatchedFace", ["+ embedding: vector(512)", "+ image: bytes (purged)", "+ similarity: float"], [])],
        [("c_consent", "FaceConsent", ["+ version: str", "+ accepted_at", "+ withdrawn_at"], []),
         ("c_fenrol", "FaceEnrolment", ["+ status: active|pending_review|", "  blocked|rejected|withdrawn|reset", "+ check_reasons: json", "+ face_score, ocr_matric"], []),
         ("c_fimg", "FaceEnrolmentImage", ["+ kind: selfie|card", "+ data: bytes (deleted", "  on decision)"], []),
         ("c_femb", "FaceEmbedding", ["+ embedding: vector(512)"], [])],
        [("c_mat", "KbMaterial", ["+ title, file_name", "+ status: pending|indexed|", "  no_text|unsupported|error", "+ chunk_count: int"], []),
         ("c_chunk", "KbChunk", ["+ text: str", "+ location (page / slide)", "+ embedding: vector(384)", "+ tsv: tsvector"], []),
         ("c_chat", "AiChatSession", ["+ title: str", "+ student or lecturer owner"], []),
         ("c_msg", "AiChatMessage", ["+ role: user|assistant", "+ content: str", "+ citations: json", "+ topic, kind, payload"], [])],
    ]
    stack(S, [40, 450, 860, 1270, 1680], spec, w, 110)
    m = lambda a, b, la, ends, pos=0.5, side="top", kind=None: line(a, b, la, end="none", ends=ends, pos=pos, side=side, kind=kind)
    L += [
        m("c_audit", "c_user", "* - 1 actor", (BOTTOM, TOP), side="middle"),
        m("c_student", "c_user", "1 - 1", (TOP, BOTTOM), side="middle"),
        m("c_lect", "c_user", "1 - 1", (LEFT, LEFT), kind="elbow", side="middle"),
        m("c_occ", "c_course", "* - 1", (TOP, BOTTOM), side="middle"),
        m("c_enrol", "c_occ", "* - 1", (TOP, BOTTOM), side="middle"),
        m("c_enrol", "c_student", "* - 1", (LEFT, (1, 0.5)), pos=0.3),
        m("c_occ", "c_lect", "* - 0..1", ((0, 0.8), (1, 0.3)), pos=0.7, side="bottom"),
        m("c_sess", "c_occ", "* - 1", ((0, 0.6), RIGHT), pos=0.5),
        m("c_rec", "c_sess", "* - 1", (TOP, BOTTOM), side="middle"),
        m("c_flag", "c_rec", "* - 1 session", (TOP, BOTTOM), side="middle"),
        m("c_unm", "c_flag", "* - 1 session", (TOP, BOTTOM), side="middle"),
        m("c_cam", "c_sess", "0..1 - * room camera", (RIGHT, (0, 0.9)), pos=0.5, side="bottom"),
        m("c_fenrol", "c_consent", "* - 1 student", (TOP, BOTTOM), side="middle"),
        m("c_fimg", "c_fenrol", "* - 1", (TOP, BOTTOM), side="middle"),
        m("c_femb", "c_fimg", "* - 1 student", (TOP, BOTTOM), side="middle"),
        m("c_chunk", "c_mat", "* - 1", (TOP, BOTTOM), side="middle"),
        m("c_msg", "c_chat", "* - 1", (TOP, BOTTOM), side="middle"),
    ]
    S.append(shape("cls_note", 40, 1500, 900, 110,
                   html("Not drawn as lines", ["Student 1-* FaceConsent, FaceEnrolment, FaceEmbedding, AttendanceRecord, AttendanceFlag;",
                                               "Course 1-* KbMaterial, AiChatSession; User 1-* overrides and flag decisions.",
                                               "Vertical neighbours in a column are linked through the student or session named on the line."], 13),
                   kind="note", fill=YELLOW))
    return {"id": p, "title": "3a Class Diagram (domain)", "shapes": S, "lines": L}


def page_class_services():
    p = "svc"
    S, L = [], []
    S.append(title_shape(p, "SmartClass - Class Diagram (services)",
                         "Service modules in backend/app/services (Python modules drawn as classes, main public functions). Dashed arrow = imports and calls."))
    sv = "«service» "
    spec = [
        [("s_auth", sv + "moodle_auth", [], ["authenticate(username, password)", "get_user_token(...)", "read_profile(token)"]),
         ("s_msync", sv + "moodle_sync", [], ["sync_all(db, client)", "sync_user(db, user, courses)", "moodle_sync_loop()"]),
         ("s_audit", sv + "audit_service", [], ["write_log(db, actor, action, ...)"]),
         ("s_consent", sv + "consent_service", [], ["active_consent(db, student_id)", "require_current_consent(...)"])],
        [("s_sched", sv + "session_schedule", [], ["tick(db, now)", "open_session_for(db, occ, date)", "start_now / extend / confirm", "session_scheduler_loop()"]),
         ("s_sess", sv + "session_service", [], ["close_session(id, db)", "get_session_counts(id, db)"]),
         ("s_amsync", sv + "attendance_moodle_sync", [], ["sync_session(db, id, client)", "sync_soon / queue_resync", "resolve_conflict(...)", "attendance_moodle_sync_loop()"])],
        [("s_rec", sv + "recognition_service", [], ["recognise_frame(...)", "match_embedding(db, emb, occ)", "vote(camera, session, ids, now)"]),
         ("s_att", sv + "attendance_service", [], ["status_for_recognition(session, t)", "mark_present(...)", "low_attendance_monitor()"]),
         ("s_flags", sv + "attendance_flags", [], ["create_flag(db, student, session)", "confirm_flag / reject_flag", "store_unmatched / purge_unmatched"])],
        [("s_dev", sv + "device_service", [], ["authenticate(db, key)", "issue_key(camera)", "is_online(camera)"]),
         ("s_fver", sv + "face_verification", [], ["verify_card(...)", "check_quality(img, lines, ...)", "read_card / match_faces"])],
        [("s_ingest", sv + "kb.sync + kb.ingest", [], ["sync_course(db, course, client)", "ingest_file(db, course, meta, data)", "kb_sync_loop()"]),
         ("s_asst", sv + "kb.assistant", [], ["answer_question(db, chat, course, q)", "parse_answer(raw, passages)"]),
         ("s_search", sv + "kb.search", [], ["search_materials(db, course, q, k)", "material_passages(db, material)"]),
         ("s_llm", sv + "kb.llm", [], ["chat(messages, max_tokens)", "chat_json(messages, ...)"])],
    ]
    stack(S, [40, 520, 1000, 1480, 1960], spec, 400, 120)
    # Dependencies = the `from app.services import ...` lines between these modules.
    deps = [("s_auth", "s_msync"), ("s_msync", "s_audit"), ("s_sched", "s_sess"), ("s_sched", "s_audit"),
            ("s_att", "s_sess"), ("s_sess", "s_amsync"), ("s_amsync", "s_audit"), ("s_rec", "s_att"),
            ("s_rec", "s_flags"), ("s_rec", "s_sched"), ("s_flags", "s_amsync"), ("s_flags", "s_att"),
            ("s_asst", "s_search"), ("s_asst", "s_llm")]
    L += [line(a, b, None, end="openArrow", stroke=DASH) for a, b in deps]
    S.append(shape("svc_note", 1480, 700, 400, 130,
                   html("Not in the arrows", ["Routers (backend/app/routers) call these", "services; routers/device.py uses", "device_service to check X-Device-Key."], 13),
                   kind="note", fill=YELLOW))
    return {"id": p, "title": "3b Class Diagram (services)", "shapes": S, "lines": L}


# ─── 4. ERD (from the real schema) ───────────────────────────────────────────

def load_schema():
    sys.path.insert(0, str(ROOT / "backend"))
    import app.models  # noqa: F401  registers every table
    from app.core.database import Base
    from sqlalchemy.dialects import postgresql

    dialect = postgresql.dialect()
    tables = {}
    for t in Base.metadata.sorted_tables:
        cols = []
        for c in t.columns:
            typ = c.type.compile(dialect=dialect).lower().replace("timestamp without time zone", "timestamp")
            fk = next(iter(c.foreign_keys), None)
            cols.append({"name": c.name, "type": typ, "pk": c.primary_key, "nullable": c.nullable,
                         "fk": fk.column.table.name if fk is not None else None})
        tables[t.name] = cols
    return tables


ERD_COLUMNS = [
    ["users", "students", "lecturers", "audit_logs"],
    ["courses", "class_occurrences", "enrollments", "cameras"],
    ["attendance_sessions", "attendance_records"],
    ["attendance_flags", "unmatched_faces", "face_review_entries"],
    ["face_consents", "face_enrolments", "face_enrolment_images", "face_embeddings"],
    ["kb_materials", "kb_chunks"],
    ["ai_chat_sessions", "ai_chat_messages"],
]


def page_erd(tables):
    p = "erd"
    S, L = [], []
    S.append(title_shape(p, "SmartClass - Entity Relationship Diagram",
                         "Generated from backend/app/models (the schema alembic upgrade head builds): 21 tables. PK primary key, FK foreign key, ! not null. Crow's foot = many, bar = one, circle = optional."))
    placed = [n for col in ERD_COLUMNS for n in col]
    missing = sorted(set(tables) - set(placed))
    if missing:
        raise SystemExit(f"ERD_COLUMNS is missing tables: {missing}")
    w = 340
    for ci, names in enumerate(ERD_COLUMNS):
        y = 40
        for name in names:
            rows = []
            for c in tables[name]:
                tag = "PK " if c["pk"] else ("FK " if c["fk"] else "")
                req = "" if c["nullable"] else " !"
                rows.append(f"{tag}{c['name']} : {c['type']}{req}")
            h = 40 + 18 * (len(rows) + 1)
            body = (f'<p style="font-size:14px;text-align:center"><b>{esc(name)}</b></p>'
                    f'<p style="font-size:12px;text-align:left">' + "<br>".join(esc(r) for r in rows) + "</p>")
            S.append(shape(f"t_{name}", 40 + ci * (w + 110), y, w, h, body, fill="#F4F8FC"))
            y += h + 80
    for name, cols in tables.items():
        for c in cols:
            if c["fk"]:
                L.append(line(f"t_{name}", f"t_{c['fk']}", None, start="zeroOrMore",
                              end="zeroOrOne" if c["nullable"] else "exactlyOne", stroke=THIN))
    return {"id": p, "title": "4 ERD", "shapes": S, "lines": L}


# ─── 5. Activity diagrams (swim lanes) ───────────────────────────────────────

LANE_W, ROW_H, BOX_W, BOX_H, LANE_TOP = 340, 160, 250, 100, 70


def activity(pid, title, sub, lanes, steps, flows):
    """lanes: [(name, fill)]; steps: (id, lane, row, text, kind);
    flows: (a, b, label, from_port, to_port, line_kind). Ports are pinned so lines leave and
    enter on chosen sides instead of being routed through other boxes."""
    S, L = [title_shape(pid, title, sub)], []
    rows = max(s[2] for s in steps) + 1
    h = LANE_TOP + rows * ROW_H + 40
    S.append({"id": f"{pid}_lanes", "type": "swimLanes", "boundingBox": {"x": 40, "y": 40, "w": LANE_W * len(lanes), "h": h},
              "vertical": True, "assistedLayout": False, "titleBar": {"height": 50, "verticalText": False},
              "lanes": [{"title": n, "width": LANE_W, "headerFill": "#1F4E79", "laneFill": f} for n, f in lanes]})
    for sid, lane, row, text, kind in steps:
        bw, bh = {"decision": (230, 120), "terminator": (230, 80)}.get(kind, (BOX_W, BOX_H))
        x = 40 + lane * LANE_W + (LANE_W - bw) / 2
        y = 40 + LANE_TOP + row * ROW_H + (ROW_H - bh) / 2
        S.append(shape(f"{pid}_{sid}", x, y, bw, bh, f'<p style="font-size:13px;text-align:center">{esc(text)}</p>', kind=kind, fill="#FFFFFF"))
    for a, b, label, p1, p2, kind in flows:
        L.append(line(f"{pid}_{a}", f"{pid}_{b}", label or None, ends=(p1, p2), kind=kind, pos=0.5, side="middle"))
    return {"id": pid, "title": title.split(" - ")[-1], "shapes": S, "lines": L}


S_, E_ = "straight", "elbow"


def page_act_attendance():
    lanes = [("Server scheduler", GREY), ("Camera device", BLUE), ("Server recognition", GREEN),
             ("Student app", BLUE), ("Lecturer app", BLUE), ("Moodle sync loop", ORANGE)]
    steps = [
        ("start", 0, 0, "15 min before the class starts", "terminator"),
        ("open", 0, 1, "Open the attendance session (room camera attached)", "process"),
        ("detect", 1, 1, "Detect faces in each frame (on the device)", "process"),
        ("send", 1, 2, "POST face crops to /device/faces with the device key", "process"),
        ("match", 2, 2, "Embed crop (InsightFace), match class students, cosine >= 0.40", "process"),
        ("matched", 2, 3, "Matched?", "decision"),
        ("unm", 2, 4, "Store unmatched crop (purged later)", "process"),
        ("votes", 2, 5, "Seen in 3 frames in a row?", "decision"),
        ("mark", 2, 6, "Record Present (before cut-off) or Late; first match wins", "process"),
        ("flag", 3, 4, "Not recognised: student taps 'I'm here'", "process"),
        ("review", 4, 4, "Review flag with the closest crop: confirm or reject", "process"),
        ("banner", 3, 7, "Show 'attendance recorded' banner", "process"),
        ("close", 0, 8, "Class ends: close session, unmarked students become Absent", "process"),
        ("override", 4, 9, "Optional override (e.g. Excused), reason optional, audited", "process"),
        ("sync", 5, 10, "Send statuses to mod_attendance; retry with backoff; re-sync after override", "process"),
        ("end", 5, 11, "Statuses visible in SPeCTRUM", "terminator"),
    ]
    flows = [
        ("start", "open", "", BOTTOM, TOP, S_),
        ("open", "detect", "", RIGHT, LEFT, S_),
        ("detect", "send", "", BOTTOM, TOP, S_),
        ("send", "match", "", RIGHT, LEFT, S_),
        ("match", "matched", "", BOTTOM, TOP, S_),
        ("matched", "unm", "no", BOTTOM, TOP, S_),
        ("matched", "votes", "yes", RIGHT, RIGHT, E_),
        ("votes", "mark", "yes", BOTTOM, TOP, S_),
        ("votes", "detect", "not yet", LEFT, LEFT, E_),
        ("unm", "flag", "", RIGHT, LEFT, S_),
        ("flag", "review", "", RIGHT, LEFT, S_),
        ("review", "mark", "confirm", BOTTOM, (1, 0.3), E_),
        ("mark", "banner", "", (1, 0.75), TOP, E_),
        ("mark", "close", "", BOTTOM, RIGHT, E_),
        ("close", "override", "", BOTTOM, LEFT, E_),
        ("override", "sync", "", BOTTOM, LEFT, E_),
        ("sync", "end", "", BOTTOM, TOP, S_),
    ]
    return activity("act1", "SmartClass - Activity: face attendance for one class",
                    "Modules 3 and 4. Scheduled session, recognition with voting, student flag, lecturer review, close, Moodle sync.",
                    lanes, steps, flows)


def page_act_enrolment():
    lanes = [("Student app", BLUE), ("Server", GREEN), ("Lecturer (or admin fallback)", BLUE)]
    steps = [
        ("start", 0, 0, "Profile > Face enrolment", "terminator"),
        ("consent", 0, 1, "Read and accept the PDPA consent (current version)", "process"),
        ("capture", 0, 2, "Take guided selfies and a photo of the UM matric card", "process"),
        ("quality", 1, 2, "Check card photo quality (blur, glare, dark)", "process"),
        ("qok", 1, 3, "Quality OK?", "decision"),
        ("retake", 0, 3, "Show retake message; after 2 tries allow 'submit anyway'", "process"),
        ("checks", 1, 4, "OCR matric + name, selfie consistency, selfie vs card face", "process"),
        ("pass", 1, 5, "All checks pass?", "decision"),
        ("pending", 2, 5, "Status pending_review: photos kept for review", "process"),
        ("active", 1, 6, "Status active: store 512-d embedding, delete photos", "process"),
        ("decide", 2, 6, "Approve or reject (with reason)?", "decision"),
        ("rejected", 2, 7, "Status rejected: photos deleted, student may retry", "process"),
        ("status", 0, 8, "Student sees the status (active / pending / rejected)", "process"),
        ("end", 0, 9, "Done (withdrawing consent deletes the face data)", "terminator"),
    ]
    flows = [
        ("start", "consent", "", BOTTOM, TOP, S_),
        ("consent", "capture", "", BOTTOM, TOP, S_),
        ("capture", "quality", "", RIGHT, LEFT, S_),
        ("quality", "qok", "", BOTTOM, TOP, S_),
        ("qok", "retake", "no (blocked)", LEFT, RIGHT, S_),
        ("retake", "capture", "", TOP, BOTTOM, S_),
        ("qok", "checks", "yes", BOTTOM, TOP, S_),
        ("checks", "pass", "", BOTTOM, TOP, S_),
        ("pass", "active", "yes", BOTTOM, TOP, S_),
        ("pass", "pending", "no", RIGHT, LEFT, S_),
        ("pending", "decide", "", BOTTOM, TOP, S_),
        ("decide", "active", "approve", LEFT, RIGHT, S_),
        ("decide", "rejected", "reject", BOTTOM, TOP, S_),
        ("active", "status", "", BOTTOM, (1, 0.25), E_),
        ("rejected", "status", "", BOTTOM, (1, 0.75), E_),
        ("status", "end", "", BOTTOM, TOP, S_),
    ]
    return activity("act2", "SmartClass - Activity: face self-enrolment",
                    "Module 1 (FR-109 to FR-117). The card check runs locally (RapidOCR + InsightFace); no photo is kept after a decision.",
                    lanes, steps, flows)


def page_act_chat():
    lanes = [("Student app", BLUE), ("Server (kb.assistant)", GREEN), ("LLM API", ORANGE)]
    steps = [
        ("start", 0, 0, "Assistant tab: pick a course, type a question", "terminator"),
        ("save", 1, 1, "Save the question in the chat", "process"),
        ("quiz", 1, 2, "Quiz attempt active (Module 6)?", "decision"),
        ("lock", 0, 2, "Show 'assistant paused during the quiz'", "process"),
        ("rewrite", 1, 3, "Follow-up? Rewrite it as a standalone query", "process"),
        ("search", 1, 4, "Hybrid search: pgvector meaning + full-text keywords, top passages", "process"),
        ("llm", 2, 4, "Answer from the passages with numbered citations; label the topic", "process"),
        ("ok", 1, 5, "LLM answered?", "decision"),
        ("err", 0, 5, "503: 'assistant unavailable, try again' (nothing saved)", "process"),
        ("format", 1, 6, "Remove LaTeX, renumber citations 1, 2, 3, save the answer", "process"),
        ("show", 0, 7, "Show the answer with citation chips", "process"),
        ("pdf", 0, 8, "Tap a citation: open the file at that page", "process"),
        ("end", 0, 9, "Done (also: summary, flashcards, practice)", "terminator"),
    ]
    flows = [
        ("start", "save", "", BOTTOM, LEFT, E_),
        ("save", "quiz", "", BOTTOM, TOP, S_),
        ("quiz", "lock", "yes", LEFT, RIGHT, S_),
        ("quiz", "rewrite", "no", BOTTOM, TOP, S_),
        ("rewrite", "search", "", BOTTOM, TOP, S_),
        ("search", "llm", "", RIGHT, LEFT, S_),
        ("llm", "ok", "", BOTTOM, RIGHT, E_),
        ("ok", "err", "no", LEFT, RIGHT, S_),
        ("ok", "format", "yes", BOTTOM, TOP, S_),
        ("format", "show", "", BOTTOM, RIGHT, E_),
        ("show", "pdf", "", BOTTOM, TOP, S_),
        ("pdf", "end", "", BOTTOM, TOP, S_),
    ]
    return activity("act3", "SmartClass - Activity: AI assistant question",
                    "Module 8 (FR-805 to FR-809). Answers are grounded in the course's own Moodle materials.",
                    lanes, steps, flows)


# ─── 6. Navigation diagrams ──────────────────────────────────────────────────

def nav_page(pid, title, sub, tabs, extra_lines=()):
    """tabs: [(tab label, fill, [screens top to bottom])]; Login on top, tab bar under it."""
    S, L = [title_shape(pid, title, sub)], []
    n = len(tabs)
    col_w, bw, bh = 300, 230, 70
    total = n * col_w
    S.append(shape(f"{pid}_login", 40 + total / 2 - 130, 40, 260, 80, html("Login", ["Moodle username + password"], 13), kind="terminator", fill=GREY))
    S.append(shape(f"{pid}_tabs", 40, 200, total - 70, 70, html("Bottom tab bar (side bar on wide web screens)", None, 14), fill=YELLOW))
    L.append(line(f"{pid}_login", f"{pid}_tabs", "signed in", ends=(BOTTOM, TOP), side="middle"))
    for i, (tab, fill, screens) in enumerate(tabs):
        x = 40 + i * col_w
        prev = f"{pid}_tabs"
        for j, scr in enumerate(screens):
            sid = f"{pid}_{i}_{j}"
            name, note = scr if isinstance(scr, tuple) else (scr, None)
            S.append(shape(sid, x, 350 + j * (bh + 70), bw, bh, html(name, [note] if note else None, 13), fill=fill))
            if j == 0:
                L.append(line(prev, sid, tab, ends=((round((x + bw / 2 - 40) / (total - 70), 4), 1), TOP), side="middle"))
            else:
                L.append(line(prev, sid, None, ends=(BOTTOM, TOP)))
            prev = sid
    for a, b, label in extra_lines:
        L.append(line(f"{pid}_{a}", f"{pid}_{b}", label, stroke=DASH, ends=((0.5, 1), (0, 0.75)), kind="elbow", pos=0.7, side="bottom"))
    return S, L


def page_nav_student():
    tabs = [("Home", BLUE, ["Home"]),
            ("Attendance", BLUE, ["Attendance", ("AttSessionDetail", "one class"), ("AttReportStatus", "'I'm here' flag")]),
            ("Assistant", BLUE, [("Assistant", "chat + study tools"), ("AssistantPdf", "cited page"), "Flashcards", "Practice"]),
            ("Participation", PURPLE, [("Participation", "Shino, M5 mock"), "PartSessionPerf"]),
            ("Profile", BLUE, ["Profile", ("FaceEnrolment", "status"), ("FaceConsent", "PDPA"), ("FaceCapture", "selfies + card")])]
    S, L = nav_page("navs", "SmartClass - Navigation: student app",
                    "mobile/student/src/navigation/AppNavigator.jsx. One native stack per tab. Purple = Shino's module. The 'attendance recorded' banner shows over every tab.",
                    tabs, [("0_0", "1_0", "attendance card")])
    return {"id": "navs", "title": "5a Navigation (student)", "shapes": S, "lines": L}


def page_nav_lecturer():
    tabs = [("Home", BLUE, [("Dashboard", "today's classes"), ("ClassDetail", "live session, roster"), ("AttendanceDetail", "override, flags"), ("FaceVerification", "pending faces"), "Profile"]),
            ("Attendance", BLUE, [("AttendanceSessions", "all sessions"), "AttendanceDetail"]),
            ("Quiz", PURPLE, [("QuizList", "Shino, M6 mock"), "CreateQuiz", "LiveResults", "ResultsClosed", "Breakdown"]),
            ("AI Assistant", BLUE, [("LecturerAssistant", "materials, trends"), ("LecturerAsk", "ask my materials"), ("BeforeClass", "before next class")]),
            ("Analytics", PURPLE, [("Analytics", "Shino, M7")]),
            ("Admin (web only)", ORANGE, [("Accounts", "admin role"), ("Face verification", "fallback queue"), "Audit log", ("SPeCTRUM sync", "Moodle sync"), ("Devices", "camera keys")])]
    S, L = nav_page("navl", "SmartClass - Navigation: lecturer app (phone + browser)",
                    "mobile/lecturer/src/navigation/AppNavigator.jsx. Lecturers get the first five tabs; an admin signs in on the web and gets only the Admin tabs (a phone shows 'use a browser').",
                    tabs)
    return {"id": "navl", "title": "5b Navigation (lecturer)", "shapes": S, "lines": L}


# ─── 7. Wireframes ───────────────────────────────────────────────────────────

def phone(pid, x, title, parts):
    """A 360x740 phone frame; parts: (html text, height, fill)."""
    S = [shape(f"{pid}_frame", x, 40, 360, 740, None, fill="#FFFFFF"),
         shape(f"{pid}_bar", x + 20, 60, 320, 50, f'<p style="font-size:15px;text-align:left"><b>{esc(title)}</b></p>', fill="#1F4E79")]
    S[-1]["style"]["textColor"] = "#FFFFFF"
    y = 130
    for i, (text, h, fill) in enumerate(parts):
        S.append(shape(f"{pid}_p{i}", x + 20, y, 320, h, f'<p style="font-size:12px;text-align:left">{text}</p>', fill=fill))
        y += h + 14
    return S


def page_wireframes():
    S = [title_shape("wf", "SmartClass - Wireframes (key screens)",
                     "Simplified mock-ups of the built screens (labels taken from the code). Real screenshots go in the report (T104).")]
    S += phone("wf1", 40, "Assistant  [WIA2005 v]", [
        ("<b>You</b>: What is boundary value analysis?", 60, "#E8F0FE"),
        ("<b>Assistant</b>: Boundary value analysis tests values at the edges of each input range ... [1] [2]", 130, "#FFFFFF"),
        ("Citation chips: [1] Lecture 5.pdf p.12  [2] Tutorial 3.pdf p.2  (tap = open page)", 80, YELLOW),
        ("Study tools: Summary | Flashcards | Practice | Find related videos", 70, GREY),
        ("Chats | New chat", 50, GREY),
        ("[ Ask about your course materials ... ]  (Send)", 60, "#FFFFFF")])
    S += phone("wf2", 460, "My Attendance", [
        ("<b>WIA2005 Software Testing</b><br>Attendance rate 86%  (12 of 14)", 90, "#FFFFFF"),
        ("Week 7 Lecture - Present 09:02", 50, "#E3F4E6"),
        ("Week 6 Tutorial - Late 10:17", 50, "#FFF1DC"),
        ("Week 6 Lecture - Absent", 50, "#FDE2E2"),
        ("Week 5 Lecture - Excused (override)", 50, GREY),
        ("Tap a class: details + 'I'm here' if not recognised", 70, YELLOW),
        ("Tabs: Home | Attendance | Assistant | Participation | Profile", 60, GREY)])
    S += phone("wf3", 880, "WIA0000 Lecture", [
        ("<b>Live session</b>  open until 11:00   [Extend] [Close]", 70, "#E3F4E6"),
        ("Present 18 - Late 3 - Absent 2 - Flags 1", 50, "#FFFFFF"),
        ("Weekly schedule  Mon 09:00-11:00, DK1   [Edit]", 60, GREY),
        ("[ Search name or matric no. ]", 50, "#FFFFFF"),
        ("Ali (S1234567) - Present", 50, "#FFFFFF"),
        ("Mei (S7654321) - Flag: confirm / reject", 50, "#FFF1DC"),
        ("SPeCTRUM sync: synced 10:58  (From SPeCTRUM)", 60, YELLOW)])
    bx = 1300
    side = shape("wf4_side", bx + 20, 80, 180, 460, '<p style="font-size:12px;text-align:left"><b>SmartClass admin</b><br><br>Accounts<br>Face verification<br>Audit log<br>SPeCTRUM sync<br>Devices</p>', fill="#1F4E79")
    side["style"]["textColor"] = "#FFFFFF"
    S += [shape("wf4_frame", bx, 40, 760, 520, None, fill="#FFFFFF"), side,
          shape("wf4_search", bx + 220, 80, 520, 50, '<p style="font-size:12px;text-align:left">[ Search by name, email, matric or staff number ]   (New administrator)</p>', fill="#FFFFFF"),
          shape("wf4_r1", bx + 220, 150, 520, 60, '<p style="font-size:12px;text-align:left">Lim Wei - student - active - face: Pending review  [Review in Face verification]</p>', fill="#FFF1DC"),
          shape("wf4_r2", bx + 220, 224, 520, 60, '<p style="font-size:12px;text-align:left">Dr Tan - lecturer - active   [Deactivate]</p>', fill="#FFFFFF"),
          shape("wf4_r3", bx + 220, 298, 520, 60, '<p style="font-size:12px;text-align:left">Siti - student - inactive   [Reactivate] [Reset face data]</p>', fill=GREY),
          shape("wf4_r4", bx + 220, 372, 520, 50, '<p style="font-size:12px;text-align:left">(Show more)</p>', fill="#FFFFFF"),
          shape("wf4_cap", bx, 580, 760, 50, '<p style="font-size:13px;text-align:center"><b>Lecturer app in a browser: Admin Accounts</b></p>', kind="text")]
    for i, cap in enumerate(["Student: Assistant", "Student: Attendance", "Lecturer: ClassDetail"]):
        S.append(shape(f"wf_cap{i}", 40 + i * 420, 800, 360, 50, f'<p style="font-size:13px;text-align:center"><b>{cap}</b></p>', kind="text"))
    return {"id": "wf", "title": "6 Wireframes", "shapes": S, "lines": []}


def build():
    tables = load_schema()
    pages = [page_architecture(), page_modules(), page_class_domain(), page_class_services(), page_erd(tables),
             page_act_attendance(), page_act_enrolment(), page_act_chat(), page_nav_student(), page_nav_lecturer(),
             page_wireframes()]
    return {"version": 1, "pages": pages}


if __name__ == "__main__":
    doc = build()
    # Compact, one shape or line per text line: the whole document is passed inline to the
    # Lucid connector, so it has to stay small and readable in pieces.
    c = lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)
    parts = []
    for pg in doc["pages"]:
        body = ",\n".join([c(s) for s in pg["shapes"]])
        lines = ",\n".join([c(ln) for ln in pg["lines"]])
        parts.append(f'{{"id":{c(pg["id"])},"title":{c(pg["title"])},"shapes":[\n{body}],"lines":[\n{lines}]}}')
    OUT.write_text('{"version":1,"pages":[\n' + ",\n".join(parts) + "]}\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(doc['pages'])} pages, {OUT.stat().st_size} bytes")
