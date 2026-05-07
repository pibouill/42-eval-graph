#!/usr/bin/env python3
"""
Fetch evaluation data from 42 intra API.

Usage:
    python pull.py                          # Use dates from config.yml (default)
    python pull.py --from 2024-09-01      # Specific start date
    python pull.py --from 2024-09-01 --to 2024-12-15  # Specific range
    python pull.py --cohort 2024-09-01     # By cohort start date
    python pull.py --sample               # Generate sample data (no API)
"""

import argparse
import json
import time
import signal
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os
import traceback
import threading

# Handle Ctrl+C - exit immediately without cleanup
def signal_handler(sig, frame):
    print(f"\n{Colors.YELLOW}Stopped{Colors.ENDC}")
    os._exit(1)

signal.signal(signal.SIGINT, signal_handler)

# Colors for fancy output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}═══ {text} {Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}• {text}{Colors.ENDC}")

def print_step(num, total, text):
    print(f"{Colors.CYAN}[{num}/{total}]{Colors.ENDC} {text}")

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try imports, show helpful error if missing
MISSING_DEPS = []
try:
    import networkx as nx
except ImportError:
    MISSING_DEPS.append("networkx")
try:
    import community as community_louvain
except ImportError:
    MISSING_DEPS.append("python-louvain")
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None
try:
    from intra import ic
except ImportError as e:
    MISSING_DEPS.append(f"intra (local module): {e}")

if MISSING_DEPS:
    print(f"\n{Colors.RED}{Colors.BOLD}Error: Missing required dependencies:{Colors.ENDC}")
    for dep in MISSING_DEPS:
        print(f"  {Colors.RED}•{Colors.ENDC} {dep}")
    print(f"\n{Colors.CYAN}Install them with: {Colors.BOLD}pip install -r requirements.txt{Colors.ENDC}\n")
    sys.exit(1)


def validate_date(date_str, name="date"):
    """Validate date string format YYYY-MM-DD."""
    if not date_str:
        return None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print_error(f"Invalid {name} format: {date_str}")
        print_info(f"Expected format: YYYY-MM-DD (e.g., 2024-09-01)")
        return None


def check_api_credentials():
    """Check if API credentials are configured."""
    config_paths = ['config.yml', 'config.yaml']
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                if config and config.get('intra'):
                    client = config['intra'].get('client', '')
                    secret = config['intra'].get('secret', '')
                    if client and secret:
                        return True
            except Exception as e:
                print_warning(f"Could not read {config_path}: {e}")
    
    print_error("API credentials not found or invalid in config.yml")
    print(f"\n{Colors.CYAN}To fix:{Colors.ENDC}")
    print(f"  1. Copy config.sample.yml to config.yml")
    print(f"  2. Edit config.yml with your 42 API credentials")
    print(f"\n{Colors.DIM}Get credentials from: https://profile.intra.42.fr/oauth/applications{Colors.ENDC}")
    return False


def get_date_range(from_date=None, to_date=None, cohort_date=None, use_config=False):
    """Calculate date range based on arguments."""
    if use_config:
        try:
            import yaml
            for config_file in ['config.yml', 'config.yaml']:
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
                    date_range = config.get('date_range', '')
                    if date_range:
                        parts = date_range.replace(' ', '').split(',')
                        return parts[0], parts[1] if len(parts) > 1 else None
        except FileNotFoundError:
            pass
        except Exception as e:
            print_warning(f"Could not read config.yml: {e}")

    if cohort_date:
        return cohort_date, None

    if from_date:
        return from_date, to_date

    # Smart defaults - detect current semester
    now = datetime.now()
    year = now.year
    month = now.month

    if month >= 9:
        start = f"{year}-09-01"
    elif month >= 1:
        start = f"{year}-01-01"
    else:
        start = f"{year}-09-01"
    
    return start, None


def fetch_evaluations(from_date, to_date=None, cohort_date=None, campus_id=56, cursus_id=21):
    """Fetch evaluations from 42 API."""
    if to_date:
        date_range = f"{from_date},{to_date}"
    elif cohort_date:
        print_info(f"Fetching users who started on {cohort_date}...")
        users = fetch_cohort_users(cohort_date, campus_id, cursus_id)
        if not users:
            print_error("No users found for cohort date")
            return []

        print_success(f"Found {len(users)} users")
        print_info("Fetching evaluations...")
        from_date_obj = datetime.strptime(cohort_date, "%Y-%m-%d")
        next_day = from_date_obj + timedelta(days=1)
        date_range = f"{cohort_date},{next_day.strftime('%Y-%m-%d')}"
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        date_range = f"{from_date},{today}"

    params = {
        'filter[campus_id]': campus_id,
        'filter[cursus_id]': cursus_id,
        'range[created_at]': date_range,
        'sort': 'created_at'
    }

    print_info(f"Fetching evaluations for range: {date_range}...")

    # Get total count
    try:
        query_string = f"page=1&per_page=1&filter[campus_id]={campus_id}&filter[cursus_id]={cursus_id}&range[created_at]={date_range}&sort=created_at"
        initial_response = ic.get(f"scale_teams?{query_string}")
        if initial_response and initial_response.status_code == 200:
            total_count = int(initial_response.headers.get('X-Total', 0))
    except:
        total_count = 0

    start_time = time.time()
    pages_needed = (total_count + 99) // 100

    try:
        if tqdm and pages_needed > 1:
            pbar = tqdm(
                total=pages_needed,
                desc=f"{Colors.CYAN}Fetching{Colors.ENDC}",
                bar_format="{l_bar}{bar}| {n}/{total} [{elapsed}<{remaining}]"
            )

            page_count = [0]
            def progress_callback(completed):
                delta = completed - page_count[0]
                if delta > 0:
                    pbar.update(delta)
                    page_count[0] = completed

            res = ic.pages_threaded('scale_teams', params=params, progress_callback=progress_callback)
            pbar.close()
        else:
            res = ic.pages_threaded('scale_teams', params=params)

        elapsed = time.time() - start_time
        print_success(f"{len(res):,} evaluations in {elapsed:.1f}s")
        return res
    except Exception as e:
        error_msg = str(e)
        if '401' in error_msg or 'Unauthorized' in error_msg:
            print_error("Invalid API credentials")
            print_info("Check your client/secret in config.yml")
        elif '403' in error_msg or 'Forbidden' in error_msg:
            print_error("API access denied")
            print_info("Check your credentials have the right scopes")
        else:
            print_error(f"Failed to fetch from API: {error_msg}")
        return []


def fetch_cohort_users(cohort_date, campus_id, cursus_id):
    """Fetch users who started on a specific date."""
    try:
        date_obj = datetime.strptime(cohort_date, "%Y-%m-%d")
        next_day = date_obj + timedelta(days=1)
        ranged_date = f"{cohort_date},{next_day.strftime('%Y-%m-%d')}"

        cursus_users = ic.pages_threaded('cursus_users', params={
            'filter[campus_id]': campus_id,
            'filter[cursus_id]': cursus_id,
            'range[begin_at]': ranged_date
        })

        return [str(cu['user']['id']) for cu in cursus_users]
    except Exception as e:
        print_error(f"Failed to fetch cohort users: {e}")
        return []


def process(res, include_dates=True):
    """Process evaluation data into nodes and links."""
    if not res:
        return {"nodes": [], "links": []}

    nodes = set()
    links = defaultdict(lambda: {'count': 0, 'first_eval': None, 'last_eval': None})

    print_info(f"Processing {len(res)} evaluation entries...")
    
    for entry in res:
        try:
            corrector = entry['corrector']['login']
            correcteds = entry['correcteds']
            created_at = entry.get('created_at', '')[:10] if include_dates else ''

            nodes.add(corrector)
            for corrected in correcteds:
                corrected_login = corrected['login']
                nodes.add(corrected_login)

                key = (corrector, corrected_login)
                links[key]['count'] += 1

                if include_dates and created_at:
                    if not links[key]['first_eval'] or created_at < links[key]['first_eval']:
                        links[key]['first_eval'] = created_at
                    if not links[key]['last_eval'] or created_at > links[key]['last_eval']:
                        links[key]['last_eval'] = created_at
        except KeyError as e:
            continue

    if not nodes:
        print_warning("No valid nodes found in data")
        return {"nodes": [], "links": []}

    print_success(f"Found {len(nodes)} unique students")
    print_info(f"Found {len(links)} evaluation links")

    # Perform clustering
    print_info("Running clustering algorithm...")
    try:
        G = nx.Graph()
        G.add_nodes_from(nodes)
        G.add_edges_from([
            (source, target, {'weight': data['count']})
            for (source, target), data in links.items()
        ])

        partition = community_louvain.best_partition(G)
        num_clusters = len(set(partition.values()))
        print_success(f"Identified {num_clusters} clusters")
    except Exception as e:
        print_warning(f"Clustering failed: {e}")
        partition = {node: 0 for node in nodes}

    # Build output data
    links_data = []
    for (source, target), data in links.items():
        link_obj = {
            'source': source,
            'target': target,
            'value': data['count']
        }
        if include_dates:
            if data.get('first_eval'):
                link_obj['first_eval'] = data['first_eval']
                link_obj['last_eval'] = data['last_eval']
        links_data.append(link_obj)

    nodes_data = [{"id": node, "group": partition.get(node, 0)} for node in sorted(nodes)]

    return {
        "nodes": nodes_data,
        "links": links_data
    }


def write(data, filename='web/data.json'):
    """Write data to JSON file."""
    if not data:
        print_error(f"No data to write to {filename}")
        return False
    
    try:
        dirname = os.path.dirname(filename)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print_success(f"Written to {filename}")
        return True
    except Exception as e:
        print_error(f"Failed to write to {filename}: {e}")
        return False


def generate_sample():
    """Generate sample data for testing."""
    print_info("Generating sample data...")
    nodes = [{"id": f"user{i}", "group": i % 3} for i in range(1, 21)]
    links = [
        {"source": "user1", "target": "user2", "value": 5, "first_eval": "2024-09-01", "last_eval": "2024-12-15"},
        {"source": "user1", "target": "user3", "value": 3, "first_eval": "2024-10-01", "last_eval": "2024-11-15"},
        {"source": "user2", "target": "user3", "value": 2, "first_eval": "2024-09-15", "last_eval": "2024-10-30"},
        {"source": "user4", "target": "user5", "value": 8, "first_eval": "2024-09-01", "last_eval": "2025-01-20"},
        {"source": "user5", "target": "user6", "value": 1, "first_eval": "2025-01-10", "last_eval": "2025-01-10"},
    ]
    for i in range(7, 21):
        links.append({
            "source": f"user{i}",
            "target": f"user{i+1}",
            "value": (i % 5) + 1,
            "first_eval": f"2024-{9+(i%4):02d}-01",
            "last_eval": f"2025-{1+(i%3):02d}-15"
        })
    print_success("Sample data generated!")
    return {"nodes": nodes, "links": links}


def main():
    parser = argparse.ArgumentParser(
        description=f'{Colors.BOLD}42 Eval Graph{Colors.ENDC} - Fetch peer evaluation data from 42 Intra',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.CYAN}Examples:{Colors.ENDC}
  {Colors.GREEN}python pull.py{Colors.ENDC}                     Use dates from config.yml
  {Colors.GREEN}python pull.py --from 2024-09-01{Colors.ENDC}  Fetch from specific date
  {Colors.GREEN}python pull.py --cohort 2024-09-01{Colors.ENDC} Users who started on date
  {Colors.GREEN}python pull.py --sample{Colors.ENDC}          Generate sample data
        """
    )

    parser.add_argument('--from', dest='from_date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to', dest='to_date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--cohort', dest='cohort_date', help='Cohort start date (YYYY-MM-DD)')
    parser.add_argument('--sample', action='store_true', help='Generate sample data (no API)')
    parser.add_argument('--force', '-f', action='store_true', help='Force refresh (ignore cache)')

    parser.add_argument('--campus', type=int, default=56, help='Campus ID (default: 56)')
    parser.add_argument('--cursus', type=int, default=21, help='Cursus ID (default: 21)')

    args = parser.parse_args()

    # Print banner
    print(f"""
{Colors.HEADER}{Colors.BOLD}42 EVAL GRAPH{Colors.ENDC}
{Colors.DIM}Peer Evaluations Network Generator{Colors.ENDC}
    """)

    # Check for existing data (cache)
    data_file = 'web/data.json'
    if os.path.exists(data_file) and not args.force:
        mtime = os.path.getmtime(data_file)
        age_hours = (time.time() - mtime) / 3600
        
        if age_hours < 24:
            print_info(f"Found existing data.json ({age_hours:.1f} hours old)")
            print_info("Use --force to refresh, or delete data.json manually")
            print(f"\n{Colors.DIM}Exiting...{Colors.ENDC}\n")
            sys.exit(0)

    # Validate date formats
    if args.from_date:
        valid_from = validate_date(args.from_date, "from date")
        if not valid_from:
            sys.exit(1)
        args.from_date = valid_from
    
    if args.to_date:
        valid_to = validate_date(args.to_date, "to date")
        if not valid_to:
            sys.exit(1)
        args.to_date = valid_to
    
    if args.cohort_date:
        valid_cohort = validate_date(args.cohort_date, "cohort date")
        if not valid_cohort:
            sys.exit(1)
        args.cohort_date = valid_cohort

    # --to requires --from
    if args.to_date and not args.from_date:
        print_error("--to requires --from to be specified")
        sys.exit(1)

    # Sample mode
    if args.sample:
        data = generate_sample()
        if write(data, 'web/data.json'):
            print(f"\n{Colors.GREEN}{Colors.BOLD}Done!{Colors.ENDC}\n")
        return

    # Check API credentials
    if not check_api_credentials():
        sys.exit(1)

    from_date = args.from_date
    to_date = args.to_date
    cohort_date = args.cohort_date

    if not any([from_date, to_date, cohort_date]):
        from_date, to_date = get_date_range(use_config=True)
        if from_date:
            print_info(f"Using config date range: {from_date} → {to_date or 'today'}")

    # Fetch data
    print_header("Fetching Data")
    try:
        res = fetch_evaluations(
            from_date=from_date,
            to_date=to_date,
            cohort_date=cohort_date,
            campus_id=args.campus,
            cursus_id=args.cursus
        )
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.ENDC}")
        sys.exit(130)
    except Exception as e:
        print_error(f"Failed to fetch: {e}")
        sys.exit(1)

    if not res:
        print_warning("No evaluations found. This could mean:")
        print(f"  • No evaluations in the specified date range")
        print(f"  • Invalid campus/cursus IDs")
        print(f"  • API rate limiting")
        print(f"\n{Colors.DIM}Try a different date range or check your credentials.{Colors.ENDC}\n")
        sys.exit(0)

    print_success(f"Found {len(res)} evaluations")

    # Process data
    print_header("Processing Data")
    try:
        data = process(res, include_dates=True)
    except Exception as e:
        print_error(f"Failed to process data: {e}")
        sys.exit(1)

    if not data or not data.get('nodes'):
        print_error("No valid data after processing")
        sys.exit(1)

    # Write to file
    print_header("Saving Data")
    if not write(data, 'web/data.json'):
        sys.exit(1)

    # Also generate cluster data
    print_header("Generating Clusters")
    try:
        process_and_save_clusters(data)
    except Exception as e:
        print_warning(f"Could not generate cluster data: {e}")

    print(f"\n{Colors.GREEN}{Colors.BOLD}✨ All done!{Colors.ENDC}\n")


def process_and_save_clusters(data):
    """Process and save cluster-specific data."""
    if not data or not data.get('links'):
        return
    
    import networkx as nx
    import community as community_louvain
    from collections import defaultdict

    try:
        nodes = {n['id']: n['group'] for n in data['nodes']}
        G = nx.Graph()
        for link in data['links']:
            G.add_edge(link['source'], link['target'], weight=link['value'])

        partition = community_louvain.best_partition(G)
    except Exception as e:
        print_warning(f"Clustering failed: {e}")
        return

    cluster_map = defaultdict(list)
    for node, cluster in partition.items():
        cluster_map[cluster].append(node)

    for cluster_id, cluster_nodes in cluster_map.items():
        cluster_nodes_data = [
            {"id": node, "group": partition[node]}
            for node in cluster_nodes
        ]
        cluster_links = [
            link for link in data['links']
            if link['source'] in cluster_nodes and link['target'] in cluster_nodes
        ]
        cluster_data = {
            "nodes": cluster_nodes_data,
            "links": cluster_links
        }
        with open(f'web/data_cluster_{cluster_id}.json', 'w') as f:
            json.dump(cluster_data, f, indent=4)

    with open('web/clusters.json', 'w') as f:
        json.dump(list(cluster_map.keys()), f, indent=4)
    
    print_success(f"Generated {len(cluster_map)} cluster files")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.ENDC}")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
