from Ingestion_Pipeline.models import doc_embedding

async def generate_embeddings(dict: dict):
    # print("Embeddings Stage: \n", dict)
    embedding_texts = [
    f"Topic: {q['topic']}\n"
    f"Subtopic: {q['subtopic']}\n"
    f"Question: {q['question_text']}"
    for q in dict['chunks']
    ]

    embeddings = doc_embedding.embed_documents(embedding_texts)

    for question, embedding in zip(dict['chunks'], embeddings):
        question["embedding"] = embedding

    return dict




