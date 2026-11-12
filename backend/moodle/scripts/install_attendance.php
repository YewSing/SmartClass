<?php
// Installs mod_attendance (pinned to the MOODLE_405_STABLE commit below) into /bitnami/moodle/mod/attendance.
// Idempotent: does nothing when that version is already there. Moodle's upgrade.php then registers it.
// Run: docker exec -u daemon smartclass-moodle-moodle-1 php /scripts/install_attendance.php
const SHA = '7985321ce811bdbc0f9728c0918518b8b5936bae';
const VERSION = 2024082404;
$dest = '/bitnami/moodle/mod/attendance';
$stage = '/bitnami/moodle/.smartclass_stage';   // same filesystem as $dest, so rename() works

// The $plugin->version in a plugin folder's version.php, or null when it is not there.
function installed_version(string $dir): ?int {
    $file = $dir . '/version.php';
    if (!is_readable($file)) return null;
    $text = file_get_contents($file);
    if ($text === false || !preg_match('/\$plugin->version\s*=\s*(\d+)/', $text, $m)) return null;
    return (int)$m[1];
}

// Recursive delete: files, symlinks and nested dirs. No-op when the directory is absent.
function rrmdir(string $dir): void {
    if (is_link($dir)) { unlink($dir); return; }
    if (!is_dir($dir)) return;
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );
    foreach ($it as $item) {
        if ($item->isDir() && !$item->isLink()) rmdir($item->getPathname());
        else unlink($item->getPathname());
    }
    rmdir($dir);
}

if (installed_version($dest) === VERSION) {
    echo "mod_attendance already installed (" . VERSION . ")\n";
    exit(0);
}

$url = 'https://codeload.github.com/danmarsden/moodle-mod_attendance/zip/' . SHA;
$zip = file_get_contents($url);
if ($zip === false) {
    fwrite(STDERR, "Download failed\n");
    exit(1);
}

rrmdir($stage);
if (!mkdir($stage, 0775, true)) {
    fwrite(STDERR, "Could not create $stage\n");
    exit(1);
}
if (file_put_contents($stage . '/attendance.zip', $zip) === false) {
    fwrite(STDERR, "Could not write the downloaded zip\n");
    rrmdir($stage);
    exit(1);
}

$archive = new ZipArchive();
if ($archive->open($stage . '/attendance.zip') !== true) {
    fwrite(STDERR, "Could not open the downloaded zip\n");
    rrmdir($stage);
    exit(1);
}
$archive->extractTo($stage);
$archive->close();

$src = $stage . '/moodle-mod_attendance-' . SHA;
if (installed_version($src) !== VERSION) {
    fwrite(STDERR, "Unexpected plugin version in download\n");
    rrmdir($stage);
    exit(1);
}

if (file_exists($dest) || is_link($dest)) rrmdir($dest);
if (!rename($src, $dest)) {
    fwrite(STDERR, "Could not move the plugin into $dest\n");
    rrmdir($stage);
    exit(1);
}
rrmdir($stage);
echo "Installed mod_attendance " . VERSION . "\n";
