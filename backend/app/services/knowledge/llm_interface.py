from openai import OpenAI, AsyncOpenAI, APIError, RateLimitError
from typing import List, Dict, Any
import json

from app.core.config import settings
from app.models.data_models import DocumentChunk
from typing import List

# Initialize OpenAI Client
# Ensure OPENAI_API_KEY is loaded in settings via .env
if not settings.OPENAI_API_KEY:
    print("WARNING: OpenAI API Key not configured. LLM calls will fail.")
    # Optionally initialize client anyway, calls will raise error later
    # Or raise configuration error here
    async_client = None # Set to None if key is missing
else:
     async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def format_context(context_chunks: List[DocumentChunk]) -> str:
    """Formats the retrieved chunks into a single string for the LLM prompt."""
    if not context_chunks:
        return "No relevant context found."

    formatted_context = ""
    for i, chunk in enumerate(context_chunks):
        source_info = f"Source: {chunk.source}"
        if chunk.page:
            source_info += f" (Page: {chunk.page})"
        formatted_context += f"--- Context Chunk {i+1} ---\n"
        formatted_context += f"{source_info}\n"
        formatted_context += f"Content: {chunk.text}\n\n"

    return formatted_context.strip()


async def generate_answer(question: str, context_chunks: List[DocumentChunk]) -> Dict[str, Any]:
    """
    Generates an answer using an LLM based on the provided question and context.

    Args:
        question: The user's question.
        context_chunks: A list of relevant DocumentChunk objects from retrieval.

    Returns:
        A dictionary containing the answer, type, and potentially structured data.
        Example: {"answer": "...", "type": "text", "data": None, "chart_data": None}
    """
    if not async_client:
         return {
            "answer": "LLM functionality is disabled because the OpenAI API key is not configured.",
            "type": "error",
            "data": None,
            "chart_data": None
        }

    formatted_context = format_context(context_chunks)

    system_prompt = """You are an AI assistant answering questions based *only* on the provided context.
If the answer is not found in the context, state that the information is not available in the provided documents.
Do not make up information or use external knowledge.
Be concise and directly answer the question.
If the context contains structured data (like from a table or list) relevant to the question, present the answer clearly. If the question asks for a calculation (like total or average) based on data in the context, perform the calculation and state the result.
Format your final answer clearly.
"""

    user_prompt = f"""Based on the following context:

{formatted_context}

---
Answer the question: {question}"""

    print(f"[LLM Service] Calling OpenAI API (Model: {settings.OPENAI_MODEL_NAME})...")
    # print(f"[LLM Service] User Prompt Context Snippet:\n{user_prompt[:500]}...") # Debug: Log snippet

    try:
        response = await async_client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2, # Lower temperature for more factual answers
            max_tokens=500, # Adjust as needed
        )

        llm_answer = response.choices[0].message.content.strip()
        print("[LLM Service] Received response from OpenAI.")

        # Basic check if LLM couldn't find the answer
        answer_lower = llm_answer.lower()
        if "not available in the provided document" in answer_lower or \
           "not found in the context" in answer_lower or \
           "information is not available" in answer_lower:
            answer_type = "not_found"
        else:
            # [TODO: Dhaksesh/Advanced] Add logic here to detect if the answer
            # represents table data or chart data based on LLM output or context analysis.
            # For now, assume text.
            answer_type = "text"


        return {
            "answer": llm_answer,
            "type": answer_type,
            "data": None, # [TODO] Populate if type is data_table
            "chart_data": None # [TODO] Populate if type is data_chart
        }

    except RateLimitError as e:
        print(f"[LLM Service] ERROR: OpenAI Rate Limit Exceeded: {e}")
        return {"answer": "Error: The system is currently experiencing high load. Please try again later.", "type": "error"}
    except APIError as e:
        print(f"[LLM Service] ERROR: OpenAI API Error: {e}")
        return {"answer": f"Error: Could not get answer from LLM. API Error: {e.code}", "type": "error"}
    except Exception as e:
        print(f"[LLM Service] ERROR: An unexpected error occurred during LLM call: {e}")
        # import traceback
        # traceback.print_exc() # Log full traceback for debugging
        return {"answer": "Error: An unexpected error occurred while generating the answer.", "type": "error"}

