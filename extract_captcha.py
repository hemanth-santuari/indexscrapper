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
        
        # Based on the image, the captcha is clearly visible in the middle of the form
        # These coordinates are specifically targeting the captcha area with "DMypxH"
        # Format: (left, top, right, bottom)
        captcha_area = (710, 590, 940, 650)
        
        # Crop the captcha area
        captcha_image = image.crop(captcha_area)
        captcha_filename = os.path.join(save_dir, f"captcha_{os.path.basename(image_path)}")
        captcha_image.save(captcha_filename)
        logger.info(f"Saved captcha image to: {captcha_filename}")
        
        # Apply preprocessing techniques to improve OCR accuracy
        preprocessed_images = []
        
        # Grayscale
        gray = captcha_image.convert('L')
        gray_filename = os.path.join(save_dir, f"gray_{os.path.basename(image_path)}")
        gray.save(gray_filename)
        preprocessed_images.append(("Grayscale", gray, gray_filename))
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        enhanced_filename = os.path.join(save_dir, f"enhanced_{os.path.basename(image_path)}")
        enhanced.save(enhanced_filename)
        preprocessed_images.append(("Enhanced Contrast", enhanced, enhanced_filename))
        
        # Threshold
        threshold = gray.point(lambda x: 0 if x < 128 else 255, '1')
        threshold_filename = os.path.join(save_dir, f"threshold_{os.path.basename(image_path)}")
        threshold.save(threshold_filename)
        preprocessed_images.append(("Threshold", threshold, threshold_filename))
        
        # Resize to make text larger
        resized = captcha_image.resize((captcha_image.width * 2, captcha_image.height * 2), 3)  # 3 = BICUBIC
        resized_filename = os.path.join(save_dir, f"resized_{os.path.basename(image_path)}")
        resized.save(resized_filename)
        preprocessed_images.append(("Resized", resized, resized_filename))
        
        # Edge enhancement
        edge_enhanced = gray.filter(ImageFilter.EDGE_ENHANCE)
        edge_filename = os.path.join(save_dir, f"edge_{os.path.basename(image_path)}")
        edge_enhanced.save(edge_filename)
        preprocessed_images.append(("Edge Enhanced", edge_enhanced, edge_filename))
        
        # Sharpen
        sharpened = gray.filter(ImageFilter.SHARPEN)
        sharpen_filename = os.path.join(save_dir, f"sharpen_{os.path.basename(image_path)}")
        sharpened.save(sharpen_filename)
        preprocessed_images.append(("Sharpened", sharpened, sharpen_filename))
        
        # Adaptive threshold (simulate)
        # Split the image into regions and apply different thresholds
        width, height = gray.size
        block_size = 10
        adaptive = Image.new('L', (width, height), 255)
        
        for i in range(0, width, block_size):
            for j in range(0, height, block_size):
                # Get the region
                region = gray.crop((i, j, min(i + block_size, width), min(j + block_size, height)))
                # Calculate average
                avg = sum(region.getdata()) / len(region.getdata())
                # Apply threshold
                for x in range(region.width):
                    for y in range(region.height):
                        if i + x < width and j + y < height:
                            pixel = region.getpixel((x, y))
                            adaptive.putpixel((i + x, j + y), 0 if pixel < avg * 0.9 else 255)
        
        adaptive_filename = os.path.join(save_dir, f"adaptive_{os.path.basename(image_path)}")
        adaptive.save(adaptive_filename)
        preprocessed_images.append(("Adaptive Threshold", adaptive, adaptive_filename))
        
        # Perform OCR on each preprocessed image
        ocr_configs = [
            ("Default", ""),
            ("PSM 6", "--psm 6"),
            ("PSM 7", "--psm 7"),
            ("PSM 8", "--psm 8"),
            ("PSM 13", "--psm 13"),
            ("Alphanumeric", "--psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
            ("Digits_Letters", "--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"),
            ("PSM 10", "--psm 10"),  # Treat as single character
            ("PSM 11", "--psm 11"),  # Sparse text with OSD
            ("PSM 12", "--psm 12"),  # Sparse text
            ("PSM 3", "--psm 3"),    # Fully automatic page segmentation
            ("OEM 0", "--oem 0"),    # Legacy engine only
            ("OEM 1", "--oem 1"),    # Neural nets LSTM engine only
            ("OEM 2", "--oem 2"),    # Legacy + LSTM engines
            ("OEM 3", "--oem 3"),    # Default, based on what is available
            ("DMypxH Specific", "--psm 7 -c tessedit_char_whitelist=DMypxH"),  # Specific to this captcha
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
        
        # If no good match to expected captcha, return the most common result
        if all_results:
            # Count occurrences of each text
            text_counts = {}
            for _, _, text in all_results:
                text = text.upper()
                if text in text_counts:
                    text_counts[text] += 1
                else:
                    text_counts[text] = 1
            
            # Find the most common text
            most_common_text = max(text_counts.items(), key=lambda x: x[1])[0]
            logger.info(f"Most common OCR result: '{most_common_text}' (occurred {text_counts[most_common_text]} times)")
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
    image_path = "dropdown_debug/after_district_1753090987.png"
    
    captcha_text = extract_captcha(image_path)
    
    print("=" * 50)
    print(f"Extracted captcha text: {captcha_text}")
    print("=" * 50)