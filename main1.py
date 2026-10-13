import time
from dotenv import load_dotenv
load_dotenv()
from Query_Pipeline.llm import prompt_template
from Ingestion_Pipeline.models import query_embedding
from Ingestion_Pipeline.vectorestore import query_embedding_from_db
from Query_Pipeline.llm import model

while True:
    print("User: ", end="")
    user_input = input()
    if user_input.lower() == "exit":
        break

    # 1. Measure embedding generation time
    t_start_emb = time.perf_counter()
    qry_emb = query_embedding.embed_query(user_input)
    emb_time = time.perf_counter() - t_start_emb

    # 2. Measure vector DB retrieval time
    t_start_retrieval = time.perf_counter()
    chunks = query_embedding_from_db(qry_emb)
    retrieval_time = time.perf_counter() - t_start_retrieval

    prompt = prompt_template(user_input, chunks)

    # 3. Measure LLM query answer time with streaming
    t_start_llm = time.perf_counter()
    print("AI: ", end="", flush=True)
    for chunk in model.stream(prompt):
        content = chunk.content
        if isinstance(content, list):
            for part in content:
                print(part.get("text", str(part)) if isinstance(part, dict) else str(part), end="", flush=True)
        else:
            print(content, end="", flush=True)
    print()
    answer_time = time.perf_counter() - t_start_llm

    total_time = emb_time + retrieval_time + answer_time
    print(f"\n[⏱️ Embedding: {emb_time:.2f}s | Retrieval: {retrieval_time:.2f}s | LLM Answer: {answer_time:.2f}s | Total: {total_time:.2f}s]\n")
    # for chunk in chunks:
    #     print(chunk[0]+"\n")
    #     print("metadata: ", chunk[1])