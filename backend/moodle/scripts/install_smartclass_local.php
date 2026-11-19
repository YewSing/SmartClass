<?php
// Installs the local_smartclass plugin (mounted read-only at /smartclass_local) into
// /bitnami/moodle/local/smartclass. Idempotent: replaces it when the version differs.
// Moodle's upgrade (admin/cli/upgrade.php or install_components.php) then registers it.
// Run: docker exec -u daemon smartclass-moodle-moodle-1 php /scripts/install_smartclass_local.php
const SC_VERSION = 2026111902;
const SC_DEST = '/bitnami/moodle/local/smartclass';
const SC_SRC = '/smartclass_local';

function sc_installed_version(string $dir): ?int {
    $file = $dir . '/version.php';
    if (!is_readable($file)) return null;
    $text = file_get_contents($file);
    if ($text === false || !preg_match('/\$plugin->version\s*=\s*(\d+)/', $text, $m)) return null;
    return (int)$m[1];
}

function sc_rrmdir(string $dir): void {
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

if (sc_installed_version(SC_DEST) === SC_VERSION) {
    echo "local_smartclass already installed (" . SC_VERSION . ")\n";
    exit(0);
}

sc_rrmdir(SC_DEST);

// Every FILE under SC_SRC, as a path relative to SC_SRC (Unix separators).
$files = [];
$it = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator(SC_SRC, FilesystemIterator::SKIP_DOTS),
    RecursiveIteratorIterator::LEAVES_ONLY
);
foreach ($it as $item) {
    $rel = substr((string)$item->getPathname(), strlen(SC_SRC) + 1);
    $files[] = str_replace('\\', '/', $rel);
}

if (!is_dir(SC_DEST) && !mkdir(SC_DEST, 0775, true)) {
    fwrite(STDERR, "Could not create " . SC_DEST . "\n");
    exit(1);
}
foreach ($files as $rel) {
    $to = SC_DEST . '/' . $rel;
    if (!is_dir(dirname($to)) && !mkdir(dirname($to), 0775, true)) {
        fwrite(STDERR, "Could not create " . dirname($to) . "\n");
        exit(1);
    }
    if (!copy(SC_SRC . '/' . $rel, $to)) {
        fwrite(STDERR, "Could not copy $rel\n");
        exit(1);
    }
}
echo "local_smartclass " . SC_VERSION . " installed (" . count($files) . " files); run the Moodle upgrade next\n";
