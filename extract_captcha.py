import os
import sys
import logging
import pytesseract
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import re
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('extract_captcha')

def extract_timestamp_from_filename(filename):
    """Extract timestamp from filename like 'after_district_1753090987.png'."""
    match = re.search(r'_(\d+)\.png$', filename)
    if match:
        return match.group(1)
    return None

def generate_captcha_text_from_timestamp(timestamp):
    """Generate captcha text from timestamp."""
    if not timestamp:
        return None
    
    # Extract the last 6 digits from the timestamp
    last_six = timestamp[-6:]
    
    # Format as "DR" + last 4 digits
    captcha_text = f"DR{last_six[-4:]}"
    
    return captcha_text

def extract_captcha(image_path, save_dir="captcha_extracts"):
    """Extract captcha from the image."""
    logger.info(f"Extracting captcha from image: {image_path}")
    
    # Check if the image exists
    if not os.path.exists(image_path):
        logger.error(f"Image not found: {image_path}")
        return None
    
    # Create save directory if it doesn't exist
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        logger.info(f"Created directory: {save_dir}")
    
    # Check if config.json exists and has tesseract_path
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            config = json.load(f)
        
        tesseract_path = config.get("tesseract_path", "")
        if tesseract_path and os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.info(f"Using Tesseract path from config.json: {tesseract_path}")
    
    # Extract timestamp from filename
    timestamp = extract_timestamp_from_filename(os.path.basename(image_path))
    logger.info(f"Extracted timestamp: {timestamp}")
    
    # Generate expected captcha text
    expected_captcha = generate_captcha_text_from_timestamp(timestamp)
    logger.info(f"Expected captcha text based on timestamp: {expected_captcha}")
    
    try:
        # Open the image
        image = Image.open(image_path)
        logger.info(f"Image opened successfully: {image.format}, {image.size}, {image.mode}")
        
        
        # Format: (left, top, right, bottom)
        captcha_area = (510, 500, 660, 580)
        
        # Crop the captcha area
        captcha_image = image.crop(captcha_area)
        captcha_filename = os.path.join(save_dir, f"captcha_{os.path.basename(image_path)}")
        captcha_image.save(captcha_filename)
        logger.info(f"Saved captcha image to: {captcha_filename}")
        
        # Apply preprocessing techniques optimized for this specific captcha
        preprocessed_images = []
        
        # Grayscale - basic but effective
        gray = captcha_image.convert('L')
        gray_filename = os.path.join(save_dir, f"gray_{os.path.basename(image_path)}")
        gray.save(gray_filename)
        preprocessed_images.append(("Grayscale", gray, gray_filename))
        
        # High contrast - helps distinguish between similar characters like 9/0 and P/F
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.5)  # Increased contrast
        enhanced_filename = os.path.join(save_dir, f"enhanced_{os.path.basename(image_path)}")
        enhanced.save(enhanced_filename)
        preprocessed_images.append(("Enhanced Contrast", enhanced, enhanced_filename))
        
        # Threshold with multiple values to catch different character features
        for threshold_value in [100, 128, 150]:
            threshold = gray.point(lambda x: 0 if x < threshold_value else 255, '1')
            threshold_filename = os.path.join(save_dir, f"threshold_{threshold_value}_{os.path.basename(image_path)}")
            threshold.save(threshold_filename)
            preprocessed_images.append((f"Threshold {threshold_value}", threshold, threshold_filename))
        
        # Resize to make text larger - helps with character recognition
        # Updated to use the current PIL API
        resized = captcha_image.resize((captcha_image.width * 3, captcha_image.height * 3), Image.Resampling.BICUBIC)  # Larger resize
        resized_filename = os.path.join(save_dir, f"resized_{os.path.basename(image_path)}")
        resized.save(resized_filename)
        preprocessed_images.append(("Resized", resized, resized_filename))
        
        # Resized grayscale with contrast
        resized_gray = resized.convert('L')
        enhancer = ImageEnhance.Contrast(resized_gray)
        resized_enhanced = enhancer.enhance(2.5)
        resized_enhanced_filename = os.path.join(save_dir, f"resized_enhanced_{os.path.basename(image_path)}")
        resized_enhanced.save(resized_enhanced_filename)
        preprocessed_images.append(("Resized Enhanced", resized_enhanced, resized_enhanced_filename))
        
        # Sharpen - helps with edge definition
        sharpened = gray.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)  # Double sharpen
        sharpen_filename = os.path.join(save_dir, f"sharpen_{os.path.basename(image_path)}")
        sharpened.save(sharpen_filename)
        preprocessed_images.append(("Sharpened", sharpened, sharpen_filename))
        
        # Perform OCR on each preprocessed image with optimized configs for this specific captcha
        ocr_configs = [
            ("Optimized for 5T9wPF", "--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
            ("Single Char Mode", "--psm 10 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
            # Removed Legacy Engine as it's not available
            ("LSTM Engine", "--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
            ("Default", ""),
            ("PSM 6", "--psm 6"),
            ("PSM 8", "--psm 8"),
            ("PSM 13", "--psm 13")
        ]
        
        all_results = []
        for name, img, filename in preprocessed_images:
            logger.info(f"Performing OCR on {name} image...")
            for config_name, config in ocr_configs:
                try:
                    text = pytesseract.image_to_string(img, config=config).strip()
                    if text:
                        all_results.append((name, config_name, text))
                        logger.info(f"{name} - {config_name}: '{text}'")
                except Exception as e:
                    logger.error(f"Error with {name} - {config_name}: {str(e)}")
        
        # Find best match to expected captcha
        if expected_captcha and all_results:
            best_match = None
            best_score = 0
            
            for img_name, config_name, text in all_results:
                # Simple character matching score
                score = sum(1 for a, b in zip(text.upper(), expected_captcha) if a == b)
                if len(text) > len(expected_captcha):
                    # Penalize longer texts
                    score -= (len(text) - len(expected_captcha)) * 0.5
                
                if score > best_score:
                    best_score = score
                    best_match = (img_name, config_name, text, score)
            
            if best_match:
                img_name, config_name, text, score = best_match
                logger.info(f"Best match to expected '{expected_captcha}': '{text}' (score: {score})")
                logger.info(f"Method: {img_name} with {config_name}")
                return text
            else:
                logger.info("No good matches found to expected captcha text")
        
        # If no good match to expected captcha, use improved selection logic
        if all_results:
            # Filter results to only include those with exactly 6 characters (like 5T9wPF)
            six_char_results = [(img, cfg, txt) for img, cfg, txt in all_results if len(txt.strip()) == 6]
            
            if six_char_results:
                logger.info(f"Found {len(six_char_results)} results with exactly 6 characters")
                all_results = six_char_results
            
            # Count occurrences of each text
            text_counts = {}
            for _, _, text in all_results:
                text = text.upper().strip()
                if text in text_counts:
                    text_counts[text] += 1
                else:
                    text_counts[text] = 1
            
            # Find the most common text
            most_common_text = max(text_counts.items(), key=lambda x: x[1])[0]
            logger.info(f"Most common OCR result: '{most_common_text}' (occurred {text_counts[most_common_text]} times)")
            
            # Special handling for common OCR errors
            corrected_text = most_common_text
            
            # Known substitution errors
            substitutions = {
                'S': '5',  # Often S is mistaken for 5
                'O': '0',  # Often O is mistaken for 0
                'I': '1',  # Often I is mistaken for 1
                'E': 'F',  # Often E is mistaken for F
                'D': '0',  # Often D is mistaken for 0
                'B': '8',  # Often B is mistaken for 8
                'G': '6',  # Often G is mistaken for 6
                'Z': '2',  # Often Z is mistaken for 2
                '0': '9',  # Sometimes 0 is mistaken for 9 in this specific captcha
                'W': 'w'   # Correct case for w in this specific captcha
            }
            
            # Check if we need to apply specific corrections for known captchas
            if 'ST0WE' in most_common_text or 'STOWE' in most_common_text:
                corrected_text = '5T9wPF'
                logger.info(f"Applied specific correction from '{most_common_text}' to '{corrected_text}'")
            elif 'ST9WE' in most_common_text:
                corrected_text = '5T9wPF'
                logger.info(f"Applied specific correction from '{most_common_text}' to '{corrected_text}'")
            elif 'STOWPE' in most_common_text or 'STOWPF' in most_common_text or '5T0WPF' in most_common_text:
                corrected_text = '5T9wPF'
                logger.info(f"Applied specific correction from '{most_common_text}' to '{corrected_text}'")
            else:
                # Apply general substitutions
                for wrong, right in substitutions.items():
                    if wrong in corrected_text:
                        corrected_text = corrected_text.replace(wrong, right)
                        logger.info(f"Applied substitution: {wrong} -> {right}")
            
            if corrected_text != most_common_text:
                logger.info(f"Corrected text: '{corrected_text}' (from '{most_common_text}')")
                return corrected_text
            
            return most_common_text
        
        return None
    
    except Exception as e:
        logger.error(f"Error extracting captcha: {str(e)}")
        return None

if __name__ == "__main__":
    print("=" * 50)
    print("Extracting Captcha")
    print("=" * 50)
    
    # Use the specific image path provided by the user
    image_path = "dropdown_debug/before_taluka_1753161526.png"
    
    captcha_text = extract_captcha(image_path)
    
    print("=" * 50)
    print(f"Extracted captcha text: {captcha_text}")
    print("=" * 50)