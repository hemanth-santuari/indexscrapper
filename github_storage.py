import requests
import json
import base64
import logging

logger = logging.getLogger('property_scraper')

class GitHubStorage:
    def __init__(self, repository, token):
        """
        Initialize GitHub storage client.
        
        Args:
            repository: GitHub repository in format 'username/repo-name'
            token: GitHub personal access token with repo scope
        """
        self.repository = repository
        self.token = token
        self.api_url = f"https://api.github.com/repos/{repository}/contents"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        logger.info(f"Initialized GitHub storage for repository: {repository}")
    
    def get_file(self, path):
        """
        Get file content from GitHub repository.
        
        Args:
            path: Path to the file in the repository
            
        Returns:
            tuple: (file_content as dict, file_sha for updates)
        """
        logger.info(f"Getting file from GitHub: {path}")
        try:
            response = requests.get(f"{self.api_url}/{path}", headers=self.headers)
            if response.status_code == 200:
                content = response.json()
                file_content = base64.b64decode(content['content']).decode('utf-8')
                logger.info(f"Successfully retrieved file from GitHub: {path}")
                return json.loads(file_content), content['sha']
            elif response.status_code == 404:
                logger.warning(f"File not found in GitHub repository: {path}")
                return None, None
            else:
                logger.error(f"Error getting file from GitHub: {response.status_code} - {response.text}")
                return None, None
        except Exception as e:
            logger.error(f"Exception getting file from GitHub: {str(e)}")
            return None, None
    
    def update_file(self, path, content, sha=None):
        """
        Update or create a file in GitHub repository.
        
        Args:
            path: Path to the file in the repository
            content: Content to write (will be converted to JSON)
            sha: SHA of the file if it exists (required for updates)
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Updating file in GitHub: {path}")
        try:
            data = {
                "message": "Update progress file",
                "content": base64.b64encode(json.dumps(content, indent=4).encode('utf-8')).decode('utf-8')
            }
            
            # If sha is provided, it's an update; otherwise, it's a create
            if sha:
                data["sha"] = sha
            
            response = requests.put(f"{self.api_url}/{path}", headers=self.headers, json=data)
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully updated file in GitHub: {path}")
                return True, response.json().get('content', {}).get('sha')
            else:
                logger.error(f"Error updating file in GitHub: {response.status_code} - {response.text}")
                return False, None
        except Exception as e:
            logger.error(f"Exception updating file in GitHub: {str(e)}")
            return False, None
    
    def merge_progress_files(self, local_progress, remote_progress):
        """
        Merge local and remote progress files to prevent conflicts.
        
        Args:
            local_progress: Local progress data
            remote_progress: Remote progress data from GitHub
            
        Returns:
            dict: Merged progress data
        """
        if not remote_progress:
            return local_progress
            
        # Create a new merged progress
        merged_progress = remote_progress.copy()
        
        # Merge completed tasks
        if 'completed' in local_progress:
            if 'completed' not in merged_progress:
                merged_progress['completed'] = []
                
            for task in local_progress['completed']:
                if task not in merged_progress['completed']:
                    merged_progress['completed'].append(task)
        
        # Merge VM tasks
        if 'vm_tasks' in local_progress:
            if 'vm_tasks' not in merged_progress:
                merged_progress['vm_tasks'] = {}
                
            for vm_id, vm_info in local_progress['vm_tasks'].items():
                merged_progress['vm_tasks'][vm_id] = vm_info
        
        logger.info(f"Merged progress files: {len(merged_progress.get('completed', []))} completed tasks")
        return merged_progress