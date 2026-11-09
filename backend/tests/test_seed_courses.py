"""Every seed student must have a course with materials, or the AI assistant looks broken when tried."""
from scripts.seed import COURSES, MATERIALS_COURSE, STUDENT_DATA, courses_for_student


def test_materials_course_exists_in_the_seed():
    assert MATERIALS_COURSE in [c[0] for c in COURSES]


def test_every_seed_student_has_the_materials_course():
    all_codes = [c[0] for c in COURSES]
    for i in range(len(STUDENT_DATA)):
        chosen = courses_for_student(i, all_codes)
        assert MATERIALS_COURSE in chosen, f"student {i}"
        assert 4 <= len(chosen) <= 6
        assert len(set(chosen)) == len(chosen)
