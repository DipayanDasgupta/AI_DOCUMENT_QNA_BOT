import google.generativeai as genai; from typing import List, Dict, Any, Optional; import json; import asyncio; import os; import traceback
from app.core.config import settings; from app.models.data_models import DocumentChunk
gemini_model = None; gemini_client_configured = False
def configure_gemini_client():
    global gemini_model, gemini_client_configured;
    if gemini_client_configured: return; print("[LLM Service] Attempting to configure Gemini client...")
    if not settings.GEMINI_API_KEY: print("WARNING: Gemini API Key not configured."); gemini_model = None; gemini_client_configured = True; return
    try: genai.configure(api_key=settings.GEMINI_API_KEY); gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME); print(f"[LLM Service] Gemini client configured for model: {settings.GEMINI_MODEL_NAME}"); gemini_client_configured = True
    except Exception as e: print(f"ERROR: Failed to configure Gemini client: {e}"); gemini_model = None; gemini_client_configured = True
configure_gemini_client()
def format_context(context_chunks: List[DocumentChunk]) -> str:
    if not context_chunks: return "No relevant context was found in the uploaded documents."
    formatted = "";
    for chunk in context_chunks: source_info = f"Source: {chunk.source}" + (f" (Page: {chunk.page})" if chunk.page else ""); formatted += f"{source_info}\nContent: {chunk.text}\n\n"
    return formatted.strip()
def format_web_results(web_results: Optional[List[Dict[str, str]]]) -> str:
     if not web_results: return "No relevant information found from web search."
     formatted = ""; i = 0
     for result in web_results: i+=1; formatted += f"--- Web Result {i} ---\nTitle: {result.get('title', 'N/A')}\nURL: {result.get('url', 'N/A')}\nSnippet: {result.get('content', 'N/A')}\n\n"
     return formatted.strip()
async def generate_answer(question: str, context_chunks: List[DocumentChunk], web_search_results: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    if not gemini_client_configured: configure_gemini_client()
    if not gemini_model: print("[LLM Service] Aborting: Gemini model unavailable."); return {"answer": "LLM unavailable.", "type": "error"}
    document_context = format_context(context_chunks); web_context = format_web_results(web_search_results)
    prompt = f"""**Instructions:** ... (Keep the detailed prompt from the 'Final Overhaul' script here) ... **Context:**\n{document_context}\n--- End of Document Context ---\n\n**Web Search Results:**\n{web_context}\n--- End of Web Search Results ---\n\n**Question:** {question}\n\n**Answer:**\n"""
    print(f"[LLM Service] Calling Gemini API..."); print(f"[LLM Service] Doc Context (Start): {document_context[:300]}..."); print(f"[LLM Service] Web Context (Start): {web_context[:300]}...")
    generation_config = genai.types.GenerationConfig(temperature=0.6, max_output_tokens=1500)
    safety_settings = [ {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    try:
        loop = asyncio.get_running_loop(); response = await loop.run_in_executor(None, lambda: gemini_model.generate_content(prompt, generation_config=generation_config, safety_settings=safety_settings))
        raw_response_text = "[No text]"; answer = ""; answer_type = "error"
        try:
            raw_response_text = response.text; print(f"[LLM Service] Raw response: {raw_response_text!r}")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason: raise ValueError(f"Blocked: {response.prompt_feedback.block_reason}")
            if response.candidates and response.candidates[0].content.parts:
                 answer = response.text.strip()
                 if not answer: answer_type = "not_found"; answer = "LLM returned empty answer."
                 elif "do not contain relevant information" in answer.lower() or "information is not available" in answer.lower(): answer_type = "not_found"
                 else: answer_type = "text"
            else: raise ValueError(f"No valid candidate. Reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
        except (ValueError, AttributeError, Exception) as e: print(f"[LLM Service] WARN processing response: {e}"); answer = f"Error processing LLM response: {e}"; answer_type="error"
        return {"answer": answer, "type": answer_type, "data": None, "chart_data": None}
    except Exception as e: print(f"[LLM Service] ERROR Gemini call failed: {e}"); traceback.print_exc(); return {"answer": "Error communicating with LLM.", "type": "error"}
