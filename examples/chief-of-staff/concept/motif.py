"""Fixture motif: a serif C whose opening holds a check stroke."""

from pathlib import Path

from logo_maker.motif import Motif

U = 330
CHECK = [(410, 530), (410 + 0.42 * U, 530 + 0.42 * U), (410 + 1.25 * U, 530 - 0.62 * U)]

m = Motif()
letter, _ = m.glyphs("C", "Playfair Display:wght=900", 780, 210, 770)
letter = m.difference(letter, m.stroke(CHECK, 150))
m.add("letter", letter, fill="#1E4A7A", role="primary")
m.add("check", m.stroke(CHECK, 80), fill="#2F6B4F", role="secondary", height=1.27)
m.save(Path(__file__).parent)
