import os
import yaml
import math
import json
import time
import logging
import requests
import threading

from tqdm import tqdm
from queue import Queue
from copy import deepcopy
from pygments import highlight
from pygments.lexers.data import JsonLexer
from pygments.formatters.terminal import TerminalFormatter

requests.packages.urllib3.disable_warnings()

LOG = logging.getLogger(__name__)

class IntraAPIClient(object):
    verify_requests = False

    def __init__(self, progress_bar=False):
        base_dir = os.path.dirname(os.path.realpath(__file__))
        
        # Check if config file exists
        config_path = base_dir + '/config.yml'
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                "Please copy config.sample.yml to config.yml and configure your API credentials."
            )
        
        with open(config_path, 'r') as cfg_stream:
            config = yaml.safe_load(cfg_stream)
        
        # Validate config has required fields
        if not config:
            raise ValueError("Configuration file is empty")
        
        if 'intra' not in config:
            raise ValueError("Missing 'intra' section in config.yml")
        
        intra_config = config['intra']
        
        # Check required credentials
        if not intra_config.get('client'):
            raise ValueError("Missing 'client' in config.yml intra section")
        if not intra_config.get('secret'):
            raise ValueError("Missing 'secret' in config.yml intra section")
        
        # Set configuration values with defaults
        self.client_id = intra_config['client']
        self.client_secret = intra_config['secret']
        self.token_url = intra_config.get('uri', 'https://api.intra.42.fr/v2/oauth/token')
        self.api_url = intra_config.get('endpoint', 'https://api.intra.42.fr/v2')
        self.scopes = intra_config.get('scopes', 'public')
        self.progress_bar = progress_bar
        self.token = None

    def request_token(self):
        request_token_payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": self.scopes,
        }
        LOG.debug("Attempting to get a token from intranet")
        self.token = "token_dummy"
        res = self.request(requests.post, self.token_url, params=request_token_payload)
        rj = res.json()
        self.token = rj["access_token"]
        LOG.info(f"Got new acces token from intranet {self.token}")

    def _make_authed_header(self, header={}):
        ret = {"Authorization": f"Bearer {self.token}"}
        ret.update(header)
        return ret

    def request(self, method, url, headers={}, **kwargs):
        if not self.token:
            self.request_token()
        tries = 0
        if not url.startswith("http"):
            url = f"{self.api_url}/{url}"

        while True:
            LOG.debug(f"Attempting a request to {url}")

            try:
                res = method(
                    url,
                    headers=self._make_authed_header(headers),
                    verify=self.verify_requests,
                    **kwargs
                )

                rc = res.status_code
                if rc == 401:
                    if 'www-authenticate' in res.headers:
                        _, desc = res.headers['www-authenticate'].split('error_description="')
                        desc, _ = desc.split('"')
                        if desc == "The access token expired" or desc == "The access token is invalid":
                            if self.token != "token_dummy":
                                LOG.warning(f"Server said our token {self.token} {desc.split(' ')[-1]}")
                            if tries < 5:
                                LOG.info("Refreshing token")
                                self.request_token()
                                tries += 1
                                continue
                    break
                return res
            except Exception as e:
                LOG.error(f"Request failed: {e}")
                if tries < 3:
                    tries += 1
                    time.sleep(1)
                    continue
                return None

    def get(self, url, params=None, **kwargs):
        if params:
            # Add params to URL
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += '&'.join([f"{k}={v}" for k, v in params.items()])
        return self.request(requests.get, url, **kwargs)

    def post(self, url, **kwargs):
        return self.request(requests.post, url, **kwargs)

    def put(self, url, **kwargs):
        return self.request(requests.put, url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request(requests.delete, url, **kwargs)

    def pages(self, url, stop_on_error=False):
        page = 1
        while True:
            try:
                response = self.get(f"{url}?page={page}&per_page=100")
            except Exception as e:
                if stop_on_error:
                    LOG.error(f"API request failed: {e}")
                    break
                raise e
            if response.status_code != 200:
                if stop_on_error:
                    LOG.error(f"API returned {response.status_code}")
                    break
                raise Exception(f"Error code: {response.status_code}")
            response = response.json()
            if len(response) == 0:
                break
            for r in response:
                yield r
            page += 1

    def pages_threaded(self, url, params=None, num_thread=10, stop_on_error=False, progress_callback=None):
        # Build query string from params dict
        query_parts = []
        if params:
            for key, value in params.items():
                query_parts.append(f"{key}={value}")
        query_string = "&".join(query_parts) if query_parts else ""
        
        queue = Queue()
        threads = []
        output_list = []
        completed = [0]  # Use list for mutable reference in closure

        def worker():
            while True:
                page = queue.get()
                if page is None:
                    break
                try:
                    base_url = f"{url}?page={page}&per_page=100"
                    if query_string:
                        base_url += f"&{query_string}"
                    response = self.get(base_url)
                    if response is None:
                        LOG.warning(f"API returned None for page {page}")
                    elif response.status_code == 200:
                        response_data = response.json()
                        if response_data:
                            for r in response_data:
                                output_list.append(r)
                    elif stop_on_error:
                        LOG.error(f"API returned {response.status_code}")
                except Exception as e:
                    LOG.warning(f"API request failed for page {page}: {e}")
                finally:
                    completed[0] += 1
                    if progress_callback:
                        progress_callback(completed[0])
                    queue.task_done()

        # Create and start worker threads
        for _ in range(num_thread):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        # get number of pages
        try:
            count_url = f"{url}?page=1&per_page=100"
            if query_string:
                count_url += f"&{query_string}"
            response = self.get(count_url)
            if response.status_code == 200:
                number_of_pages = int(response.headers.get('X-Total', 1))
            else:
                number_of_pages = 1
        except Exception as e:
            LOG.error(f"API request failed: {e}")
            number_of_pages = 1

        # fill queue
        for page in range(1, math.ceil(number_of_pages / 100) + 1):
            queue.put(page)

        # wait for all tasks to be done
        queue.join()

        # stop workers
        for _ in range(num_thread):
            queue.put(None)
        for t in threads:
            t.join()

        return output_list

    def close(self):
        pass

    def __str__(self):
        return "<IntraAPIClient - {}>".format(self.token)


def load_config():
    base_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(base_dir, 'config.yml')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please run: cp config.sample.yml config.yml\n"
            "Then edit config.yml with your 42 API credentials."
        )
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    if not config:
        raise ValueError("config.yml is empty")
    
    required_fields = ['intra']
    missing = [f for f in required_fields if f not in config]
    if missing:
        raise ValueError(f"Missing required fields in config.yml: {', '.join(missing)}")
    
    intra_fields = ['client', 'secret']
    intra_missing = [f for f in intra_fields if f not in config['intra'] or not config['intra'][f]]
    if intra_missing:
        raise ValueError(f"Missing required intra fields: {', '.join(intra_missing)}")
    
    return config


# Initialize global client
try:
    ic = IntraAPIClient()
except FileNotFoundError as e:
    print(f"Error: {e}")
    print("Please copy config.sample.yml to config.yml and configure your API credentials.")
    exit(1)
except ValueError as e:
    print(f"Error: {e}")
    print("Please check your config.yml file.")
    exit(1)
except Exception as e:
    print(f"Error initializing API client: {e}")
    exit(1)


if __name__ == "__main__":
    try:
        print("Testing API connection...")
        ic.request_token()
        print("Successfully connected to 42 API!")
        print(f"Token: {ic.token[:20]}...")
    except Exception as e:
        print(f"Failed to connect: {e}")
        exit(1)