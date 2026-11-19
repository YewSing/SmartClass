<?php
defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_smartclass_create_quiz' => [
        'classname'   => 'local_smartclass_external',
        'methodname'  => 'create_quiz',
        'description' => 'Create a mod_quiz activity with SmartClass questions (MCQ + essay for short answers).',
        'type'        => 'write',
        'ajax'        => true,
        'services'    => ['smartclass'],
    ],
    'local_smartclass_quiz_attempts' => [
        'classname'   => 'local_smartclass_external',
        'methodname'  => 'quiz_attempts',
        'description' => 'List the finished attempts of a mod_quiz activity with per-question responses.',
        'type'        => 'read',
        'ajax'        => true,
        'services'    => ['smartclass'],
    ],
];
