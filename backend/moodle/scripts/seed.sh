#!/usr/bin/env bash
# Seed courses/users/enrolments/materials. Usage: seed.sh [--dry-run]
export MSYS_NO_PATHCONV=1
exec docker exec -u daemon "${MOODLE_CONTAINER:-smartclass-moodle-moodle-1}" php /scripts/seed_courses.php "$@"
