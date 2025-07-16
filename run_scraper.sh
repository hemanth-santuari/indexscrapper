#!/bin/bash

echo "Starting Maharashtra Property Document Scraper..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.7+ and try again."
    exit 1
fi

# Check if requirements are installed
echo "Checking and installing requirements..."
python3 -m pip install -r requirements.txt

# Create directories if they don't exist
mkdir -p logs downloads

echo
echo "Choose an option:"
echo "1. Run scraper once"
echo "2. Run scheduler (continuous mode)"
echo "3. Exit"
echo

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        echo "Running scraper once..."
        python3 property_scraper.py
        ;;
    2)
        echo "Running scheduler in continuous mode..."
        echo "Press Ctrl+C to stop the scheduler."
        python3 scheduler.py
        ;;
    3)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice. Please try again."
        exit 1
        ;;
esac

echo "Press Enter to exit..."
read