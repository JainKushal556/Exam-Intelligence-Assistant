# 🎓 Exam Intelligence Assistant

An intelligent **Retrieval-Augmented Generation (RAG)** system designed to ingest, parse, vector-index, and semantically retrieve college/university examination question papers and answers.

---

## 🚀 Key Features

- **Document Processing**: Automated PDF extraction and structured parsing.
- **LLM-Powered Semantic Chunking**: Intelligent question boundary identification using modern LLMs (Gemini / Groq / Ollama).
- **Vector Database**: High-performance semantic similarity search with PostgreSQL and `pgvector`.
- **Query & Retrieval Pipeline**: Accurate academic answering backed by course codes, subjects, semesters, and question contexts.
- **FastAPI Backend**: Fast, asynchronous REST API with CORS support.
- **Modern Web Interface**: Responsive and clean frontend dashboard for query testing and document inspection.

---

## 📁 Project Structure

```plaintext
├── backend/                  # FastAPI Application & APIs
│   ├── main.py               # API endpoints
│   ├── utilities.py          # Helper functions
│   └── uploaded_files/       # Staging directory for uploads
├── frontend/                 # Web Interface
│   ├── index.html            # Main dashboard UI
│   ├── style.css             # Styling & modern design
│   └── app.js                # Frontend client logic
├── Ingestion_Pipeline/       # Document ingestion & indexing
│   ├── loader.py             # PDF Loader
│   ├── chunker.py            # LLM chunking logic
│   ├── embedding.py          # Vector embedding generation
│   ├── models.py             # Pydantic schemas
│   ├── prompt.py             # Chunker prompt engineering
│   └── vectorestore.py       # PostgreSQL/pgvector database handler
├── Query_Pipeline/           # RAG retrieval & answer generation
│   ├── llm.py                # LLM answer synthesis
│   ├── prompt.py             # Query prompts
│   └── utility.py            # Retrieval utilities
├── Batch_Pipeline/           # Bulk dataset ingestion
│   └── batch_ingest.py       # Batch indexing script
├── requirements.txt          # Python dependencies
└── .env.example              # Environment variables template
```

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/JainKushal556/Exam-Intelligence-Assistant.git
cd Exam-Intelligence-Assistant
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```
Update your `.env` with:
- `GOOGLE_API_KEY`
- `GROQ_API_KEY`
- PostgreSQL database credentials (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_DATABASE`)

---

## 🏃 Running the Application

### Start the FastAPI Server:
```bash
uvicorn backend.main:app --reload --port 8000
```

### Open the Frontend:
Simply open `frontend/index.html` in your browser or serve it using any static server:
```bash
# Example with python http.server:
python -m http.server 3000 --directory frontend
```

---

## 📄 License
MIT License
