import asyncio
from dotenv import load_dotenv
load_dotenv()

from Ingestion_Pipeline.chunker import llm_chunker
from Ingestion_Pipeline.loader import pdf_loader
from pathlib import Path
import psycopg2
import os
from Ingestion_Pipeline.embedding import generate_embeddings
from Ingestion_Pipeline.vectorestore import insert_exam_paper, insert_exam_questions, get_file_hash, createdb

async def main():
    path = ""
    path = Path("PDFs/quick_chunking_test_question_paper.pdf")
    docs = pdf_loader(path)
    res = await llm_chunker(docs)
    final_res = await generate_embeddings(res)
    print("paper_metadata keys", final_res['paper_metadata'].keys())
    print("chunks keys", final_res['chunks'][0].keys())
    return
    # Initialize DB tables if not created yet
    # createdb()

    

    con = None
    try:
        con = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_DATABASE"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )
    except Exception as e:
        print(e)

    else:
        # 1. Insert Paper data into exam_papers table
        paper_id = insert_exam_paper(
            con,
            final_res['paper_metadata'].get('subject', 'Unknown Subject'),
            final_res['paper_metadata'].get('source', path.name),
            final_res['paper_metadata'].get('course_code'),
            final_res['paper_metadata'].get('year'),
            final_res['paper_metadata'].get('semester'),
            final_res['paper_metadata'].get('exam_type'),
            get_file_hash(path),
            final_res['paper_metadata'].get('total_pages', len(docs))
        )

        # 2. Insert Questions & Embeddings into exam_questions table
        insert_exam_questions(
            con, 
            paper_id, 
            final_res['chunks']
            )

        print("\n🎉 Full Ingestion Pipeline Complete!")
        print(f"Paper ID: {paper_id}")
        print(f"Total Questions Saved in DB: {len(final_res['chunks'])}")

    finally:
        if con:
            con.close()

if __name__ == "__main__":
    asyncio.run(main())

