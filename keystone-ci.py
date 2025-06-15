#!/usr/bin/env python3
"""
Keystone CI - Command-line interface for running Keystone test suites in CI/CD pipelines.

Usage:
  keystone-ci.py run --suite-id=<id> --base-url=<url> [--api-key=<key>] [--output=<format>] [--timeout=<seconds>] [--poll-interval=<seconds>] [--ci-run-id=<id>] [--branch=<name>] [--commit=<sha>]
  keystone-ci.py status --suite-run-id=<id> [--api-key=<key>] [--output=<format>]
  keystone-ci.py -h | --help
  keystone-ci.py --version

Options:
  -h --help                Show this screen.
  --version                Show version.
  --suite-id=<id>          Suite ID to run.
  --suite-run-id=<id>      Suite run ID to check status.
  --base-url=<url>         Base URL for test execution.
  --api-key=<key>          API key for authentication [default: env:KEYSTONE_API_KEY].
  --output=<format>        Output format: text, json, github [default: text].
  --timeout=<seconds>      Maximum time to wait for tests [default: 600].
  --poll-interval=<sec>    Polling interval in seconds [default: 5].
  --ci-run-id=<id>         CI run identifier.
  --branch=<name>          Branch name.
  --commit=<sha>           Commit SHA.
"""

import os
import sys
import time
import json
import requests
from typing import Dict, Any, Optional

# Try to import docopt, provide fallback if not available
try:
    from docopt import docopt
except ImportError:
    print("Error: docopt not installed. Please run: pip install docopt")
    sys.exit(1)


class KeystoneCI:
    """Keystone CI client for running test suites."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.withkeystone.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {"X-API-Key": api_key}
        self.debug = os.environ.get('KEYSTONE_DEBUG', '').lower() in ('1', 'true', 'yes')
    
    def trigger_suite_run(self, suite_id: str, test_base_url: str, 
                         ci_run_id: Optional[str] = None,
                         branch: Optional[str] = None,
                         commit: Optional[str] = None) -> Dict[str, Any]:
        """Trigger a suite run."""
        url = f"{self.base_url}/api/v1/suites/{suite_id}/ci/trigger"
        
        payload = {
            "base_url": test_base_url,
            "ci_run_id": ci_run_id,
            "branch": branch,
            "commit": commit
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        print(f"🚀 Triggering suite run...")
        print(f"   URL: {url}")
        print(f"   Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Suite run triggered successfully!")
        print(f"   Suite Run ID: {result.get('suite_run_id')}")
        print(f"   Poll URL: {result.get('poll_url')}")
        print(f"   Run URL: {result.get('run_url')}")
        
        if self.debug:
            print(f"\n🔍 Debug - Raw response:")
            print(json.dumps(result, indent=2))
        
        return result
    
    def get_suite_run_status(self, suite_run_id: str) -> Dict[str, Any]:
        """Get status of a suite run."""
        url = f"{self.base_url}/api/v1/suites/ci/{suite_run_id}/status"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        data = response.json()
        print(f"📊 Status: {data.get('status', 'unknown')} | Tests: {data.get('total_tests', 0)} | Passed: {data.get('passed_tests', 0)} | Failed: {data.get('failed_tests', 0)}")
        
        if self.debug:
            print(f"🔍 Debug - Raw status response:")
            print(json.dumps(data, indent=2))
        
        return data
    
    def wait_for_completion(self, suite_run_id: str, timeout: int = 600, 
                           poll_interval: int = 5) -> Dict[str, Any]:
        """Poll for suite run completion."""
        start_time = time.time()
        
        print(f"⏳ Waiting for suite run to complete (timeout: {timeout}s, poll interval: {poll_interval}s)...")
        
        while time.time() - start_time < timeout:
            status = self.get_suite_run_status(suite_run_id)
            
            if status['status'] in ['completed', 'failed', 'aborted']:
                elapsed = int(time.time() - start_time)
                print(f"✅ Suite run finished in {elapsed}s with status: {status['status']}")
                return status
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Suite run did not complete within {timeout} seconds")


def format_output(data: Dict[str, Any], format_type: str, suite_run_id: Optional[str] = None):
    """Format output based on requested format."""
    if format_type == 'json':
        print(json.dumps(data, indent=2))
    
    elif format_type == 'github':
        # Set GitHub Actions outputs
        if suite_run_id:
            print(f"::set-output name=suite_run_id::{suite_run_id}")
        print(f"::set-output name=status::{data['status']}")
        print(f"::set-output name=passed_tests::{data['passed_tests']}")
        print(f"::set-output name=failed_tests::{data['failed_tests']}")
        print(f"::set-output name=total_tests::{data['total_tests']}")
        print(f"::set-output name=run_url::{data.get('run_url', '')}")
        
        # Also print summary
        if data['failed_tests'] > 0:
            print(f"\n❌ Tests failed: {data['failed_tests']} out of {data['total_tests']}")
            sys.exit(1)
        else:
            print(f"\n✅ All {data['total_tests']} tests passed!")
    
    else:  # text format
        print(f"\nSuite Run Status: {data['status']}")
        print(f"Total Tests: {data['total_tests']}")
        print(f"Passed: {data['passed_tests']}")
        print(f"Failed: {data['failed_tests']}")
        
        if data.get('run_url'):
            print(f"\nView results: {data['run_url']}")
        
        # Show individual test results
        if data.get('tests'):
            print("\nTest Results:")
            print("-" * 60)
            for test in data['tests']:
                status_icon = "✅" if test['status'] == 'completed' else "❌"
                print(f"{status_icon} {test['test_name']}: {test['status']} ({test['duration_ms']}ms)")


def main():
    """Main CLI entry point."""
    arguments = docopt(__doc__, version='Keystone CI 1.0.0')
    
    # Get API key from environment or argument
    api_key = arguments['--api-key']
    if api_key == 'env:KEYSTONE_API_KEY':
        api_key = os.environ.get('KEYSTONE_API_KEY')
        if not api_key:
            print("Error: KEYSTONE_API_KEY environment variable not set")
            sys.exit(1)
    
    # Determine API base URL
    api_base_url = os.environ.get('KEYSTONE_API_URL', 'https://api.withkeystone.com')
    
    client = KeystoneCI(api_key, api_base_url)
    
    try:
        if arguments['run']:
            # Trigger suite run
            print(f"Triggering suite {arguments['--suite-id']}...")
            result = client.trigger_suite_run(
                suite_id=arguments['--suite-id'],
                test_base_url=arguments['--base-url'],
                ci_run_id=arguments.get('--ci-run-id'),
                branch=arguments.get('--branch'),
                commit=arguments.get('--commit')
            )
            
            suite_run_id = result['suite_run_id']
            print(f"Suite run started: {suite_run_id}")
            
            # Wait for completion
            timeout = int(arguments['--timeout'])
            poll_interval = int(arguments['--poll-interval'])
            
            print(f"Polling for results (timeout: {timeout}s)...")
            final_status = client.wait_for_completion(suite_run_id, timeout, poll_interval)
            
            # Format output
            format_output(final_status, arguments['--output'], suite_run_id)
            
            # Exit with error if tests failed
            if final_status['failed_tests'] > 0:
                sys.exit(1)
        
        elif arguments['status']:
            # Check status only
            status = client.get_suite_run_status(arguments['--suite-run-id'])
            format_output(status, arguments['--output'])
            
            # Exit with error if tests failed
            if status['status'] == 'failed' or status['failed_tests'] > 0:
                sys.exit(1)
    
    except requests.exceptions.HTTPError as e:
        print(f"API Error: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except TimeoutError as e:
        print(f"Timeout: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
