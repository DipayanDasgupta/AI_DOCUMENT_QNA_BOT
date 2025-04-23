from PIL import Image
import pytesseract
from app.core.config import settings
import os
from typing import Union # Import Union

# Set Tesseract command if configured
if settings.TESSERACT_CMD and os.path.exists(settings.TESSERACT_CMD):
     pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

def perform_ocr(image_input: Union[str, Image.Image]) -> str:
    """
    Performs OCR on an image file path OR a PIL Image object.

    Args:
        image_input: Either the path to the image file (str) or a PIL Image object.

    Returns:
        The extracted text string, or an empty string if OCR fails.
    """
    try:
        # Check if tesseract command is valid if set explicitly
        if settings.TESSERACT_CMD and not os.path.exists(settings.TESSERACT_CMD):
             print(f"WARNING: Tesseract command '{settings.TESSERACT_CMD}' not found. OCR may fail.")

        if isinstance(image_input, str): # Input is a file path
             print(f"[OCR Service] Performing OCR on file: {image_input}")
             if not os.path.exists(image_input):
                  print(f"ERROR: Image file not found: {image_input}")
                  return ""
             img = Image.open(image_input)
        elif isinstance(image_input, Image.Image): # Input is a PIL Image object
             print("[OCR Service] Performing OCR on PIL Image object...")
             img = image_input
        else:
             print(f"ERROR: Invalid input type for OCR: {type(image_input)}")
             return ""

        # Perform OCR
        text = pytesseract.image_to_string(img)
        print(f"[OCR Service] OCR complete.")
        return text.strip()

    except ImportError:
        print("ERROR: Pillow library not found. Cannot process images.")
        return ""
    except pytesseract.TesseractNotFoundError:
        print("ERROR: Tesseract executable not found in PATH or not configured correctly. OCR failed.")
        return ""
    except Exception as e:
        image_source = image_input if isinstance(image_input, str) else "PIL Image"
        print(f"ERROR: OCR failed for {image_source}: {e}")
        return ""

