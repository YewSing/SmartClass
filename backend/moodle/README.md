# Local Moodle (SPeCTRUM simulation)

A local Moodle 4.5 (Bitnami legacy images) standing in for UM SPeCTRUM so SmartClass can call the Moodle web-service API.
Separate from the app DB in `../docker-compose.yml`.

## Start

```bash
cd backend/moodle
docker compose up -d          # first boot installs Moodle: ~3-5 min; wait for HTTP 200 on :8080/login/index.php
./scripts/setup.sh            # web services, "smartclass" service, smartclass_svc user, token -> .env.moodle, branding
./scripts/seed.sh             # users, courses, enrolments, course materials (idempotent)
./scripts/seed.sh --dry-run   # users/courses only; does not list files
```

Run the scripts from Git Bash. They `docker exec -u daemon` into `smartclass-moodle-moodle-1`.
Always run PHP as `daemon` (Apache's user). Running as root creates root-owned files in moodledata and Moodle then fails with
`invaliddatarootpermissions` / HTTP 500. If that happens: `docker exec -u 0 smartclass-moodle-moodle-1 chown -R daemon:daemon /bitnami/moodledata`.

Reset only this stack: `docker compose down -v` (removes the three `smartclass-moodle_*` volumes; never touches `backend_pgdata`).

## Accounts

| Role | Username | Password |
|---|---|---|
| Admin | admin | Admin123! |
| Lecturer | lecturer1 (WIF3001, WIF3004), lecturer2 (WIA2005) | Lecturer123! |
| Student | student1..student5 | Student123! |

Enrolments: see `seed_config.json`. Moodle UI: http://localhost:8080

## Token / API

`setup.sh` writes `backend/moodle/.env.moodle` (git-ignored):
`MOODLE_URL=http://localhost:8080` and `MOODLE_TOKEN=<smartclass_svc token>`. Copy them into `backend/.env`.

The service `smartclass` exposes: `core_webservice_get_site_info`, `core_enrol_get_users_courses`, `core_enrol_get_enrolled_users`,
`core_course_get_contents`, `core_course_get_courses_by_field`, `core_user_get_users_by_field`.

A student token (what a student login would yield):

```bash
curl -s http://localhost:8080/login/token.php -d username=student1 --data-urlencode 'password=Student123!' -d service=smartclass
curl -s http://localhost:8080/webservice/rest/server.php -d wstoken=$TOK -d wsfunction=core_enrol_get_users_courses -d userid=<id> -d moodlewsrestformat=json
curl -s http://localhost:8080/webservice/rest/server.php -d wstoken=$TOK -d wsfunction=core_course_get_contents -d courseid=<id> -d moodlewsrestformat=json
curl -L "<fileurl>&token=$TOK" -o file     # download a course file
```

## Materials seeding

`seed_config.json` lists each course's `source_folder` (under the materials root mounted read-only at `/materials`; override the host path with `MATERIALS_ROOT`).
Only `pdf`, `pptx`, `docx` are uploaded. Legacy `.doc/.ppt`, dotfiles, `venv`/`node_modules` are skipped.
`default_exclude` and each course's `exclude` globs filter out assignments, group projects, labs, PYQs and personal submissions.
Section placement follows "Week N" in the path or filename. Re-running skips files already present. Skip reasons are printed.

## Notes

- Moodle has no mail server in the container; the seed script sets `noemailever`.
- Images: `bitnamilegacy/moodle:4.5`, `bitnamilegacy/mariadb:11.4`.
