
from google.genai import documents
from google.genai import documents
import asyncio
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from Ingestion_Pipeline.models import doc_embedding,doc_chunker_ollama_local
from Ingestion_Pipeline.vectorestore import insert_embedding_indb
from Ingestion_Pipeline.prompt import stage1_prompt , stage2_prompt
import json
import time
import re
from pathlib import Path

def default_chunker(docs: list[Document]) -> list[Document]:
    if not docs:
        print("No documents found.")
        return []

    chunksize = 1000
    overlap = 200
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunksize,
        chunk_overlap=overlap,
        add_start_index=True
        )
    chunks = text_splitter.split_documents(docs)
    print(chunks)
    embeddings = doc_embedding.embed_documents([chunk.page_content for chunk in chunks])
    insert_embedding_indb([chunk.page_content for chunk in chunks], embeddings, [chunk.metadata for chunk in chunks])

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        chunk.metadata["chunk_index"] = i
        print(f"\n--- Chunk {i} ---")
        print(f"Content:\n{chunk.page_content}")
        print(f"Metadata: {chunk.metadata}")
        print(f"Embedding (dim={len(emb)}): {emb[:5]}... [showing first 5 of {len(emb)} values]")

    print(f"\nGenerated {len(chunks)} chunks.")
    return chunks


async def llm_chunker(docs : list[Document]):

    s_time = time.time()
    source_filename = ""
    if docs:
        source_path = docs[0].metadata.get("source")      
        source_filename = Path(str(source_path).replace("\\", "/")).name

    full_text = pre_process(docs)
    e_time = time.time()
    print(f"pre_process time: {e_time - s_time:.4f}s")

    prompt = stage1_prompt(full_text)

    s_time = time.time()
    res = await doc_chunker_ollama_local.ainvoke(prompt)
    stage1_chunks = parse_json_safely(res.content)
    e_time = time.time()
    print(f"Stage 1 processing time: {e_time - s_time:.2f}s")

    paper_metadata = stage1_chunks.get("paper_metadata", {})
    question_groups = stage1_chunks.get("question_groups", [])
    paper_metadata["source"] = source_filename
    paper_metadata["total_pages"] = len(docs)
    # print("Paper Metadata:", paper_metadata)

    s_time = time.time()
    stage2_chunks = await grouped_tasks(question_groups)
    # for chunk in stage2_chunks:
    #     print(chunk)
    e_time = time.time()
    print(f"Stage 2 total parallel processing time: {e_time - s_time:.2f}s")

    return {
        "paper_metadata": paper_metadata,
        "chunks": stage2_chunks
    }


def pre_process(docs):
    pages = []
    full_text_parts = []

    for doc in docs:
        page_number = doc.metadata.get("page", None)
        page_number = 0 if page_number is None else page_number
        page_number +=1
        pages.append({
            "metadata": doc.metadata,
            "page_content": doc.page_content
        })

        full_text_parts.append(
            f"--- PAGE {page_number if page_number is not None else 'Unknown'} ---\n"
            f"{doc.page_content}"
        )

    full_text = "\n\n".join(full_text_parts)
    return full_text 


async def process_single_group(chunk, index):
    parent_no = str(chunk.get("question_number", index))
    content = chunk.get("content", "")

    print(f"Starting parallel processing for parent question Q{parent_no}...")

    expected_parts = list(dict.fromkeys(
        [match.lower() for match in re.findall(r"(?:^|\s|\b|\()([a-z])\)\s+", content, re.IGNORECASE)]
    ))

    prompt = stage2_prompt(chunk)
    res = await doc_chunker_ollama_local.ainvoke(prompt)

    parsed = parse_stage2_json(res.content)

    actual_parts = []
    for question in parsed:
        question_no = str(question.get("question_number", ""))
        match = re.search(r"\(([a-z])\)", question_no, re.I)
        if match:
            actual_parts.append(match.group(1).lower())

    # Only check expected parts if genuine sub-question labels (starting with 'a') exist
    if "a" in expected_parts:
        missing_parts = [
            part for part in expected_parts
            if part not in actual_parts
        ]
        if missing_parts:
            print(f"⚠️ Warning for Q{parent_no}: Expected parts {expected_parts}, but received {actual_parts}. Proceeding with extracted questions.")

    # Auto-disambiguate duplicate question numbers to prevent DB and validation errors
    seen_counts = {}
    for question in parsed:
        q_no = str(question.get("question_number", "")).strip()
        if not q_no:
            q_no = str(parent_no)
        
        if q_no in seen_counts:
            seen_counts[q_no] += 1
            question["question_number"] = f"{q_no}_{seen_counts[q_no]}"
        else:
            seen_counts[q_no] = 0
            question["question_number"] = q_no

    print(f"✅ Extracted {len(parsed)} sub-questions for Q{parent_no}")
    return parsed


async def grouped_tasks(chunks):
    tasks = [process_single_group(chunk, i) for i, chunk in enumerate(chunks, start=1)]
    results = await asyncio.gather(*tasks)

    all_stage2_chunks = []
    for parsed in results:
        all_stage2_chunks.extend(parsed)

    # print(f"\nTotal Stage 2 records: {len(all_stage2_chunks)}")
    return all_stage2_chunks


def parse_json_safely(res_content):
    # 1. Extract text from the LLM response
    if isinstance(res_content, list):
        parts = []

        for part in res_content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)

        text = "".join(parts)

    else:
        text = str(res_content)

    text = text.strip()

    if not text:
        raise ValueError("LLM response is empty.")

    # 2. Remove Markdown code fences if present
    text = re.sub(
        r"^\s*```(?:json)?\s*|\s*```\s*$",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    # 3. Try parsing the complete response first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4. If extra text exists, find a valid JSON object or array
    decoder = json.JSONDecoder()

    for match in re.finditer(r"[\[{]", text):
        start = match.start()

        try:
            parsed, _ = decoder.raw_decode(text[start:])
            return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError(
        "No valid JSON object found in response.\n"
        f"Response preview: {text[:500]}"
    )





def parse_stage2_json(res_content):
    # Convert the LLM response into text
    if isinstance(res_content, list):
        text = "".join(
            part.get("text", "")
            for part in res_content
            if isinstance(part, dict) and "text" in part
        )
    else:
        text = str(res_content)

    text = text.strip()

    # Remove Markdown code fences
    text = re.sub(
        r"^\s*```(?:json)?\s*|\s*```\s*$",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    # First, try parsing the complete response
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end < start:
            # Fallback check for array
            start_arr = text.find("[")
            end_arr = text.rfind("]")
            if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
                try:
                    parsed = json.loads(text[start_arr:end_arr + 1])
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "Stage 2 returned malformed JSON.\n"
                        f"Response preview: {text[:500]}"
                    ) from exc
            else:
                raise ValueError(
                    "Stage 2 must return a JSON object with a 'questions' key.\n"
                    f"Response preview: {text[:500]}"
                )
        else:
            json_text = text[start:end + 1]
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Stage 2 returned malformed JSON.\n"
                    f"Response preview: {text[:500]}"
                ) from exc

    if isinstance(parsed, dict) and "questions" in parsed:
        questions = parsed["questions"]
    elif isinstance(parsed, list):
        questions = parsed
    else:
        raise ValueError(
            "Expected Stage 2 response to contain a 'questions' list, "
            f"but received {type(parsed).__name__}."
        )

    if not isinstance(questions, list):
        raise ValueError(
            "The 'questions' field in Stage 2 response must be a JSON array."
        )

    if not all(isinstance(item, dict) for item in questions):
        raise ValueError(
            "Every item in Stage 2 'questions' array must be a JSON object."
        )

    return questions
