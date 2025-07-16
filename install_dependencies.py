#!/usr/bin/env python3
"""
Installation script for property scraper dependencies.
This script installs dependencies one by one with error handling and helpful messages.
"""

import subprocess
import sys
import os
import platform

def print_step(message):
    """Print a step message with formatting."""
    print("\n" + "="*80)
    print(f"  {message}")
    print("="*80)

def run_command(command):
    """Run a command and return the result."""
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def install_package(package):
    """Install a package using pip."""
    print(f"Installing {package}...")
    success, output = run_command([sys.executable, "-m", "pip", "install", package])
    
    if success:
        print(f"✅ Successfully installed {package}")
        return True
    else:
        print(f"❌ Failed to install {package}")
        print(f"Error: {output}")
        return False

def check_system_dependencies():
    """Check for required system dependencies."""
    print_step("Checking system dependencies")
    
    system = platform.system()
    
    if system == "Linux":
        # Check for build essentials on Linux
        print("Checking for build-essential...")
        success, _ = run_command(["dpkg", "-s", "build-essential"])
        if not success:
            print("⚠️  build-essential not found. This may be needed for some packages.")
            print("   Try: sudo apt-get install build-essential python3-dev")
        
        # Check for tesseract on Linux
        print("Checking for tesseract-ocr...")
        success, _ = run_command(["which", "tesseract"])
        if not success:
            print("⚠️  tesseract-ocr not found. This is needed for OCR capabilities.")
            print("   Try: sudo apt-get install tesseract-ocr")
    
    elif system == "Windows":
        # Check for tesseract on Windows
        print("Checking for Tesseract OCR...")
        tesseract_path = os.environ.get("TESSERACT_PATH")
        if not tesseract_path or not os.path.exists(tesseract_path):
            print("⚠️  Tesseract OCR not found in TESSERACT_PATH environment variable.")
            print("   Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            print("   Then set TESSERACT_PATH environment variable to the installation directory.")
    
    elif system == "Darwin":  # macOS
        # Check for tesseract on macOS
        print("Checking for tesseract...")
        success, _ = run_command(["which", "tesseract"])
        if not success:
            print("⚠️  tesseract not found. This is needed for OCR capabilities.")
            print("   Try: brew install tesseract")

def install_dependencies():
    """Install all dependencies from requirements.txt with error handling."""
    print_step("Installing dependencies")
    
    # Upgrade pip first
    print("Upgrading pip...")
    run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Read requirements file
    with open("requirements.txt", "r") as f:
        requirements = f.readlines()
    
    # Filter out comments and empty lines
    packages = []
    for line in requirements:
        line = line.strip()
        if line and not line.startswith("#"):
            packages.append(line)
    
    # Install core dependencies first
    core_deps = [
        "requests",
        "beautifulsoup4",
        "selenium",
        "webdriver-manager",
        "python-dotenv",
        "pillow",
        "schedule",
        "boto3"
    ]
    
    print("Installing core dependencies...")
    for package in core_deps:
        matching_packages = [p for p in packages if p.startswith(package)]
        if matching_packages:
            if not install_package(matching_packages[0]):
                print(f"⚠️  Failed to install core dependency: {matching_packages[0]}")
                print("   This may affect the functionality of the scraper.")
    
    # Install potentially problematic packages with alternatives
    problematic_packages = {
        "opencv-python": "opencv-python-headless",
        "pytesseract": None,  # No direct alternative
        "lxml": None,  # No direct alternative
        "undetected-chromedriver": None,  # No direct alternative
        "numpy": "numpy==1.21.6"  # Try an older version that has pre-built wheels
    }
    
    print("\nInstalling potentially problematic packages...")
    for package, alternative in problematic_packages.items():
        matching_packages = [p for p in packages if p.startswith(package)]
        if matching_packages:
            # Special handling for numpy
            if package == "numpy":
                print(f"Installing {package} (with special handling)...")
                # Try installing numpy without version constraint first
                if not install_package("numpy"):
                    print("Trying numpy with specific version...")
                    if not install_package("numpy==1.21.6"):
                        print("Trying numpy with older version...")
                        if not install_package("numpy==1.19.5"):
                            print(f"⚠️  Failed to install numpy after multiple attempts.")
                            print("   This may affect numerical processing functionality.")
                            print("   You may need to install numpy manually or install system dependencies:")
                            if platform.system() == "Linux":
                                print("   sudo apt-get install python3-numpy")
                            elif platform.system() == "Windows":
                                print("   Try installing a pre-built wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#numpy")
            else:
                # Normal handling for other packages
                if not install_package(matching_packages[0]) and alternative:
                    print(f"Trying alternative: {alternative}...")
                    if not install_package(alternative):
                        print(f"⚠️  Failed to install both {package} and its alternative.")
                        print("   This may affect some functionality of the scraper.")
    
    # Install remaining packages
    print("\nInstalling remaining packages...")
    remaining = [p for p in packages if not any(p.startswith(core) for core in core_deps) and 
                                       not any(p.startswith(prob) for prob in problematic_packages)]
    
    for package in remaining:
        if not install_package(package):
            print(f"⚠️  Failed to install: {package}")
            print("   This may affect some functionality of the scraper.")

def main():
    """Main function."""
    print_step("Property Scraper Dependency Installer")
    print("This script will install all required dependencies for the property scraper.")
    
    # Check system dependencies
    check_system_dependencies()
    
    # Install Python dependencies
    install_dependencies()
    
    print_step("Installation Complete")
    print("If there were any errors, please check the troubleshooting section in README.md")
    print("You may need to install some system dependencies manually.")

if __name__ == "__main__":
    main()