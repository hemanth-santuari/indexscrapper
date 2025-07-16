# Free Captcha Solving Guide

This guide provides information on free methods to solve captchas without using paid services.

## Manual Captcha Solving

The property scraper already includes a manual captcha solving option that displays the captcha image in a simple GUI window. This is the most reliable free method but requires human intervention.

## Automated Free Captcha Solving Methods

### 1. Simple OCR for Basic Captchas

For simple text-based captchas, you can use free OCR libraries:

```bash
pip install pytesseract
pip install pillow
```

Example implementation:

```python
import pytesseract
from PIL import Image
from io import BytesIO
import base64

def solve_captcha_with_ocr(image_data):
    """
    Attempt to solve a captcha using OCR

    Args:
        image_data: The captcha image data (bytes or base64 string)

    Returns:
        The solved captcha text or None if failed
    """
    try:
        # Convert image_data to an image
        if isinstance(image_data, str):
            # Assume it's base64 encoded
            image_data = base64.b64decode(image_data)

        image = Image.open(BytesIO(image_data))

        # Preprocess the image to improve OCR accuracy
        # Convert to grayscale
        image = image.convert('L')

        # Increase contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2)

        # Remove noise
        from PIL import ImageFilter
        image = image.filter(ImageFilter.MedianFilter())

        # Threshold the image
        threshold = 140
        from PIL import ImageOps
        image = ImageOps.invert(image)

        # Use pytesseract to extract text
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        text = pytesseract.image_to_string(image, config=custom_config)

        # Clean up the text
        text = text.strip()
        text = ''.join(c for c in text if c.isalnum())

        return text
    except Exception as e:
        print(f"Error solving captcha with OCR: {str(e)}")
        return None
```

Note: This method works best for simple captchas. The Maharashtra government website captchas may be too complex for basic OCR.

### 2. Machine Learning Approaches

For more complex captchas, you can use free machine learning libraries:

```bash
pip install tensorflow
pip install keras
pip install opencv-python
```

Training a model requires:

1. Collecting many captcha examples
2. Labeling them manually
3. Training a CNN model

This is a more advanced approach and requires some machine learning knowledge.

### 3. Browser Extensions

Some browser extensions can help with captcha solving:

- Buster Captcha Solver for Humans (Chrome/Firefox)
- Captcha Solver (Chrome)

To use these with Selenium:

```python
def setup_driver_with_extensions():
    """Set up Chrome with captcha solving extensions"""
    chrome_options = Options()

    # Add extension
    chrome_options.add_extension('path/to/extension.crx')

    # Other options
    chrome_options.add_argument('--start-maximized')

    return webdriver.Chrome(options=chrome_options)
```

### 4. Implementing a Simple Captcha Solver for the Website

For the Maharashtra property website specifically, you can try to implement a custom solver:

1. Collect 100-200 captcha images from the website
2. Manually label them
3. Train a simple model using scikit-learn or TensorFlow

Example collection script:

```python
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import base64

def collect_captcha_samples(num_samples=100, output_dir='captcha_samples'):
    """Collect captcha samples from the website"""
    os.makedirs(output_dir, exist_ok=True)

    chrome_options = Options()
    driver = webdriver.Chrome(options=chrome_options)

    try:
        for i in range(num_samples):
            # Navigate to the website
            driver.get("https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index")

            # Wait for captcha to load
            time.sleep(2)

            # Get the captcha image
            captcha_img = driver.find_element(By.CSS_SELECTOR, "img[alt='Captcha']")

            # Get the captcha image as base64
            captcha_base64 = driver.execute_script("""
                var img = document.querySelector("img[alt='Captcha']");
                var canvas = document.createElement('canvas');
                canvas.width = img.width;
                canvas.height = img.height;
                var ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                return canvas.toDataURL('image/png').replace(/^data:image\/(png|jpg);base64,/, '');
            """)

            # Save the captcha image
            with open(os.path.join(output_dir, f'captcha_{i}.png'), 'wb') as f:
                f.write(base64.b64decode(captcha_base64))

            print(f"Collected captcha {i+1}/{num_samples}")

            # Refresh the page to get a new captcha
            driver.refresh()
            time.sleep(1)

    finally:
        driver.quit()
```

## Integrating with the Property Scraper

To integrate these free captcha solving methods with the property scraper:

1. Update the `captcha_solver.py` file to include the OCR method:

```python
def solve_captcha_image(self, image_data, max_retries=3):
    """
    Solve a captcha from image data.

    Args:
        image_data: The captcha image data (bytes or base64 string)
        max_retries: Maximum number of retries for API services

    Returns:
        The solved captcha text or None if failed
    """
    if self.api_key and self.service != 'manual':
        # Try to solve using the selected API service
        # (existing code)
        pass
    else:
        # Try OCR first
        ocr_result = solve_captcha_with_ocr(image_data)
        if ocr_result and len(ocr_result) >= 5:  # Assuming captcha is at least 5 chars
            logger.info(f"Captcha solved with OCR: {ocr_result}")
            return ocr_result

        # If OCR fails, fall back to manual solving
        return self._solve_manually(image_data)
```

## Limitations of Free Captcha Solving

1. **Accuracy**: Free methods are generally less accurate than paid services
2. **Automation**: Most free methods still require some manual intervention
3. **Complexity**: The captchas on government websites are often designed to be difficult for automated systems
4. **Time**: Free methods may take longer to solve captchas

## Best Practices

1. Implement multiple methods and fall back from one to another
2. Start with OCR and only use manual solving if OCR fails
3. Collect and label captchas from the specific website for better accuracy
4. Consider using a combination of methods for different scenarios
