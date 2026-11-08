<?php
// Configures Moodle as a SPeCTRUM simulation: web services, REST, "smartclass" service,
// token capabilities, service account + token, branding. Idempotent.
// Run: docker exec smartclass-moodle-moodle-1 php /scripts/configure_moodle.php
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
require_once($CFG->libdir . '/clilib.php');
require_once($CFG->dirroot . '/webservice/lib.php');
require_once($CFG->dirroot . '/user/lib.php');
require_once($CFG->libdir . '/externallib.php');

\core\session\manager::set_user(get_admin());
$sys = context_system::instance();

// 1. Web services + REST
set_config('enablewebservices', 1);
set_config('enablemobilewebservice', 1);
\core\plugininfo\webservice::enable_plugin('rest', 1);
set_config('passwordpolicy', 0);          // simple dev passwords
set_config('maxbytes', 536870912);        // 512MB uploads

// 2. External service "smartclass"
$functions = [
    'core_webservice_get_site_info', 'core_enrol_get_users_courses', 'core_enrol_get_enrolled_users',
    'core_course_get_contents', 'core_course_get_courses_by_field', 'core_user_get_users_by_field',
];
$wsman = new webservice();
$service = $DB->get_record('external_services', ['shortname' => 'smartclass']);
if (!$service) {
    $s = new stdClass();
    $s->name = 'smartclass'; $s->shortname = 'smartclass'; $s->enabled = 1;
    $s->restrictedusers = 0; $s->downloadfiles = 1; $s->uploadfiles = 0;
    $s->requiredcapability = null;
    $id = $wsman->add_external_service($s);
    $service = $DB->get_record('external_services', ['id' => $id]);
    echo "Created service smartclass (id $id)\n";
} else {
    $service->enabled = 1; $service->restrictedusers = 0; $service->downloadfiles = 1;
    $DB->update_record('external_services', $service);
}
foreach ($functions as $fn) {
    if (!$wsman->service_function_exists($fn, $service->id)) {
        $wsman->add_external_function_to_service($fn, $service->id);
        echo "  + $fn\n";
    }
}

// 3. Let ordinary users create tokens and use REST
$authrole = $DB->get_field('role', 'id', ['shortname' => 'user'], MUST_EXIST);
foreach (['moodle/webservice:createtoken', 'webservice/rest:use'] as $cap) {
    assign_capability($cap, CAP_ALLOW, $authrole, $sys->id, true);
}

// 4. Service account (site admin so it can read all courses/enrolments) + permanent token
$svc = $DB->get_record('user', ['username' => 'smartclass_svc', 'mnethostid' => $CFG->mnet_localhost_id]);
if (!$svc) {
    $u = new stdClass();
    $u->username = 'smartclass_svc';
    $u->firstname = 'SmartClass'; $u->lastname = 'Service'; $u->email = 'smartclass_svc@example.com';
    $u->auth = 'manual'; $u->confirmed = 1; $u->mnethostid = $CFG->mnet_localhost_id;
    $u->password = hash_internal_user_password('Svc-Smartclass-123!');
    $uid = user_create_user($u, false, false);
    $svc = $DB->get_record('user', ['id' => $uid]);
    echo "Created user smartclass_svc\n";
}
$admins = explode(',', $CFG->siteadmins);
if (!in_array($svc->id, $admins)) {
    $admins[] = $svc->id;
    set_config('siteadmins', implode(',', $admins));
}
$tok = $DB->get_record('external_tokens', ['userid' => $svc->id, 'externalserviceid' => $service->id, 'tokentype' => EXTERNAL_TOKEN_PERMANENT]);
if ($tok) {
    $token = $tok->token;
} else {
    $token = external_generate_token(EXTERNAL_TOKEN_PERMANENT, $service, $svc->id, $sys);
}

// 5. Branding: Boost + UM navy
set_config('theme', 'boost');
set_config('brandcolor', '#1B3A6B', 'theme_boost');
$site = $DB->get_record('course', ['id' => SITEID]);
$site->fullname = 'SPeCTRUM (Simulated)'; $site->shortname = 'SPeCTRUM';
$DB->update_record('course', $site);
theme_reset_all_caches();
purge_all_caches();

echo "SMARTCLASS_SVC_TOKEN=$token\n";
