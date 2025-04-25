import google.generativeai as genai
from typing import List, Dict, Any, Optional
import json
import asyncio
import os
import traceback
from collections import defaultdict

from app.core.config import settings
from app.models.data_models import DocumentChunk

# --- Globals & Configuration ---
gemini_model = None
gemini_client_configured = False

def configure_gemini_client():
    global gemini_model, gemini_client_configured
    if gemini_client_configured: return
    print("[LLM Service] Attempting to configure Gemini client...")
    if not settings.GEMINI_API_KEY: print("WARN: Gemini API Key missing."); gemini_model = None; gemini_client_configured = True; return
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
        print(f"[LLM Service] Gemini client OK for model: {settings.GEMINI_MODEL_NAME}")
        gemini_client_configured = True
    except Exception as e: print(f"ERROR: Failed to configure Gemini: {e}"); gemini_model = None; gemini_client_configured = True

configure_gemini_client()

def format_context(context_chunks: List[DocumentChunk]) -> str:
    if not context_chunks: return "No relevant context was found in the uploaded documents."
    grouped_by_source = defaultdict(list)
    for chunk in context_chunks:
        source_key = f"{chunk.source}" + (f" (Page approx. {chunk.page})" if chunk.page else "")
        grouped_by_source[source_key].append(chunk.text)
    formatted_context = ""
    for source, texts in grouped_by_source.items():
        formatted_context += f"--- From Source: {source} ---\n"
        formatted_context += "\n\n".join(texts)
        formatted_context += "\n--- End of Source ---\n\n"
    return formatted_context.strip()

def format_web_results(web_results: Optional[List[Dict[str, str]]]) -> str:
     if not web_results: return "No relevant information found from web search."
     formatted = ""; i = 0
     for result in web_results: i+=1; formatted += f"--- Web Result {i} ---\nTitle: {result.get('title', 'N/A')}\nURL: {result.get('url', 'N/A')}\nSnippet: {result.get('content', 'N/A')}\n\n"
     return formatted.strip()

async def generate_answer(question: str, context_chunks: List[DocumentChunk], web_search_results: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    if not gemini_client_configured: configure_gemini_client()
    if not gemini_model: return {"answer": "LLM unavailable.", "type": "error"}

    document_context = format_context(context_chunks)
    web_context = format_web_results(web_search_results)

    # --- **FINAL REFINED PROMPT** ---
    prompt = f"""**Instructions:**
- You are an AI assistant answering questions based *exclusively* on the information provided in the 'Document Context' and 'Web Search Results' sections below.
- **Thoroughly analyze ALL provided context snippets from all sources.** Synthesize information across different parts to create a comprehensive answer.
- If the question asks for a general explanation or summary (e.g., "explain...", "what is this about?", "summarize..."), provide a **detailed and well-structured** explanation covering the key aspects mentioned in the context. Use multiple paragraphs if necessary and draw connections between different pieces of information found in the context.
- If the question is specific, provide a precise answer using only facts stated in the context.
- If the context contains summaries of structured data (like tables), refer to that summary to answer related questions about counts, totals, etc., performing simple calculations if possible from the summary.
- **Crucially: If the information needed to answer the question accurately and comprehensively is not present in *either* the Document Context or the Web Search Results, state clearly: "Based on the provided documents and web search, I cannot provide a complete answer to this question."** Do not guess or use external knowledge.
- Do NOT include meta-references like "(Context Chunk X)".

**Document Context:**
{document_context}
--- End of Document Context ---

**Web Search Results:**
{web_context}
--- End of Web Search Results ---

**Question:** {question}

**Answer:**
"""

    print(f"[LLM Service] Calling Gemini API (Model: {settings.GEMINI_MODEL_NAME})...")
    print(f"[LLM Service] Approx. total prompt length: {len(prompt)} chars") # Log prompt length
    print(f"[LLM Service] Doc Context (Start): {document_context[:200]}...") # Shorter snippet ok
    print(f"[LLM Service] Web Context (Start): {web_context[:200]}...")

    generation_config = genai.types.GenerationConfig(
      temperature=0.7, # Keep slightly higher temp
    )
    safety_settings = [ {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: gemini_model.generate_content(prompt, generation_config=generation_config, safety_settings=safety_settings))

        raw_response_text = "[No response text]"; answer = ""; answer_type = "error"
        try:
            raw_response_text = response.text
            print(f"[LLM Service] Raw response: {raw_response_text!r}")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason: raise ValueError(f"Blocked: {response.prompt_feedback.block_reason}")
            if response.candidates and response.candidates[0].content.parts:
                 answer = response.text.strip()
                 if not answer: answer_type = "not_found"; answer = "LLM returned empty answer."
                 elif "cannot provide a complete answer" in answer.lower() or \
                      "provided documents and web search do not contain" in answer.lower() or \
                      "information wasn't found" in answer.lower(): answer_type = "not_found"
                 else: answer_type = "text"
            else: raise ValueError(f"No valid candidate. Reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
        except (ValueError, AttributeError, Exception) as e: print(f"[LLM Service] WARN processing response: {e}"); answer = f"Error processing LLM response: {e}"; answer_type="error"

        return {"answer": answer, "type": answer_type, "data": None, "chart_data": None}

    except Exception as e: print(f"[LLM Service] ERROR Gemini call failed: {e}"); traceback.print_exc(); return {"answer": "Error communicating with LLM.", "type": "error"}

