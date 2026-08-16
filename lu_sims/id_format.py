import re


class InvalidAcademicID(ValueError):
    pass


def format_academic_id(raw):
    """Reshape a matric number or staff ID typed with any separator/casing into
    the canonical SEGMENT/SEGMENT/SEGMENT form, e.g. "2026 csc 010" -> "2026/CSC/010".

    Requires at least one separator between all 3 segments - a fully glued
    "2026CSC010" is rejected rather than guessed at, because staff IDs have two
    adjacent alphabetic segments (role + dept code, e.g. HOD then CSC) that can't
    be split unambiguously without one.
    """
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", raw.strip()) if p]
    if len(parts) != 3:
        raise InvalidAcademicID(
            "Enter it as three parts separated by a space, dash, or slash - e.g. 2026/CSC/010."
        )
    return "/".join(p.upper() for p in parts)


def format_course_code(raw, level):
    """Reshape a course code typed with any separator/casing into DEPTXXX form,
    e.g. "csc 101" -> "CSC101", and require the number's leading digit to match
    the course's level (a 200 Level course must look like XXX2XX).

    Unlike format_academic_id, separators are optional here rather than required -
    a course code only ever has one letter-run followed by one digit-run (no risk
    of an ambiguous split like the role+dept case), so "CSC101" is unambiguous
    without a separator and is in fact the real-world convention.
    """
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw.strip())
    match = re.fullmatch(r"([A-Za-z]{2,6})(\d{3})", cleaned)
    if not match:
        raise InvalidAcademicID(
            "Enter it as a department code followed by 3 digits - e.g. CSC101 or GST102."
        )
    letters, digits = match.groups()
    expected = str(level // 100)
    if digits[0] != expected:
        raise InvalidAcademicID(
            f"A {level} Level course code should start with {letters.upper()}{expected} - got {letters.upper()}{digits}."
        )
    return f"{letters.upper()}{digits}"
