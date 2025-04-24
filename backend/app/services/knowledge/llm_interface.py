import google.generativeai as genai
from typing import List, Dict, Any, Optional
import json
import asyncio
import os
import traceback # Import traceback for logging

from app.core.config import settings
from app.models.data_models import DocumentChunk

# --- Globals ---
gemini_model = None
gemini_client_configured = False

def configure_gemini_client():
    """Initializes the Gemini client if not already done."""
    global gemini_model, gemini_client_configured
    if gemini_client_configured:
        return

    print("[LLM Service] Attempting to configure Gemini client...")
    if not settings.GEMINI_API_KEY:
        print("WARNING: Gemini API Key not configured.")
        gemini_model = None
        gemini_client_configured = True # Mark as configured (but failed)
        return

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
        print(f"[LLM Service] Gemini client configured for model: {settings.GEMINI_MODEL_NAME}")
        gemini_client_configured = True
    except Exception as e:
        print(f"ERROR: Failed to configure Gemini client: {e}")
        gemini_model = None
        gemini_client_configured = True # Mark as configured (but failed)

# Call configuration once on import
configure_gemini_client()

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
    Generates an answer using Google Gemini based on the provided question and context.
    """
    if not gemini_client_configured:
         configure_gemini_client() # Try again in case key was added later

    if not gemini_model:
         print("[LLM Service] Aborting generation: Gemini model not available.")
         return {
            "answer": "LLM functionality is disabled or failed to initialize. Check API key configuration and backend logs.",
            "type": "error", "data": None, "chart_data": None
        }

    formatted_context = format_context(context_chunks)

    # Simplified System Prompt (integrated into main prompt for Gemini)
    prompt = f"""Based *only* on the following context:

**Context:**
{formatted_context}

---
**Question:** {question}

**Instructions:**
- Answer the question using *only* information found in the Context above.
- If the question asks for a summary or asks "what is this about?", synthesize a summary from the key points in the Context.
- If the context does not contain the answer, state clearly: "The provided documents do not contain information relevant to this question."
- Be as detailed as the context allows.

 - **IMPORTANT:** Do NOT include any meta-references like "(Context Chunk X)" in your final answer.
**Answer:**
""" # Ensure the closing triple quote is here and correctly placed

    print(f"[LLM Service] Calling Gemini API (Model: {settings.GEMINI_MODEL_NAME})...")
    # --- Debug Logging ---
    print(f"[LLM Service] Context Provided (First 1000 chars):\n{formatted_context[:1000]}...")
    print("-" * 20 + " END CONTEXT SNIPPET " + "-" * 20)
    # Log the prompt *without* the potentially huge context for clarity
    prompt_structure_log = f"""**Instructions:**
- Answer the question using *only* information found in the Context above.
- If the question asks for a summary or asks "what is this about?", synthesize a summary from the key points in the Context.
- If the context does not contain the answer, state clearly: "The provided documents do not contain information relevant to this question."
- Be as detailed as the context allows.

---
**Question:** {question}

**Answer:**
"""
    print(f"[LLM Service] Prompt Structure Sent (Context omitted):\n{prompt_structure_log}")
    # --- End Debug Logging ---


    # Configuration for generation
    generation_config = genai.types.GenerationConfig(
      temperature=0.6, # Slightly increased temperature
      max_output_tokens=1500 # Increased token limit
    )
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: gemini_model.generate_content(
                prompt, # Pass the full prompt with context
                generation_config=generation_config,
                safety_settings=safety_settings
            )
        )

        # --- Process Gemini Response ---
        raw_response_text = "[No response text accessible]" # Default
        gemini_answer = "" # Default empty answer
        answer_type = "error" # Default to error

        try:
            # Log raw response text if possible
            raw_response_text = response.text
            print(f"[LLM Service] Raw response content from Gemini: {raw_response_text!r}") # Use !r

            # Check for safety blocks using prompt_feedback first
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 block_reason = response.prompt_feedback.block_reason
                 error_msg = f"Content generation blocked by safety filters. Reason: {block_reason}."
                 print(f"[LLM Service] WARNING: {error_msg}")
                 return {"answer": "Could not generate an answer due to content safety filters.", "type": "error"}

            # Check candidates for content
            if response.candidates and hasattr(response.candidates[0], 'content') and hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts:
                 gemini_answer = response.text.strip() # Get text if candidate is valid
                 print("[LLM Service] Received valid response content from Gemini.")

                 # Determine type based on content
                 answer_lower = gemini_answer.lower()
                 if "the provided documents do not contain information relevant to this question" in answer_lower:
                     answer_type = "not_found"
                 else:
                     # [TODO] Add logic to detect table/chart data if needed
                     answer_type = "text" # Assume text otherwise

            else: # No valid candidate content
                finish_reason = "Unknown"
                if hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                    finish_reason = response.candidates[0].finish_reason
                error_msg = f"No valid content candidate found in response. Finish Reason: {finish_reason}"
                print(f"[LLM Service] WARNING: {error_msg}")
                if "SAFETY" in str(finish_reason).upper():
                    return {"answer": "Could not generate an answer due to content safety filters.", "type": "error"}
                else:
                    return {"answer": f"LLM did not generate a valid answer. (Reason: {finish_reason})", "type": "error"}

        except ValueError:
            # Handle cases where accessing response.text might raise ValueError (e.g., blocked content)
             print("[LLM Service] ValueError accessing response text, likely blocked content.")
             # Check prompt feedback again just in case
             if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                  return {"answer": "Could not generate an answer due to content safety filters.", "type": "error"}
             else:
                  return {"answer": "LLM response was blocked or empty.", "type": "error"}
        except AttributeError as ae:
             print(f"[LLM Service] AttributeError accessing response parts: {ae}")
             return {"answer": "Error processing LLM response format.", "type": "error"}


        # Return successful result
        return {
            "answer": gemini_answer,
            "type": answer_type,
            "data": None,
            "chart_data": None
        }

    except Exception as e:
        # Catch other errors during the API call or processing
        print(f"[LLM Service] ERROR: An unexpected error occurred during Gemini API call/processing: {e}")
        traceback.print_exc()
        return {"answer": "Error: An unexpected error occurred while communicating with the LLM.", "type": "error"}

