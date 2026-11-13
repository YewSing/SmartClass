// T105: builds docs/ap2-slides.pptx, the AP2 monitoring-session deck (Yew Sing, M1/M3/M4/M8).
//
// Facts come from the T104 report (docs/report/ap2-report.html); figures are the T103
// diagram exports in docs/diagrams/. backend/tests/test_docs_slides.py checks the built
// deck against both, so re-run this after either changes:
//
//   node docs/slides/build_slides.js
//
// Needs pptxgenjs (`npm install -g pptxgenjs`, or set NODE_PATH to where it is installed).
// No screenshots are embedded: app screens are marked frames that Yew Sing fills by hand
// (test accounts only, no real face, card or course material).
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..", "..");
const DIAGRAMS = path.join(ROOT, "docs", "diagrams");
const OUT = path.join(ROOT, "docs", "ap2-slides.pptx");

// Palette: deep teal (UM-ish, calm), amber accent, coral for "not done".
const P = {
  ink: "16302F",
  teal: "0F4C4A",
  tealMid: "2F7D78",
  mint: "DCEDEA",
  mist: "F3F8F7",
  white: "FFFFFF",
  amber: "E8A33D",
  amberSoft: "FBEBD0",
  coral: "D9644A",
  coralSoft: "F8DDD6",
  grey: "5B6B6A",
  line: "C9D8D5",
};
const HEAD = "Cambria";
const BODY = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "SmartClass - AP2 progress (Yew Sing)";
pres.author = "Yong Yew Sing";
pres.subject = "AP2 monitoring session: Modules 1, 3, 4, 8";
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };

const W = 13.333;
const M = 0.6; // side margin
const CW = W - 2 * M; // content width
const TOP = 1.75; // content top under the title

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: P.teal },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.2, w: CW, h: 1.3,
      fontFace: HEAD, fontSize: 54, bold: true, color: P.white, valign: "bottom", margin: 0 },
      text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.65, w: CW, h: 2.9,
      fontFace: BODY, fontSize: 22, color: P.mint, valign: "top", margin: 0 }, text: "" } },
  ],
});

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: P.white },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 0.35, w: CW, h: 0.35,
      fontFace: BODY, fontSize: 13, bold: true, color: P.tealMid, charSpacing: 2, margin: 0 },
      text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.7, w: CW, h: 0.8,
      fontFace: HEAD, fontSize: 36, bold: true, color: P.ink, valign: "top", margin: 0 },
      text: "" } },
    { text: { text: "SmartClass · AP2 progress · Yong Yew Sing (M1, M3, M4, M8)",
      options: { x: M, y: 7.05, w: 8, h: 0.3, fontFace: BODY, fontSize: 10, color: P.grey,
        margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 7.05, w: 0.6, h: 0.3, fontFace: BODY, fontSize: 10,
    color: P.grey, align: "right" },
});

// ---------- helpers ----------
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// Place a diagram inside a box, keeping its aspect ratio, centred in the box.
function addDiagram(slide, name, box, alt) {
  const file = path.join(DIAGRAMS, name);
  const s = pngSize(file);
  const r = Math.min(box.w / s.w, box.h / s.h);
  const w = s.w * r;
  const h = s.h * r;
  slide.addImage({ path: file, x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h,
    altText: alt, objectName: name });
}

function heading(slide, kicker, title) {
  slide.addText(kicker, { placeholder: "kicker" });
  slide.addText(title, { placeholder: "title" });
}

function text(slide, t, opts) {
  slide.addText(t, { isTextBox: true, fontFace: BODY, fontSize: 15, color: P.ink, margin: 0,
    valign: "top", ...opts });
}

function card(slide, x, y, w, h, fill, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12,
    fill: { color: fill || P.mist }, line: { color: fill || P.mist }, objectName: name });
}

function badge(slide, x, y, label, fill, color) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.55, h: 0.55, fill: { color: fill || P.amber },
    line: { color: fill || P.amber } });
  slide.addText(label, { isTextBox: true, x, y, w: 0.55, h: 0.55, align: "center",
    valign: "middle", fontFace: HEAD, fontSize: 16, bold: true, color: color || P.ink,
    margin: 0 });
}

function bullets(items, size) {
  return items.map((t, i) => ({ text: t, options: { bullet: true, fontSize: size || 15,
    paraSpaceAfter: 6, breakLine: i < items.length - 1 } }));
}

// A marked frame for an app screenshot that Yew Sing inserts by hand.
function shotFrame(slide, x, y, w, h, label) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.15,
    fill: { color: P.mist }, line: { color: P.tealMid, dashType: "dash", width: 1.25 },
    objectName: "screenshot-frame" });
  slide.addText([
    { text: "Screenshot", options: { bold: true, breakLine: true } },
    { text: label },
  ], { isTextBox: true, x: x + 0.15, y, w: w - 0.3, h, align: "center", valign: "middle",
    fontFace: BODY, fontSize: 12, color: P.tealMid, margin: 0 });
}

function table(slide, header, rows, opts) {
  const head = header.map((h) => ({ text: h, options: { bold: true, color: P.white,
    fill: { color: P.teal } } }));
  const body = rows.map((r, i) => r.map((c) => (typeof c === "object" ? c : {
    text: c, options: { fill: { color: i % 2 ? P.white : P.mist } } })));
  slide.addTable([head, ...body], { x: M, y: TOP, w: CW, fontFace: BODY, fontSize: 13,
    color: P.ink, border: { type: "solid", pt: 0.75, color: P.line }, valign: "middle",
    margin: [0.05, 0.1, 0.05, 0.1], ...opts });
}

function chip(textValue, kind) {
  const fills = { ok: P.mint, wait: P.amberSoft, no: P.coralSoft };
  return { text: textValue, options: { bold: true, fill: { color: fills[kind] } } };
}

const SECTIONS = {
  intro: "Introduction",
  obj: "Objectives progress",
  req: "Requirements progress",
  meth: "Methodology",
  dev: "System development",
  test: "Testing and evaluation",
  ap1: "AP1 feedback",
  end: "Next steps",
};
for (const t of Object.values(SECTIONS)) pres.addSection({ title: t });

function slideIn(section, master) {
  return pres.addSlide({ masterName: master || "CONTENT", sectionTitle: SECTIONS[section] });
}

function notes(slide, say, qa) {
  const lines = [say, "", "Likely questions:"];
  for (const [q, a] of qa) lines.push(`Q: ${q}`, `A: ${a}`, "");
  slide.addNotes(lines.join("\n").trim());
}

// ---------- 1. Title ----------
{
  const s = slideIn("intro", "TITLE_DARK");
  s.addText("SmartClass", { placeholder: "title" });
  s.addText([
    { text: "Smart classroom management for Universiti Malaya", options: { breakLine: true } },
    { text: "AP2 progress · Yong Yew Sing · Modules 1, 3, 4, 8 · 14 November 2026",
      options: { fontSize: 18, color: P.amber } },
  ], { placeholder: "body" });
  notes(s,
    "Open with the one-line idea: students sign in with SPeCTRUM, a camera at the door takes " +
    "attendance by face, attendance goes back to SPeCTRUM, and an AI assistant answers from " +
    "the lecturer's own materials with citations. I cover my four modules; Shino presents hers.",
    [
      ["What changed since AP1?", "IoT environment control and desk projection were dropped " +
        "(proposal revision, November 2026). Module 8 became an AI learning assistant over the " +
        "course materials in a simulated SPeCTRUM (a local Moodle 4.5)."],
      ["Is this connected to the real SPeCTRUM?", "No. A local Moodle 4.5 in Docker simulates " +
        "it, with the same web-service API and the Attendance plugin. Real SPeCTRUM uses " +
        "Microsoft 365 sign-in and would need UM IT approval."],
    ]);
}

// ---------- 2. Module split ----------
{
  const s = slideIn("intro");
  heading(s, "INTRODUCTION", "Two students, eight modules");
  const colW = (CW - 0.4) / 2;
  const cols = [
    { who: "Yong Yew Sing (this talk)", fill: P.mint, mods: [
      ["M1", "User Management"], ["M3", "Attendance Management"],
      ["M4", "Face Recognition Verification"], ["M8", "AI Learning Assistant"]] },
    { who: "Chow Shino", fill: P.mist, mods: [
      ["M2", "Dashboard & Notifications"], ["M5", "Classroom Interaction"],
      ["M6", "AI Quiz"], ["M7", "Learning Analytics"]] },
  ];
  cols.forEach((c, i) => {
    const x = M + i * (colW + 0.4);
    card(s, x, TOP, colW, 3.75, c.fill, `split-${i}`);
    text(s, c.who, { x: x + 0.35, y: TOP + 0.25, w: colW - 0.7, h: 0.45, fontFace: HEAD,
      fontSize: 22, bold: true });
    c.mods.forEach(([id, name], j) => {
      const y = TOP + 0.95 + j * 0.68;
      badge(s, x + 0.35, y, id, i === 0 ? P.amber : P.line);
      text(s, name, { x: x + 1.1, y: y + 0.08, w: colW - 1.5, h: 0.45, fontSize: 18 });
    });
  });
  text(s, [
    { text: "Shared: ", options: { bold: true } },
    { text: "one FastAPI backend and two apps. Where my modules meet Shino's, I build only the " +
      "agreed interface (attendance read API for M7, material retrieval for M6)." },
  ], { x: M, y: 5.8, w: CW, h: 0.5, fontSize: 15 });
  text(s, [
    { text: "Dropped since AP1: ", options: { bold: true, color: P.coral } },
    { text: "IoT environment control and desk projection." },
  ], { x: M, y: 6.35, w: CW, h: 0.4, fontSize: 15 });
  notes(s,
    "Each of us is graded on our own modules. I never build Shino's modules; where mine need " +
    "hers I build only the interface described in the FR document, and requests between us " +
    "are written down in docs/requests-for-shino.md.",
    [
      ["How do the modules depend on each other?", "M7 reads attendance through my read " +
        "interface (FR-313). M6 retrieves course passages through my retrieval interface " +
        "(FR-814). Five M8 features (FR-820 to FR-824) need M6 quiz results, so they wait."],
      ["How do you avoid merge conflicts?", "I work on a separate branch and merge to main " +
        "only finished, checked work through a pull request."],
    ]);
}

// ---------- 3. Objectives ----------
{
  const s = slideIn("obj");
  heading(s, "01 · OBJECTIVES PROGRESS", "All four modules built and tested");
  const mods = [
    ["M1", "User Management", "Moodle sign-in, roles, PDPA consent, face self-enrolment " +
      "checked against the matric card", "Done · tried on real phones (T23)", "ok"],
    ["M3", "Attendance Management", "Sessions from the timetable, four statuses, overrides, " +
      "reports, sync to Moodle Attendance", "Done · full class run with camera next (T48)",
      "wait"],
    ["M4", "Face Recognition", "Camera at the door detects faces; the server recognises them; " +
      "students can flag a miss", "Done with a webcam · Raspberry Pi run next (T47)", "wait"],
    ["M8", "AI Learning Assistant", "Cited chat over Moodle materials, summaries, flashcards, " +
      "practice, lecturer trends", "Done · quiz-based parts wait for M6", "wait"],
  ];
  const gw = (CW - 0.4) / 2;
  const gh = 2.4;
  mods.forEach(([id, name, obj, status, kind], i) => {
    const x = M + (i % 2) * (gw + 0.4);
    const y = TOP + Math.floor(i / 2) * (gh + 0.3);
    card(s, x, y, gw, gh, P.mist, `obj-${id}`);
    badge(s, x + 0.3, y + 0.3, id);
    text(s, name, { x: x + 1.05, y: y + 0.36, w: gw - 1.4, h: 0.45, fontFace: HEAD,
      fontSize: 20, bold: true });
    text(s, obj, { x: x + 0.3, y: y + 1.0, w: gw - 0.6, h: 0.75, fontSize: 15 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.3, y: y + 1.8, w: gw - 0.6, h: 0.4,
      rectRadius: 0.08, fill: { color: kind === "ok" ? P.mint : P.amberSoft },
      line: { color: kind === "ok" ? P.mint : P.amberSoft } });
    text(s, status, { x: x + 0.45, y: y + 1.8, w: gw - 0.9, h: 0.4, fontSize: 14, bold: true,
      valign: "middle" });
  });
  notes(s,
    "Every module is built with automated tests. What is left is measuring on real hardware: " +
    "the Pi run and a full class run with the camera. Module 8's quiz-based features depend " +
    "on Shino's quiz module.",
    [
      ["Why hasn't the Raspberry Pi been used yet?", "The device client is the same Python " +
        "code on a laptop webcam and on the Pi; only the camera differs. The Pi run (T47) " +
        "measures frame rate (NFR-11) and recognition time (NFR-10)."],
      ["How does a student get their face enrolled without an admin?", "They take three guided " +
        "selfies and a photo of their matric card. The server compares the faces and reads the " +
        "matric number by OCR; a clear pass is approved at once, anything else goes to the " +
        "lecturer's verification queue."],
    ]);
}

// ---------- 4. FR status ----------
{
  const s = slideIn("req");
  heading(s, "02 · REQUIREMENTS PROGRESS", "62 of 71 functional requirements done");
  // Per module, from the T104 report's FR table.
  const labels = ["M1 (19)", "M3 (20)", "M4 (11)", "M8 (21)"];
  s.addChart(pres.charts.BAR, [
    { name: "Done", labels, values: [18, 19, 9, 16] },
    { name: "Partly", labels, values: [1, 0, 1, 0] },
    { name: "Not done", labels, values: [0, 1, 1, 0] },
    { name: "Deferred on M6", labels, values: [0, 0, 0, 5] },
  ], {
    x: M, y: TOP, w: 7.3, h: 4.9, barDir: "bar", barGrouping: "stacked",
    chartColors: [P.tealMid, P.amber, P.coral, "9AA9A7"],
    showValue: true, dataLabelPosition: "ctr", dataLabelColor: P.white, dataLabelFontSize: 12,
    dataLabelFontFace: BODY,
    catAxisLabelFontFace: BODY, catAxisLabelFontSize: 14, catAxisLabelColor: P.ink,
    catAxisOrientation: "maxMin",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontFace: BODY, legendFontSize: 12,
    legendColor: P.ink, showTitle: true, title: "Functional requirements per module",
    titleFontFace: BODY, titleFontSize: 14, titleColor: P.ink, objectName: "fr-chart",
  });
  const stats = [
    ["62", "Done", "built with automated tests", P.tealMid],
    ["2", "Partly", "FR-114 push notice waits for M2; FR-401 Pi field run", P.amber],
    ["2", "Not done", "FR-314 PDF export, FR-411 offline buffer (both Could Have)", P.coral],
    ["5", "Deferred on M6", "FR-820 to FR-824 need quiz results", P.grey],
  ];
  const sx = M + 7.7;
  stats.forEach(([n, label, why, color], i) => {
    const y = TOP + i * 1.22;
    text(s, n, { x: sx, y, w: 1.1, h: 1.0, fontFace: HEAD, fontSize: 44, bold: true, color,
      valign: "middle" });
    text(s, [
      { text: label, options: { bold: true, fontSize: 16, breakLine: true } },
      { text: why, options: { fontSize: 13, color: P.grey } },
    ], { x: sx + 1.2, y: y + 0.08, w: CW - 7.7 - 1.2, h: 1.0 });
  });
  notes(s,
    "Every Must Have that does not depend on Shino's quiz module is built. The full table with " +
    "the evidence (test name or screen) for each FR is in the report.",
    [
      ["Why are FR-820 to FR-824 not done?", "They use quiz results (weak topics, " +
        "recommendations, blocking help during a graded quiz). The quiz is Shino's Module 6, " +
        "so I built the retrieval interface she calls and will add these once quiz data exists."],
      ["Why no PDF export?", "FR-314 is Could Have; CSV covers the need and opens in Excel."],
      ["What does 'Done' mean?", "Built, with automated tests, the fast checks passing and a " +
        "separate review; for screens, an end-to-end flow too."],
    ]);
}

// ---------- 5. NFR status ----------
{
  const s = slideIn("req");
  heading(s, "02 · REQUIREMENTS PROGRESS", "Non-functional requirements");
  table(s, ["Group", "NFRs", "Status", "Evidence or next step"], [
    ["Security and privacy", "NFR-01 to 09", chip("Met", "ok"),
      "Only embeddings kept; consent first; role checks; per-device keys; audit log"],
    ["Reliability", "NFR-20 to 24", chip("Met", "ok"),
      "Moodle outage retried; LLM outage gives a clear 503; no duplicate records"],
    ["Maintainability", "NFR-28 to 30", chip("Met", "ok"),
      "One LLM adapter (Gemini, DeepSeek); tests run without camera, Moodle or LLM"],
    ["Accuracy", "NFR-16 to 19", chip("Partly", "wait"),
      "Q&A evaluation harness built; set being finalised (T83); face accuracy at T48"],
    ["Performance", "NFR-10 to 15", chip("To measure", "wait"),
      "Pi run (T47), phone timing (T48), load during UAT"],
    ["Usability", "NFR-25 to 27", chip("To confirm", "wait"),
      "Class controls within 3 taps; guided enrolment; confirm in UAT (T107)"],
  ], { colW: [2.6, 1.8, 1.5, CW - 5.9], rowH: 0.62, fontSize: 14 });
  notes(s,
    "Security, privacy and reliability are met in code and covered by tests. Performance and " +
    "accuracy need real hardware and real users, which is the next phase.",
    [
      ["How do you protect face data under PDPA?", "Consent is recorded before any capture. " +
        "Only face embeddings are stored; photos are deleted when the decision is made. " +
        "Withdrawing consent deletes the embeddings at once and writes an audit entry."],
      ["Is the API on HTTPS?", "Locally no; NFR-07 applies to the UAT server (T99), which " +
        "will run behind HTTPS."],
    ]);
}

// ---------- 6. Methodology ----------
{
  const s = slideIn("meth");
  heading(s, "03 · METHODOLOGY", "Incremental: small tasks, each gated");
  const steps = [
    ["1", "Task", "PLAN.md task cites its FRs and a \"Done when\" line"],
    ["2", "Build", "code for that task only"],
    ["3", "Test", "tests written with the code"],
    ["4", "Check", "lint, backend and app unit tests on every task"],
    ["5", "Review", "separate review for bugs and weakened tests"],
    ["6", "E2E", "screens need their Maestro or Playwright flow"],
  ];
  const n = steps.length;
  const gap = 0.25;
  const bw = (CW - gap * (n - 1)) / n;
  steps.forEach(([num, name, what], i) => {
    const x = M + i * (bw + gap);
    card(s, x, TOP, bw, 2.55, i === n - 1 ? P.mint : P.mist, `step-${num}`);
    badge(s, x + 0.2, TOP + 0.2, num);
    text(s, name, { x: x + 0.2, y: TOP + 0.9, w: bw - 0.4, h: 0.4, fontFace: HEAD,
      fontSize: 18, bold: true });
    text(s, what, { x: x + 0.2, y: TOP + 1.35, w: bw - 0.35, h: 1.1, fontSize: 13 });
  });
  card(s, M, TOP + 2.85, CW, 0.75, P.amberSoft, "checkpoint");
  text(s, [
    { text: "Human checkpoint after each module: ", options: { bold: true } },
    { text: "I test on a real phone and in a browser before more is built (T23, T94, T48)." },
  ], { x: M + 0.3, y: TOP + 2.85, w: CW - 0.6, h: 0.75, valign: "middle", fontSize: 15 });
  text(s, "Stack", { x: M, y: TOP + 3.85, w: 0.9, h: 0.4, fontFace: HEAD, fontSize: 18,
    bold: true, valign: "middle" });
  const stack = ["React Native + Expo SDK 54", "Expo web (lecturer, admin)", "FastAPI",
    "PostgreSQL + pgvector", "InsightFace buffalo_sc", "Gemini / DeepSeek", "Moodle 4.5 (Docker)"];
  let cx = M + 1.0;
  let cy = TOP + 3.85;
  stack.forEach((t) => {
    const w = 0.25 + t.length * 0.105;
    if (cx + w > M + CW) { cx = M + 1.0; cy += 0.5; }
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: cy, w, h: 0.4, rectRadius: 0.2,
      fill: { color: P.white }, line: { color: P.tealMid, width: 1 } });
    text(s, t, { x: cx, y: cy, w, h: 0.4, align: "center", valign: "middle", fontSize: 13,
      color: P.teal });
    cx += w + 0.15;
  });
  notes(s,
    "Work is cut into small tasks of about a day. A task counts as done only when every gate " +
    "passes. Decisions and results are logged in PROGRESS.md, so the history is traceable.",
    [
      ["Is this Agile or Waterfall?", "Incremental and iterative: short tasks with a review " +
        "gate, and a checkpoint after each module that works like a sprint review with myself " +
        "as the user."],
      ["Did you use AI tools to write code?", "Yes, an AI coding assistant under my plan. I " +
        "write the requirements and the task list, every change must pass tests and a review, " +
        "and I test each module on real devices at the checkpoints."],
      ["Why FastAPI and React Native?", "One Python backend for face recognition and the LLM " +
        "pipeline; one React Native code base gives Android, iOS and, for the lecturer, the web."],
    ]);
}

// ---------- 7. Architecture ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "System architecture");
  addDiagram(s, "01-system-architecture.png", { x: M, y: TOP, w: 8.6, h: 5.1 },
    "System architecture: two Expo apps and a camera device client talk to the FastAPI " +
    "backend, which uses PostgreSQL with pgvector, a local Moodle, an LLM and InsightFace.");
  text(s, bullets([
    "Two Expo apps; the lecturer app also runs in a browser and holds the admin area",
    "Camera client detects faces; the server recognises them",
    "Local Moodle 4.5 simulates SPeCTRUM, with the Attendance plugin",
    "One LLM adapter: provider set by environment variables",
  ], 15), { x: M + 9.0, y: TOP + 0.2, w: CW - 9.0, h: 4.8 });
  notes(s,
    "Walk left to right: apps and the camera device, the FastAPI backend in the middle, and " +
    "the four things it depends on.",
    [
      ["Why recognise on the server, not on the Pi?", "The Pi only detects faces and sends " +
        "crops; the face embeddings of enrolled students never leave the server, and the Pi " +
        "stays cheap and fast."],
      ["What happens if Moodle is down?", "Attendance is kept in SmartClass and synced later " +
        "with backoff; sign-in shows 'SPeCTRUM is not reachable right now' (503)."],
    ]);
}

// ---------- 8. Modules ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "Module diagram");
  text(s, bullets([
    "My modules: M1, M3, M4, M8",
    "M4 feeds recognitions into M3",
    "M3 exposes a read interface to Shino's M7",
    "M8 exposes retrieval to Shino's M6",
  ], 15), { x: M, y: TOP + 0.2, w: 3.6, h: 4.8 });
  addDiagram(s, "02-module-diagram.png", { x: M + 3.9, y: TOP, w: CW - 3.9, h: 5.1 },
    "Module diagram of the eight SmartClass modules and the interfaces between them.");
  notes(s,
    "The arrows are real calls in the code. The two interfaces to Shino's modules are " +
    "documented in docs/interfaces.md and checked by tests.",
    [
      ["How is the interface to Shino tested?", "tests/test_docs_interfaces.py checks the " +
        "documented signatures and events against the code, so the document cannot drift."],
    ]);
}

// ---------- 9. Class diagrams ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "Class diagrams");
  const half = (CW - 0.4) / 2;
  addDiagram(s, "03a-class-diagram-domain.png", { x: M, y: TOP, w: half, h: 4.75 },
    "Class diagram of the domain models.");
  addDiagram(s, "03b-class-diagram-services.png", { x: M + half + 0.4, y: TOP, w: half, h: 4.75 },
    "Class diagram of the backend services and their dependencies.");
  text(s, "Domain models", { x: M, y: TOP + 4.8, w: half, h: 0.35, align: "center",
    fontSize: 13, color: P.grey });
  text(s, "Services (arrows = real imports)", { x: M + half + 0.4, y: TOP + 4.8, w: half,
    h: 0.35, align: "center", fontSize: 13, color: P.grey });
  notes(s,
    "Both diagrams are generated from the code: the domain classes from the SQLAlchemy models " +
    "and the service arrows from the real imports in app.services.",
    [
      ["Are the diagrams up to date?", "They are generated by docs/diagrams/build_lucid.py; a " +
        "test fails if the committed diagram file differs from a fresh build."],
    ]);
}

// ---------- 10. ERD ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "Entity relationship diagram");
  addDiagram(s, "04-erd.png", { x: M, y: TOP, w: CW, h: 4.75 },
    "Entity relationship diagram of the database tables and foreign keys.");
  text(s, "21 tables, built from the SQLAlchemy models that the Alembic migrations create; " +
    "a test checks every table and foreign key is drawn.", { x: M, y: TOP + 4.8, w: CW,
    h: 0.35, align: "center", fontSize: 13, color: P.grey });
  notes(s,
    "Point at the four areas: accounts and consent, courses and sessions, attendance with " +
    "flags and devices, and the knowledge base with chats.",
    [
      ["Where are face embeddings stored?", "In PostgreSQL with pgvector, linked to the " +
        "student; photos are not kept after the enrolment decision."],
      ["How do you change the schema safely?", "Every change is an Alembic migration with a " +
        "test that upgrades a fresh test database."],
    ]);
}

// ---------- 11. Activity diagrams ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "Activity diagrams");
  const items = [
    ["05a-activity-attendance.png", "Attendance by face"],
    ["05b-activity-face-enrolment.png", "Face self-enrolment"],
    ["05c-activity-ai-chat.png", "AI chat with citations"],
  ];
  const w3 = (CW - 0.6) / 3;
  items.forEach(([f, label], i) => {
    const x = M + i * (w3 + 0.3);
    addDiagram(s, f, { x, y: TOP, w: w3, h: 4.75 }, `Activity diagram: ${label}.`);
    text(s, label, { x, y: TOP + 4.8, w: w3, h: 0.35, align: "center", fontSize: 13,
      color: P.grey });
  });
  notes(s,
    "Attendance: the session opens from the timetable, the camera recognises a student over " +
    "three frames, Present or Late, and close marks the rest Absent. Enrolment: consent, " +
    "selfies, card, automatic check, or the lecturer's queue. Chat: retrieve passages, answer " +
    "with citations, or label it general knowledge.",
    [
      ["What if a student is not recognised?", "They tap 'I'm here' in the app; the lecturer " +
        "sees the flag with the closest unmatched face and confirms or rejects it."],
      ["What if the AI answers outside the course?", "The answer is labelled general " +
        "knowledge, so the student knows it is not from the materials."],
    ]);
}

// ---------- 12. Navigation ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "Navigation: student and lecturer apps");
  const half = (CW - 0.4) / 2;
  addDiagram(s, "06a-navigation-student.png", { x: M, y: TOP, w: half, h: 4.75 },
    "Navigation diagram of the student app.");
  addDiagram(s, "06b-navigation-lecturer.png", { x: M + half + 0.4, y: TOP, w: half, h: 4.75 },
    "Navigation diagram of the lecturer app, including the web-only admin area.");
  text(s, "Student app", { x: M, y: TOP + 4.8, w: half, h: 0.35, align: "center",
    fontSize: 13, color: P.grey });
  text(s, "Lecturer app (admin area in the browser)", { x: M + half + 0.4, y: TOP + 4.8,
    w: half, h: 0.35, align: "center", fontSize: 13, color: P.grey });
  notes(s,
    "Both apps use bottom tabs with a stack per tab. Administrators sign in to the lecturer " +
    "app in a browser and get four extra screens: accounts, Moodle sync, devices, audit log.",
    [
      ["Why no separate admin website?", "The old admin dashboard was retired; the admin " +
        "needs only a few screens, so they live in the lecturer web app with one code base."],
    ]);
}

// ---------- 13. Wireframes ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "Wireframes");
  addDiagram(s, "07-wireframes.png", { x: M, y: TOP, w: CW, h: 5.1 },
    "Wireframes of the main student and lecturer screens.");
  notes(s,
    "The wireframes show the main screens; the built screens follow them (next slide).",
    [
      ["Did you test the design with users?", "Not yet with other users; I check every " +
        "module on a real phone at its checkpoint, and the UAT (T107) uses a task list."],
    ]);
}

// ---------- 14. Built screens ----------
{
  const s = slideIn("dev");
  heading(s, "04 · SYSTEM DEVELOPMENT", "What was built");
  const mods = [
    ["M1", "Moodle sign-in; consent, 3 selfies and card photo; admin accounts",
      "Student face enrolment status"],
    ["M3", "Sessions from timetable; Present, Late, Excused, Absent; Moodle sync",
      "Lecturer live session with counts and sync"],
    ["M4", "Camera client; 3-frame match; \"recorded\" banner; \"I'm here\" flag",
      "Student flag and lecturer alert"],
    ["M8", "Cited chat; PDF at the page; flashcards, practice; trends",
      "Student assistant answer with citations"],
  ];
  const w4 = (CW - 0.9) / 4;
  mods.forEach(([id, what, shot], i) => {
    const x = M + i * (w4 + 0.3);
    badge(s, x, TOP, id);
    text(s, what, { x, y: TOP + 0.7, w: w4, h: 1.15, fontSize: 14 });
    shotFrame(s, x + 0.25, TOP + 1.95, w4 - 0.5, 3.05, shot);
  });
  notes(s,
    "Show one screen per module, then switch to the live demo if time allows. Screenshots use " +
    "test accounts only: no real face, card, course material or key.",
    [
      ["Can you show it working?", "Yes: the lecturer web app in the browser and the student " +
        "app on my phone through Expo Go, against the local Moodle."],
      ["How fast is the 'attendance recorded' banner?", "Target is 5 seconds (NFR-12); it " +
        "will be timed on a phone in the full class run (T48)."],
    ]);
}

// ---------- 15. Test levels ----------
{
  const s = slideIn("test");
  heading(s, "05 · TESTING AND EVALUATION", "Tests at every level");
  const labels = ["Backend unit", "App unit", "API + database", "With Moodle", "Live LLM"];
  s.addChart(pres.charts.BAR, [{ name: "Tests", labels, values: [212, 115, 513, 14, 28] }], {
    x: M, y: TOP, w: 7.6, h: 4.9, barDir: "bar", chartColors: [P.tealMid],
    catAxisOrientation: "maxMin",
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: P.ink, dataLabelFontSize: 12,
    dataLabelFontFace: BODY,
    catAxisLabelFontFace: BODY, catAxisLabelFontSize: 14, catAxisLabelColor: P.ink,
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, showTitle: true, title: "Automated tests per level",
    titleFontFace: BODY, titleFontSize: 14, titleColor: P.ink, objectName: "test-chart",
  });
  const stats = [
    ["767", "backend tests", "unit, API + database, Moodle and live LLM"],
    ["16", "Maestro flows", "phone end-to-end on an Android emulator (8 student, 8 lecturer)"],
    ["11", "Playwright specs", "lecturer web app and admin area"],
  ];
  const sx = M + 8.0;
  stats.forEach(([n, label, why], i) => {
    const y = TOP + i * 1.6;
    card(s, sx, y, CW - 8.0, 1.4, P.mist, `test-stat-${i}`);
    text(s, n, { x: sx + 0.25, y, w: 1.6, h: 1.4, fontFace: HEAD, fontSize: 40, bold: true,
      color: P.teal, valign: "middle" });
    text(s, [
      { text: label, options: { bold: true, fontSize: 16, breakLine: true } },
      { text: why, options: { fontSize: 13, color: P.grey } },
    ], { x: sx + 1.85, y: y + 0.2, w: CW - 8.0 - 2.05, h: 1.1 });
  });
  notes(s,
    "Normal tests never call Moodle or the LLM: they use fakes or recorded real model answers, " +
    "so they are fast and repeatable. The live LLM suite runs against the real model on a " +
    "synthetic course whenever the AI code or prompts change.",
    [
      ["How do you test an AI whose answers change?", "Live tests check structure and " +
        "grounding (valid citations, cited passage contains the key term, off-topic labelled " +
        "general), not exact wording, on a synthetic course we wrote ourselves."],
      ["How do you test face recognition without real faces?", "Generated images and " +
        "InsightFace's bundled sample images; no student photo is ever committed (PDPA)."],
      ["What is the coverage?", "Every FR in the report names its test or E2E flow."],
    ]);
}

// ---------- 16. Results + sample cases ----------
{
  const s = slideIn("test");
  heading(s, "05 · TESTING AND EVALUATION", "Latest results and sample test cases");
  table(s, ["Run", "Date", "Result"], [
    ["Fast checks (lint, backend, app unit)", "14 Nov", chip("725 backend passed; apps 61 + 54", "ok")],
    ["Live LLM suite", "14 Nov", chip("28 passed", "ok")],
    ["Playwright (lecturer web)", "13 Nov", chip("29 passed", "ok")],
  ], { colW: [5.0, 1.4, CW - 6.4], rowH: 0.45, fontSize: 13 });
  table(s, ["Requirement", "Test case", "Expected", "Result"], [
    ["FR-101, NFR-24", "Sign in while Moodle is down", "503, no account created", chip("Pass", "ok")],
    ["FR-116, NFR-03", "Student withdraws face consent", "Embeddings deleted, audited",
      chip("Pass", "ok")],
    ["FR-302", "Recognised after the late threshold", "Status Late", chip("Pass", "ok")],
    ["FR-311, NFR-20", "Moodle down during attendance sync", "Retried with backoff until synced",
      chip("Pass", "ok")],
    ["FR-403", "Real face of a student not in the course", "Not recorded", chip("Pass", "ok")],
    ["FR-813, NFR-09", "Topic asked by only 2 students", "Hidden from lecturer trends",
      chip("Pass", "ok")],
  ], { y: TOP + 2.05, colW: [2.0, 4.6, 4.3, CW - 10.9], rowH: 0.42, fontSize: 13 });
  notes(s,
    "The report lists 15 test cases with the automated test that proves each one; these are " +
    "six of them.",
    [
      ["Were the Maestro flows re-run recently?", "Each flow passed when its screen was built " +
        "(9 to 13 November); I re-run all of them before the demo."],
      ["What failed along the way?", "For example the practice questions marked every pick " +
        "wrong because the model answered with a letter; the server now maps letters to the " +
        "option and a test covers it."],
    ]);
}

// ---------- 17. Error handling ----------
{
  const s = slideIn("test");
  heading(s, "05 · TESTING AND EVALUATION", "Error handling");
  table(s, ["Failure", "What the user sees", "What the system does"], [
    ["SPeCTRUM (Moodle) down at sign-in", "\"SPeCTRUM is not reachable right now\" (503)",
      "No account created or changed"],
    ["Moodle down during attendance sync", "Sync status failed, then synced",
      "Attendance kept; retried with backoff"],
    ["Poor enrolment photo", "A specific retake message (blurry, no face)",
      "Nothing stored; lecturer review after repeats"],
    ["LLM down or slow", "A clear error in the chat (503)", "Nothing half-saved; other modules work"],
    ["LLM daily quota used up", "Same clear error", "Not retried; per-minute limits are retried"],
    ["Camera loses the server", "Device shows offline", "Client logs and retries"],
  ], { colW: [3.4, 4.5, CW - 7.9], rowH: 0.62, fontSize: 14 });
  notes(s,
    "Each row has an automated test named in the report (for example " +
    "test_moodle_down_gives_503 and test_llm_unavailable_is_503_and_nothing_saved).",
    [
      ["What if the face model fails to load?", "Face endpoints answer 503 'Face recognition " +
        "model not loaded'; sign-in, attendance viewing and the assistant keep working."],
      ["What if one course's materials fail to sync?", "That material shows 'error' to the " +
        "lecturer; the other courses still sync."],
    ]);
}

// ---------- 18. Evaluation still to run ----------
{
  const s = slideIn("test");
  heading(s, "05 · TESTING AND EVALUATION", "Evaluation before the final demo");
  const evals = [
    ["T47", "Raspberry Pi run", "Frame rate (NFR-11) and recognition time (NFR-10) at the door"],
    ["T48", "Full class run", "Timetable opens the class; Present, Late, flag, override, Moodle check"],
    ["T83", "AI answer quality", "Q&A evaluation set: correctness and citation support (NFR-18/19)"],
    ["T107", "Small UAT", "Classmates and a lecturer try both apps with a task list"],
  ];
  const w4 = (CW - 0.9) / 4;
  evals.forEach(([id, name, what], i) => {
    const x = M + i * (w4 + 0.3);
    card(s, x, TOP + 0.2, w4, 3.6, P.mist, `eval-${id}`);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.3, y: TOP + 0.5, w: 1.0, h: 0.45,
      rectRadius: 0.1, fill: { color: P.amber }, line: { color: P.amber } });
    text(s, id, { x: x + 0.3, y: TOP + 0.5, w: 1.0, h: 0.45, align: "center",
      valign: "middle", fontSize: 14, bold: true });
    text(s, name, { x: x + 0.3, y: TOP + 1.2, w: w4 - 0.6, h: 0.5, fontFace: HEAD,
      fontSize: 18, bold: true });
    text(s, what, { x: x + 0.3, y: TOP + 1.8, w: w4 - 0.6, h: 1.8, fontSize: 14 });
  });
  text(s, "UAT runs on a server with installable Android apps (T99), so testers need no laptop.",
    { x: M, y: TOP + 4.15, w: CW, h: 0.5, fontSize: 15, color: P.grey });
  notes(s,
    "Honest status: the system is built; these runs produce the numbers for the evaluation " +
    "chapter.",
    [
      ["How will you measure face recognition accuracy?", "In the class run (T48): students " +
        "walk in, and I count correct, missed and wrong recognitions against who was there."],
      ["How many UAT users?", "A few classmates and a lecturer, each with a task list; results " +
        "go into docs/testing/uat.md."],
    ]);
}

// ---------- 19. AP1 feedback ----------
{
  const s = slideIn("ap1");
  heading(s, "06 · AP1 FEEDBACK", "AP1 feedback and what was done");
  const blank = () => [{ text: "" }, { text: "" }, { text: "" }];
  table(s, ["Panel comment at AP1", "What was done", "Where to see it"],
    [blank(), blank(), blank(), blank()],
    { colW: [4.6, 4.6, CW - 9.2], rowH: 0.85, fontSize: 14 });
  text(s, "Rows are filled by Yew Sing from the AP1 panel comments (task T106).",
    { x: M, y: TOP + 4.45, w: CW, h: 0.4, fontSize: 13, italic: true, color: P.grey });
  notes(s,
    "Go through each AP1 comment and what changed because of it. To be written by Yew Sing " +
    "(T106) from the AP1 feedback and the panel rubric.",
    [
      ["Did you act on every comment?", "Answer per row; if one was not acted on, say why " +
        "(for example a scope decision agreed with the supervisor)."],
    ]);
}

// ---------- 20. Next steps ----------
{
  const s = slideIn("end", "TITLE_DARK");
  s.addText("Next steps", { placeholder: "title" });
  s.addText(bullets([
    "Raspberry Pi run and full class run (T47, T48)",
    "Finalise the AI Q&A evaluation set (T83)",
    "UAT server with installable apps, then a small UAT (T99, T107)",
    "Quiz-based AI features once Shino's Module 6 is ready (FR-820 to FR-824)",
  ], 20), { placeholder: "body" });
  notes(s,
    "Close with what is left and ask for questions.",
    [
      ["Will you finish on time?", "All four modules are built; the remaining work is " +
        "measurement and UAT, planned before the final demo."],
      ["What is the biggest risk?", "The Pi frame rate and recognition at the door in real " +
        "light; the laptop webcam is the backup device (FR-409)."],
    ]);
}

pres.writeFile({ fileName: OUT }).then((f) => console.log(`wrote ${f}`));
