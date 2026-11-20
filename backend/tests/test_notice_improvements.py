from ingestion.chunker import (
    SemanticChunker,
    strip_notice_boilerplate,
)
from ingestion.schemas import ExtractedTable, FetchedDocument, NoticeMemoryData
from ingestion.supersession_resolver import SupersessionResolver
from ingestion.table_extractor import split_table_to_chunks


def test_strip_notice_boilerplate_removes_letterhead_and_copy_to():
    sample_text = """GOVERNMENT ENGINEERING COLLEGE, AJMER
AN AUTONOMOUS INSTITUTION OF GOVT. OF RAJASTHAN
NH-8, BARLIYA CHORAHA, AJMER - 305025

Ref: ECA/Exam/2026/105                                Date: 12.11.2026

OFFICE ORDER

All the students of B.Tech V Semester (Main/Back) are hereby informed that
the Mid Term Examination will commence from 25.11.2026. The detailed schedule
is available on the college website.

All students must carry their college identity card and admit card.

Page 1 of 2

Copy forwarded for information and necessary action to:
1. Principal for kind information
2. All HODs (CSE/ECE/EE/ME/CE)
3. Proctor Section
4. Chief Warden
5. Webmaster for website upload
6. Guard file
"""
    cleaned = strip_notice_boilerplate(sample_text)

    # Core message, dates, and ref must be preserved
    assert "B.Tech V Semester (Main/Back)" in cleaned
    assert "25.11.2026" in cleaned
    assert "Ref: ECA/Exam/2026/105" in cleaned

    # Boilerplate distribution and page footer must be stripped
    assert "Principal for kind information" not in cleaned
    assert "Guard file" not in cleaned
    assert "Copy forwarded" not in cleaned
    assert "Page 1 of 2" not in cleaned
    assert "GOVERNMENT ENGINEERING COLLEGE, AJMER" not in cleaned
    assert "NH-8, BARLIYA CHORAHA" not in cleaned


def test_split_table_to_chunks_preserves_repeated_markdown_headers():
    headers = ["Date", "Day", "Time", "Semester", "Branch", "Subject"]
    rows = [
        ["2026-11-25", "Monday", "10:00-11:00", "5th Sem", "CSE", f"Subject {i}"]
        for i in range(1, 25)
    ]
    table = ExtractedTable(
        headers=headers,
        rows=rows,
        page_number=1,
        title="Mid Term Timetable",
    )

    chunks = split_table_to_chunks(table, max_rows=10)
    assert len(chunks) == 3  # 10 + 10 + 4 rows

    for idx, sub_table in enumerate(chunks, start=1):
        md = sub_table.to_markdown()
        # Each split sub-chunk must have the exact Markdown header row and separator
        assert "| Date | Day | Time | Semester | Branch | Subject |" in md
        assert "| --- | --- | --- | --- | --- | --- |" in md
        assert f"Part {idx}/3" in sub_table.title

    # Total rows across all chunks must equal original 24
    total_rows = sum(len(c.rows) for c in chunks)
    assert total_rows == 24


def test_contextual_header_injection_and_token_safety():
    chunker = SemanticChunker(target_tokens=400, max_tokens=500)

    # Sample notice
    doc = FetchedDocument(
        source_url="https://ecajmer.ac.in/circulars/cs-it/101.pdf",
        source_type="pdf",
        raw_content=b"sample content",
        extracted_text="""# Registration for Odd Semester 2026-27

All students of B.Tech 3rd, 5th, and 7th Semester are required to deposit their college fees
and complete registration through the college ERP portal before 20.08.2026.
Late fees of Rs. 100 per day will be applicable after the due date.""",
        tables=[],
        metadata={
            "title": "Registration Notice for Odd Semester 2026-27",
            "sno": "ECA/Acad/2026/89",
            "document_date": "2026-08-01",
            "department": "Computer Science and Engineering",
            "semester": "3rd Sem, 5th Sem, 7th Sem",
            "target_branch": ["CSE", "IT"],
        },
    )

    memory_data = NoticeMemoryData(
        notice_type="fee_notice",
        department="Computer Science and Engineering",
        target_year=["2nd Year", "3rd Year", "4th Year"],
        target_semester=["3rd Sem", "5th Sem", "7th Sem"],
        target_branch=["CSE", "IT"],
        academic_session="2026-27",
        effective_date="2026-08-01",
        notice_serial="ECA/Acad/2026/89",
        title_summary="Odd Semester Fee Registration 2026-27",
        key_facts=[{"fact": "Last date without fine is 20.08.2026", "category": "deadline"}],
        content_fingerprint="fee_notice:cse-it:3rd-sem-5th-sem:2026-27",
    )

    chunks = chunker.chunk_document(doc, memory_data=memory_data)
    assert len(chunks) >= 1

    for chk in chunks:
        # Contextual header must be prepended
        assert "[Notice: Odd Semester Fee Registration 2026-27" in chk.content
        assert "Ref: ECA/Acad/2026/89" in chk.content
        assert "Section: Computer Science and Engineering" in chk.content
        # Token count must remain within safe budget
        assert chk.token_count <= 550


def test_corrigendum_and_revision_detection():
    # Should detect revisions
    assert SupersessionResolver.is_corrigendum_or_revision("Revised Mid Term Examination Schedule")
    assert SupersessionResolver.is_corrigendum_or_revision("Corrigendum regarding B.Tech Fee Date")
    assert SupersessionResolver.is_corrigendum_or_revision("Postponement of Practical Examination")
    assert SupersessionResolver.is_corrigendum_or_revision(
        "Notice in continuation of Office Order No. 42"
    )
    assert SupersessionResolver.is_corrigendum_or_revision(
        "Extension of last date for form submission"
    )


def test_portal_chronological_ordering_and_metadata_extraction():
    from datetime import date

    from ingestion.schemas import ChunkData
    from ingestion.upsert import (
        _clean_extracted_title,
        _extract_document_meta,
        _parse_notice_date,
    )

    # 1. Date parsing validation
    assert _parse_notice_date("2026-11-18") == date(2026, 11, 18)
    assert _parse_notice_date("18-11-2026") == date(2026, 11, 18)
    assert _parse_notice_date("2311-01-20") is None  # Out-of-range year rejected

    # 2. Boilerplate title rejection
    assert _clean_extracted_title("ENGINEERING COLLEGE AJMER") is None
    assert _clean_extracted_title("Govt. Engineering College, Ajmer") is None
    assert _clean_extracted_title("Department of Computer Science & Engineering") is None
    assert _clean_extracted_title("NOTICE") is None
    assert (
        _clean_extracted_title("Rescheduling of DE Lab Practical Examination")
        == "Rescheduling of DE Lab Practical Examination"
    )

    # 3. Metadata extraction with ground-truth title from portal
    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/uploads/circulars/1794978741521-Document 294.pdf",
        source_type="pdf",
        raw_content=b"test",
        extracted_text="Some text",
        metadata={
            "title": "Mercy Test for 5th Semester CS, IT and Cyber Security Students (2026-27)",
            "sno": "2026WEB0889",
            "date": "2026-11-18",
            "portal_id": 889,
        },
    )
    title, sno, dt, pid = _extract_document_meta(fetched, [])
    assert title == "Mercy Test for 5th Semester CS, IT and Cyber Security Students (2026-27)"
    assert sno == "2026WEB0889"
    assert dt == date(2026, 11, 18)
    assert pid == 889

    # 4. Fallback extraction from chunk content avoiding boilerplate letterheads
    fetched_empty_meta = FetchedDocument(
        source_url="https://ecajmer.ac.in/uploads/circulars/1794976846205-Document 293.pdf",
        source_type="pdf",
        raw_content=b"test",
        extracted_text="",
        metadata={},
    )
    chunk_letterhead = ChunkData(
        content="# ENGINEERING COLLEGE AJMER\nRef. No. 123",
        token_count=10,
        chunk_index=0,
    )
    chunk_body = ChunkData(
        content="# Rescheduling of DE Lab Practical Examination\n**Notice S.No:** 2026WEB0888\n**Date:** 2026-11-18",
        token_count=20,
        chunk_index=1,
    )
    title2, sno2, dt2, pid2 = _extract_document_meta(
        fetched_empty_meta, [chunk_letterhead, chunk_body]
    )
    assert title2 == "Rescheduling of DE Lab Practical Examination"
    assert sno2 == "2026WEB0888"
    assert dt2 == date(2026, 11, 18)
    assert pid2 == 888

    # 5. Strict chronological ordering parity with college portal
    notices = [
        {"sno": "2025WEB0959", "date": date(2025, 11, 20), "portal_id": 959},
        {"sno": "2026WEB0887", "date": date(2026, 11, 18), "portal_id": 887},
        {"sno": "2026WEB0889", "date": date(2026, 11, 18), "portal_id": 889},
        {"sno": "2026WEB0888", "date": date(2026, 11, 18), "portal_id": 888},
        {"sno": "2026WEB0874", "date": date(2026, 11, 3), "portal_id": 874},
    ]

    sorted_notices = sorted(
        notices,
        key=lambda x: (x["date"], x["sno"], x["portal_id"]),
        reverse=True,
    )

    expected_snos = ["2026WEB0889", "2026WEB0888", "2026WEB0887", "2026WEB0874", "2025WEB0959"]
    assert [n["sno"] for n in sorted_notices] == expected_snos
