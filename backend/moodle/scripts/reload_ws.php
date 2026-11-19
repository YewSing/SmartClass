<?php
// Registers local_smartclass's external functions into mdl_external_functions
// (the upgrade path can skip this when a partial install already recorded the plugin).
// Idempotent. Run: docker exec -u daemon smartclass-moodle-moodle-1 php /scripts/reload_ws.php
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
require_once($CFG->libdir . '/externallib.php');

\core\session\manager::set_user(get_admin());
external_reload_component('local_smartclass');
purge_all_caches();
echo "external functions reloaded\n";
