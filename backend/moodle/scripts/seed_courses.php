<?php
// Seeds courses, users, enrolments and course modules (one mod_attendance activity per course,
// mod_resource files) from /seed/seed_config.json. Idempotent.
// Run: docker exec smartclass-moodle-moodle-1 php /scripts/seed_courses.php [--dry-run]
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
$CFG->noemailever = true; // no mail server in the container
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/user/lib.php');
require_once($CFG->dirroot . '/lib/enrollib.php');
require_once($CFG->dirroot . '/lib/filelib.php');
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->dirroot . '/mod/resource/lib.php');

$dry = in_array('--dry-run', $argv);
$conf = json_decode(file_get_contents('/seed/seed_config.json'), true);
if (!$conf) { fwrite(STDERR, "Bad JSON in /seed/seed_config.json\n"); exit(1); }
$root = rtrim($conf['materials_root'], '/');
$allowed = array_map('strtolower', $conf['allowed_extensions'] ?? ['pdf', 'pptx', 'docx']);
\core\session\manager::set_user(get_admin());
$admin = get_admin();

// Glob -> regex. ** crosses '/', * stays within a segment, ? is one char. '**/' also matches an empty prefix.
function glob_to_regex(string $g): string {
    $re = ''; $n = strlen($g);
    for ($i = 0; $i < $n; $i++) {
        $c = $g[$i];
        if ($c === '*') {
            if (($g[$i + 1] ?? '') === '*') {
                if (($g[$i + 2] ?? '') === '/') { $re .= '(?:.*/)?'; $i += 2; }
                else { $re .= '.*'; $i += 1; }
            } else { $re .= '[^/]*'; }
        } elseif ($c === '?') { $re .= '[^/]'; }
        else { $re .= preg_quote($c, '#'); }
    }
    return '#^' . $re . '$#iu';
}
function matches_any(string $rel, array $globs): ?string {
    foreach ($globs as $g) { if (preg_match(glob_to_regex($g), $rel)) return $g; }
    return null;
}

// ---- Local, git-ignored extra users/enrolments (e.g. a developer's own account with a real
// matric number). scripts/seed.sh copies backend/moodle/seed_config.local.json here if it exists.
$localpath = '/tmp/seed_config.local.json';
if (is_readable($localpath)) {
    $local = json_decode(file_get_contents($localpath), true);
    if (!$local) { fwrite(STDERR, "Bad JSON in seed_config.local.json\n"); exit(1); }
    $conf['users'] = array_merge($conf['users'], $local['users'] ?? []);
    $conf['enrolments'] = array_merge($conf['enrolments'], $local['enrolments'] ?? []);
    echo "local seed: " . count($local['users'] ?? []) . " user(s)\n";
}

// ---- Custom profile fields (SmartClass reads them as programme / year_sem, FR-107)
require_once($CFG->dirroot . '/user/profile/lib.php');
$fieldids = [];
if (!empty($conf['profile_fields']) && !$dry) {
    $cat = $DB->get_record('user_info_category', ['name' => 'Student record']);
    if (!$cat) {
        $cat = (object)['name' => 'Student record', 'sortorder' => $DB->count_records('user_info_category') + 1];
        $cat->id = $DB->insert_record('user_info_category', $cat);
    }
    foreach ($conf['profile_fields'] as $i => $f) {
        $ex = $DB->get_record('user_info_field', ['shortname' => $f['shortname']]);
        if (!$ex) {
            echo "create profile field: {$f['shortname']}\n";
            $ex = (object)[
                'shortname' => $f['shortname'], 'name' => $f['name'], 'datatype' => 'text',
                'description' => '', 'descriptionformat' => FORMAT_HTML, 'categoryid' => $cat->id,
                'sortorder' => $i + 1, 'required' => 0, 'locked' => 1, 'visible' => PROFILE_VISIBLE_ALL,
                'forceunique' => 0, 'signup' => 0, 'defaultdata' => '', 'defaultdataformat' => FORMAT_HTML,
                'param1' => 30, 'param2' => 255, 'param3' => 0,
            ];
            $ex->id = $DB->insert_record('user_info_field', $ex);
        }
        $fieldids[$f['shortname']] = $ex->id;
    }
}

// ---- Users. Existing users get their idnumber, department and profile fields updated.
$ids = [];
foreach ($conf['users'] as $u) {
    $ex = $DB->get_record('user', ['username' => $u['username'], 'mnethostid' => $CFG->mnet_localhost_id]);
    if ($ex) {
        $ids[$u['username']] = $ex->id;
        $upd = new stdClass(); $upd->id = $ex->id; $changed = false;
        foreach (['idnumber', 'department'] as $k) {
            if (isset($u[$k]) && $ex->$k !== $u[$k]) { $upd->$k = $u[$k]; $changed = true; }
        }
        if ($changed && !$dry) user_update_user($upd, false, false);
        echo ($changed ? "user updated" : "user exists") . ": {$u['username']}\n";
    } else {
        echo "create user: {$u['username']}\n";
        if ($dry) continue;
        $o = new stdClass();
        $o->username = $u['username']; $o->firstname = $u['firstname']; $o->lastname = $u['lastname'];
        $o->email = $u['email']; $o->auth = 'manual'; $o->confirmed = 1; $o->mnethostid = $CFG->mnet_localhost_id;
        $o->password = hash_internal_user_password($u['password']);
        $o->lang = 'en'; $o->city = 'Kuala Lumpur'; $o->country = 'MY';
        $o->idnumber = $u['idnumber'] ?? ''; $o->department = $u['department'] ?? '';
        $ids[$u['username']] = user_create_user($o, false, false);
    }
    if (!$dry && !empty($u['profile'])) {
        $p = new stdClass(); $p->id = $ids[$u['username']];
        foreach ($u['profile'] as $short => $value) {
            if (isset($fieldids[$short])) { $p->{'profile_field_' . $short} = $value; }
        }
        profile_save_data($p);
    }
}

// ---- Courses
$courses = [];
foreach ($conf['courses'] as $c) {
    $ex = $DB->get_record('course', ['shortname' => $c['shortname']]);
    if ($ex) { $courses[$c['shortname']] = $ex; echo "course exists: {$c['shortname']}\n"; continue; }
    echo "create course: {$c['shortname']}\n";
    if ($dry) continue;
    $d = new stdClass();
    $d->shortname = $c['shortname']; $d->fullname = $c['fullname']; $d->category = 1;
    $d->format = 'topics'; $d->visible = 1; $d->summary = ''; $d->summaryformat = FORMAT_HTML;
    $d->enablecompletion = 1;
    $courses[$c['shortname']] = create_course($d);
}

// ---- Enrolments
$manual = enrol_get_plugin('manual');
foreach ($conf['enrolments'] as $e) {
    if (empty($courses[$e['course']]) || empty($ids[$e['username']])) { echo "skip enrolment (missing): " . json_encode($e) . "\n"; continue; }
    $course = $courses[$e['course']];
    $role = $DB->get_record('role', ['shortname' => $e['role']], '*', MUST_EXIST);
    $inst = null;
    foreach (enrol_get_instances($course->id, true) as $i) { if ($i->enrol === 'manual') $inst = $i; }
    if (!$inst) {
        $manual->add_default_instance($course);
        foreach (enrol_get_instances($course->id, true) as $i) { if ($i->enrol === 'manual') $inst = $i; }
    }
    $ctx = context_course::instance($course->id);
    $already = $DB->record_exists('user_enrolments', ['enrolid' => $inst->id, 'userid' => $ids[$e['username']]]);
    if ($already && user_has_role_assignment($ids[$e['username']], $role->id, $ctx->id)) continue;
    echo "enrol {$e['username']} in {$e['course']} as {$e['role']}\n";
    $manual->enrol_user($inst, $ids[$e['username']], $role->id);
}

// ---- Attendance activity (one per course; T35 syncs sessions into it)
$attmod = $DB->get_record('modules', ['name' => 'attendance']);
if (!$attmod) {
    echo "!! mod_attendance not installed (run setup.sh); no Attendance activities added\n";
} else {
    foreach ($conf['courses'] as $c) {
        $short = $c['shortname'];
        if (empty($courses[$short])) continue;          // dry run on a new course
        $course = $courses[$short];
        if ($DB->record_exists('attendance', ['course' => $course->id])) { echo "attendance exists: $short\n"; continue; }
        echo "add attendance: $short\n";
        if ($dry) continue;
        $mi = new stdClass();
        $mi->modulename = 'attendance'; $mi->module = $attmod->id;
        $mi->name = 'Attendance'; $mi->intro = 'Synced from SmartClass. Students do not mark themselves.';
        $mi->introformat = FORMAT_HTML;
        $mi->section = 0; $mi->visible = 1; $mi->visibleoncoursepage = 1;
        $mi->cmidnumber = ''; $mi->groupmode = NOGROUPS; $mi->groupingid = 0;
        add_moduleinfo($mi, $course);
    }
}

// ---- Materials
$fs = get_file_storage();
$userctx = context_user::instance($admin->id);
$modid = $DB->get_field('modules', 'id', ['name' => 'resource'], MUST_EXIST);
$summary = [];
foreach ($conf['courses'] as $c) {
    $short = $c['shortname'];
    $summary[$short] = ['uploaded' => [], 'existing' => 0, 'skipped' => []];
    if (empty($courses[$short])) continue;
    $course = $courses[$short];
    if (empty($c['source_folder'])) { echo "no materials for $short\n"; continue; }
    $srcrel = trim($c['source_folder'], '/');
    $folder = $root . '/' . $srcrel;
    // Safety: must be a course subfolder (SEM x/Course), never the SEM folder or root itself
    $real = realpath($folder);
    if ($real === false || !is_dir($real) || substr_count($srcrel, '/') < 1 || strpos($srcrel, '..') !== false) {
        echo "!! source folder invalid/not found for $short: $folder\n"; continue;
    }
    $excl = array_merge($conf['default_exclude'] ?? [], $c['exclude'] ?? []);
    $incl = $c['include'] ?? [];
    $files = [];
    $it = new RecursiveIteratorIterator(new RecursiveCallbackFilterIterator(
        new RecursiveDirectoryIterator($real, FilesystemIterator::SKIP_DOTS),
        function ($cur) {
            if ($cur->isDir()) {
                $n = $cur->getFilename();
                return !($n[0] === '.' || in_array($n, ['node_modules','venv','site-packages','__pycache__']));
            }
            return true;
        }
    ));
    foreach ($it as $f) {
        if (!$f->isFile()) continue;
        $rel = str_replace('\\', '/', substr($f->getPathname(), strlen($real) + 1));
        $files[$rel] = $f->getPathname();
    }
    ksort($files);
    $sections = [];
    foreach ($files as $rel => $path) {
        $ext = strtolower(pathinfo($rel, PATHINFO_EXTENSION));
        $base = basename($rel);
        $skip = function ($why) use (&$summary, $short, $rel) { $summary[$short]['skipped'][] = [$rel, $why]; };
        if ($base[0] === '.') { $skip('dotfile'); continue; }
        if ($ext === 'ppt' || $ext === 'doc') { $skip('legacy format .' . $ext); continue; }
        if ($g = matches_any($rel, $excl)) { $skip("excluded by $g"); continue; }
        if (!in_array($ext, $allowed)) { $skip('extension .' . $ext . ' not allowed'); continue; }
        if ($incl && !matches_any($rel, $incl)) { $skip('not matched by include list'); continue; }
        // Section: "Week N" in any path component or filename, else 1
        $sec = 1;
        if (preg_match('/week[\s_\-]*0*(\d+)/i', $rel, $m)) $sec = max(1, min(52, (int)$m[1]));
        if ($DB->record_exists_sql("SELECT 1 FROM {resource} WHERE course = ? AND name = ?", [$course->id, $base])) {
            $summary[$short]['existing']++; continue;
        }
        if ($dry) { $summary[$short]['uploaded'][] = "$base (section $sec) [dry]"; continue; }
        if (!isset($sections[$sec])) {
            course_create_sections_if_missing($course, range(0, $sec));
            $sections[$sec] = true;
        }
        $draftid = file_get_unused_draft_itemid();
        $fs->create_file_from_pathname([
            'contextid' => $userctx->id, 'component' => 'user', 'filearea' => 'draft',
            'itemid' => $draftid, 'filepath' => '/', 'filename' => $base,
        ], $path);
        $mi = new stdClass();
        $mi->modulename = 'resource'; $mi->module = $modid; $mi->course = $course->id;
        $mi->section = $sec; $mi->visible = 1; $mi->visibleoncoursepage = 1;
        $mi->name = $base; $mi->introeditor = ['text' => '', 'format' => FORMAT_HTML, 'itemid' => 0];
        $mi->showdescription = 0; $mi->files = $draftid; $mi->display = 0 /* RESOURCELIB_DISPLAY_AUTO */;
        $mi->showsize = 0; $mi->showtype = 0; $mi->showdate = 0; $mi->printintro = 0; $mi->filterfiles = 0;
        $mi->cmidnumber = '';
        try {
            create_module($mi);
            $summary[$short]['uploaded'][] = $base;
            echo "  uploaded [$short s$sec] $base\n";
        } catch (Throwable $ex) {
            $summary[$short]['skipped'][] = [$rel, 'ERROR ' . $ex->getMessage()];
            echo "  ERROR $base: " . $ex->getMessage() . "\n";
        }
    }
    // Name the weekly sections
    if (!$dry) {
        foreach (array_keys($sections) as $n) {
            $sr = $DB->get_record('course_sections', ['course' => $course->id, 'section' => $n]);
            if ($sr && ($sr->name === null || $sr->name === '')) {
                course_update_section($course, $sr, ['name' => "Week $n"]);
            }
        }
        rebuild_course_cache($course->id, true);
    }
}

echo "\n==== SUMMARY ====\n";
foreach ($summary as $short => $s) {
    echo "$short: uploaded " . count($s['uploaded']) . ", already present {$s['existing']}, skipped " . count($s['skipped']) . "\n";
    foreach ($s['uploaded'] as $f) echo "  UPLOADED: $f\n";
    foreach ($s['skipped'] as [$f, $why]) echo "  SKIPPED: $f  <- $why\n";
}
