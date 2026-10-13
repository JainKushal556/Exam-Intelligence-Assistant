from langchain_google_genai import GoogleGenerativeAIEmbeddings , ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
import os
EMBED_MODEL_NAME = "gemini-embedding-001"

doc_embedding = GoogleGenerativeAIEmbeddings(
    model=EMBED_MODEL_NAME,
    output_dimensionality=1536,
    task_type="retrieval_document"
)

query_embedding = GoogleGenerativeAIEmbeddings(
    model=EMBED_MODEL_NAME,
    output_dimensionality=1536,
    task_type="retrieval_query"
)

doc_chunker = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    max_retries=2,
    timeout=120
)

doc_chunker_ollama_local = ChatOllama(
    model="qwen2.5:7b",
    format="json",
    temperature=0
)

query_model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    max_retries=2,
    timeout=120
)



doc_chunker_ollama_cloud = ChatOllama(
    base_url="https://jainkushal556--ollama-qwen-service-serve.modal.run",
    model="qwen2.5:7b",
    format="json"
)

doc_chunker_groq = ChatGroq(
    model="qwen/qwen3.8-27b"
)

