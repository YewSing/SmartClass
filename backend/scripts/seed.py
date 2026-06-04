"""
Seed script: 1 admin, 10 lecturers, 26 FSKTM courses with occurrences, 50 students
with realistic enrollment.

Run from backend/:  python scripts/seed.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal as async_session_factory
from app.core.security import hash_password
from app.models.user import User, Student, Lecturer
from app.models.class_ import Course, ClassOccurrence, Enrollment
from app.models.face import FaceEmbedding
from app.models.camera import Camera
from app.models.session import AttendanceSession
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog

# ─── Courses ─────────────────────────────────────────────────────────────────

COURSES = [
    ("WIA1002", "Data Structure",                               2),
    ("WIA1003", "Computer System Architecture",                 2),
    ("WIA1005", "Network Technology Foundation",                2),
    ("WIA1006", "Machine Learning",                             2),
    ("WIA2001", "Database",                                     2),
    ("WIA2002", "Software Modeling",                            1),
    ("WIA2003", "Probability and Statistics",                   1),
    ("WIA2004", "Operating Systems",                            2),
    ("WIA2005", "Algorithm Design and Analysis",                2),
    ("WIA2007", "Mobile Application Development",               1),
    ("WIA2010", "Human Computer Interaction",                   1),
    ("WIA3001", "Industrial Training",                          0),  # LECTURE only
    ("WIA3002", "Academic Project I",                           0),
    ("WIA3003", "Academic Project II",                          0),
    ("WIF2003", "Web Programming",                              2),
    ("WIF3001", "Software Testing",                             1),
    ("WIF3002", "Software Process and Quality",                 1),
    ("WIF3004", "Software Architecture and Design Paradigms",   1),
    ("WIF3005", "Software Maintenance and Evolution",           1),
    ("WIF3006", "Component Based Software Engineering",         1),
    ("WIF3008", "Real Time Systems",                            1),
    ("WIF3009", "Python for Scientific Computing",              2),
    ("WIF3010", "Programming Language Paradigm",                1),
    ("WIF3011", "Concurrent and Parallel Programming",          1),
    ("WIG3005", "Game Development",                             1),
    ("WIC2008", "Internet of Things",                           2),
]
# sections: 0 = LECTURE only, 1 = 1 LECTURE + 1 TUTORIAL, 2 = 1 LECTURE + 2 TUTORIALs

# ─── Lecturers ───────────────────────────────────────────────────────────────

LECTURER_DATA = [
    ("Prof. Dr. Ahmad Faizal bin Ibrahim",  "ahmadfarizal@um.edu.my",  "FS10001", "Software Engineering"),
    ("Dr. Siti Norfazila binti Ghazali",    "sitinorfazila@um.edu.my", "FS10002", "Computer Science"),
    ("Dr. Lim Chee Siong",                  "limcsiong@um.edu.my",     "FS10003", "Computer Science"),
    ("Dr. Nurul Hafizah binti Adnan",       "nhafizah@um.edu.my",      "FS10004", "Software Engineering"),
    ("Dr. Rajesh Kumar A/L Subramaniam",    "rajeshk@um.edu.my",       "FS10005", "Information Systems"),
    ("Dr. Mohd Azlan bin Hussain",          "mazlan@um.edu.my",        "FS10006", "Computer Science"),
    ("Dr. Wan Nor Arifin bin Wan Mansor",   "wnarifin@um.edu.my",      "FS10007", "Information Systems"),
    ("Dr. Tan Kian Lam",                    "tankl@um.edu.my",         "FS10008", "Software Engineering"),
    ("Dr. Farah Hani binti Nordin",         "farahhani@um.edu.my",     "FS10009", "Computer Science"),
    ("Dr. Syahrul Nizam bin Junaini",       "syahrulnj@um.edu.my",     "FS10010", "Software Engineering"),
]

# ─── Students ────────────────────────────────────────────────────────────────

STUDENT_DATA = [
    ("Ahmad Izzul Hakim bin Roslan",        "23004001", "23004001@siswa.um.edu.my"),
    ("Nurul Aina Syafiqah binti Aziz",      "23004002", "23004002@siswa.um.edu.my"),
    ("Muhammad Haziq bin Zulkifli",         "23004003", "23004003@siswa.um.edu.my"),
    ("Lim Wei Jing",                        "23004004", "23004004@siswa.um.edu.my"),
    ("Priya Devi A/P Krishnan",             "23004005", "23004005@siswa.um.edu.my"),
    ("Wan Faris bin Wan Azmi",              "23004006", "23004006@siswa.um.edu.my"),
    ("Nur Syahirah binti Ismail",           "23004007", "23004007@siswa.um.edu.my"),
    ("Chong Kai Ming",                      "23004008", "23004008@siswa.um.edu.my"),
    ("Kavitha A/P Rajan",                   "23004009", "23004009@siswa.um.edu.my"),
    ("Mohd Ridhwan bin Othman",             "23004010", "23004010@siswa.um.edu.my"),
    ("Tan Xin Yi",                          "23004011", "23004011@siswa.um.edu.my"),
    ("Firdaus Aqmal bin Hamzah",            "23004012", "23004012@siswa.um.edu.my"),
    ("Siti Aisyah binti Malik",             "23004013", "23004013@siswa.um.edu.my"),
    ("Wong Jia Xin",                        "23004014", "23004014@siswa.um.edu.my"),
    ("Aravind A/L Murugan",                 "23004015", "23004015@siswa.um.edu.my"),
    ("Khairul Nizam bin Zainal",            "23004016", "23004016@siswa.um.edu.my"),
    ("Ng Hui Shan",                         "23004017", "23004017@siswa.um.edu.my"),
    ("Izzatul Farhanah binti Nasir",        "23004018", "23004018@siswa.um.edu.my"),
    ("Chan Yee Ling",                       "23004019", "23004019@siswa.um.edu.my"),
    ("Muhammad Amir bin Kamal",             "23004020", "23004020@siswa.um.edu.my"),
    ("Deepa A/P Pillai",                    "23004021", "23004021@siswa.um.edu.my"),
    ("Zulaikha binti Rahman",               "23004022", "23004022@siswa.um.edu.my"),
    ("Lee Chun Wai",                        "23004023", "23004023@siswa.um.edu.my"),
    ("Nur Fadhilah binti Nordin",           "23004024", "23004024@siswa.um.edu.my"),
    ("Suresh A/L Gopal",                    "23004025", "23004025@siswa.um.edu.my"),
    ("Hafiz Irfan bin Azhari",              "23004026", "23004026@siswa.um.edu.my"),
    ("Yap Wen Qi",                          "23004027", "23004027@siswa.um.edu.my"),
    ("Nabilah binti Shafie",                "23004028", "23004028@siswa.um.edu.my"),
    ("Mohd Afiq bin Zainodin",              "23004029", "23004029@siswa.um.edu.my"),
    ("Tan Mei Ling",                        "23004030", "23004030@siswa.um.edu.my"),
    ("Arjun A/L Nair",                      "24004001", "24004001@siswa.um.edu.my"),
    ("Nur Izzati binti Halim",              "24004002", "24004002@siswa.um.edu.my"),
    ("Teh Jia Qi",                          "24004003", "24004003@siswa.um.edu.my"),
    ("Muhammad Irfan bin Yusof",            "24004004", "24004004@siswa.um.edu.my"),
    ("Sharmeela A/P Vijayan",               "24004005", "24004005@siswa.um.edu.my"),
    ("Amira Zahirah binti Abd Razak",       "24004006", "24004006@siswa.um.edu.my"),
    ("Chua Boon Keat",                      "24004007", "24004007@siswa.um.edu.my"),
    ("Mohamad Azri bin Zulkarnain",         "24004008", "24004008@siswa.um.edu.my"),
    ("Nisha A/P Maniam",                    "24004009", "24004009@siswa.um.edu.my"),
    ("Loh Zhi Xuan",                        "24004010", "24004010@siswa.um.edu.my"),
    ("Farhan Izzuddin bin Jaafar",          "24004011", "24004011@siswa.um.edu.my"),
    ("Shalini A/P Balakrishnan",            "24004012", "24004012@siswa.um.edu.my"),
    ("Ong Wei Kiat",                        "24004013", "24004013@siswa.um.edu.my"),
    ("Farizah binti Zainudin",              "24004014", "24004014@siswa.um.edu.my"),
    ("Ganesh A/L Ramasamy",                 "24004015", "24004015@siswa.um.edu.my"),
    ("Syafiq Amirul bin Rosli",             "24004016", "24004016@siswa.um.edu.my"),
    ("Koh Siew Lin",                        "24004017", "24004017@siswa.um.edu.my"),
    ("Ain Syazwani binti Hamid",            "24004018", "24004018@siswa.um.edu.my"),
    ("Vishnu A/L Krishnaswamy",             "24004019", "24004019@siswa.um.edu.my"),
    ("Goh Pei Shan",                        "24004020", "24004020@siswa.um.edu.my"),
]

# ─── Schedule helpers ─────────────────────────────────────────────────────────

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
SLOTS = [("08:00", "10:00"), ("10:00", "12:00"), ("14:00", "16:00"), ("16:00", "18:00")]
LEC_ROOMS = ["DK 2 FSKTM", "DK 5 FSKTM", "BILIK KULIAH 1 FSKTM", "BILIK KULIAH 2 FSKTM", "BILIK KULIAH 3 FSKTM"]
TUT_ROOMS = ["MAKMAL MIKRO 1 FSKTM", "MAKMAL LANJUTAN FSKTM", "BILIK KULIAH 3 FSKTM", "BILIK KULIAH 2 FSKTM"]


def _all_slots():
    return [(d, s, e) for d in DAYS for s, e in SLOTS]


def _assign_slot(lecturer_schedule: dict, lec_id: int, slots: list, room_pool: list, idx: list) -> tuple:
    """Return next free (day, start, end, room) for this lecturer, wrapping around slots."""
    used = lecturer_schedule.setdefault(lec_id, set())
    for _ in range(len(slots)):
        day, start, end = slots[idx[0] % len(slots)]
        idx[0] += 1
        key = (day, start)
        if key not in used:
            used.add(key)
            room = room_pool[(idx[0] - 1) % len(room_pool)]
            return day, start, end, room
    # All slots taken — reuse with different room (shouldn't happen with 20 slots and ≤4 occs/lec)
    day, start, end = slots[0]
    return day, start, end, room_pool[0]


# ─── Seed ─────────────────────────────────────────────────────────────────────

async def seed():
    async with async_session_factory() as db:
        # ── 0. Wipe existing data (FK-safe order) ──────────────────────────
        await db.execute(delete(AuditLog))
        await db.execute(delete(AttendanceRecord))
        await db.execute(delete(AttendanceSession))
        await db.execute(delete(Enrollment))
        await db.execute(delete(FaceEmbedding))
        await db.execute(delete(ClassOccurrence))  # must precede Course and Lecturer
        await db.execute(delete(Course))
        await db.execute(delete(Camera))
        await db.execute(delete(Lecturer))          # must precede User
        await db.execute(delete(Student))           # must precede User
        await db.execute(delete(User))
        await db.flush()

        # ── 1. Admin ────────────────────────────────────────────────────────
        admin = User(
            email="admin@um.edu.my",
            password_hash=hash_password("Admin@1234"),
            role="admin",
            name="Admin User",
            phone="+60312345000",
            status="active",
        )
        db.add(admin)
        await db.flush()

        # ── 2. Lecturers ────────────────────────────────────────────────────
        lecturer_ids: list[int] = []
        for name, email, staff_id, dept in LECTURER_DATA:
            u = User(
                email=email,
                password_hash=hash_password("Lecturer@1234"),
                role="lecturer",
                name=name,
                status="active",
            )
            db.add(u)
            await db.flush()
            lec = Lecturer(user_id=u.id, staff_id=staff_id, dept=dept)
            db.add(lec)
            await db.flush()
            lecturer_ids.append(lec.id)

        print(f"  Created {len(lecturer_ids)} lecturers")

        # ── 3. Courses + Occurrences ────────────────────────────────────────
        all_lec_slots = _all_slots()
        all_tut_slots = _all_slots()
        lecturer_schedule: dict[int, set] = {}
        lec_idx = [0]
        tut_idx = [10]   # offset so tutorials start at a different point in the cycle
        lec_round = [0]  # round-robin for assigning lecturers

        def next_lec() -> int:
            i = lec_round[0] % len(lecturer_ids)
            lec_round[0] += 1
            return lecturer_ids[i]

        course_occ_map: dict[str, dict] = {}  # code → {lecture_id, tutorial_ids}

        total_occ = 0
        for code, name, sections in COURSES:
            course = Course(code=code, name=name)
            db.add(course)
            await db.flush()

            occs: dict = {"lecture_id": None, "tutorial_ids": []}

            # LECTURE
            lec_id = next_lec()
            day, start, end, room = _assign_slot(lecturer_schedule, lec_id, all_lec_slots, LEC_ROOMS, lec_idx)
            lec_occ = ClassOccurrence(
                course_id=course.id, type="LECTURE",
                day_of_week=day, start_time=start, end_time=end,
                room=room, lecturer_id=lec_id, label=None,
            )
            db.add(lec_occ)
            await db.flush()
            occs["lecture_id"] = lec_occ.id
            total_occ += 1

            # TUTORIALs
            for t in range(sections):
                tut_lec_id = next_lec()
                day, start, end, room = _assign_slot(lecturer_schedule, tut_lec_id, all_tut_slots, TUT_ROOMS, tut_idx)
                label = "Tutorial" if sections == 1 else f"Tutorial Group {t + 1}"
                tut_occ = ClassOccurrence(
                    course_id=course.id, type="TUTORIAL",
                    day_of_week=day, start_time=start, end_time=end,
                    room=room, lecturer_id=tut_lec_id, label=label,
                )
                db.add(tut_occ)
                await db.flush()
                occs["tutorial_ids"].append(tut_occ.id)
                total_occ += 1

            course_occ_map[code] = occs

        print(f"  Created 26 courses, {total_occ} occurrences")

        # ── 4. Cameras (one per unique room used in occurrences) ─────────────
        rooms_result = await db.execute(
            select(ClassOccurrence.room).distinct()
        )
        unique_rooms = sorted(r for (r,) in rooms_result.all() if r)

        for idx, room in enumerate(unique_rooms, start=1):
            device_id = f"CAM-{idx:03d}"
            cam = Camera(
                label=room,
                room=room,
                device_id=device_id,
                status="online",
            )
            db.add(cam)

        await db.flush()
        print(f"  Created {len(unique_rooms)} cameras")

        # ── 5. Students + Enrollments ─────────────────────────────────────────
        all_codes = [c[0] for c in COURSES]

        for i, (name, matric, email) in enumerate(STUDENT_DATA):
            u = User(
                email=email,
                password_hash=hash_password("Student@1234"),
                role="student",
                name=name,
                status="active",
            )
            db.add(u)
            await db.flush()

            stu = Student(
                user_id=u.id,
                matric_no=matric,
                programme="Bachelor of Computer Science",
                faculty="FSKTM",
                year_sem="Year 2 Sem 1" if matric.startswith("24") else "Year 3 Sem 1",
            )
            db.add(stu)
            await db.flush()

            # 4–6 courses per student (cycles through the full course list evenly)
            num_courses = 4 + (i % 3)
            start_idx = (i * 4) % len(all_codes)
            chosen = [all_codes[(start_idx + j) % len(all_codes)] for j in range(num_courses)]

            enrolled_ids: set[int] = set()
            for code in chosen:
                occs = course_occ_map[code]

                if occs["lecture_id"] not in enrolled_ids:
                    db.add(Enrollment(student_id=stu.id, occurrence_id=occs["lecture_id"]))
                    enrolled_ids.add(occs["lecture_id"])

                if occs["tutorial_ids"]:
                    tut_id = occs["tutorial_ids"][i % len(occs["tutorial_ids"])]
                    if tut_id not in enrolled_ids:
                        db.add(Enrollment(student_id=stu.id, occurrence_id=tut_id))
                        enrolled_ids.add(tut_id)

            await db.flush()

        print(f"  Created {len(STUDENT_DATA)} students with enrollments")

        # ── 6. Dev test lecturer + always-on course ───────────────────────────
        # One occurrence per day of the week (00:00–23:59) so the time gate
        # never blocks testing. All 50 students are enrolled so face detection
        # works end-to-end without extra setup.
        test_u = User(
            email="devlecturer@um.edu.my",
            password_hash=hash_password("DevTest@1234"),
            role="lecturer",
            name="Dev Test Lecturer",
            status="active",
        )
        db.add(test_u)
        await db.flush()

        test_lec = Lecturer(user_id=test_u.id, staff_id="FS99999", dept="Testing")
        db.add(test_lec)
        await db.flush()

        test_course = Course(code="WIA0000", name="Dev Test Class")
        db.add(test_course)
        await db.flush()

        test_cam = Camera(label="TEST LAB", room="TEST LAB", device_id="CAM-TEST", status="online")
        db.add(test_cam)
        await db.flush()

        test_occs = []
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            occ = ClassOccurrence(
                course_id=test_course.id,
                type="LECTURE",
                day_of_week=day,
                start_time="00:00",
                end_time="23:59",
                room="TEST LAB",
                lecturer_id=test_lec.id,
                label=None,
            )
            db.add(occ)
            test_occs.append(occ)

        await db.flush()

        all_students_result = await db.execute(select(Student))
        all_students = all_students_result.scalars().all()
        for occ in test_occs:
            for stu in all_students:
                db.add(Enrollment(student_id=stu.id, occurrence_id=occ.id))

        await db.flush()
        print(f"  Created dev test lecturer (WIA0000, 7 occurrences, {len(all_students)} students enrolled)")

        await db.commit()
        print("\nSeed complete.")
        print("  Admin:     admin@um.edu.my / Admin@1234")
        print("  Lecturers: see LECTURER_DATA emails / Lecturer@1234")
        print("  Students:  <matric>@siswa.um.edu.my / Student@1234")
        print("  DEV test:  devlecturer@um.edu.my / DevTest@1234  (WIA0000, always-on)")


if __name__ == "__main__":
    asyncio.run(seed())
