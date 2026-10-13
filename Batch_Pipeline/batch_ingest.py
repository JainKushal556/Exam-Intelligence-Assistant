import os
import sys
import time
import asyncio
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

from Ingestion_Pipeline.loader import pdf_loader
from Ingestion_Pipeline.chunker import llm_chunker
from Ingestion_Pipeline.embedding import generate_embeddings
from Ingestion_Pipeline.vectorestore import (
    createdb,
    insert_exam_paper,
    insert_exam_questions,
    get_file_hash
)


def get_db_connection():
    """Connect to PostgreSQL / Supabase Database."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_DATABASE"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )


def ensure_db_connection(con):
    """Check if connection is alive; reconnect if closed or dropped due to idle timeout."""
    if con is None or getattr(con, "closed", True):
        return get_db_connection()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT 1;")
        return con
    except Exception:
        try:
            con.close()
        except Exception:
            pass
        return get_db_connection()


def is_already_ingested(con, file_hash: str) -> bool:
    """Check if this PDF has already been ingested using its file hash."""
    try:
        with con.cursor() as cur:
            cur.execute("SELECT paper_id FROM exam_papers WHERE file_hash = %s LIMIT 1;", (file_hash,))
            result = cur.fetchone()
            return result is not None
    except Exception as e:
        try:
            con.rollback()
        except Exception:
            pass
        return False


async def ingest_single_pdf(con, pdf_path: Path) -> dict:
    """Run full ingestion pipeline for one PDF file."""
    start_time = time.time()
    file_hash = get_file_hash(pdf_path)

    # 1. Check if already ingested in DB
    if is_already_ingested(con, file_hash):
        return {
            "status": "SKIPPED",
            "message": "Already present in database.",
            "duration": round(time.time() - start_time, 2)
        }

    # 2. Load PDF
    docs = pdf_loader(pdf_path)
    if not docs:
        raise ValueError("No text or pages could be loaded from PDF.")

    # 3. LLM Chunker (Stage 1 & Stage 2)
    chunk_res = await llm_chunker(docs)

    # 4. Generate Vector Embeddings
    final_res = await generate_embeddings(chunk_res)

    # 5. Insert Paper Metadata into exam_papers table
    con = ensure_db_connection(con)
    paper_metadata = final_res.get("paper_metadata", {})
    subject_val = paper_metadata.get("subject") or pdf_path.stem or "Unknown Subject"
    source_val = paper_metadata.get("source") or pdf_path.name

    paper_id = insert_exam_paper(
        con,
        subject=subject_val,
        source_filename=source_val,
        course_code=paper_metadata.get("course_code"),
        year=paper_metadata.get("year"),
        semester=paper_metadata.get("semester"),
        exam_type=paper_metadata.get("exam_type"),
        file_hash=file_hash,
        total_pages=paper_metadata.get("total_pages", len(docs))
    )

    # 6. Insert All Extracted Questions & Embeddings into exam_questions table
    insert_exam_questions(
        con,
        paper_id=paper_id,
        chunks=final_res.get("chunks", [])
    )

    elapsed = round(time.time() - start_time, 2)
    return {
        "status": "SUCCESS",
        "paper_id": paper_id,
        "questions_count": len(final_res.get("chunks", [])),
        "duration": elapsed
    }


async def batch_ingest(folder_path: str):
    """Batch process all PDF files in the specified folder."""
    folder = Path(folder_path)

    if not folder.exists() or not folder.is_dir():
        print(f"❌ Error: Folder '{folder_path}' does not exist or is not a directory.")
        return

    # Find all PDF files (including subdirectories)
    pdf_files = sorted(list(folder.rglob("*.pdf")))

    if not pdf_files:
        print(f"⚠️ No PDF files found in '{folder_path}'.")
        return

    print("=" * 65)
    print(f"📂 BATCH INGESTION STARTED")
    print(f"📁 Target Folder : {folder.resolve()}")
    print(f"📄 Total PDFs    : {len(pdf_files)}")
    print("=" * 65)

    # Ensure tables exist
    try:
        createdb()
    except Exception as e:
        print(f"Note on table init: {e}")

    con = None
    try:
        con = get_db_connection()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return

    stats = {
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "total_questions": 0,
        "errors": []
    }

    batch_start = time.time()

    for idx, pdf_path in enumerate(pdf_files, start=1):
        print(f"\n[{idx}/{len(pdf_files)}] 📄 Processing: {pdf_path.name}")
        print(f"    Path: {pdf_path}")

        try:
            con = ensure_db_connection(con)
            result = await ingest_single_pdf(con, pdf_path)

            if result["status"] == "SUCCESS":
                stats["success"] += 1
                stats["total_questions"] += result["questions_count"]
                print(f"    ✅ Ingested successfully in {result['duration']}s | Paper ID: {result['paper_id']} | Questions: {result['questions_count']}")

            elif result["status"] == "SKIPPED":
                stats["skipped"] += 1
                print(f"    ⏭️  Skipped (Already in DB) in {result['duration']}s")

        except Exception as err:
            stats["failed"] += 1
            stats["errors"].append({"file": pdf_path.name, "error": str(err)})
            print(f"    ❌ Failed: {err}")
            # Rollback connection so subsequent transactions can continue
            if con:
                try:
                    con.rollback()
                except Exception:
                    pass

    total_batch_time = round(time.time() - batch_start, 2)

    # Close DB connection
    if con:
        con.close()

    # Final Summary Report
    print("\n" + "=" * 65)
    print("📊 BATCH INGESTION SUMMARY REPORT")
    print("=" * 65)
    print(f"Total PDFs Scanned      : {len(pdf_files)}")
    print(f"✅ Successfully Ingested: {stats['success']}")
    print(f"⏭️  Skipped (Duplicate)  : {stats['skipped']}")
    print(f"❌ Failed               : {stats['failed']}")
    print(f"📝 Total Questions Saved: {stats['total_questions']}")
    print(f"⏱️  Total Time Taken     : {total_batch_time}s ({round(total_batch_time/60, 2)} mins)")

    if stats["errors"]:
        print("\n⚠️ Failed Files Details:")
        for fail in stats["errors"]:
            print(f"  - {fail['file']}: {fail['error']}")

    print("=" * 65)
    print("🎉 All operations completed!\n")


if __name__ == "__main__":
    import sys

    # Get folder path from command line or ask user
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = input("\n📂 Enter the folder path containing PDFs (or press Enter for 'PDFs'): ").strip()
        if not target_dir:
            target_dir = "PDFs"

    asyncio.run(batch_ingest(target_dir))
