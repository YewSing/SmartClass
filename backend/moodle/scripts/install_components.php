<?php
// Installs any dropped-in plugins (e.g. local_smartclass) when core is already current
// and `admin/cli/upgrade.php` therefore short-circuits. Idempotent.
// Run: docker exec -u daemon smartclass-moodle-moodle-1 php /scripts/install_components.php
define('CLI_SCRIPT', true);
require('/bitnami/moodle/config.php');
require_once($CFG->libdir . '/adminlib.php');
require_once($CFG->libdir . '/upgradelib.php');

\core\session\manager::set_user(get_admin());
$result = upgrade_noncore(true);
purge_all_caches();
echo "upgrade_noncore done\n";
