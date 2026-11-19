<?php
// Web-service functions for SmartClass (Module 3/6 sync).
// create_quiz:  creates a mod_quiz activity + question-bank questions + slots.
//               SmartClass 'mcq' maps to qtype multichoice; 'short_answer' maps to
//               qtype essay (manual grading -> the lecturer's "Needs review" flow).
// quiz_attempts: finished attempts of a quiz with per-slot responses, so SmartClass
//               can import answers taken in Moodle.
defined('MOODLE_INTERNAL') || die();

require_once($CFG->dirroot . '/mod/quiz/lib.php');
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->libdir . '/questionlib.php');

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

class local_smartclass_external extends external_api {

    public static function create_quiz_parameters() {
        $question = new external_single_structure([
            'index' => new external_value(PARAM_INT, 'SmartClass question index (order)'),
            'type' => new external_value(PARAM_ALPHANUMEXT, 'mcq or short_answer'),
            'question' => new external_value(PARAM_RAW, 'Question text'),
            'options' => new external_multiple_structure(
                new external_value(PARAM_RAW, 'Option text'), 'MCQ options', VALUE_DEFAULT, []),
            'correct_answer' => new external_value(PARAM_RAW, 'Correct option letter(s), MCQ only', VALUE_OPTIONAL),
            'suggested_answer' => new external_value(PARAM_RAW, 'Model answer, essay only', VALUE_OPTIONAL),
            'score' => new external_value(PARAM_FLOAT, 'Maximum marks'),
        ]);
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Course id'),
            'name' => new external_value(PARAM_TEXT, 'Quiz name'),
            'timeopen' => new external_value(PARAM_INT, 'Open unix time (0 = always open)'),
            'timeclose' => new external_value(PARAM_INT, 'Close unix time (0 = no close)'),
            'timelimit' => new external_value(PARAM_INT, 'Time limit in minutes (0 = none)'),
            'attempts' => new external_value(PARAM_INT, 'Number of allowed attempts'),
            'questions' => new external_multiple_structure($question),
        ]);
    }

    public static function create_quiz($params) {
        global $DB;
        $params = self::validate_parameters(self::create_quiz_parameters(), $params);
        $course = $DB->get_record('course', ['id' => $params['courseid']], '*', MUST_EXIST);
        $context = context_course::instance($course->id);
        require_capability('moodle/course:manageactivities', $context);
        self::validate_context($context);

        $maxmark = 0.0;
        foreach ($params['questions'] as $q) {
            $maxmark += (float)$q['score'];
        }

        // 1. The quiz activity record.
        $quiz = (object)[
            'course' => $course->id,
            'name' => $params['name'],
            'intro' => '', 'introformat' => FORMAT_HTML,
            'timeopen' => $params['timeopen'], 'timeclose' => $params['timeclose'],
            'timelimit' => max(0, $params['timelimit']) * 60,
            'attempts' => max(1, $params['attempts']),
            'grade' => max(1.0, $maxmark),
            'sumgrades' => 0,
            'questionsperpage' => 0, 'grademethod' => QUIZ_GRADEHIGHEST,
            'browsercurity' => '-', 'delay1' => 0, 'delay2' => 0,
            'showmarks' => 1, 'reviewoptions' => 0,
            'timecreated' => time(), 'timemodified' => time(),
        ];
        $quiz->id = $DB->insert_record('quiz', $quiz);

        // 2. Link it into the course (section 0).
        $module = $DB->get_record('modules', ['name' => 'quiz'], '*', MUST_EXIST);
        $cm = (object)[
            'course' => $course->id, 'module' => $module->id, 'instance' => $quiz->id,
            'section' => 0, 'visible' => 1, 'groupmode' => 0, 'groupingid' => 0,
            'showdescription' => 0, 'completion' => 0, 'availability' => null,
        ];
        $cm->id = $DB->insert_record('course_modules', $cm);
        course_add_cm_to_section($course->id, $cm->id, 0, 0);
        rebuild_course_cache($course->id, true);

        // 3. Questions in the course question bank, added as slots.
        $cat = local_smartclass_category($context);
        $created = [];
        foreach ($params['questions'] as $q) {
            $qid = local_smartclass_question($cat, $q);
            quiz_add_quiz_question($qid, $quiz, 0);
            $created[] = ['index' => (int)$q['index'], 'questionid' => (int)$qid];
        }
        quiz_update_sumgrades($quiz);
        $DB->update_record('quiz', $quiz);

        return ['quiz_id' => (int)$quiz->id, 'cmid' => (int)$cm->id,
                'questions' => $created];
    }

    public static function create_quiz_returns() {
        return new external_single_structure([
            'quiz_id' => new external_value(PARAM_INT, 'mod_quiz instance id'),
            'cmid' => new external_value(PARAM_INT, 'Course module id'),
            'questions' => new external_multiple_structure(new external_single_structure([
                'index' => new external_value(PARAM_INT, 'SmartClass question index'),
                'questionid' => new external_value(PARAM_INT, 'Moodle question id'),
            ])),
        ]);
    }

    public static function quiz_attempts_parameters() {
        return new external_function_parameters([
            'quizid' => new external_value(PARAM_INT, 'mod_quiz instance id'),
        ]);
    }

    public static function quiz_attempts($params) {
        global $DB, $CFG;
        $params = self::validate_parameters(self::quiz_attempts_parameters(), $params);
        $quiz = $DB->get_record('quiz', ['id' => $params['quizid']], '*', MUST_EXIST);
        $course = $DB->get_record('course', ['id' => $quiz->course], '*', MUST_EXIST);
        $cm = get_coursemodule_from_instance('quiz', $quiz->id, $quiz->course, false, MUST_EXIST);
        require_capability('mod/quiz:viewreports', context_module::instance($cm->id));

        $rows = $DB->get_records('quiz_attempts',
            ['quiz' => $quiz->id], 'id ASC');
        $out = [];
        foreach ($rows as $a) {
            if ($a->state !== 'finished' && $a->state !== 'abandoned') {
                continue;
            }
            // Per-slot responses from the attempt's question usage.
            $attemptobj = quiz_attempt::create($a->id);
            $responses = [];
            foreach ($attemptobj->get_slots() as $slot) {
                $qa = $attemptobj->get_question_attempt($slot);
                $text = local_smartclass_response_text($qa);
                if ($text === '') {
                    continue;
                }
                $responses[] = [
                    'slot' => (int)$slot,
                    'questionid' => (int)$qa->get_question()->id,
                    'response' => $text,
                ];
            }
            $out[] = [
                'attempt_id' => (int)$a->id,
                'userid' => (int)$a->userid,
                'state' => $a->state,
                'sumgrades' => (float)$a->sumgrades,
                'max_grade' => (float)$quiz->sumgrades,
                'timestart' => (int)$a->timestart,
                'timefinish' => (int)$a->timefinish,
                'responses' => $responses,
            ];
        }
        return ['quiz_id' => (int)$quiz->id, 'attempts' => $out];
    }

    public static function quiz_attempts_returns() {
        return new external_single_structure([
            'quiz_id' => new external_value(PARAM_INT, 'mod_quiz instance id'),
            'attempts' => new external_multiple_structure(new external_single_structure([
                'attempt_id' => new external_value(PARAM_INT, 'Attempt id'),
                'userid' => new external_value(PARAM_INT, 'Moodle user id'),
                'state' => new external_value(PARAM_ALPHANUMEXT, 'finished or abandoned'),
                'sumgrades' => new external_value(PARAM_FLOAT, 'Marks achieved'),
                'max_grade' => new external_value(PARAM_FLOAT, 'Quiz max marks'),
                'timestart' => new external_value(PARAM_INT, 'Start unix time'),
                'timefinish' => new external_value(PARAM_INT, 'Finish unix time'),
                'responses' => new external_multiple_structure(new external_single_structure([
                    'slot' => new external_value(PARAM_INT, 'Slot number'),
                    'questionid' => new external_value(PARAM_INT, 'Moodle question id'),
                    'response' => new external_value(PARAM_RAW, 'The student\'s answer text'),
                ])),
            ])),
        ]);
    }
}

/** The course's SmartClass question category (created on demand). */
function local_smartclass_category($context) {
    global $DB;
    $cat = $DB->get_record('question_categories',
        ['contextid' => $context->id, 'name' => 'SmartClass', 'parent' => 0]);
    if ($cat) {
        return $cat;
    }
    $top = question_get_default_category($context->id, true);
    $cat = (object)[
        'name' => 'SmartClass', 'contextid' => $context->id,
        'info' => 'Questions synced from SmartClass', 'infoformat' => FORMAT_HTML,
        'parent' => $top->id, 'sortorder' => 999,
    ];
    $cat->id = $DB->insert_record('question_categories', $cat);
    return $cat;
}

/** Create one question in the bank; returns its id. */
function local_smartclass_question($cat, $q) {
    global $DB;
    $base = (object)[
        'category' => $cat->id,
        'parent' => 0,
        'name' => 'SmartClass Q' . ($q['index'] + 1),
        'questiontext' => $q['question'], 'questiontextformat' => FORMAT_HTML,
        'generalfeedback' => '', 'generalfeedbackformat' => FORMAT_HTML,
        'defaultmark' => max(0.0, (float)$q['score']),
        'penalty' => 0, 'qtype' => $q['type'] === 'mcq' ? 'multichoice' : 'essay',
        'createdby' => null, 'modifiedby' => null,
    ];
    $form = clone $base;

    if ($q['type'] === 'mcq') {
        $options = $q['options'] ?? [];
        $letters = [];
        foreach (range('A', 'Z') as $i => $letter) {
            $letters[strtolower($letter)] = $i;
        }
        $correct = preg_split('/\s*,\s*/', strtolower(trim((string)($q['correct_answer'] ?? ''))), -1, PREG_SPLIT_NO_EMPTY);
        $single = count($correct) <= 1;
        $form->single = $single ? 1 : 0;
        $form->shuffleanswers = 0;
        $form->answer = [];
        foreach ($options as $i => $text) {
            $letter = strtolower(chr(ord('A') + $i));
            $form->answer[] = [
                'text' => $text,
                'format' => FORMAT_HTML,
                'fraction' => in_array($letter, $correct, true) ? 1.0 : 0.0,
                'feedback' => ['text' => '', 'format' => FORMAT_HTML],
            ];
        }
    } else {
        // Essay: manual grading, model answer shown to the grader.
        $form->responseformat = 'editor';
        $form->responsefieldlines = 10;
        $form->attachments = 0;
        $form->attachmentsrequired = 0;
        $form->graderinfo = ['text' => (string)($q['suggested_answer'] ?? ''), 'format' => FORMAT_HTML];
        $form->responsetemplate = ['text' => '', 'format' => FORMAT_HTML];
        $form->minwordlimit = -1;
        $form->maxwordlimit = -1;
    }

    $question = question_bank::get_qtype($base->qtype)->save_question($base, $form);
    return $question->id;
}

/** Best-effort plain-text extraction of a student's response from a question attempt. */
function local_smartclass_response_text($qa) {
    $data = (array)$qa->get_response_summary();
    if ($data === []) {
        $data = (array)$qa->get_submitted_data();
    }
    $texts = [];
    array_walk_recursive($data, function ($v) use (&$texts) {
        if (is_string($v) && trim($v) !== '' && !is_numeric($v)) {
            $texts[] = trim($v);
        }
    });
    // Drop response-version noise (keys like '-submit'), keep the human text.
    return implode("\n", array_unique($texts));
}
