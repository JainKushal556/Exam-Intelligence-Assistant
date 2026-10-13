

def structure_retrieved_chunks(chunks: list) -> dict:
    """
    Convert SQL tuple/dict rows into structured data for
    LLM context and frontend source display.
    """

    # Must match the SELECT column order in your retrieval SQL.
    column_names = [
        "subject",
        "course_code",
        "year",
        "semester",
        "exam_type",
        "source_filename",
        "file_hash",
        "total_pages",
        "paper_id",
        "parent_question_no",
        "question_no",
        "question_text",
        "topic",
        "subtopic",
        "topic_keywords",
        "unit_name",
        "marks",
        "marks_scheme",
        "page_start",
        "page_end",
        "metadata",
        "similarity",
    ]

    structured_chunks = []
    context_parts = []
    sources = []

    for index, chunk in enumerate(chunks, start=1):

        # Convert tuple/list row to dictionary
        if isinstance(chunk, dict):
            record = chunk

        elif isinstance(chunk, (tuple, list)):
            if len(chunk) != len(column_names):
                raise ValueError(
                    f"Row {index} has {len(chunk)} values, "
                    f"but {len(column_names)} columns were expected. "
                    "Check the SELECT column order."
                )

            record = dict(zip(column_names, chunk))

        else:
            raise TypeError(
                f"Unsupported row type: {type(chunk).__name__}"
            )

        # 1. Structured question record
        item = {
            "source_id": index,
            "paper_id": record.get("paper_id"),
            "question_no": record.get("question_no"),
            "parent_question_no": record.get("parent_question_no"),
            "question_text": record.get("question_text"),
            "topic": record.get("topic"),
            "subtopic": record.get("subtopic"),
            "topic_keywords": record.get("topic_keywords") or [],
            "unit_name": record.get("unit_name"),
            "marks": record.get("marks"),
            "marks_scheme": record.get("marks_scheme"),
            "subject": record.get("subject"),
            "course_code": record.get("course_code"),
            "year": record.get("year"),
            "semester": record.get("semester"),
            "exam_type": record.get("exam_type"),
            "source_filename": record.get("source_filename"),
            "page_start": record.get("page_start"),
            "page_end": record.get("page_end"),
            "similarity": record.get("similarity"),
        }

        structured_chunks.append(item)

        # 2. Context for the LLM
        context_parts.append(
            f"""
Year: {item['year']}
Semester: {item['semester']}
Question: {item['question_text']}
Topic: {item['topic']}
Marks: {item['marks']}
""".strip()
        )

        # 3. Source information for frontend
        sources.append({
            "source_id": index,
            "question_no": item["question_no"],
            "question_text": item["question_text"],
            "topic": item["topic"],
            "subtopic": item["subtopic"],
            "subject": item["subject"],
            "year": item["year"],
            "source_filename": item["source_filename"],
            "page_start": item["page_start"],
            "page_end": item["page_end"],
            "marks": item["marks"],
            "similarity": item["similarity"],
        })

    return {
        "retrieved_count": len(structured_chunks),
        "chunks": structured_chunks,
        "context": "\n\n---\n\n".join(context_parts),
        "sources": sources,
    }
