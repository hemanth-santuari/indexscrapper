import os
import sys
import base64
import requests
import json
import time
import logging
import os
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from io import BytesIO
import tkinter as tk
from tkinter import Label, Entry, Button, StringVar

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logging.warning("pytesseract not installed. OCR-based captcha solving will not be available.")

logger = logging.getLogger('captcha_solver')

class CaptchaSolver:
    def __init__(self, api_key='', service='ocr'):
        """Initialize the CaptchaSolver with an optional API key and service."""
        self.api_key = api_key
        self.service = service.lower()
        self.supported_services = ['2captcha', 'anticaptcha', 'ocr', 'manual']
        
        if self.api_key and self.service not in self.supported_services:
            logger.warning(f"Unsupported captcha service: {self.service}. Falling back to OCR or manual mode.")
            self.service = 'ocr' if PYTESSERACT_AVAILABLE else 'manual'
        
        if self.service == 'ocr' and not PYTESSERACT_AVAILABLE:
            logger.warning("OCR service selected but pytesseract not installed. Falling back to manual mode.")
            self.service = 'manual'
    
    def solve_captcha_image(self, image_data, max_retries=3):
        """
        Solve a captcha from image data.
        
        Args:
            image_data: The captcha image data (bytes or base64 string)
            max_retries: Maximum number of retries for API services
            
        Returns:
            The solved captcha text or None if failed
        """
        if self.service == 'ocr' or not self.api_key:
            if PYTESSERACT_AVAILABLE:
                ocr_result = self._solve_with_ocr(image_data)
                if ocr_result and len(ocr_result) >= 4:
                    logger.info(f"Captcha solved with OCR: {ocr_result}")
                    return ocr_result
                logger.warning("OCR failed to solve captcha or result too short.")
            
            if not self.api_key:
                return self._solve_manually(image_data)
        
        if self.service == 'manual':
            return self._solve_manually(image_data)
        
        for attempt in range(max_retries):
            try:
                if self.service == '2captcha':
                    return self._solve_with_2captcha(image_data)
                elif self.service == 'anticaptcha':
                    return self._solve_with_anticaptcha(image_data)
            except Exception as e:
                logger.error(f"Error solving captcha with {self.service} (attempt {attempt+1}/{max_retries}): {str(e)}")
                time.sleep(2)  # Wait before retry
        
        if PYTESSERACT_AVAILABLE:
            logger.warning(f"All {max_retries} attempts with {self.service} failed. Trying OCR.")
            ocr_result = self._solve_with_ocr(image_data)
            if ocr_result and len(ocr_result) >= 4:
                logger.info(f"Captcha solved with OCR after API failure: {ocr_result}")
                return ocr_result
        
        logger.warning("Falling back to manual solving.")
        return self._solve_manually(image_data)
    
    def _solve_with_2captcha(self, image_data):
        """Solve captcha using 2Captcha service."""
        logger.info("Solving captcha with 2Captcha...")
        
        if isinstance(image_data, bytes):
            image_data = base64.b64encode(image_data).decode('utf-8')
        
        # Submit the captcha
        url = "https://2captcha.com/in.php"
        data = {
            'key': self.api_key,
            'method': 'base64',
            'body': image_data,
            'json': 1
        }
        response = requests.post(url, data=data)
        result = response.json()
        
        if result['status'] != 1:
            raise Exception(f"Failed to submit captcha: {result['request']}")
        
        captcha_id = result['request']
        
        # Wait for the result
        url = "https://2captcha.com/res.php"
        params = {
            'key': self.api_key,
            'action': 'get',
            'id': captcha_id,
            'json': 1
        }
        
        for _ in range(30):
            time.sleep(5)
            response = requests.get(url, params=params)
            result = response.json()
            
            if result['status'] == 1:
                logger.info("Captcha solved successfully with 2Captcha")
                return result['request']
            
            if result['request'] != 'CAPCHA_NOT_READY':
                raise Exception(f"Failed to solve captcha: {result['request']}")
        
        raise Exception("Timeout waiting for captcha solution")
    
    def _solve_with_anticaptcha(self, image_data):
        """Solve captcha using Anti-Captcha service."""
        logger.info("Solving captcha with Anti-Captcha...")
        
        if isinstance(image_data, bytes):
            image_data = base64.b64encode(image_data).decode('utf-8')
        
        # Create task
        url = "https://api.anti-captcha.com/createTask"
        data = {
            "clientKey": self.api_key,
            "task": {
                "type": "ImageToTextTask",
                "body": image_data,
                "phrase": False,
                "case": True,
                "numeric": 0,
                "math": False,
                "minLength": 0,
                "maxLength": 0
            }
        }
        
        response = requests.post(url, json=data)
        result = response.json()
        
        if result.get('errorId', 0) != 0:
            raise Exception(f"Failed to submit captcha: {result.get('errorDescription', 'Unknown error')}")
        
        task_id = result['taskId']
        
        # Get task result
        url = "https://api.anti-captcha.com/getTaskResult"
        data = {
            "clientKey": self.api_key,
            "taskId": task_id
        }
        
        for _ in range(30):
            time.sleep(5)
            response = requests.post(url, json=data)
            result = response.json()
            
            if result.get('errorId', 0) != 0:
                raise Exception(f"Error checking captcha status: {result.get('errorDescription', 'Unknown error')}")
            
            if result.get('status') == 'ready':
                logger.info("Captcha solved successfully with Anti-Captcha")
                return result.get('solution', {}).get('text', '')
        
        raise Exception("Timeout waiting for captcha solution")
    
    def _solve_manually(self, image_data):
        """Show the captcha image and get manual input."""
        logger.info("Solving captcha manually...")
        
        # Convert image_data to an image
        if isinstance(image_data, str):
            # Assume it's base64 encoded
            image_data = base64.b64decode(image_data)
        
        image = Image.open(BytesIO(image_data))
        
        captcha_text = None
        
        def submit_captcha():
            nonlocal captcha_text
            captcha_text = captcha_var.get()
            root.quit()
        
        root = tk.Tk()
        root.title("Captcha Solver")
        root.geometry("300x200")
        
        Label(root, text="Enter the captcha text:").pack(pady=10)
        
        image = image.resize((200, 80), Image.Resampling.LANCZOS)
        photo = tk.PhotoImage(data=self._image_to_data(image))
        Label(root, image=photo).pack(pady=10)
        
        captcha_var = StringVar()
        Entry(root, textvariable=captcha_var, width=20).pack(pady=5)
        
        Button(root, text="Submit", command=submit_captcha).pack(pady=10)
        
        root.mainloop()
        
        root.destroy()
        
        logger.info(f"Manual captcha solution: {captcha_text}")
        return captcha_text
    
    def _image_to_data(self, image):
        """Convert PIL Image to PhotoImage compatible data."""
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def _solve_with_ocr(self, image_data):
        """Solve captcha using OCR with pytesseract."""
        if not PYTESSERACT_AVAILABLE:
            logger.error("pytesseract not installed. Cannot use OCR.")
            return None
        
        try:
            logger.info("Attempting to solve captcha with OCR...")
            
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)
            
            image = Image.open(BytesIO(image_data))
            
            debug_dir = os.path.join(os.getcwd(), 'captcha_debug')
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            timestamp = int(time.time())
            original_path = os.path.join(debug_dir, f'original_{timestamp}.png')
            image.save(original_path)
            
            image = image.convert('L')
            
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2)
            
            image = image.filter(ImageFilter.MedianFilter())
            
            threshold = 140
            image = ImageOps.invert(image)
            
            processed_path = os.path.join(debug_dir, f'processed_{timestamp}.png')
            image.save(processed_path)
            
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            text = text.strip()
            text = ''.join(c for c in text if c.isalnum())
            
            logger.info(f"OCR result: {text}")
            return text
        except Exception as e:
            logger.error(f"Error solving captcha with OCR: {str(e)}")
            return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        solver = CaptchaSolver()
        
        if PYTESSERACT_AVAILABLE:
            print("Trying OCR first...")
            ocr_result = solver._solve_with_ocr(image_data)
            print(f"OCR solution: {ocr_result}")
        
        print("Now trying manual solving...")
        manual_result = solver._solve_manually(image_data)
        print(f"Manual solution: {manual_result}")
    else:
        print("Usage: python captcha_solver.py <captcha_image_path>")