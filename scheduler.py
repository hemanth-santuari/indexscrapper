import os
import sys
import time
import json
import random
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
import schedule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('logs', f'scheduler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('scheduler')

class ScraperScheduler:
    def __init__(self, config_path='scheduler_config.json'):
        """Initialize the scheduler with configuration."""
        self.config_path = config_path
        self.load_config()
        
        # Create directories if they don't exist
        os.makedirs('logs', exist_ok=True)
        os.makedirs('downloads', exist_ok=True)
        
    def load_config(self):
        """Load configuration from file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        else:
            # Default configuration
            self.config = {
                "schedules": [
                    {"time": "08:00", "proxy_index": 0, "user_agent_index": 0},
                    {"time": "12:00", "proxy_index": 1, "user_agent_index": 1},
                    {"time": "16:00", "proxy_index": 2, "user_agent_index": 2},
                    {"time": "20:00", "proxy_index": 0, "user_agent_index": 3},
                    {"time": "00:00", "proxy_index": 1, "user_agent_index": 4}
                ],
                "random_delay_minutes": [0, 30],  # Random delay between 0-30 minutes
                "max_runtime_minutes": 60,  # Maximum runtime for each session
                "python_executable": "python"
            }
            self.save_config()
    
    def save_config(self):
        """Save configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def run_scraper(self, proxy_index, user_agent_index):
        """Run the scraper with specific proxy and user agent."""
        try:
            # Load the main config
            with open('config.json', 'r') as f:
                main_config = json.load(f)
            
            # Create a temporary config with selected proxy and user agent
            temp_config = main_config.copy()
            
            if proxy_index is not None and main_config.get('proxies') and len(main_config['proxies']) > proxy_index:
                temp_config['proxies'] = [main_config['proxies'][proxy_index]]
            
            if user_agent_index is not None and main_config.get('user_agents') and len(main_config['user_agents']) > user_agent_index:
                temp_config['user_agents'] = [main_config['user_agents'][user_agent_index]]
            
            # Write temporary config
            temp_config_path = 'temp_config.json'
            with open(temp_config_path, 'w') as f:
                json.dump(temp_config, f, indent=4)
            
            # Run the scraper with the temporary config
            logger.info(f"Starting scraper with proxy index {proxy_index} and user agent index {user_agent_index}")
            
            # Set environment variable to use the temporary config
            env = os.environ.copy()
            env['SCRAPER_CONFIG'] = temp_config_path
            
            # Start the scraper process
            process = subprocess.Popen(
                [self.config['python_executable'], 'property_scraper.py'],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Set a timeout for the process
            start_time = datetime.now()
            max_runtime = timedelta(minutes=self.config['max_runtime_minutes'])
            
            while process.poll() is None:
                # Check if we've exceeded the maximum runtime
                if datetime.now() - start_time > max_runtime:
                    logger.warning(f"Scraper exceeded maximum runtime of {self.config['max_runtime_minutes']} minutes. Terminating.")
                    process.terminate()
                    break
                
                # Sleep for a bit to avoid high CPU usage
                time.sleep(5)
            
            # Get the output
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Scraper exited with code {process.returncode}")
                logger.error(f"Stderr: {stderr}")
            else:
                logger.info("Scraper completed successfully")
            
            # Clean up
            if os.path.exists(temp_config_path):
                os.remove(temp_config_path)
                
        except Exception as e:
            logger.error(f"Error running scraper: {str(e)}")
    
    def schedule_job(self, schedule_config):
        """Schedule a job with the given configuration."""
        proxy_index = schedule_config.get('proxy_index')
        user_agent_index = schedule_config.get('user_agent_index')
        
        # Add a random delay if configured
        if self.config.get('random_delay_minutes'):
            min_delay, max_delay = self.config['random_delay_minutes']
            delay_minutes = random.randint(min_delay, max_delay)
            logger.info(f"Adding random delay of {delay_minutes} minutes")
            time.sleep(delay_minutes * 60)
        
        # Run the scraper
        self.run_scraper(proxy_index, user_agent_index)
    
    def setup_schedules(self):
        """Set up all scheduled jobs."""
        for idx, schedule_config in enumerate(self.config['schedules']):
            job_time = schedule_config.get('time')
            if job_time:
                logger.info(f"Scheduling job {idx+1} at {job_time}")
                
                # Create a closure to capture the current schedule_config
                def create_job(config):
                    return lambda: self.schedule_job(config)
                
                # Schedule the job
                schedule.every().day.at(job_time).do(create_job(schedule_config))
    
    def run_once(self, proxy_index=None, user_agent_index=None):
        """Run the scraper once with the specified configuration."""
        self.run_scraper(proxy_index, user_agent_index)
    
    def run_scheduler(self):
        """Run the scheduler continuously."""
        self.setup_schedules()
        
        logger.info("Scheduler started. Press Ctrl+C to exit.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")

if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description='Schedule property scraper runs')
    parser.add_argument('--config', type=str, default='scheduler_config.json',
                        help='Path to scheduler configuration file')
    parser.add_argument('--run-once', action='store_true',
                        help='Run the scraper once and exit')
    parser.add_argument('--proxy', type=int, default=None,
                        help='Proxy index to use for run-once mode')
    parser.add_argument('--user-agent', type=int, default=None,
                        help='User agent index to use for run-once mode')
    
    args = parser.parse_args()
    
    # Create scheduler
    scheduler = ScraperScheduler(config_path=args.config)
    
    if args.run_once:
        # Run once with specified configuration
        scheduler.run_once(proxy_index=args.proxy, user_agent_index=args.user_agent)
    else:
        # Run scheduler continuously
        scheduler.run_scheduler()