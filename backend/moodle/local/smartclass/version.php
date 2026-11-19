<?php
// local_smartclass: exposes the web-service functions SmartClass needs that Moodle
// core does not provide (creating a mod_quiz activity with questions).
defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_smartclass';
$plugin->version = 2026111902;
$plugin->requires = 2024100700;  // Moodle 4.5
