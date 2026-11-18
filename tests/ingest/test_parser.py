from __future__ import annotations

from ingest.parser import parse_pdf


def _sections(doc):
    return {s.section_id: s for s in doc.sections}


def long_table(n: int) -> str:
    rows = "\n".join(
        f"| E-{100 + i} | Fault number {i}, a description long enough to wrap in its cell "
        f"so rows have uneven heights | Check joint J{i % 6 + 1} |"
        for i in range(n)
    )
    return f"| Code | Description | Action |\n|---|---|---|\n{rows}\n"


def test_headings_levels_paths_and_pages(make_pdf):
    md = """# Cover

Intro text on the cover.

<!-- pagebreak -->

# 1 Safety

Read this first.

## 1.1 Lockout

Lock the main switch.

### 1.1.1 Verification

Try to start the drives.

<!-- pagebreak -->

# 2 Troubleshooting

## 2.1 Overheating

Check the fan.

# Appendix A Glossary

Terms.
"""
    doc = parse_pdf(make_pdf(md))
    s = _sections(doc)

    assert s["1.1.1"].heading_path == ["1 Safety", "1.1 Lockout", "1.1.1 Verification"]
    assert s["1.1.1"].level == 3
    assert s["2.1"].heading_path == ["2 Troubleshooting", "2.1 Overheating"]
    assert s["A"].heading_path == ["Appendix A Glossary"]
    assert s["1"].page_start == 2
    assert s["2"].page_start == 3
    assert s["2.1"].blocks[0].text == "Check the fan."
    # Unnumbered text before the first numbered heading is front matter, not a heading.
    assert doc.sections[0].section_id == ""
    assert "Intro text on the cover." in [b.text for b in doc.sections[0].blocks]


def test_running_header_and_footer_are_removed(make_pdf):
    md = "\n\n<!-- pagebreak -->\n\n".join(
        f"# {i} Chapter {i}\n\nBody of chapter {i}." for i in range(1, 6)
    )
    doc = parse_pdf(make_pdf(md))
    texts = [b.text for s in doc.sections for b in s.blocks]
    assert texts, "expected body text"
    assert not any("ACME Test Manual" in t or "TM-01" in t or "Page " in t for t in texts)


def test_ligatures_are_expanded(make_pdf):
    doc = parse_pdf(make_pdf("# 1 Filters\n\nThe fine filter affects airflow efficiency.\n"))
    text = _sections(doc)["1"].blocks[0].text
    assert text == "The fine filter affects airflow efficiency."
    assert not any(ch in text for ch in "ﬀﬁﬂﬃﬄ")


def test_table_broken_across_pages_is_stitched(make_pdf):
    md = f"# 1 Codes\n\nAll codes:\n\n{long_table(60)}\nAfter the table.\n"
    doc = parse_pdf(make_pdf(md))
    blocks = _sections(doc)["1"].blocks
    tables = [b for b in blocks if b.kind == "table"]

    assert len(tables) == 1
    t = tables[0]
    assert t.page_end > t.page_start, "fixture should force a page break inside the table"
    assert t.has_header and t.rows[0] == ["Code", "Description", "Action"]
    assert [r[0] for r in t.rows[1:]] == [f"E-{100 + i}" for i in range(60)]
    assert blocks[-1].text == "After the table."


def test_procedure_steps_keep_line_breaks(make_pdf):
    doc = parse_pdf(
        make_pdf("# 1 Procedure\n\n1. Stop the robot.\n2. Lock out.\n3. Open the cover.\n")
    )
    text = _sections(doc)["1"].blocks[0].text
    assert text.splitlines() == ["1. Stop the robot.", "2. Lock out.", "3. Open the cover."]


def test_ra3_manual_structure(ra3_doc):
    s = _sections(ra3_doc)
    assert ra3_doc.lang == "en"
    for sid in ("4.4", "6.2", "7.2", "7.3", "7.4", "8.1", "9.1"):
        assert sid in s, f"missing section {sid}"
    assert s["7.3.2"].heading_path == [
        "7 Troubleshooting",
        "7.3 Vibration spike (J2 vibration)",
        "7.3.2 Likely causes",
    ]

    error_table = next(b for b in s["6.2"].blocks if b.kind == "table")
    codes = [r[0] for r in error_table.rows[1:]]
    assert codes[0] == "W-110" and codes[-1] == "E-510" and "E-217" in codes
    assert len(codes) == 22

    torque = next(b for b in s["9.1"].blocks if b.kind == "table")
    j3_flange = next(r for r in torque.rows if r[0].startswith("J3 gearbox output flange"))
    assert j3_flange[1:] == ["M10", "12.9", "12", "79 Nm"]


def test_ra3_limits_match_simulator(ra3_doc):
    """The manual is written against iiot-smart-factory-sim baselines; keep them in sync."""
    limits = next(b for b in _sections(ra3_doc)["4.4"].blocks if b.kind == "table")
    baseline = {r[0].split()[0]: r[1] for r in limits.rows[1:]}
    assert baseline == {"temperature": "62.5 °C", "vibration": "1.55 g", "current": "6.0 A"}
