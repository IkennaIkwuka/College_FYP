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
