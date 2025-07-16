# Property Scraper

This property scraper is designed to scrape property details from a government website. It can be run locally or in GitHub Codespaces.

## Features

- Automatic proxy fetching from free proxy websites
- Captcha solving using OCR or manual input
- Progress tracking to resume from where you left off
- Optional cloud storage integration (GitHub or AWS S3) for progress tracking
- PDF downloading and processing

## Setup

### Local Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
   
   If you encounter installation issues, try using the provided installation script:
   ```
   python install_dependencies.py
   ```
   This script installs dependencies one by one with error handling and provides helpful troubleshooting messages.

2. Configure the scraper:
   - Open `config.json`
   - Set `use_cloud_storage` to `false` for local-only operation
   - Or configure GitHub storage for cloud synchronization:
     ```json
     "use_cloud_storage": true,
     "cloud_storage_type": "github",
     "cloud_storage_config": {
         "repository": "your-username/your-repo",
         "token": "your-github-token",
         "progress_key": "progress.json"
     }
     ```

### GitHub Codespaces Setup

1. Create a new GitHub Codespace from your repository
2. The Codespace will automatically install dependencies when it starts
3. If needed, run the installation script to ensure all dependencies are properly installed:
   ```
   python install_dependencies.py
   ```
4. Configure the scraper as described in the local setup section

## How It Works

### Instance Identification

Each instance of the scraper generates a unique ID. This ID is used for logging and tracking purposes.

```python
self.instance_id = f"local_{uuid.uuid4().hex[:8]}"
```

### Task Management

1. The scraper checks if there are any available tasks that aren't completed.
2. If a task is available, the scraper processes it and marks it as completed.
3. The progress is saved to a local file and optionally synchronized with cloud storage.

## Running the Scraper

### Standard Mode

Run the scraper with real browser automation:

```
python property_scraper.py
```

### Demo Mode

Run the scraper in demo mode (simulates the scraping process without making real requests):

```
# Add this to your code to run in demo mode
if __name__ == "__main__":
    scraper = PropertyScraper()
    scraper.run_demo_mode()
```

## Monitoring

You can monitor the progress by:

1. Checking the logs in the `logs` directory.
2. Examining the progress.json file, which contains:
   - Completed tasks
   - Current task being processed

## Troubleshooting

### Task Processing Issues
- If the scraper consistently fails to process a task, it will skip that task and move on to the next available one.
- If you need to reset the progress, delete the progress.json file.
- If you're using cloud storage, make sure your credentials are correct and the repository/bucket exists.

### Installation Issues
- If you encounter build errors during installation, try installing the packages one by one to identify which one is causing the issue.
- Some packages require additional system dependencies:
  - `pytesseract` requires tesseract-ocr to be installed on the system:
    - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
    - Windows: Download and install from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
  - `opencv-python` may cause build issues. Try using `opencv-python-headless` instead by editing requirements.txt.
  - `lxml` and other packages with C extensions may require build tools:
    - Ubuntu/Debian: `sudo apt-get install build-essential python3-dev`
    - Windows: Install Visual C++ Build Tools

- For GitHub integration, make sure your token has the necessary permissions:
  - It needs `repo` scope to read and write to repositories
  - Generate a token at GitHub Settings > Developer settings > Personal access tokens

### Numpy Installation Issues

If you encounter issues installing numpy (which is common due to its C extensions), try these solutions:

1. Use the installation script which will try multiple numpy versions:
   ```
   python install_dependencies.py
   ```

2. Try installing numpy separately before other dependencies:
   ```
   pip install numpy==1.21.6
   pip install -r requirements.txt
   ```

3. On Windows, you can download pre-built wheels from:
   https://www.lfd.uci.edu/~gohlke/pythonlibs/#numpy

4. On Linux, you can install the system package:
   ```
   sudo apt-get install python3-numpy
   ```

5. Make sure you have the necessary build tools installed:
   - Windows: Install Visual C++ Build Tools
   - Linux: `sudo apt-get install build-essential python3-dev`

### GitHub Codespaces Specific Issues

- If you encounter browser automation issues in Codespaces, make sure to use the headless mode for Chrome.
- For file permission issues, you may need to run `chmod +x install_dependencies.py` before executing the script.
- If you're having trouble with the browser in Codespaces, try using the demo mode which doesn't require a real browser.
