from PIL import Image
import pytesseract
from app.core.config import settings
import os
from typing import Union
import numpy as np

# Try importing OpenCV, handle gracefully if not installed
try:
    import cv2
    OPENCV_AVAILABLE = True
    print("[OCR Service] OpenCV library found.")
except ImportError:
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!!! WARNING: opencv-python-headless not found or installed.   !!!")
    print("!!!          Image preprocessing for OCR will be skipped.     !!!")
    print("!!!          Run: pip install opencv-python-headless          !!!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    OPENCV_AVAILABLE = False
    cv2 = None # Define cv2 as None to avoid NameErrors later

# Set Tesseract command if configured
if settings.TESSERACT_CMD and os.path.exists(settings.TESSERACT_CMD):
     pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

def preprocess_image_for_ocr(image: np.ndarray) -> np.ndarray:
    """Applies preprocessing steps to an image loaded with OpenCV."""
    if not OPENCV_AVAILABLE:
        print("[OCR Preprocessing] Skipping: OpenCV not available.")
        return image # Return original if OpenCV cannot be used

    print("[OCR Preprocessing] Applying steps...")
    # 1. Convert to Grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    print("[OCR Preprocessing] Converted to grayscale.")

    # 2. Apply Thresholding (Otsu's binarization works well often)
    #    Alternatively, use adaptive thresholding for varying light:
    #    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    thresh_val, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    print(f"[OCR Preprocessing] Applied Otsu thresholding (Value: {thresh_val}).")

    # 3. Optional: Noise Reduction (Median Blur)
    #    Can sometimes help, but might blur small details in handwriting
    # processed = cv2.medianBlur(thresh, 3)
    # print("[OCR Preprocessing] Applied median blur.")
    processed = thresh # Skip blur for now unless needed

    # 4. Optional: Deskewing (More complex - requires finding orientation)
    #    Example using moments (simplified):
    #    try:
    #        coords = cv2.findNonZero(processed)
    #        angle = cv2.minAreaRect(coords)[-1]
    #        if angle < -45: angle = -(90 + angle)
    #        else: angle = -angle
    #        (h, w) = image.shape[:2]
    #        center = (w // 2, h // 2)
    #        M = cv2.getRotationMatrix2D(center, angle, 1.0)
    #        processed = cv2.warpAffine(processed, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    #        print(f"[OCR Preprocessing] Applied deskewing (Angle: {angle:.2f}).")
    #    except Exception as deskew_err:
    #        print(f"[OCR Preprocessing] Deskewing failed or skipped: {deskew_err}")


    print("[OCR Preprocessing] Steps complete.")
    return processed


def perform_ocr(image_input: Union[str, Image.Image]) -> str:
    """Performs OCR, applying preprocessing if OpenCV is available."""
    pil_image = None
    image_source = "Unknown"

    try:
        # --- Load Image (ensure PIL format for pytesseract later) ---
        if isinstance(image_input, str): # Input is a file path
             image_source = image_input
             print(f"[OCR Service] Loading image from file: {image_source}")
             if not os.path.exists(image_source):
                  print(f"ERROR: Image file not found: {image_source}")
                  return ""
             # Load with PIL first to ensure compatibility
             pil_image = Image.open(image_source)
        elif isinstance(image_input, Image.Image): # Input is a PIL Image object
             image_source = "PIL Image object"
             print(f"[OCR Service] Using provided {image_source}")
             pil_image = image_input
        else:
             print(f"ERROR: Invalid input type for OCR: {type(image_input)}")
             return ""

        # --- Preprocessing ---
        processed_image_for_tesseract = pil_image # Default to original PIL image
        if OPENCV_AVAILABLE and pil_image:
             try:
                 # Convert PIL Image to OpenCV format (NumPy array)
                 open_cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                 # Apply preprocessing functions
                 processed_open_cv_image = preprocess_image_for_ocr(open_cv_image)
                 # Convert preprocessed OpenCV image back to PIL format for Pytesseract
                 processed_image_for_tesseract = Image.fromarray(cv2.cvtColor(processed_open_cv_image, cv2.COLOR_BGR2RGB))
                 print("[OCR Service] Preprocessing applied.")
             except Exception as preproc_err:
                  print(f"WARNING: Preprocessing failed: {preproc_err}. Using original image for OCR.")
                  processed_image_for_tesseract = pil_image # Fallback

        # --- Perform OCR ---
        print("[OCR Service] Performing Tesseract OCR...")
        # Use specific language if known, add config options if needed
        # e.g., custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed_image_for_tesseract, lang='eng') # Pass preprocessed image
        print("[OCR Service] OCR complete.")
        return text.strip()

    except ImportError as imp_err:
        # Catch potential Pillow/Numpy import errors if environment is broken
        print(f"ERROR: Required library not found ({imp_err}). Cannot process images.")
        return ""
    except pytesseract.TesseractNotFoundError:
        print("ERROR: Tesseract executable not found. OCR failed.")
        return ""
    except Exception as e:
        print(f"ERROR: OCR failed for {image_source}: {e}")
        import traceback
        traceback.print_exc()
        return ""

