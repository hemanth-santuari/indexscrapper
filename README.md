# Property Scraper with Distributed Task Management

This property scraper is designed to work across multiple virtual machines (VMs), with each VM picking up where the previous one left off. This allows for efficient distributed scraping without duplicating work.

## Features

- Automatic proxy fetching from free proxy websites
- Captcha solving using OCR or manual input
- Distributed task management across multiple VMs
- Cloud storage integration (AWS S3) for progress tracking
- VM activity timeout detection
- Race condition prevention

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
   
   If you encounter installation issues, try using the provided installation script:
   ```
   python install_dependencies.py
   ```
   This script installs dependencies one by one with error handling and provides helpful troubleshooting messages.

2. Configure AWS S3 for distributed scraping:
   - Open `config.json`
   - Set `use_cloud_storage` to `true`
   - Configure the S3 bucket and credentials:
     ```json
     "cloud_storage_config": {
         "bucket_name": "your-bucket-name",
         "progress_key": "progress.json",
         "aws_access_key_id": "YOUR_ACCESS_KEY",
         "aws_secret_access_key": "YOUR_SECRET_KEY",
         "region_name": "us-east-1"
     }
     ```

3. Create an S3 bucket in your AWS account with the name specified in the config.

## How It Works

### VM Identification

Each VM generates a unique ID using its hostname and a random UUID. This ID is used to track which VM is working on which task.

```python
self.vm_id = f"{socket.gethostname()}_{uuid.uuid4().hex[:8]}"
```

### Task Management

1. When a VM starts, it first checks if there are any available tasks that aren't completed or being worked on by other VMs.
2. If a task is available, the VM marks it as being worked on by updating the `vm_tasks` field in the progress file.
3. After completing a task, the VM marks it as completed in the `completed` field.
4. The progress file is synchronized with S3 to ensure all VMs have the latest information.

### Timeout Detection

If a VM becomes inactive (no updates for 30 minutes), other VMs can take over its tasks. This prevents tasks from being stuck if a VM crashes or loses connection.

## Running the Scraper

To run the scraper on multiple VMs:

1. Set up each VM with the same configuration (same S3 bucket and credentials).
2. Run the scraper on each VM:
   ```
   python property_scraper.py
   ```

Each VM will automatically coordinate with others through the shared progress file in S3.

## Monitoring

You can monitor the progress by:

1. Checking the logs in the `logs` directory on each VM.
2. Examining the progress.json file in your S3 bucket, which contains:
   - Completed tasks
   - Current tasks for each VM
   - Last activity timestamp for each VM

## Troubleshooting

### Task Processing Issues
- If a VM consistently fails to process a task, it will skip that task and move on to the next available one.
- If all VMs are inactive for more than 30 minutes, their tasks will be considered available for processing when a VM becomes active again.
- If you need to reset the progress, delete the progress.json file from your S3 bucket.

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

- For AWS S3 integration, make sure your AWS credentials are properly configured:
  - Update the credentials in `config.json`
  - Or set up AWS CLI configuration: `aws configure`

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
