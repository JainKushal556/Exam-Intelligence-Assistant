from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI , HTTPException , status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File
from pathlib import Path
from backend.utilities import format_size
from datetime import datetime
import shutil
import os
import time
import json

from Query_Pipeline.llm import llm_answer, llm_answer_stream




app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
@app.head("/")
def root():
    return {"status": "ok", "message": "Exam RAG API Live"}

# @app.get("/files")
# def read_files():
#     # 1. First, check persistent PostgreSQL database
#     db_records = get_uploaded_documents()
#     if db_records:
#         files_list = []
#         for row in db_records:
#             filename, filesize_bytes, uploaded_at = row
#             created_time = uploaded_at.strftime("%d %b %Y, %I:%M %p") if uploaded_at else "Recently"
#             files_list.append({
#                 "name": filename,
#                 "size": format_size(filesize_bytes),
#                 "raw_size_bytes": filesize_bytes,
#                 "added_date": created_time
#             })
#         return files_list

#     # 2. Fallback to scanning local folder if database has no records yet
#     folder = Path("backend/uploaded_files")
#     if not folder.exists():
#         return []
#     files_list = []
    
#     for f in folder.iterdir():
#         if f.is_file() and f.name != ".gitkeep":
#             file_stat = f.stat()
#             created_time = datetime.fromtimestamp(file_stat.st_ctime).strftime("%d %b %Y, %I:%M %p")
            
#             files_list.append({
#                 "name": f.name,
#                 "size": format_size(file_stat.st_size),
#                 "raw_size_bytes": file_stat.st_size,
#                 "added_date": created_time
#             })
            
#     return files_list

# @app.post("/uploadfile")
# async def upload_file(file: UploadFile = File(...)):
#     start_time = time.time()
#     if file is None or not file.filename:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="No file uploaded! Please select a file."
#         )
    
#     directory_path = Path("backend/uploaded_files")
#     directory_path.mkdir(exist_ok=True)

#     final_path = os.path.join(directory_path,file.filename)
#     with open(final_path,"wb") as destination:
#         shutil.copyfileobj(file.file,destination)
        
#     if filetotext(final_path):
#         await chunker()
#         # Record file metadata in PostgreSQL database for permanent persistence across cloud reboots
#         file_size = os.path.getsize(final_path)
#         record_uploaded_document(file.filename, file_size)
#     else:
#         end_time = time.time()
#         elapsed_time = end_time - start_time
#         return {
#             "status": "UnSuccessful",
#             "filename": file.filename,
#             "filetype":file.content_type,
#             "file_path":final_path,
#             "time_taken": elapsed_time,
#         }
#     end_time = time.time()
#     elapsed_time = end_time - start_time
#     return {
#         "status": "Success",
#         "filename": file.filename,
#         "filetype":file.content_type,
#         "file_path":final_path,
#         "time_taken": elapsed_time
#     }


# from Query_Pipeline.call_logger import log_call

@app.post("/query")
async def user_query(query : str):
    if not query or not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty! Please provide a valid question."
        )
    start_time = time.time()

    # t_embed_start = time.time()
    # embeddings = await generate_query_embeddings(query)
    # embed_time_ms = round((time.time() - t_embed_start) * 1000, 2)

    # t_retrieval_start = time.time()
    # retrived_chunks = chunk_retriver(embeddings)
    # retrieval_time_ms = round((time.time() - t_retrieval_start) * 1000, 2)

    # generated_answer = await generate_answer(query, retrived_chunks)

    llm_result = await llm_answer(query)
    if isinstance(llm_result, dict):
        generated_answer = llm_result.get("answer", "")
        sources = llm_result.get("sources", [])
    else:
        generated_answer = llm_result
        sources = []

    end_time = time.time()
    elapsed_time = round(end_time - start_time, 2)

    return {
        "query": query, 
        "answer": generated_answer,
        "sources": sources,
        "time_taken": elapsed_time,
    }

@app.post("/query-stream")
@app.get("/query-stream")
async def user_query_stream(query: str):
    if not query or not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty! Please provide a valid question."
        )
    start_time = time.time()
    
    result = await llm_answer_stream(query)
    stream_gen = result["stream"]
    sources = result.get("sources", [])

    async def event_generator():
        # 1. First event: send sources metadata
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        
        # 2. Token-by-token text streaming
        async for token in stream_gen:
            if token:
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

        # 3. Final event: done marker with execution time
        elapsed_time = round(time.time() - start_time, 2)
        yield f"data: {json.dumps({'type': 'done', 'time_taken': elapsed_time})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}


# uvicorn backend.main:app --reload