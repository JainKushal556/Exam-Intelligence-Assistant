import psycopg2
import os
from psycopg2.extras import Json
from dotenv import load_dotenv
load_dotenv()
import hashlib
from Ingestion_Pipeline.prompt import similarity_search_query

def get_file_hash(pdf_path):
    sha256 = hashlib.sha256()

    with open(pdf_path, "rb") as file:
        for block in iter(lambda: file.read(8192), b""):
            sha256.update(block)

    return sha256.hexdigest()
def create_exam_papers_table():
    con = None
    cur = None
    try:
        con = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            dbname=os.getenv("DB_DATABASE"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cur = con.cursor()
        cur.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;
            CREATE TABLE IF NOT EXISTS exam_papers (
    paper_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    subject VARCHAR(150) NOT NULL,
    course_code VARCHAR(50),
    year INTEGER,
    semester VARCHAR(30),
    exam_type VARCHAR(100),

    source_filename TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE,
    total_pages INTEGER,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_exam_year
        CHECK (year IS NULL OR year BETWEEN 1900 AND 2200),

    CONSTRAINT chk_total_pages
        CHECK (total_pages IS NULL OR total_pages > 0)
    );
        """)
        con.commit()
        print("Table exam_papers created successfully.")
    except Exception as e:
        print(f"Error in createdb: {e}")
        if con:
            con.rollback()
    finally:
        if cur:
            cur.close()
        if con:
            con.close()

def create_exam_questions_table():
    con = None
    cur = None
    try:
        con = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            dbname=os.getenv("DB_DATABASE"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exam_questions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    paper_id BIGINT NOT NULL
        REFERENCES exam_papers(paper_id)
        ON DELETE CASCADE,

    parent_question_no VARCHAR(30),
    question_no VARCHAR(50) NOT NULL,
    question_text TEXT NOT NULL,

    topic VARCHAR(200),
    subtopic VARCHAR(200),
    topic_keywords TEXT[] NOT NULL DEFAULT '{}',
    unit_name VARCHAR(100),

    marks NUMERIC(6, 2),
    marks_scheme TEXT,

    page_start INTEGER,
    page_end INTEGER,

    question_type VARCHAR(50),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Example dimension only; match this to your embedding model.
    embedding VECTOR(1536),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_paper_question
        UNIQUE (paper_id, question_no),

    CONSTRAINT chk_question_marks
        CHECK (marks IS NULL OR marks >= 0),

    CONSTRAINT chk_question_pages
        CHECK (
            (page_start IS NULL OR page_start > 0)
            AND
            (page_end IS NULL OR page_end >= COALESCE(page_start, 1))
        )
    );
        """)
        con.commit()
        print("Table exam_questions created successfully.")
    except Exception as e:
        print(f"Error in createdb: {e}")
        if con:
            con.rollback()
    finally:
        if cur:
            cur.close()
        if con:
            con.close()

def createdb():
    create_exam_papers_table()
    create_exam_questions_table()
    


def insert_exam_paper(
    conn,
    subject,
    source_filename,
    course_code=None,
    year=None,
    semester=None,
    exam_type=None,
    file_hash=None,
    total_pages=None
):
    query = """
        INSERT INTO exam_papers (
            subject,
            course_code,
            year,
            semester,
            exam_type,
            source_filename,
            file_hash,
            total_pages
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING paper_id;
    """

    try:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    subject,
                    course_code,
                    year,
                    semester,
                    exam_type,
                    source_filename,
                    file_hash,
                    total_pages
                )
            )

            paper_id = cur.fetchone()[0]

        conn.commit()

        print(f"Exam paper inserted successfully. ID: {paper_id}")
        return paper_id

    except Exception:
        conn.rollback()
        raise


def insert_exam_questions(conn, paper_id, chunks):
    query = """
        INSERT INTO exam_questions (
            paper_id,
            parent_question_no,
            question_no,
            question_text,
            topic,
            subtopic,
            topic_keywords,
            unit_name,
            marks,
            marks_scheme,
            page_start,
            page_end,
            metadata,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
        ON CONFLICT (paper_id, question_no) DO UPDATE SET
            question_text = EXCLUDED.question_text,
            topic = EXCLUDED.topic,
            subtopic = EXCLUDED.subtopic,
            embedding = EXCLUDED.embedding;
    """
    try:
        with conn.cursor() as cur:
            for q in chunks:
                cur.execute(
                    query,
                    (
                        paper_id,
                        q.get("parent_question_no"),
                        q.get("question_number"),
                        q.get("question_text"),
                        q.get("topic"),
                        q.get("subtopic"),
                        q.get("topic_keywords", []),
                        q.get("unit_name"),
                        q.get("marks"),
                        q.get("marks_scheme"),
                        q.get("page_start"),
                        q.get("page_end"),
                        Json({}),
                        str(q.get("embedding"))
                    )
                )
        conn.commit()
        print(f"✅ Successfully inserted {len(chunks)} questions into exam_questions table!")
    except Exception as e:
        conn.rollback()
        print(f"Error inserting questions: {e}")
        raise


def insert_embedding_indb(chunk, embedding, metadata):

    createdb()
    try:
        con = psycopg2.connect(host=os.getenv("DB_HOST"),dbname=os.getenv("DB_DATABASE"),user=os.getenv("DB_USER"),password=os.getenv("DB_PASSWORD"),port = os.getenv("DB_PORT"))
        cur = con.cursor()
    except Exception as e:
        print(e)
        return
    else:
        try:
            for i in range(len(chunk)):
                cur.execute("INSERT INTO document_embeddings (chunk, embedding, metadata) VALUES (%s, %s::vector, %s)", (chunk[i], str(embedding[i]), Json(metadata[i])))
            con.commit()
            print("Embeddings inserted successfully")
        except Exception as e:
            print(e)
            con.rollback()
        finally:
            if con:
                con.close()
            if cur:
                cur.close()

def retrive_chunks(query_embedding, top_k):
    try:
        con = psycopg2.connect(host=os.getenv("DB_HOST"),dbname=os.getenv("DB_DATABASE"),user=os.getenv("DB_USER"),password=os.getenv("DB_PASSWORD"),port = os.getenv("DB_PORT"),sslmode="require")
        cur = con.cursor()
    except Exception as e:
        print(f"❌ [retrive_chunks] DB connection failed: {e}")
        return []
    else:

        try:
            cur.execute(
            similarity_search_query(), 
                (str(query_embedding), str(query_embedding), top_k)
            )
            results = cur.fetchall()
            return results
        except Exception as e:
            print(f"❌ [retrive_chunks] Query execution failed: {e}")
            return []
        finally:
            if con:
                con.close()
            if cur:
                cur.close()