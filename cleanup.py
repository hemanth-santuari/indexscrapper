import os
import shutil

def cleanup():
    """Clean up all cache and temporary data."""
    print("Cleaning up cache and temporary data...")
    
    # Directories to clean
    dirs_to_clean = [
        "captcha_debug",
        "dropdown_debug",
        "logs",
        "downloads",
        "__pycache__"
    ]
    
    # Files to remove
    files_to_remove = [
        "geckodriver.log"
    ]
    
    # Clean directories
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"Removed directory: {dir_name}")
                # Recreate empty directory
                os.makedirs(dir_name, exist_ok=True)
                print(f"Recreated empty directory: {dir_name}")
            except Exception as e:
                print(f"Error removing directory {dir_name}: {str(e)}")
    
    # Remove files
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
                print(f"Removed file: {file_name}")
            except Exception as e:
                print(f"Error removing file {file_name}: {str(e)}")
    
    # Remove .pyc files
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".pyc"):
                try:
                    os.remove(os.path.join(root, file))
                    print(f"Removed .pyc file: {os.path.join(root, file)}")
                except Exception as e:
                    print(f"Error removing .pyc file {os.path.join(root, file)}: {str(e)}")
    
    print("Cleanup completed!")

if __name__ == "__main__":
    cleanup()