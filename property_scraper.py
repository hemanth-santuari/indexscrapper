import os
import time
import random
import json
import logging
import base64
import requests
import uuid
import socket
import boto3
from datetime import datetime, timedelta
from bs4 import BeautifulSoup, NavigableString, Tag
import concurrent.futures
from github_storage import GitHubStorage
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from solvecaptcha import Solvecaptcha
import warnings

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    from io import BytesIO
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logging.warning("pytesseract not installed. OCR-based captcha solving will not be available.")

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configure logging with UTF-8 encoding
import io
import sys

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Create a UTF-8 encoded stream for console output
utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join('logs', f'scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            encoding='utf-8'
        ),
        logging.StreamHandler(utf8_stdout)
    ]
)
logger = logging.getLogger('property_scraper')

class PropertyScraper:
    def __init__(self, config_path='config.json'):
        """Initialize the PropertyScraper with configuration."""
        self.base_url = "https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index"
        self.download_dir = os.path.join(os.getcwd(), 'downloads')
        self.local_progress_file = 'progress.json'
        self.daily_limit = 5
        self.delay_between_requests = (3, 7)
        
        self.instance_id = f"local_{uuid.uuid4().hex[:8]}"
        logger.info(f"Instance ID: {self.instance_id}")
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.proxies = config.get('proxies', [])
                self.user_agents = config.get('user_agents', [])
                self.captcha_api_key = config.get('captcha_api_key', '')
                self.tesseract_path = config.get('tesseract_path', '')
                self.use_free_proxies = config.get('use_free_proxies', True)
                self.free_proxy_min_count = config.get('free_proxy_min_count', 5)
                
                # Set tesseract path if provided
                if self.tesseract_path and PYTESSERACT_AVAILABLE:
                    pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
                    logger.info(f"Tesseract path set to: {self.tesseract_path}")
                
                self.use_cloud_storage = config.get('use_cloud_storage', False)
                self.cloud_storage_type = config.get('cloud_storage_type', 's3')
                self.cloud_storage_config = config.get('cloud_storage_config', {})
                
                if self.use_cloud_storage:
                    if self.cloud_storage_type == 's3':
                        self.s3_bucket = self.cloud_storage_config.get('bucket_name', '')
                        self.s3_progress_key = self.cloud_storage_config.get('progress_key', 'progress.json')
                        
                        if 'aws_access_key_id' in self.cloud_storage_config and 'aws_secret_access_key' in self.cloud_storage_config:
                            self.s3_client = boto3.client(
                                's3',
                                aws_access_key_id=self.cloud_storage_config.get('aws_access_key_id'),
                                aws_secret_access_key=self.cloud_storage_config.get('aws_secret_access_key'),
                                region_name=self.cloud_storage_config.get('region_name', 'us-east-1')
                            )
                        else:
                            self.s3_client = boto3.client('s3')
                    elif self.cloud_storage_type == 'github':
                        self.github_repo = self.cloud_storage_config.get('repository', '')
                        self.github_token = self.cloud_storage_config.get('token', '')
                        self.github_progress_key = self.cloud_storage_config.get('progress_key', 'progress.json')
                        self.github_client = GitHubStorage(self.github_repo, self.github_token)
                        self.github_sha = None
                        logger.info(f"Initialized GitHub storage for repository: {self.github_repo}")
        else:
            self.proxies = []
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
            ]
            self.captcha_api_key = ''
            self.tesseract_path = ''
            self.use_free_proxies = True
            self.free_proxy_min_count = 5
            self.use_cloud_storage = False
            
        if self.use_free_proxies and not self.proxies:
            logger.info("No proxies provided in config. Fetching free proxies...")
            self.proxies = self.get_free_proxies(min_proxies=self.free_proxy_min_count)
            logger.info(f"Found {len(self.proxies)} working free proxies")
        
        self.progress = self._load_progress()
        
        self.daily_requests = 0
        self.current_session_start = datetime.now()
        
    def _load_progress(self):
        """Load progress from file if exists."""
        if self.use_cloud_storage:
            try:
                if self.cloud_storage_type == 's3':
                    return self._load_progress_from_s3()
                elif self.cloud_storage_type == 'github':
                    return self._load_progress_from_github()
            except Exception as e:
                logger.error(f"Error loading progress from cloud storage: {str(e)}")
                logger.warning("Falling back to local progress file")
        
        if os.path.exists(self.local_progress_file):
            with open(self.local_progress_file, 'r') as f:
                return json.load(f)
                
        return {
            'last_run': None,
            'completed': [],
            'current': {
                'year': None,
                'district': None,
                'taluka': None,
                'village': None,
                'doc_number': None
            }
        }
    
    def _load_progress_from_s3(self):
        """Load progress from S3 bucket."""
        try:
            logger.info(f"Loading progress from S3 bucket: {self.s3_bucket}, key: {self.s3_progress_key}")
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=self.s3_progress_key)
            progress_data = response['Body'].read().decode('utf-8')
            return json.loads(progress_data)
        except self.s3_client.exceptions.NoSuchKey:
            logger.warning(f"Progress file not found in S3 bucket: {self.s3_bucket}, key: {self.s3_progress_key}")
            return {
                'last_run': None,
                'completed': [],
                'current': {
                    'year': None,
                    'district': None,
                    'taluka': None,
                    'village': None,
                    'doc_number': None
                }
            }
        except Exception as e:
            logger.error(f"Error loading progress from S3: {str(e)}")
            raise
    
    def _save_progress(self):
        """Save current progress to file."""
        with open(self.local_progress_file, 'w') as f:
            json.dump(self.progress, f, indent=4)
            
        if self.use_cloud_storage:
            try:
                if self.cloud_storage_type == 's3':
                    self._save_progress_to_s3()
                elif self.cloud_storage_type == 'github':
                    self._save_progress_to_github()
            except Exception as e:
                logger.error(f"Error saving progress to cloud storage: {str(e)}")
                logger.warning("Progress was only saved locally")
    
    def _save_progress_to_s3(self):
        """Save progress to S3 bucket with locking mechanism to prevent race conditions."""
        try:
            try:
                latest_progress = self._load_progress_from_s3()
                
                for task in self.progress['completed']:
                    if task not in latest_progress['completed']:
                        latest_progress['completed'].append(task)
                
                merged_progress = latest_progress
            except Exception as e:
                logger.warning(f"Could not load latest progress from S3 for merging: {str(e)}")
                merged_progress = self.progress
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=self.s3_progress_key,
                Body=json.dumps(merged_progress, indent=4),
                ContentType='application/json'
            )
            logger.info(f"Progress saved to S3 bucket: {self.s3_bucket}, key: {self.s3_progress_key}")
        except Exception as e:
            logger.error(f"Error saving progress to S3: {str(e)}")
            raise
    
    def _load_progress_from_github(self):
        """Load progress from GitHub repository."""
        try:
            logger.info(f"Loading progress from GitHub repository: {self.github_repo}, file: {self.github_progress_key}")
            progress_data, self.github_sha = self.github_client.get_file(self.github_progress_key)
            
            if progress_data:
                logger.info(f"Successfully loaded progress from GitHub")
                return progress_data
            else:
                logger.warning(f"Progress file not found in GitHub repository: {self.github_progress_key}")
                return {
                    'last_run': None,
                    'completed': [],
                    'current': {
                        'year': None,
                        'district': None,
                        'taluka': None,
                        'village': None,
                        'doc_number': None
                    }
                }
        except Exception as e:
            logger.error(f"Error loading progress from GitHub: {str(e)}")
            raise
    
    def _save_progress_to_github(self):
        """Save progress to GitHub repository."""
        try:
            success, new_sha = self.github_client.update_file(
                self.github_progress_key,
                self.progress,
                self.github_sha
            )
            
            if success:
                self.github_sha = new_sha
                logger.info(f"Progress saved to GitHub repository: {self.github_repo}, file: {self.github_progress_key}")
            else:
                logger.error("Failed to save progress to GitHub")
        except Exception as e:
            logger.error(f"Error saving progress to GitHub: {str(e)}")
            raise
    
    def get_free_proxies(self, min_proxies=5, max_workers=10, timeout=5):
        """
        Get a list of working free proxies.
        
        Args:
            min_proxies: Minimum number of working proxies to find
            max_workers: Maximum number of concurrent workers for testing proxies
            timeout: Timeout in seconds for proxy testing
            
        Returns:
            List of working proxy strings
        """
        logger.info("Fetching free proxies...")
        
        working_proxies = []
        
        if len(working_proxies) < min_proxies:
            try:
                source_proxies = self._get_proxies_from_free_proxy_list()
                new_working = self._test_proxies(source_proxies, max_workers, timeout, min_proxies - len(working_proxies))
                working_proxies.extend(new_working)
                logger.info(f"Found {len(new_working)} working proxies from free-proxy-list.net")
            except Exception as e:
                logger.error(f"Error fetching proxies from free-proxy-list.net: {str(e)}")
        
        if len(working_proxies) < min_proxies:
            try:
                source_proxies = self._get_proxies_from_geonode()
                new_working = self._test_proxies(source_proxies, max_workers, timeout, min_proxies - len(working_proxies))
                working_proxies.extend(new_working)
                logger.info(f"Found {len(new_working)} working proxies from geonode")
            except Exception as e:
                logger.error(f"Error fetching proxies from geonode: {str(e)}")
        
        if len(working_proxies) < min_proxies:
            try:
                source_proxies = self._get_proxies_from_proxyscrape()
                new_working = self._test_proxies(source_proxies, max_workers, timeout, min_proxies - len(working_proxies))
                working_proxies.extend(new_working)
                logger.info(f"Found {len(new_working)} working proxies from proxyscrape")
            except Exception as e:
                logger.error(f"Error fetching proxies from proxyscrape: {str(e)}")
        
        return list(set(working_proxies))
    
    def _get_proxies_from_free_proxy_list(self):
        """Scrape free proxies from free-proxy-list.net"""
        try:
            url = 'https://free-proxy-list.net/'
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            proxies = []
            proxy_table = soup.find('table', {'id': 'proxylisttable'})
            
            if proxy_table is None:
                logger.warning("Could not find proxy table on free-proxy-list.net")
                return proxies
                
            rows = []
            try:
                # Check if proxy_table is a proper BeautifulSoup element (not a NavigableString)
                from bs4 import NavigableString
                if proxy_table and not isinstance(proxy_table, NavigableString) and hasattr(proxy_table, 'find_all'):
                    rows = proxy_table.find_all('tr')
                else:
                    logger.warning("Proxy table is not a valid BeautifulSoup element or doesn't have find_all method")
                    return proxies  # Return empty list if we can't find rows
            except Exception as e:
                logger.warning(f"Could not find rows in proxy table: {str(e)}")
                return proxies
            
            if not rows:
                logger.warning("No rows found in proxy table")
                return proxies
            
            for row in rows[1:]:
                # Check if row is a valid BeautifulSoup element
                if isinstance(row, NavigableString) or not hasattr(row, 'find_all'):
                    continue
                    
                cells = row.find_all('td')
                if len(cells) >= 7:  # Ensure we have enough cells
                    # Get cell text safely
                    def get_cell_text(cell):
                        if isinstance(cell, NavigableString):
                            return str(cell)
                        elif isinstance(cell, Tag) and hasattr(cell, 'text'):
                            return cell.text
                        else:
                            return ""
                    
                    ip = get_cell_text(cells[0])
                    port = get_cell_text(cells[1])
                    https = get_cell_text(cells[6])
                    
                    if ip and port:  # Make sure we have valid IP and port
                        if https == 'yes':
                            proxy = f'https://{ip}:{port}'
                            proxies.append(proxy)
                        else:
                            proxy = f'http://{ip}:{port}'
                            proxies.append(proxy)
        except Exception as e:
            logger.error(f"Error getting proxies: {str(e)}")
            proxies = []
        
        return proxies
    
    def _get_proxies_from_geonode(self):
        """Get free proxies from geonode API"""
        url = 'https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc'
        response = requests.get(url)
        data = response.json()
        
        proxies = []
        for proxy in data.get('data', []):
            ip = proxy.get('ip')
            port = proxy.get('port')
            protocol = proxy.get('protocols', ['http'])[0]
            
            if ip and port:
                proxy_str = f'{protocol}://{ip}:{port}'
                proxies.append(proxy_str)
        
        return proxies
    
    def _get_proxies_from_proxyscrape(self):
        """Get free proxies from proxyscrape"""
        url = 'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all'
        response = requests.get(url)
        
        proxies = []
        for line in response.text.split('\n'):
            line = line.strip()
            if line:
                proxy = f'http://{line}'
                proxies.append(proxy)
        
        return proxies
    
    def _test_proxies(self, proxies, max_workers=10, timeout=5, max_working=None):
        """
        Test a list of proxies and return working ones.
        
        Args:
            proxies: List of proxy strings to test
            max_workers: Maximum number of concurrent workers
            timeout: Timeout in seconds for each test
            max_working: Maximum number of working proxies to find (early stop)
            
        Returns:
            List of working proxy strings
        """
        working_proxies = []
        test_url = 'https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index'
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(self._is_proxy_working, proxy, test_url, timeout): proxy for proxy in proxies}
            
            for future in concurrent.futures.as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    if future.result():
                        working_proxies.append(proxy)
                        logger.info(f"Found working proxy: {proxy}")
                        
                        if max_working and len(working_proxies) >= max_working:
                            for f in future_to_proxy:
                                f.cancel()
                            break
                except Exception as e:
                    logger.debug(f"Error testing proxy {proxy}: {str(e)}")
        
        return working_proxies
    
    def _is_proxy_working(self, proxy, test_url, timeout=5):
        """Test if a proxy is working"""
        try:
            proxies = {
                'http': proxy,
                'https': proxy
            }
            response = requests.get(test_url, proxies=proxies, timeout=timeout)
            return response.status_code == 200
        except:
            return False
    
    def _setup_driver(self):
        """Set up and return a webdriver instance with appropriate options."""
        try:
            logger.info("Setting up Chrome WebDriver...")
            
            import undetected_chromedriver as uc
            from selenium.webdriver.chrome.service import Service
            
            uc_options = uc.ChromeOptions()
            uc_options.add_argument("--headless=new")  # Run in new headless mode
            uc_options.add_argument("--disable-notifications")
            uc_options.add_argument("--disable-popup-blocking")
            uc_options.add_argument("--disable-extensions")
            uc_options.add_argument("--disable-infobars")
            uc_options.add_argument("--disable-blink-features=AutomationControlled")  # Hide automation
            uc_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
            uc_options.add_argument("--no-sandbox")  # Bypass OS security model
            uc_options.add_argument("--window-size=1920,1080")  # Set window size
            
            # Additional settings for better headless performance
            uc_options.add_argument("--start-maximized")
            uc_options.add_argument("--force-device-scale-factor=1")
            uc_options.add_argument("--high-dpi-support=1")
            
            if self.user_agents:
                user_agent = random.choice(self.user_agents)
                uc_options.add_argument(f"--user-agent={user_agent}")
                logger.info(f"Using user agent: {user_agent}")
            
            logger.info("Creating Chrome driver using undetected_chromedriver with enhanced settings")
            driver = uc.Chrome(options=uc_options)
            
            driver.set_page_load_timeout(30)
            
            # Maximize window
            driver.maximize_window()
            
            # Set implicit wait
            driver.implicitly_wait(10)
            
            logger.info("Chrome WebDriver set up successfully")
            return driver
            
        except Exception as e:
            logger.error(f"Error setting up Chrome WebDriver: {str(e)}")
            raise Exception(f"Failed to set up Chrome WebDriver: {str(e)}. Browser automation is required.")
    
    def _extract_captcha_from_screenshot(self, screenshot_path):
        """
        Extract captcha text from a screenshot using the improved method.
        
        Args:
            screenshot_path: Path to the screenshot image
            
        Returns:
            str: Extracted captcha text or None if extraction failed
        """
        logger.info(f"Extracting captcha from screenshot: {screenshot_path}")
        
        try:
            # Check if the image exists
            if not os.path.exists(screenshot_path):
                logger.error(f"Screenshot not found: {screenshot_path}")
                return None
            
            # Create save directory if it doesn't exist
            save_dir = "captcha_extracts"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                logger.info(f"Created directory: {save_dir}")
            
            # Open the image
            image = Image.open(screenshot_path)
            logger.info(f"Image opened successfully: {image.format}, {image.size}, {image.mode}")
            
            # Crop the captcha area using the improved coordinates
            captcha_area = (710, 590, 940, 650)
            captcha_image = image.crop(captcha_area)
            captcha_filename = os.path.join(save_dir, f"captcha_{os.path.basename(screenshot_path)}")
            captcha_image.save(captcha_filename)
            logger.info(f"Saved captcha image to: {captcha_filename}")
            
            # Apply preprocessing - Grayscale (best method based on testing)
            gray = captcha_image.convert('L')
            gray_filename = os.path.join(save_dir, f"gray_{os.path.basename(screenshot_path)}")
            gray.save(gray_filename)
            
            # Perform OCR with the best configuration
            custom_config = r'--psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            text = pytesseract.image_to_string(gray, config=custom_config).strip()
            
            if text:
                logger.info(f"Successfully extracted captcha text: '{text}'")
                return text
            else:
                logger.warning("OCR returned empty text")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting captcha: {str(e)}")
            return None
    
    def _handle_captcha(self, driver):
        """Handle captcha solving using the improved screenshot method. Returns True if successful, False otherwise."""
        try:
            logger.info("Looking for captcha...")
            
            # Find the captcha image
            captcha_img = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//img[contains(@src, 'captcha') or contains(@id, 'captcha') or contains(@class, 'captcha-image')]"))
            )
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_img)
            time.sleep(2)  # Wait for scroll to complete
            
            # Check if we have a district dropdown screenshot from this session
            timestamp = int(time.time())
            district_screenshot_path = None
            
            # Look for the most recent after_district_*.png file
            dropdown_debug_dir = "dropdown_debug"
            if os.path.exists(dropdown_debug_dir):
                district_screenshots = [f for f in os.listdir(dropdown_debug_dir) if f.startswith("after_district_") and f.endswith(".png")]
                if district_screenshots:
                    # Sort by timestamp (newest first)
                    district_screenshots.sort(reverse=True)
                    district_screenshot_path = os.path.join(dropdown_debug_dir, district_screenshots[0])
                    logger.info(f"Found district screenshot: {district_screenshot_path}")
            
            captcha_text = None
            
            # If we have a district screenshot, extract the captcha from it using extract_captcha.py
            if district_screenshot_path and os.path.exists(district_screenshot_path):
                logger.info(f"Using existing district screenshot for captcha extraction: {district_screenshot_path}")
                
                # Import extract_captcha function from extract_captcha.py
                try:
                    from extract_captcha import extract_captcha
                    captcha_text = extract_captcha(district_screenshot_path)
                    
                    if captcha_text:
                        logger.info(f"Successfully extracted captcha text using extract_captcha.py: {captcha_text}")
                    else:
                        logger.warning("Failed to extract captcha text using extract_captcha.py")
                except Exception as extract_error:
                    logger.error(f"Error importing or using extract_captcha.py: {str(extract_error)}")
                    
                    # Fallback to internal extraction method if extract_captcha.py fails
                    captcha_text = self._extract_captcha_from_screenshot(district_screenshot_path)
                    if captcha_text:
                        logger.info(f"Successfully extracted captcha text using internal method: {captcha_text}")
                    else:
                        logger.warning("Failed to extract captcha text using internal method")
            
            # If we couldn't extract from district screenshot or don't have one, use SolveCaptcha API
            if not captcha_text and self.captcha_api_key:
                try:
                    # Take a screenshot of the entire page
                    full_screenshot = driver.get_screenshot_as_png()
                    
                    # Open the screenshot
                    image = Image.open(BytesIO(full_screenshot))
                    
                    # Save the full screenshot for debugging
                    os.makedirs("captcha_debug", exist_ok=True)
                    full_path = f"captcha_debug/full_page_{timestamp}.png"
                    image.save(full_path)
                    logger.info(f"Saved full page screenshot to {full_path}")
                    
                    # Try to extract captcha from the full screenshot using extract_captcha.py
                    try:
                        from extract_captcha import extract_captcha
                        captcha_text = extract_captcha(full_path)
                        if captcha_text:
                            logger.info(f"Successfully extracted captcha text from full screenshot: {captcha_text}")
                    except Exception as extract_error:
                        logger.error(f"Error extracting captcha from full screenshot: {str(extract_error)}")
                    
                    # If extract_captcha.py failed, try SolveCaptcha API
                    if not captcha_text:
                        # Initialize SolveCaptcha with API key from config
                        solver = Solvecaptcha(self.captcha_api_key)
                        
                        # Convert image to base64
                        img_byte_arr = BytesIO()
                        image.save(img_byte_arr, format='PNG')
                        img_byte_arr.seek(0)
                        captcha_base64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
                        
                        # Solve the captcha
                        logger.info("Solving captcha with SolveCaptcha API...")
                        captcha_text = solver.normal(captcha_base64)
                        logger.info(f"Captcha solved with SolveCaptcha API: {captcha_text}")
                except Exception as solver_error:
                    logger.error(f"Error using SolveCaptcha API: {str(solver_error)}")
            
            # If we still don't have a captcha text, we can't proceed
            if not captcha_text:
                logger.error("Failed to extract captcha text using all available methods")
                return False
            
            # Find and fill the captcha input field
            captcha_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//input[contains(@id, 'captcha') or contains(@name, 'captcha') or contains(@placeholder, 'captcha') or contains(@placeholder, 'Captcha')]"))
            )
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_input)
            time.sleep(1)
            
            # Clear the input field
            try:
                captcha_input.clear()
                driver.execute_script("arguments[0].value = '';", captcha_input)
                
                from selenium.webdriver.common.keys import Keys
                captcha_input.send_keys(Keys.CONTROL + "a")
                captcha_input.send_keys(Keys.DELETE)
                
                logger.info("Cleared captcha input field")
            except Exception as clear_error:
                logger.warning(f"Error clearing captcha input: {str(clear_error)}")
            
            # Enter the captcha text
            try:
                captcha_input.click()
                time.sleep(1)
                
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(driver)
                actions.move_to_element(captcha_input)
                actions.click()
                actions.send_keys(captcha_text)
                actions.perform()
                
                driver.execute_script(f"arguments[0].value = '{captcha_text}';", captcha_input)
                
                logger.info(f"Entered captcha text: {captcha_text}")
            except Exception as input_error:
                logger.warning(f"Error entering captcha text: {str(input_error)}")
                return False
            
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling captcha: {str(e)}")
            return False
    
    def _select_dropdown_option(self, driver, dropdown_id, option_text):
        """Select an option from a dropdown by visible text."""
        try:
            logger.info(f"Selecting '{option_text}' from dropdown '{dropdown_id}'")
            
            # Take a screenshot before dropdown interaction
            try:
                os.makedirs("dropdown_debug", exist_ok=True)
                timestamp = int(time.time())
                screenshot_path = f"dropdown_debug/before_{dropdown_id}_{timestamp}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot before dropdown interaction: {screenshot_path}")
            except Exception as ss_error:
                logger.warning(f"Could not save screenshot: {str(ss_error)}")
            
            # Find the dropdown element
            dropdown = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, dropdown_id))
            )
            
            # Scroll to the dropdown to make it visible
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
            time.sleep(3)  # Wait longer for scroll to complete
            
            # Remove any overlays that might interfere with clicking
            try:
                driver.execute_script("""
                    var overlays = document.querySelectorAll('.modal, .overlay, .popup, [style*="z-index"]');
                    for(var i=0; i<overlays.length; i++) {
                        overlays[i].style.display = 'none';
                    }
                """)
                logger.info("Removed potential overlay elements")
            except Exception as overlay_error:
                logger.warning(f"Error removing overlays: {str(overlay_error)}")
            
            # PRIORITIZE JAVASCRIPT APPROACH - Most reliable for dropdown selection
            select_success = False
            
            # JavaScript approach first
            try:
                logger.info("Trying JavaScript selection approach first")
                # Get all options to find the matching one
                options_data = driver.execute_script(f"""
                    var select = document.getElementById('{dropdown_id}');
                    var options = select.options;
                    var result = [];
                    for (var i = 0; i < options.length; i++) {{
                        result.push({{
                            text: options[i].text,
                            value: options[i].value,
                            index: i
                        }});
                    }}
                    return result;
                """)
                
                option_index = None
                option_value = None
                
                for opt in options_data:
                    if opt['text'].strip() == option_text or option_text in opt['text'].strip():
                        option_index = opt['index']
                        option_value = opt['value']
                        break
                
                if option_index is not None:
                    # Set the value and trigger change event
                    driver.execute_script(f"""
                        var select = document.getElementById('{dropdown_id}');
                        select.selectedIndex = {option_index};
                        select.value = '{option_value}';
                        var event = new Event('change', {{ bubbles: true }});
                        select.dispatchEvent(event);
                    """)
                    select_success = True
                    logger.info(f"JavaScript selection successful with index: {option_index}, value: {option_value}")
                else:
                    logger.warning(f"Could not find option '{option_text}' in dropdown options via JavaScript")
            except Exception as js_error:
                logger.warning(f"JavaScript selection failed: {str(js_error)}")
            
            # Take a screenshot after JavaScript attempt
            try:
                screenshot_path = f"dropdown_debug/after_js_{dropdown_id}_{timestamp}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot after JavaScript attempt: {screenshot_path}")
            except Exception as ss_error:
                logger.warning(f"Could not save screenshot: {str(ss_error)}")
            
            # If JavaScript approach failed, try Select class approach
            if not select_success:
                try:
                    logger.info("Trying Select class approach")
                    select = Select(dropdown)
                    select.select_by_visible_text(option_text)
                    select_success = True
                    logger.info("Select by visible text successful")
                except Exception as select_error:
                    logger.warning(f"Select by visible text failed: {str(select_error)}")
                    
                    # Try selecting by partial text
                    try:
                        options = select.options
                        for option in options:
                            if option_text in option.text:
                                select.select_by_visible_text(option.text)
                                select_success = True
                                logger.info(f"Select by partial text successful with '{option.text}'")
                                break
                    except Exception as partial_error:
                        logger.warning(f"Select by partial text failed: {str(partial_error)}")
            
            # Take a screenshot after Select class attempt
            try:
                screenshot_path = f"dropdown_debug/after_select_class_{dropdown_id}_{timestamp}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot after Select class attempt: {screenshot_path}")
            except Exception as ss_error:
                logger.warning(f"Could not save screenshot: {str(ss_error)}")
            
            # If Select class approach failed, try direct click approach
            if not select_success:
                try:
                    logger.info("Trying direct click approach")
                    # Click on the dropdown to open it
                    driver.execute_script("arguments[0].click();", dropdown)
                    time.sleep(1)
                    
                    # Try multiple XPath patterns to find the option
                    option_xpaths = [
                        f"//option[text()='{option_text}']",
                        f"//select[@id='{dropdown_id}']/option[text()='{option_text}']",
                        f"//select[@id='{dropdown_id}']/option[contains(text(), '{option_text}')]",
                        f"//select[@id='{dropdown_id}']/option[normalize-space(text())='{option_text}']"
                    ]
                    
                    for xpath in option_xpaths:
                        try:
                            option = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, xpath))
                            )
                            
                            # Try multiple click methods
                            try:
                                # JavaScript click is most reliable
                                driver.execute_script("arguments[0].click();", option)
                                select_success = True
                                logger.info(f"JavaScript click successful using xpath: {xpath}")
                                break
                            except Exception as js_click_error:
                                logger.warning(f"JavaScript click failed: {str(js_click_error)}")
                                
                                try:
                                    # Standard click
                                    option.click()
                                    select_success = True
                                    logger.info(f"Standard click successful using xpath: {xpath}")
                                    break
                                except Exception as std_click_error:
                                    logger.warning(f"Standard click failed: {str(std_click_error)}")
                                    
                                    try:
                                        # Action chains click
                                        from selenium.webdriver.common.action_chains import ActionChains
                                        actions = ActionChains(driver)
                                        actions.move_to_element(option).click().perform()
                                        select_success = True
                                        logger.info(f"Action chains click successful using xpath: {xpath}")
                                        break
                                    except Exception as action_error:
                                        logger.warning(f"Action chains click failed: {str(action_error)}")
                        except Exception as option_find_error:
                            logger.warning(f"Could not find option with xpath {xpath}: {str(option_find_error)}")
                except Exception as direct_error:
                    logger.warning(f"Direct click approach failed: {str(direct_error)}")
            
            # Take a screenshot after all selection attempts
            try:
                screenshot_path = f"dropdown_debug/after_all_attempts_{dropdown_id}_{timestamp}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved screenshot after all selection attempts: {screenshot_path}")
            except Exception as ss_error:
                logger.warning(f"Could not save screenshot: {str(ss_error)}")
            
            # Final fallback: try to select any non-default option if all else fails
            if not select_success:
                try:
                    logger.info("Trying fallback: select any non-default option")
                    driver.execute_script(f"""
                        var select = document.getElementById('{dropdown_id}');
                        if(select.options.length > 1) {{
                            select.selectedIndex = 1;  // Select the first non-default option
                            var event = new Event('change', {{ bubbles: true }});
                            select.dispatchEvent(event);
                        }}
                    """)
                    select_success = True
                    logger.info("Fallback selection successful: selected first non-default option")
                except Exception as fallback_error:
                    logger.warning(f"Fallback selection failed: {str(fallback_error)}")
            
            time.sleep(3)
            
            if select_success:
                logger.info(f"Successfully selected '{option_text}' from dropdown '{dropdown_id}'")
                return True
            else:
                logger.error(f"All selection methods failed for '{option_text}' in dropdown '{dropdown_id}'")
                return False
            
        except Exception as e:
            logger.error(f"Error selecting option '{option_text}' from dropdown '{dropdown_id}': {str(e)}")
            return False
    
    def _get_dropdown_options(self, driver, dropdown_id):
        """Get all options from a dropdown."""
        try:
            logger.info(f"Fetching options for dropdown '{dropdown_id}'...")
            
            if driver is None:
                raise Exception(f"No driver provided for '{dropdown_id}'. Browser automation is required.")
            
            dropdown = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, dropdown_id))
            )
            
            driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
            time.sleep(1)  # Wait for scroll to complete
            
            # Try to click on the dropdown using JavaScript to ensure it's active
            try:
                driver.execute_script("arguments[0].click();", dropdown)
                time.sleep(1)
            except Exception as e:
                logger.warning(f"JavaScript click on dropdown failed: {str(e)}")
            
            # Try different methods to get options
            options = []
            
            # Method 1: Use Select class
            try:
                select = Select(dropdown)
                options = [option.text for option in select.options if option.text.strip()]
            except Exception as e1:
                logger.warning(f"Getting options with Select class failed: {str(e1)}")
                
                try:
                    options_js = driver.execute_script(f"""
                        var options = document.getElementById('{dropdown_id}').options;
                        var result = [];
                        for (var i = 0; i < options.length; i++) {{
                            if (options[i].text.trim()) {{
                                result.push(options[i].text);
                            }}
                        }}
                        return result;
                    """)
                    if options_js and len(options_js) > 0:
                        options = options_js
                except Exception as e2:
                    logger.warning(f"Getting options with JavaScript failed: {str(e2)}")
            
            # Remove any empty or default options like "Select..."
            options = [opt for opt in options if opt and not opt.startswith("Select")]
            
            if options:
                logger.info(f"Found {len(options)} options for dropdown '{dropdown_id}'")
                return options
            else:
                logger.error(f"Could not get options for dropdown '{dropdown_id}'.")
                raise Exception(f"Failed to get options for dropdown '{dropdown_id}'. Browser automation is required.")
            
        except Exception as e:
            logger.error(f"Error getting options for dropdown '{dropdown_id}': {str(e)}")
            raise Exception(f"Failed to get options for dropdown '{dropdown_id}': {str(e)}. Browser automation is required.")
    
    # _get_demo_dropdown_options method removed as we now get dropdown options directly from the website
    
    def _screenshot_to_pdf(self, driver, output_path):
        """
        Take a screenshot of the current page and convert it to a PDF.
        
        Args:
            driver: The Selenium WebDriver instance
            output_path: The path where the PDF should be saved
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Taking screenshot and converting to PDF: {output_path}")
            
            # First try to import the required libraries
            try:
                from PIL import Image
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
                import io
                libraries_available = True
            except ImportError as e:
                logger.error(f"Required libraries for PDF conversion not available: {str(e)}")
                libraries_available = False
                
            if not libraries_available:
                logger.error("Cannot convert screenshot to PDF: required libraries not available")
                return False
                
            # Take a screenshot of the entire page
            # First, get the total height of the page
            total_height = driver.execute_script("return document.body.scrollHeight")
            total_width = driver.execute_script("return document.body.scrollWidth")
            
            # Set window size to capture everything
            original_size = driver.get_window_size()
            driver.set_window_size(total_width, total_height)
            
            # Take the screenshot
            screenshot = driver.get_screenshot_as_png()
            
            # Restore original window size
            driver.set_window_size(original_size['width'], original_size['height'])
            
            # Convert the screenshot to a PDF
            img = Image.open(io.BytesIO(screenshot))
            
            # Create a PDF with the same dimensions as the image
            img_width, img_height = img.size
            pdf_canvas = canvas.Canvas(output_path, pagesize=(img_width, img_height))
            
            # Add the image to the PDF
            pdf_canvas.drawInlineImage(img, 0, 0, width=img_width, height=img_height)
            pdf_canvas.save()
            
            logger.info(f"Successfully created PDF from screenshot: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error converting screenshot to PDF: {str(e)}")
            return False
    
    def _download_pdfs(self, driver):
        """Download all PDFs from the search results page by clicking on 'List No. 2' buttons."""
        try:
            # If driver is None, raise an exception
            if driver is None:
                raise Exception("No driver provided for PDF downloads. Browser automation is required.")
            
            logger.info("Looking for 'List No. 2' buttons in the search results table...")
            
            # Wait for the table to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'dataTable') or contains(@id, 'dataTable')]"))
            )
            
            # Find all "List No. 2" buttons in the table
            # The buttons might be in different columns, so we'll look for them by text
            list_no2_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'List No. 2') or contains(text(), 'IndexII')]")
            
            if not list_no2_buttons:
                logger.warning("No 'List No. 2' buttons found in the search results table")
                return 0
                
            logger.info(f"Found {len(list_no2_buttons)} 'List No. 2' buttons")
            
            # Store the current window handle
            main_window = driver.current_window_handle
            
            # Track the number of PDFs downloaded
            pdfs_downloaded = 0
            
            # Click on each button and download the PDF
            for i, button in enumerate(list_no2_buttons):
                try:
                    logger.info(f"Clicking on 'List No. 2' button {i+1}/{len(list_no2_buttons)}...")
                    
                    # Scroll to the button to make it visible
                    driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    time.sleep(0.5)  # Wait for scroll to complete
                    
                    # Get the document ID or other identifying information from the row
                    try:
                        # Try to get the document number from the row (adjust XPath as needed)
                        row = button.find_element(By.XPATH, "./ancestor::tr")
                        doc_cells = row.find_elements(By.XPATH, "./td")
                        doc_info = ""
                        if len(doc_cells) > 0:
                            doc_info = doc_cells[0].text.strip()
                    except Exception:
                        doc_info = f"doc_{i+1}"
                    
                    # Click the button (this will open a new tab)
                    button.click()
                    
                    # Wait for the new tab to open
                    time.sleep(2)
                    
                    # Switch to the new tab
                    new_tabs = [handle for handle in driver.window_handles if handle != main_window]
                    if not new_tabs:
                        logger.warning(f"No new tab opened after clicking button {i+1}")
                        continue
                        
                    driver.switch_to.window(new_tabs[0])
                    
                    # Wait for the PDF to load
                    time.sleep(3)
                    
                    # Get the current URL (should be a PDF)
                    pdf_url = driver.current_url
                    
                    # Generate a meaningful filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    if "pdf" in pdf_url.lower():
                        # Try to extract a filename from the URL
                        url_filename = pdf_url.split("/")[-1]
                        if url_filename and len(url_filename) > 5:  # Reasonable filename length
                            pdf_name = url_filename
                            if not pdf_name.endswith(".pdf"):
                                pdf_name += ".pdf"
                        else:
                            pdf_name = f"{doc_info}_{timestamp}.pdf"
                    else:
                        pdf_name = f"{doc_info}_{timestamp}.pdf"
                    
                    logger.info(f"Downloading PDF: {pdf_name} from URL: {pdf_url}")
                    
                    # Full path to save the PDF
                    pdf_path = os.path.join(self.download_dir, pdf_name)
                    
                    screenshot_success = self._screenshot_to_pdf(driver, pdf_path)
                    if screenshot_success:
                        logger.info(f"Successfully created PDF from screenshot: {pdf_path}")
                        pdfs_downloaded += 1
                    else:
                        logger.warning("Screenshot to PDF conversion failed, trying alternative methods...")
                        
                        try:
                            if pdf_url.lower().endswith(".pdf") or "pdf" in driver.current_url.lower():
                                pdf_content = None
                                
                                try:
                                    cookies = driver.get_cookies()
                                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                                    
                                    # Create a session with the same cookies
                                    session = requests.Session()
                                    for name, value in cookie_dict.items():
                                        session.cookies.set(name, value)
                                    
                                    # Add the same headers as the browser
                                    headers = {
                                        'User-Agent': driver.execute_script("return navigator.userAgent;"),
                                        'Referer': main_window
                                    }
                                    
                                    # Download the PDF
                                    response = session.get(pdf_url, headers=headers, stream=True, timeout=10)
                                    
                                    if response.status_code == 200:
                                        content_type = response.headers.get('Content-Type', '').lower()
                                        if 'pdf' in content_type or 'octet-stream' in content_type:
                                            pdf_content = response.content
                                            logger.info(f"Successfully downloaded PDF content using requests: {len(pdf_content)} bytes")
                                except Exception as req_e:
                                    logger.warning(f"Failed to download PDF using requests: {str(req_e)}")
                                
                                if pdf_content is None:
                                    try:
                                        iframe_elements = driver.find_elements(By.TAG_NAME, "iframe")
                                        if iframe_elements:
                                            for iframe in iframe_elements:
                                                iframe_src = iframe.get_attribute("src")
                                                if iframe_src and ("pdf" in iframe_src.lower()):
                                                    # Switch to iframe and try to get content
                                                    driver.switch_to.frame(iframe)
                                                    # Try to get PDF content from iframe source
                                                    iframe_url = driver.current_url
                                                    if iframe_url != pdf_url:
                                                        response = requests.get(iframe_url, stream=True)
                                                        if response.status_code == 200:
                                                            pdf_content = response.content
                                                            logger.info(f"Successfully downloaded PDF from iframe: {len(pdf_content)} bytes")
                                                    # Switch back to main content
                                                    driver.switch_to.default_content()
                                                    break
                                    except Exception as iframe_e:
                                        logger.warning(f"Failed to get PDF from iframe: {str(iframe_e)}")
                                        # Make sure we're back in the main content
                                        try:
                                            driver.switch_to.default_content()
                                        except:
                                            pass
                                
                                if pdf_content is None:
                                    try:
                                        js_result = driver.execute_script("""
                                            var pdfData = document.querySelector('embed[type="application/pdf"]');
                                            if (pdfData) {
                                                return pdfData.src;
                                            }
                                            return null;
                                        """)
                                        
                                        if js_result and js_result.startswith('data:application/pdf;base64,'):
                                            # Extract base64 data
                                            base64_data = js_result.replace('data:application/pdf;base64,', '')
                                            pdf_content = base64.b64decode(base64_data)
                                            logger.info(f"Successfully extracted PDF content using JavaScript: {len(pdf_content)} bytes")
                                    except Exception as js_e:
                                        logger.warning(f"Failed to get PDF using JavaScript: {str(js_e)}")
                                
                                if pdf_content:
                                    with open(pdf_path, 'wb') as f:
                                        f.write(pdf_content)
                                    logger.info(f"Successfully saved PDF to: {pdf_path}")
                                    pdfs_downloaded += 1
                                else:
                                    logger.warning(f"Could not extract PDF content from {pdf_url}")
                            else:
                                logger.warning(f"URL does not appear to be a PDF: {pdf_url}")
                        except Exception as e:
                            logger.error(f"Error downloading PDF: {str(e)}")
                    
                    driver.close()
                    driver.switch_to.window(main_window)
                    
                    # Add a small delay between downloads
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing 'List No. 2' button {i+1}: {str(e)}")
                    
                    if driver.current_window_handle != main_window:
                        try:
                            driver.close()
                            driver.switch_to.window(main_window)
                        except:
                            # If we can't close the tab, try to get back to the main window
                            if main_window in driver.window_handles:
                                driver.switch_to.window(main_window)
            
            logger.info(f"Successfully downloaded {pdfs_downloaded} PDFs")
            return pdfs_downloaded
            
        except Exception as e:
            logger.error(f"Error downloading PDFs: {str(e)}")
            return 0
    
    def _check_daily_limit(self):
        """Check if daily limit has been reached. Returns True if limit reached."""
        if self.daily_requests >= self.daily_limit:
            logger.info(f"Daily limit of {self.daily_limit} requests reached.")
            return True
        return False
    
    def _reset_session(self):
        """Reset session counters and update progress."""
        self.daily_requests = 0
        self.current_session_start = datetime.now()
        self.progress['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_progress()
    
    def process_combination(self, year, district, taluka, village, doc_number, driver=None):
        """
        Process a single combination of parameters.
        
        This method handles the actual scraping process for a specific combination of parameters.
        It fills in the form fields, handles captcha, and downloads any available PDFs.
        
        Args:
            year: The year to select
            district: The district to select
            taluka: The taluka to select
            village: The village to select
            doc_number: The document number to enter
            driver: The Selenium WebDriver instance
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        if driver is None:
            raise Exception("No driver provided for processing combination. Browser automation is required.")
        
        if self._check_daily_limit():
            logger.info("Daily limit reached. Stopping processing.")
            return False
        
        # Update current progress
        combination_key = f"{year}_{district}_{taluka}_{village}_{doc_number}"
        self.progress['current'] = {
            'year': year,
            'district': district,
            'taluka': taluka,
            'village': village,
            'doc_number': doc_number
        }
        
        self._save_progress()
        
        logger.info(f"Processing: Year={year}, District={district}, Taluka={taluka}, Village={village}, Doc#={doc_number}")
        
        try:
            # First fill in all the form fields
            self._select_dropdown_option(driver, "year", year)
            self._select_dropdown_option(driver, "district", district)
            self._select_dropdown_option(driver, "taluka", taluka)
            self._select_dropdown_option(driver, "village", village)
            
            try:
                doc_input_selectors = [
                    "//input[@id='doc_number']",
                    "//input[contains(@id, 'doc') or contains(@name, 'doc')]",
                    "//label[contains(text(), 'Doc') or contains(text(), 'Property') or contains(text(), 'Survey')]/following-sibling::input",
                    "//label[contains(text(), 'Doc') or contains(text(), 'Property') or contains(text(), 'Survey')]/..//input"
                ]
                
                doc_input = None
                for selector in doc_input_selectors:
                    try:
                        doc_input = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        if doc_input:
                            break
                    except:
                        continue
                
                if not doc_input:
                    inputs = driver.find_elements(By.TAG_NAME, "input")
                    for input_elem in inputs:
                        placeholder = input_elem.get_attribute("placeholder") or ""
                        label_text = ""
                        try:
                            label_id = input_elem.get_attribute("aria-labelledby") or input_elem.get_attribute("id")
                            if label_id:
                                label = driver.find_element(By.CSS_SELECTOR, f"label[for='{label_id}']")
                                label_text = label.text
                        except:
                            pass
                            
                        if "doc" in placeholder.lower() or "property" in placeholder.lower() or "survey" in placeholder.lower() or \
                           "doc" in label_text.lower() or "property" in label_text.lower() or "survey" in label_text.lower():
                            doc_input = input_elem
                            break
                
                if doc_input:
                    doc_input.clear()
                    doc_input.send_keys(str(doc_number))
                    logger.info(f"Entered document number: {doc_number}")
                else:
                    logger.error("Could not find document number input field")
                    return False
            except Exception as e:
                logger.error(f"Error entering document number: {str(e)}")
                return False
            
            # Then handle the captcha
            if not self._handle_captcha(driver):
                logger.error("Failed to handle captcha. Retrying...")
                if not self._handle_captcha(driver):
                    logger.error("Failed to handle captcha again. Skipping this combination.")
                    return False
            
            # Then click search
            try:
                search_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Search')] | //input[@type='submit' and @value='Search']"))
                )
                search_button.click()
                logger.info("Clicked search button")
            except Exception as search_error:
                logger.warning(f"Could not find search button by text: {str(search_error)}")
                try:
                    search_button = driver.find_element(By.CSS_SELECTOR, ".btn-primary, .search-btn, button.btn-blue")
                    search_button.click()
                    logger.info("Clicked search button by CSS class")
                except Exception as css_error:
                    logger.error(f"Could not find search button by CSS either: {str(css_error)}")
                    return False
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'record-details') or contains(@id, 'record')]"))
            )
            
            try:
                logger.info("Selecting 'All' entries per page from dropdown...")
                
                entries_dropdown = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//select[contains(@class, 'entries') or contains(@aria-label, 'entries')]"))
                )
                entries_dropdown.click()
                
                option = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//option[text()='All']"))
                )
                option.click()
                
                time.sleep(2)
                logger.info("Page refreshed with All entries per page")
            except Exception as e:
                logger.warning(f"Could not select entries per page: {str(e)}")
            
            downloaded = self._download_pdfs(driver)
            
            self.daily_requests += 1
            
            combination_key = f"{year}_{district}_{taluka}_{village}_{doc_number}"
            self.progress['completed'].append(combination_key)
            self._save_progress()
            
            logger.info(f"Successfully processed combination: {combination_key}")
            logger.info(f"Daily requests: {self.daily_requests}/{self.daily_limit}")
            
            delay = random.uniform(self.delay_between_requests[0], self.delay_between_requests[1])
            logger.info(f"Waiting {delay:.2f} seconds before next request...")
            time.sleep(delay)
            
            return True
        except Exception as e:
            logger.error(f"Error processing combination: {str(e)}")
            return False
    

    def _find_available_task(self):
        """
        Find a task that is not completed.
        
        This method looks for tasks that haven't been completed yet and returns the first one found.
        It requires a driver to get the actual dropdown options from the website.
        
        Returns:
            tuple: (year, district, taluka, village, doc_number) or None if no task is available
        """
        logger.info("Looking for available tasks...")
        
        # First, try to continue from where we left off
        if (self.progress['current']['year'] is not None and
            self.progress['current']['district'] is not None and
            self.progress['current']['taluka'] is not None and
            self.progress['current']['village'] is not None and
            self.progress['current']['doc_number'] is not None):
            
            year = self.progress['current']['year']
            district = self.progress['current']['district']
            taluka = self.progress['current']['taluka']
            village = self.progress['current']['village']
            doc_number = self.progress['current']['doc_number']
            
            combination_key = f"{year}_{district}_{taluka}_{village}_{doc_number}"
            
            if combination_key not in self.progress['completed']:
                logger.info(f"Continuing with previous task: {combination_key}")
                return (year, district, taluka, village, doc_number)
        
        # If we can't continue from where we left off, we need a driver to get the dropdown options
        # This will be handled in the run method where we have a driver available
        logger.info("No current task to continue. Need to get dropdown options from website.")
        return None
    
    
    def run(self):
        """
        Run the scraper.
        
        This method is the main entry point for the scraper. It sets up the browser,
        navigates to the website, and processes multiple combinations of parameters
        to scrape property data.
        """
        logger.info("Starting property scraper...")
        logger.info(f"Instance ID: {self.instance_id}")
        
        # Create debug directories
        os.makedirs("captcha_debug", exist_ok=True)
        os.makedirs("dropdown_debug", exist_ok=True)
        
        # First, try to load the latest progress from cloud storage
        if self.use_cloud_storage:
            try:
                if self.cloud_storage_type == 's3':
                    latest_progress = self._load_progress_from_s3()
                elif self.cloud_storage_type == 'github':
                    latest_progress = self._load_progress_from_github()
                else:
                    latest_progress = None
                    
                if latest_progress:
                    # Merge completed tasks
                    for task in latest_progress['completed']:
                        if task not in self.progress['completed']:
                            self.progress['completed'].append(task)
                    logger.info("Successfully loaded and merged latest progress from cloud storage")
            except Exception as e:
                logger.warning(f"Could not load latest progress from cloud storage: {str(e)}")
        
        # Try to set up the driver
        driver = self._setup_driver()
        
        # If driver setup failed, raise an exception
        if driver is None:
            raise Exception("Browser automation failed. Chrome WebDriver could not be initialized.")
            
        try:
            # Set a longer page load timeout
            driver.set_page_load_timeout(30)
            
            # Navigate to the base URL
            logger.info(f"Navigating to {self.base_url}")
            driver.get(self.base_url)
            
            # Wait for the page to fully load
            time.sleep(5)
            
            # Maximize window to ensure all elements are visible
            driver.maximize_window()
            
            # Take initial screenshot for debugging
            try:
                screenshot_path = f"captcha_debug/initial_page_{int(time.time())}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Saved initial page screenshot to {screenshot_path}")
            except Exception as ss_error:
                logger.warning(f"Could not save initial screenshot: {str(ss_error)}")
            
            # Number of combinations to process
            num_combinations = 10
            processed_count = 0
            attempts = 0
            max_attempts = 20  # Maximum number of attempts to find available tasks
            
            while processed_count < num_combinations and attempts < max_attempts:
                if self._check_daily_limit():
                    logger.info("Daily limit reached. Exiting.")
                    driver.quit()
                    return
                
                # Navigate to the main page for each new combination
                driver.get(self.base_url)
                
                # Find an available task that's not completed
                available_task = self._find_available_task()
                
                if available_task is None:
                    # If no task is available, get dropdown options from the website
                    logger.info("No available tasks found. Getting dropdown options from website...")
                    
                    # Take a screenshot before starting dropdown interactions
                    try:
                        screenshot_path = f"dropdown_debug/before_dropdowns_{int(time.time())}.png"
                        driver.save_screenshot(screenshot_path)
                        logger.info(f"Saved screenshot before dropdown interactions: {screenshot_path}")
                    except Exception as ss_error:
                        logger.warning(f"Could not save screenshot: {str(ss_error)}")
                    
                    # First, we need to select a year
                    try:
                        # Find the year dropdown
                        year_dropdown_selectors = [
                            "//select[@id='year']",
                            "//select[contains(@id, 'year') or contains(@name, 'year')]",
                            "//label[contains(text(), 'Year')]/following-sibling::select",
                            "//label[contains(text(), 'Year')]/..//select"
                        ]
                        
                        year_dropdown = None
                        for selector in year_dropdown_selectors:
                            try:
                                year_dropdown = WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                if year_dropdown:
                                    break
                            except:
                                continue
                        
                        if not year_dropdown:
                            logger.error("Could not find year dropdown")
                            attempts += 1
                            continue
                        
                        # Get the year options
                        select = Select(year_dropdown)
                        years = [option.text for option in select.options if option.text.strip() and not option.text.startswith("--Select")]
                        
                        if not years:
                            logger.error("No year options found")
                            attempts += 1
                            continue
                        
                        # Select a year
                        year = random.choice(years)
                        logger.info(f"Selected Year: {year}")
                        
                        # Click on the year dropdown and select the option
                        year_dropdown.click()
                        time.sleep(1)
                        
                        # Find and click on the option
                        year_option = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//option[text()='{year}']"))
                        )
                        year_option.click()
                        
                        # Wait for the selection to take effect
                        time.sleep(2)
                        
                        # Take a screenshot after year selection
                        try:
                            screenshot_path = f"dropdown_debug/after_year_{int(time.time())}.png"
                            driver.save_screenshot(screenshot_path)
                            logger.info(f"Saved screenshot after year selection: {screenshot_path}")
                        except Exception as ss_error:
                            logger.warning(f"Could not save screenshot: {str(ss_error)}")
                        
                        # Now that we've selected a year, the district dropdown should be populated
                        # Find the district dropdown
                        district_dropdown_selectors = [
                            "//select[@id='district']",
                            "//select[contains(@id, 'district') or contains(@name, 'district')]",
                            "//label[contains(text(), 'District')]/following-sibling::select",
                            "//label[contains(text(), 'District')]/..//select"
                        ]
                        
                        district_dropdown = None
                        for selector in district_dropdown_selectors:
                            try:
                                district_dropdown = WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                if district_dropdown:
                                    break
                            except:
                                continue
                        
                        if not district_dropdown:
                            logger.error("Could not find district dropdown")
                            attempts += 1
                            continue
                        
                        # Get the district options
                        select = Select(district_dropdown)
                        districts = [option.text for option in select.options if option.text.strip() and not option.text.startswith("--Select")]
                        
                        if not districts:
                            logger.error("No district options found")
                            attempts += 1
                            continue
                        
                        # Always select 'मुंबई' (Mumbai) as the district
                        district = 'मुंबई'
                        # If 'मुंबई' is not in the list, fall back to a random choice
                        if district not in districts:
                            logger.warning(f"District '{district}' not found in options. Available districts: {districts}")
                            district = random.choice(districts)
                        logger.info(f"Selected District: {district}")
                        
                        # Click on the district dropdown and select the option
                        district_dropdown.click()
                        time.sleep(1)
                        
                        # Find and click on the option
                        district_option = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//option[text()='{district}']"))
                        )
                        district_option.click()
                        
                        # Wait for the selection to take effect
                        time.sleep(2)
                        
                        # Take a screenshot after district selection
                        try:
                            screenshot_path = f"dropdown_debug/after_district_{int(time.time())}.png"
                            driver.save_screenshot(screenshot_path)
                            logger.info(f"Saved screenshot after district selection: {screenshot_path}")
                        except Exception as ss_error:
                            logger.warning(f"Could not save screenshot: {str(ss_error)}")
                        
                        # Now that we've selected a district, the taluka dropdown should be populated
                        # Find the taluka dropdown
                        taluka_dropdown_selectors = [
                            "//select[@id='taluka']",
                            "//select[contains(@id, 'taluka') or contains(@name, 'taluka')]",
                            "//label[contains(text(), 'Taluka')]/following-sibling::select",
                            "//label[contains(text(), 'Taluka')]/..//select"
                        ]
                        
                        taluka_dropdown = None
                        for selector in taluka_dropdown_selectors:
                            try:
                                taluka_dropdown = WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                if taluka_dropdown:
                                    break
                            except:
                                continue
                        
                        if not taluka_dropdown:
                            logger.error("Could not find taluka dropdown")
                            attempts += 1
                            continue
                        
                        # Get the taluka options
                        select = Select(taluka_dropdown)
                        talukas = [option.text for option in select.options if option.text.strip() and not option.text.startswith("--Select")]
                        
                        if not talukas:
                            logger.error("No taluka options found")
                            attempts += 1
                            continue
                        
                        # Select a taluka
                        taluka = random.choice(talukas)
                        logger.info(f"Selected Taluka: {taluka}")
                        
                        # Click on the taluka dropdown and select the option
                        taluka_dropdown.click()
                        time.sleep(1)
                        
                        # Find and click on the option
                        taluka_option = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//option[text()='{taluka}']"))
                        )
                        taluka_option.click()
                        
                        # Wait for the selection to take effect
                        time.sleep(2)
                        
                        # Take a screenshot after taluka selection
                        try:
                            screenshot_path = f"dropdown_debug/after_taluka_{int(time.time())}.png"
                            driver.save_screenshot(screenshot_path)
                            logger.info(f"Saved screenshot after taluka selection: {screenshot_path}")
                        except Exception as ss_error:
                            logger.warning(f"Could not save screenshot: {str(ss_error)}")
                        
                        # Now that we've selected a taluka, the village dropdown should be populated
                        # Find the village dropdown
                        village_dropdown_selectors = [
                            "//select[@id='village']",
                            "//select[contains(@id, 'village') or contains(@name, 'village')]",
                            "//label[contains(text(), 'Village')]/following-sibling::select",
                            "//label[contains(text(), 'Village')]/..//select"
                        ]
                        
                        village_dropdown = None
                        for selector in village_dropdown_selectors:
                            try:
                                village_dropdown = WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                if village_dropdown:
                                    break
                            except:
                                continue
                        
                        if not village_dropdown:
                            logger.error("Could not find village dropdown")
                            attempts += 1
                            continue
                        
                        # Get the village options
                        select = Select(village_dropdown)
                        villages = [option.text for option in select.options if option.text.strip() and not option.text.startswith("--Select")]
                        
                        if not villages:
                            logger.error("No village options found")
                            attempts += 1
                            continue
                        
                        # Select a village
                        village = random.choice(villages)
                        logger.info(f"Selected Village: {village}")
                        
                        # Click on the village dropdown and select the option
                        village_dropdown.click()
                        time.sleep(1)
                        
                        # Find and click on the option
                        village_option = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//option[text()='{village}']"))
                        )
                        village_option.click()
                        
                        # Wait for the selection to take effect
                        time.sleep(2)
                        
                        # Take a screenshot after village selection
                        try:
                            screenshot_path = f"dropdown_debug/after_village_{int(time.time())}.png"
                            driver.save_screenshot(screenshot_path)
                            logger.info(f"Saved screenshot after village selection: {screenshot_path}")
                        except Exception as ss_error:
                            logger.warning(f"Could not save screenshot: {str(ss_error)}")
                        
                        # Generate a random document number (0-9)
                        doc_number = random.randint(0, 9)
                        
                        # Check if this combination has already been processed or is being worked on
                        combination_key = f"{year}_{district}_{taluka}_{village}_{doc_number}"
                        if combination_key in self.progress['completed']:
                            logger.info(f"Skipping combination {combination_key} as it's already completed.")
                            attempts += 1
                            continue
                            
                    except Exception as e:
                        logger.error(f"Error selecting dropdown options: {str(e)}")
                        attempts += 1
                        continue
                else:
                    # Use the available task
                    year, district, taluka, village, doc_number = available_task
                    combination_key = f"{year}_{district}_{taluka}_{village}_{doc_number}"
                    logger.info(f"Found available task: {combination_key}")
                    
                    # Fill in the form with the available task parameters
                    self._select_dropdown_option(driver, "year", year)
                    time.sleep(1)
                    self._select_dropdown_option(driver, "district", district)
                    time.sleep(1)
                    self._select_dropdown_option(driver, "taluka", taluka)
                    time.sleep(1)
                    self._select_dropdown_option(driver, "village", village)
                    time.sleep(1)
                    
                    # Enter document number in the field
                    try:
                        doc_input_selectors = [
                            "//input[@id='doc_number']",
                            "//input[contains(@id, 'doc') or contains(@name, 'doc')]",
                            "//label[contains(text(), 'Doc') or contains(text(), 'Property') or contains(text(), 'Survey')]/following-sibling::input",
                            "//label[contains(text(), 'Doc') or contains(text(), 'Property') or contains(text(), 'Survey')]/..//input"
                        ]
                        
                        doc_input = None
                        for selector in doc_input_selectors:
                            try:
                                doc_input = WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                if doc_input:
                                    break
                            except:
                                continue
                        
                        if doc_input:
                            doc_input.clear()
                            doc_input.send_keys(str(doc_number))
                            logger.info(f"Entered document number: {doc_number}")
                        else:
                            logger.error("Could not find document number input field")
                            attempts += 1
                            continue
                    except Exception as e:
                        logger.error(f"Error entering document number: {str(e)}")
                        attempts += 1
                        continue
                
                # Update current progress
                self.progress['current'] = {
                    'year': year,
                    'district': district,
                    'taluka': taluka,
                    'village': village,
                    'doc_number': doc_number
                }
                
                self._save_progress()
                
                logger.info(f"Processing combination: {combination_key}")
                success = self.process_combination(year, district, taluka, village, doc_number, driver)
                
                if not success:
                    # If we hit the daily limit, exit
                    if self._check_daily_limit():
                        logger.info("Daily limit reached. Exiting.")
                        driver.quit()
                        return
                    
                    # Otherwise, retry with a new session
                    logger.info("Retrying with a new session...")
                    self._reset_session()
                    success = self.process_combination(year, district, taluka, village, doc_number, driver)
                    
                    if not success:
                        logger.error(f"Failed to process combination {combination_key} after retry. Skipping.")
                
                if success:
                    processed_count += 1
                
                attempts += 1
            
            if processed_count < num_combinations:
                logger.warning(f"Could only process {processed_count} combinations after {attempts} attempts")
        
        except Exception as e:
            logger.error(f"Error in main run loop: {str(e)}")
            raise Exception(f"Browser automation failed: {str(e)}")
        finally:
            try:
                driver.quit()
            except Exception:
                pass
            
        logger.info("Property scraper completed.")

if __name__ == "__main__":
    # Create directories if they don't exist
    os.makedirs('logs', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)
    
    # Configure logging with UTF-8 encoding
    import io
    import sys
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Property Scraper')
    args = parser.parse_args()
    
    # Create a UTF-8 encoded stream for console output
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    # Configure logging
    log_file = os.path.join('logs', f'scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(utf8_stdout)
        ]
    )
    
    # Run the scraper
    scraper = PropertyScraper()
    
    logger.info("Running property scraper")
    scraper.run()
