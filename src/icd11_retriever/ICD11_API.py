"""
WHO ICD-11 API Data Scraper

This module fetches hierarchical data from the WHO ICD-11 API,
starting from a specified root entity and traversing all children.
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import argparse
import re

import requests
import urllib3
from dotenv import load_dotenv

# Disable SSL warnings (consider enabling verification in production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
class Config:
    """Configuration settings for ICD-11 API."""
    CLIENT_ID = os.getenv('ICD_CLIENT_ID')
    CLIENT_SECRET = os.getenv('ICD_CLIENT_SECRET')
    TOKEN_ENDPOINT = 'https://icdaccessmanagement.who.int/connect/token'
    SCOPE = 'icdapi_access'
    GRANT_TYPE = 'client_credentials'
    BASE_URI = 'http://id.who.int/icd/entity/'
    REQUEST_DELAY = 2  # seconds between requests
    REAUTH_INTERVALS = {2, 3, 4, 5, 6, 7, 8, 9, 10}  # epochs to re-authenticate
    #DATA_DIR = Path('./data')
    
    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        if not cls.CLIENT_ID or not cls.CLIENT_SECRET:
            raise ValueError("CLIENT_ID and CLIENT_SECRET must be set in environment variables")


class ICDAPIClient:
    """Client for interacting with the WHO ICD-11 API."""
    
    def __init__(self, config: Config):
        """
        Initialize the API client.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.headers = None
        self.exceptions: List[str] = []
        self.authorize()
    
    def authorize(self) -> None:
        """
        Obtain OAuth2 access token and set authorization headers.
        
        Raises:
            requests.RequestException: If authorization fails
        """
        payload = {
            'client_id': self.config.CLIENT_ID,
            'client_secret': self.config.CLIENT_SECRET,
            'scope': self.config.SCOPE,
            'grant_type': self.config.GRANT_TYPE
        }
        
        try:
            response = requests.post(
                self.config.TOKEN_ENDPOINT,
                data=payload,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            token = response.json()['access_token']
            
            self.headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json',
                'Accept-Language': 'en',
                'API-Version': 'v2'
            }
            logger.info("Successfully authorized with ICD API")
            
        except requests.RequestException as e:
            logger.error(f"Authorization failed: {e}")
            raise
    
    def make_request(self, uri: str) -> Dict[str, Any]:
        """
        Make HTTP GET request to specified URI.
        
        Args:
            uri: The URI to request
            
        Returns:
            JSON response as dictionary, or empty dict on failure
        """
        try:
            response = requests.get(
                uri,
                headers=self.headers,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Request failed for {uri}: {e}")
            self.exceptions.append(uri)
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {uri}: {e}")
            self.exceptions.append(uri)
            return {}
    
    @staticmethod
    def extract_children_ids(data: Dict[str, Any]) -> List[str]:
        """
        Extract child IDs from response data.
        
        Args:
            data: Response data containing 'child' field
            
        Returns:
            List of extracted child IDs
        """
        child_data = data.get('child', [])
        if not child_data:
            return []
        
        return [url.split('/')[-1] for url in child_data]
    
    def fetch_children(self, child_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch data for all child IDs.
        
        Args:
            child_ids: List of child IDs to fetch
            
        Returns:
            List of data dictionaries for each child
        """
        children = []
        
        for child_id in child_ids:
            uri = f"{self.config.BASE_URI}{child_id}"
            logger.info(f"Fetching: {uri}")
            
            child_data = self.make_request(uri)
            if child_data:  # Only append non-empty responses
                children.append(child_data)
            
            time.sleep(self.config.REQUEST_DELAY)
        
        return children


class ICDHierarchyScraper:
    """Scraper for traversing ICD-11 hierarchy."""
    
    def __init__(self, client: ICDAPIClient, root_entity: Dict[str, str]):
        """
        Initialize the scraper.
        
        Args:
            client: Authenticated API client
            root_entity: Dictionary with 'title', 'entityID', and 'baseuri'
        """
        self.client = client
        self.root_entity = root_entity
        self.blob: Dict[int, Dict[str, Any]] = {}
        self.counter = 0
    
    def scrape(self) -> Dict[int, Dict[str, Any]]:
        """
        Scrape the entire hierarchy starting from root entity.
        
        Returns:
            Dictionary mapping index to entity data
        """
        toplevel_uri = f"{self.root_entity['baseuri']}{self.root_entity['entityID']}"
        logger.info(f"Starting scrape from: {toplevel_uri}")
        logger.info(f"Root: {self.root_entity['title']}")
        
        # Fetch root entity
        starter = self.client.make_request(toplevel_uri)
        if not starter:
            logger.error("Failed to fetch root entity")
            return self.blob
        
        starter['level'] = 0
        self.blob[self.counter] = starter
        self.counter += 1
        
        # Get level 1 children
        level1_ids = self.client.extract_children_ids(starter)
        
        # Traverse hierarchy breadth-first
        current_level = self.client.fetch_children(level1_ids)
        epoch = 1
        
        while current_level:
            logger.info(f"Processing epoch {epoch} with {len(current_level)} entities")
            next_level_ids = []
            
            for entity in current_level:
                entity['level'] = epoch
                self.blob[self.counter] = entity
                
                title = entity.get('title', 'Unknown')
                logger.info(f"  - {title}")
                
                # Get children for next level
                children_ids = self.client.extract_children_ids(entity)
                next_level_ids.extend(children_ids)
                
                self.counter += 1
            
            # Re-authenticate at specified intervals
            if epoch in self.client.config.REAUTH_INTERVALS:
                logger.info(f"Re-authenticating at epoch {epoch}")
                self.client.authorize()
            
            # Fetch next level
            current_level = self.client.fetch_children(next_level_ids)
            epoch += 1
            
            logger.info(f"Total entities collected: {len(self.blob)}")
        
        logger.info(f"Scraping complete. Total entities: {len(self.blob)}")
        return self.blob
    
    def save_results(self, output_path: Path) -> None:
        """
        Save scraped data to JSON file.
        
        Args:
            output_path: Path to output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.blob, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Data saved to {output_path}")
    
    def save_exceptions(self, output_path: Path) -> None:
        """
        Save failed URIs to JSON file.
        
        Args:
            output_path: Path to output JSON file
        """
        if not self.client.exceptions:
            logger.info("No exceptions to save")
            return
        
        exceptions_dict = {i: uri for i, uri in enumerate(self.client.exceptions)}
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(exceptions_dict, f, indent=2)
        
        logger.warning(f"Saved {len(self.client.exceptions)} exceptions to {output_path}")


def main(**kwargs):
    """Main execution function."""

    startnode = kwargs.get('startnode')
    startid = kwargs.get('startid')

    print(startnode, startid)

    NodeName = re.sub(r'[^a-zA-Z0-9]', '', startnode)
    os.makedirs(f'./data/{NodeName}', exist_ok=True)
    DATA_DIR = Path(f'./data/{NodeName}')

    try:
        # Validate configuration
        Config.validate()
        
        # Initialize client
        client = ICDAPIClient(Config)
        
        # Define hierarchy root
        hierarchy_root = {
            'title': startnode,
            'entityID': startid,
            'baseuri': Config.BASE_URI
        }
        
        # Initialize and run scraper
        scraper = ICDHierarchyScraper(client, hierarchy_root)
        scraper.scrape()
        
        # Save results
        scraper.save_results(DATA_DIR / 'ICD11.json')
        scraper.save_exceptions(DATA_DIR / 'error_URIs.json')
        
        logger.info("Process completed successfully")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--startnode", type = str, default = "Mental, behavioural or neurodevelopmental disorders")
    parser.add_argument("--startid", type = str, default = "334423054")
    args = parser.parse_args()

    main(**vars(args))