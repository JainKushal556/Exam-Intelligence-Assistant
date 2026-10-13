from dotenv import load_dotenv
load_dotenv()

from Ingestion_Pipeline.models import query_embedding  
from Ingestion_Pipeline.vectorestore import retrive_chunks
from Query_Pipeline.utility import structure_retrieved_chunks
from Query_Pipeline.prompt import SYSTEM_PROMPT_2_0
from google import genai
import os
import asyncio
import time
api_key = os.getenv("GEMINIAPI_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)
model_name = "gemini-3.5-flash-lite"
previous_id = None

# It Keeps Track Of Previous Chats 
async def generate_answer(query, relevant_chunks):
    global previous_id
    global model_name
    systemInstruction = SYSTEM_PROMPT_2_0
    prompt = prompt_template(query, relevant_chunks)
    print(f"Prompt:\n {prompt}")
    if previous_id is None:
        try:
            response1 =await client.aio.interactions.create(
                model=model_name,
                input=prompt,
                generation_config={
                    "temperature" : 0.6
                },
                system_instruction = systemInstruction
            )
        except Exception as e:
            return {"Error": str(e)}
        else:
            previous_id = response1.id
            print("response1 : \n", response1.output_text)
            return response1.output_text
    else:
        try:
            response2 = await client.aio.interactions.create(
                model=model_name,
                input=prompt,
                generation_config={
                    "temperature" : 0.6
                },
                system_instruction=systemInstruction,          
                previous_interaction_id= previous_id
            )
        except Exception as e:
            return {"Error": str(e)}
        else:
            previous_id = response2.id
            print("response2 : \n", response2.output_text)
            return response2.output_text

# Streaming generator for token-by-token streaming
async def generate_answer_stream(query, relevant_chunks):
    global previous_id
    global model_name
    systemInstruction = SYSTEM_PROMPT_2_0
    prompt = prompt_template(query, relevant_chunks)
    print(f"Prompt (Stream):\n {prompt}")

    call_kwargs = {
        "model": model_name,
        "input": prompt,
        "generation_config": {"temperature": 0.6},
        "system_instruction": systemInstruction,
        "stream": True,
    }
    if previous_id is not None:
        call_kwargs["previous_interaction_id"] = previous_id

    try:
        stream = await client.aio.interactions.create(**call_kwargs)
        async for event in stream:
            event_type = getattr(event, "event_type", None)
            if event_type == "step.delta":
                delta = getattr(event, "delta", None)
                text = getattr(delta, "text", None)
                if text:
                    yield text
            elif event_type in ("interaction.created", "interaction.completed"):
                interaction = getattr(event, "interaction", None)
                if interaction and hasattr(interaction, "id") and interaction.id:
                    previous_id = interaction.id
    except Exception as stream_err:
        print(f"Streaming exception: {stream_err}. Falling back to standard generation...")
        try:
            call_kwargs.pop("stream", None)
            resp = await client.aio.interactions.create(**call_kwargs)
            if hasattr(resp, "id") and resp.id:
                previous_id = resp.id
            yield getattr(resp, "output_text", str(resp))
        except Exception as fallback_err:
            yield f"Error: {fallback_err}"



def prompt_template(question: str, relevant_context: str) -> str:
    return f"""
USER QUESTION:
{question}

RETRIEVED QUESTION-PAPER CONTEXT:
{relevant_context}

Answer the user's question according to the system instructions.
First answer the question itself. Include only genuinely related
previous-year questions. If none are relevant, do not list
unrelated questions or give unsupported study suggestions.
""".strip()

def answer_query(question: str):
    
    try:
        st_time = time.time()
        q_emb = query_embedding.embed_query(question)
        end_time = time.time()
        print("Query Embedding Time: ", end_time - st_time)

    except Exception as err:
        return []

    try:
        retrieved = retrive_chunks(q_emb, 10)
        # chunk_count = len(retrieved) if retrieved else 0
        return retrieved if retrieved else []
    except Exception as err:
        return []


async def llm_answer(question):
    
    retrieved = answer_query(question)

    if not retrieved:
        context = "No specific previous year questions found in database."
        sources = []
    else:
        structured_chunks = structure_retrieved_chunks(retrieved)
        context = structured_chunks["context"]
        sources = structured_chunks.get("sources", [])
    st_time = time.time()
    answer = await generate_answer(question, context)
    end_time = time.time()
    print("LLM Answer Time: ", end_time - st_time)
    # Extract unique clean filenames for frontend source attribution
    source_files = []
    seen = set()
    for s in sources:
        raw_name = s.get("source_filename")
        if raw_name:
            clean_name = os.path.basename(str(raw_name).replace("\\", "/"))
            if clean_name and clean_name not in seen:
                seen.add(clean_name)
                source_files.append(clean_name)

    return {
        "answer": answer,
        "sources": source_files
    }

async def llm_answer_stream(question):
    retrieved = answer_query(question)

    if not retrieved:
        context = "No specific previous year questions found in database."
        sources = []
    else:
        structured_chunks = structure_retrieved_chunks(retrieved)
        context = structured_chunks["context"]
        sources = structured_chunks.get("sources", [])

    source_files = []
    seen = set()
    for s in sources:
        raw_name = s.get("source_filename")
        if raw_name:
            clean_name = os.path.basename(str(raw_name).replace("\\", "/"))
            if clean_name and clean_name not in seen:
                seen.add(clean_name)
                source_files.append(clean_name)

    return {
        "stream": generate_answer_stream(question, context),
        "sources": source_files
    }

if __name__ == "__main__":
    question = input("User: ")
    asyncio.run(llm_answer(question))


