import os
import glob
import logging
import json
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('cleanup_temp_images')

def cleanup_temp_images():
    """Clean up all temporary cropped and preprocessed images."""
    patterns = [
        "crop_*_after_district_*.png",
        "cropped_after_district_*.png",
        "preprocess_*_after_district_*.png"
    ]
    
    total_removed = 0
    
    for pattern in patterns:
        files = glob.glob(pattern)
        for file in files:
            try:
                os.remove(file)
                logger.info(f"Removed: {file}")
                total_removed += 1
            except Exception as e:
                logger.error(f"Error removing {file}: {str(e)}")
    
    logger.info(f"Total files removed: {total_removed}")

def cleanup_all_screenshots():
    """Clean up all screenshot directories."""
    directories = [
        "captcha_debug",
        "captcha_extracts",
        "dropdown_debug"
    ]
    
    total_removed = 0
    
    for directory in directories:
        if os.path.exists(directory):
            try:
                # Count files before removal
                file_count = len([name for name in os.listdir(directory) if os.path.isfile(os.path.join(directory, name))])
                
                # Remove all files in the directory
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                
                logger.info(f"Cleared {file_count} files from {directory}/")
                total_removed += file_count
            except Exception as e:
                logger.error(f"Error clearing directory {directory}: {str(e)}")
        else:
            # Create the directory if it doesn't exist
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}/")
    
    logger.info(f"Total screenshot files removed: {total_removed}")

def reset_progress_file():
    """Reset progress.json to initial state."""
    progress_file = "progress.json"
    
    # Default initial progress state
    initial_progress = {
        "last_run": None,
        "completed": [],
        "current": {
            "year": None,
            "district": None,
            "taluka": None,
            "village": None,
            "doc_number": None
        }
    }
    
    try:
        # Create a backup of the current progress file
        if os.path.exists(progress_file):
            backup_file = f"{progress_file}.bak"
            shutil.copy2(progress_file, backup_file)
            logger.info(f"Created backup of progress file: {backup_file}")
            
            # Write the initial progress state
            with open(progress_file, 'w') as f:
                json.dump(initial_progress, f, indent=4)
            logger.info(f"Reset {progress_file} to initial state")
        else:
            # Create a new progress file with initial state
            with open(progress_file, 'w') as f:
                json.dump(initial_progress, f, indent=4)
            logger.info(f"Created new {progress_file} with initial state")
    except Exception as e:
        logger.error(f"Error resetting progress file: {str(e)}")

if __name__ == "__main__":
    print("=" * 50)
    print("Cleaning up all temporary files and resetting progress")
    print("=" * 50)
    
    # Clean up temporary images
    cleanup_temp_images()
    
    # Clean up all screenshot directories
    cleanup_all_screenshots()
    
    # Reset progress file
    reset_progress_file()
    
    print("=" * 50)
    print("Cleanup completed")
    print("=" * 50)