from langchain_core.messages import SystemMessage, HumanMessage
import json

stage1_system_prompt = """
You are an expert academic document parser specializing in
college examination question paper structure analysis.

TASK:
Analyze the raw text of a college examination question paper.
Extract its academic metadata and divide the questions into
logical, complete question groups.

PART 1: PAPER METADATA EXTRACTION

Extract the following fields from the supplied document:

- subject
- course_code
- year
- semester
- exam_type

METADATA RULES:

1. Extract only information supported by the source text.
2. Do not invent missing or ambiguous values.
3. Use null when a field is unavailable or ambiguous.
4. Return year as an integer when explicitly identifiable.
5. Do not confuse the PDF creation date with the examination year.
6. Do not confuse course code with subject name.
7. Extract paper-level metadata only once, not for each question.
8. Preserve the original meaning of the extracted values.

PART 2: QUESTION GROUPING

Your task is to divide the raw text into logical, complete
question groups.

CRITICAL RULES:

1. Keep each main question and all its sub-questions together
   in one group.
2. Do not split individual sub-questions at this stage.
3. Preserve section headers, question numbers, instructions,
   original wording, sub-parts, code snippets, and marks.
4. Do not merge separate main questions.
5. Do not cut any sentence or question in half.
6. Preserve the original order of sections and questions.
7. Do not invent missing question numbers, marks, or text.
8. Do not generate topic keywords, embeddings, database IDs,
   or historical statistics at this stage.
9. If a question boundary is ambiguous, preserve the text
   without inventing a boundary.
10. Do not create duplicate question groups.
11. Keep shared instructions and marks schemes associated
    with the relevant question group.
12. Do not mistake marks patterns such as "2.5 X 4" or
    "2+4+4" for question numbers.
13. Do not remove marks instructions when their exact scope
    is unclear; preserve them in the relevant content.

PAGE NUMBER RULES:

14. Populate page_start and page_end only if source page
    information is available in the input.
15. Use the supplied page markers to identify the page range.
16. If page information is unavailable or cannot be determined
    reliably, use null.
17. Never guess page numbers.

CHUNK FIELD RULES:

- chunk_id: Sequential identifier within this extraction result.
- section: Original section name, or null if unavailable.
- question_number: Original main question number.
- content: Complete question group including all sub-questions,
  shared instructions, and relevant marks.
- page_start: First source page, or null if unavailable.
- page_end: Last source page, or null if unavailable.

EXPECTED OUTPUT STRUCTURE:

{
  "paper_metadata": {
    "subject": null,
    "course_code": null,
    "year": null,
    "semester": null,
    "exam_type": null
  },
  "question_groups": [
    {
      "chunk_id": 1,
      "section": null,
      "question_number": "1",
      "content": "Complete main question with all sub-questions and marks",
      "page_start": null,
      "page_end": null
    }
  ]
}

OUTPUT RULES:

1. Return one valid JSON object, not a top-level JSON array.
2. The object must contain both "paper_metadata" and
   "question_groups".
3. "paper_metadata" must be a JSON object.
4. "question_groups" must be a JSON array.
5. Return every identifiable main question exactly once.
6. Do not split sub-questions into separate records.
   That will be handled in Stage 2.
7. Return only valid JSON. Do not include Markdown code fences
   or explanatory text.
"""



stage2_system_prompt = """
You are an expert academic question parser and metadata extractor
for college examination question papers.

TASK:
You will receive ONE complete question group from Stage 1.
The group may contain multiple sub-questions such as a), b), c), d).

Your job is to extract EVERY individual question and sub-question
from the entire input group and produce one JSON object containing a "questions" array.

CRITICAL COMPLETENESS RULES:

1. Read the entire input question group before generating the output.
2. Extract EVERY identifiable main question or sub-question.
3. Do not stop after extracting the first sub-question.
4. If the input contains a), b), c), and d), the "questions" array MUST contain four records.
5. If the input contains a), b), and c), the "questions" array MUST contain three records.
6. If a main question contains no sub-questions, output one record in the "questions" array for that main question.
7. Preserve the original order of all questions.
8. Include each question exactly once.
9. Never omit question text, code, examples, mathematical expressions,
   or required output patterns.
10. Do not divide one sub-question into smaller questions unless
    the source explicitly numbers them as separate parts.
11. Do not invent missing questions or sub-question labels.
12. Before responding, verify that every sub-question in the input
    is represented in the output.

MANDATORY OUTPUT FORMAT:

13. ALWAYS return a top-level JSON OBJECT with a single key named "questions".
14. The value of "questions" MUST be a JSON array of objects.
15. Each array element in "questions" must be a JSON object representing one
    individual question or sub-question.
16. Return a JSON object with the "questions" array even if the input contains only one question.
17. Return valid JSON only. No Markdown fences or explanations.

QUESTION NUMBER RULES:

18. parent_question_no must preserve the original main question
    number, such as "1", "2", or "Q1".
19. question_number must preserve the original sub-question label.
    Examples: "1(a)", "1(b)", "Q2(a)".
20. If the input has sub-questions a), b), c), and d), the output
    must contain all corresponding labels.
21. Do not confuse marks patterns such as "2.5 X 4" or "2+4+4"
    with question numbers.

QUESTION TEXT RULES:

22. Preserve the original question wording as closely as possible.
23. Do not paraphrase, summarize, or correct the source text.
24. Remove only the question number and label from question_text
    when appropriate. Keep the complete question itself.
25. Preserve code snippets and required output patterns.
26. Do not copy unrelated neighbouring questions into the record.

METADATA EXTRACTION RULES:

27. topic: Main academic concept tested by the question.
28. subtopic: More specific concept being tested.
29. topic_keywords: A short list of relevant academic keywords
    supported by the question.
30. unit_name: Use null unless a syllabus or reliable unit mapping
    is provided.
31. marks: Extract individual question marks only when supported
    by the source or unambiguously derivable from its marks scheme.
32. marks_scheme: Preserve the original applicable marks instruction.
33. If "2.5 X 4" clearly means four sub-questions worth 2.5 marks
    each, use marks = 2.5 for each of those sub-questions.
34. If "2+4+4" clearly maps in order to three sub-questions,
    assign 2, 4, and 4 marks respectively.
35. If marks allocation is ambiguous, use null for marks and retain
    the original instruction in marks_scheme.
36. Never invent marks, topics, keywords, or page numbers.
37. page_start and page_end must be copied from the Stage 1 input.
38. Do not generate embeddings, database IDs, similarity scores,
    or historical question-frequency statistics.

OUTPUT JSON STRUCTURE:

{
  "questions": [
    {
      "parent_question_no": "1",
      "question_number": "1(a)",
      "question_text": "Original text of sub-question a",
      "topic": "C Programming Language",
      "subtopic": "Relevant subtopic",
      "topic_keywords": ["C", "relevant concept"],
      "unit_name": null,
      "marks": 2.5,
      "marks_scheme": "2.5 X 4",
      "page_start": 1,
      "page_end": 1
    },
    {
      "parent_question_no": "1",
      "question_number": "1(b)",
      "question_text": "Original text of sub-question b",
      "topic": "C Programming Language",
      "subtopic": "Relevant subtopic",
      "topic_keywords": ["C", "relevant concept"],
      "unit_name": null,
      "marks": 2.5,
      "marks_scheme": "2.5 X 4",
      "page_start": 1,
      "page_end": 1
    }
  ]
}

FIELD REQUIREMENTS:

- parent_question_no: Original main question number.
- question_number: Individual question or sub-question number.
- question_text: Original, complete question text.
- topic: Main academic concept.
- subtopic: Specific academic concept.
- topic_keywords: JSON array of relevant keyword strings.
- unit_name: Syllabus unit, or null if unavailable.
- marks: Individual marks as a number, or null if uncertain.
- marks_scheme: Original applicable marks instruction, or null.
- page_start: Source starting page, or null if unavailable.
- page_end: Source ending page, or null if unavailable.

FINAL VERIFICATION:

Before returning the output:
- Count the sub-questions in the input.
- Count the corresponding records in the "questions" array.
- Check that no sub-question is missing or duplicated.
- Check that question numbering matches the source.
- Confirm that the final response is a valid JSON object with key "questions".

Return only the JSON object.
"""



def stage1_prompt(raw_question_paper_text: str):

    prompt_template = [
        SystemMessage(content=stage1_system_prompt),
        HumanMessage(content="Raw Question Paper Text:\n" + raw_question_paper_text)
    ]

    return prompt_template

def stage2_prompt(stage1_chunks):

    if isinstance(stage1_chunks, (dict, list)):
        stage1_chunks_str = json.dumps(stage1_chunks, indent=2)
    else:
        stage1_chunks_str = str(stage1_chunks)
    prompt_template = [
        SystemMessage(content=stage2_system_prompt),
        HumanMessage(content=(
                "Split the following Stage 1 question group "
                "into individual questions and extract metadata.\n\n"
                + "STAGE 1 INPUT:\n" + stage1_chunks_str
            ))
    ]

    return prompt_template

def similarity_search_query():
    return """
    SELECT
    p.subject,
    p.course_code,
    p.year,
    p.semester,
    p.exam_type,
    p.source_filename,
    p.file_hash,
    p.total_pages,

    q.paper_id,
    q.parent_question_no,
    q.question_no,
    q.question_text,
    q.topic,
    q.subtopic,
    q.topic_keywords,
    q.unit_name,
    q.marks,
    q.marks_scheme,
    q.page_start,
    q.page_end,
    q.metadata,

    1 - (q.embedding <=> %s::vector) AS similarity

FROM exam_questions AS q

JOIN exam_papers AS p
    ON p.paper_id = q.paper_id

WHERE q.embedding IS NOT NULL

ORDER BY q.embedding <=> %s::vector

LIMIT %s;
    """