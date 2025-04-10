#!/usr/bin/env python3
# Per Commit Analysis - considered ONLY REMOVED lines cases in this
import subprocess
import re
from datetime import datetime, timedelta
import os
import requests
import json
import hmac
import hashlib

# Set DEBUG to True to enable debug logs.
DEBUG = True

# Define the 30-day threshold
THIRTY_DAYS = timedelta(days=30)

# Define files and folders to ignore
IGNORED_FILES = {
    # Files
    '.env',
    '.env.example',
    '.gitignore',
    'package.json',
    'package-lock.json',
    'pnpm-lock.json',
    'tsconfig.json',
    'tsconfig.node.json',
    'tsconfig.app.json',
    'tsconfig.spec.json',
    'readme.md'
}

IGNORED_FOLDERS = {
        'node_modules',
        '.git',
        '.github',
        'dist',
        'build',
        'coverage',
        '.husky',
        '.vscode',
        '.idea'
    }

def debug_log(message):
    if DEBUG:
        print("[DEBUG]", message)

def run_command(cmd):
    """Runs a shell command and returns its output as text."""
    debug_log(f"Running command: {cmd}")
    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
        debug_log(f"Command output: {output.strip()}")
        return output
    except subprocess.CalledProcessError as e:
        debug_log(f"Command failed: {e}")
        return ""

def get_commit_timestamp():
    """Gets the commit timestamp of HEAD."""
    ts_str = run_command("git show -s --format=%ct HEAD").strip()
    commit_ts = datetime.fromtimestamp(int(ts_str))
    debug_log(f"Commit timestamp: {commit_ts}")
    return commit_ts

def get_push_commits():
    """Gets all non-merge commits in the PR."""
    # Get the base and head SHAs from environment variables
    base_sha = os.environ.get('PR_BASE_SHA')
    head_sha = os.environ.get('PR_HEAD_SHA')
    
    if not base_sha or not head_sha:
        debug_log("No PR SHA environment variables found, falling back to HEAD")
        head_sha = run_command("git rev-parse HEAD").strip()
        base_sha = run_command(f"git rev-parse {head_sha}~1").strip()
    
    debug_log(f"Base SHA: {base_sha}")
    debug_log(f"Head SHA: {head_sha}")
    
    # Get list of commits between base and head, excluding merges
    # Using --no-merges to exclude merge commits and format to get commit hash and subject
    cmd = f"git log --no-merges --format='%H %s' {base_sha}..{head_sha}"
    output = run_command(cmd).strip()
    
    if not output:
        debug_log("No commits found in range")
        return []
    
    # Split output into lines and extract commit hashes
    commits = []
    for line in output.split('\n'):
        if line.strip():
            commit_hash = line.split()[0]
            commit_subject = ' '.join(line.split()[1:])
            debug_log(f"Found commit: {commit_hash[:8]} - {commit_subject}")
            commits.append(commit_hash)
    
    debug_log(f"Total non-merge commits found: {len(commits)}")
    return commits

def is_ignored_path(file_path):
    """Check if a file path should be ignored."""
    debug_log(f"\nChecking path: {file_path}")
    
    # Convert path to lowercase for case-insensitive comparison
    file_path = file_path.lower().strip('/')
    debug_log(f"Lowercase path: {file_path}")
    
    # Check if the file is in the ignored list
    if any(file_path.endswith(ignored.lower()) for ignored in IGNORED_FILES):
        debug_log(f"File matches ignored file pattern: {file_path}")
        return True
    
    # Split the path into parts
    path_parts = file_path.split('/')
    
    # Check if any part of the path matches an ignored folder
    for folder in IGNORED_FOLDERS:
        folder = folder.lower()
        # Check if the file is in an ignored folder
        if folder in path_parts:
            debug_log(f"File is in ignored folder: {folder}")
            return True
        
        # Check if the file path starts with an ignored folder
        if file_path.startswith(f"{folder}/"):
            debug_log(f"File path starts with ignored folder: {folder}")
            return True
    
    debug_log("Path is not ignored")
    return False

def get_file_chunks(diff_output):
    """Organizes diff output into file-wise chunks."""
    file_chunks = {}
    current_file = None
    current_chunks = []
    
    for line in diff_output.splitlines():
        if line.startswith('diff --git'):
            # If we have a previous file, save its chunks
            if current_file:
                file_chunks[current_file] = current_chunks
            
            # Start new file
            m = re.search(r' b/(.+)$', line)
            if m:
                current_file = m.group(1)
                current_chunks = [line]
        elif current_file:
            current_chunks.append(line)
    
    # Save the last file's chunks
    if current_file and current_chunks:
        file_chunks[current_file] = current_chunks
    
    return file_chunks

def analyze_specific_commit(commit_hash):
    """Analyzes a specific commit and returns analysis metrics."""
    debug_log(f"Analyzing commit: {commit_hash}")
    
    # Get repository and organization IDs from environment variables
    repo_id = f"gh_repo_{os.environ.get('GITHUB_REPOSITORY_ID', '')}"
    org_id = f"gh_org_{os.environ.get('GITHUB_ORGANIZATION_ID', '')}"
    
    # Get the commit timestamp for this specific commit
    ts_str = run_command(f"git show -s --format=%ct {commit_hash}").strip()
    commit_time = datetime.fromtimestamp(int(ts_str))
    
    # Get the diff for this specific commit
    diff_output = run_command(f"git diff {commit_hash}^ {commit_hash}")
    debug_log("Diff output received")
    
    # Initialize counters
    new_feature_count = 0
    rewrite_count = 0
    refactor_count = 0
    
    # Get file-wise chunks
    file_chunks = get_file_chunks(diff_output)
    
    # Process each file's chunks
    for file_path, chunks in file_chunks.items():
        # Skip if file should be ignored
        if is_ignored_path(file_path):
            debug_log(f"Skipping ignored file: {file_path}")
            continue
            
        debug_log(f"Processing file: {file_path}")
        
        # Process chunks for this file
        old_line_num = None
        new_line_num = None
        removed_lines_buffer = []
        hunk_header_regex = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
        
        for line in chunks:
            if line.startswith('@@'):
                m = hunk_header_regex.match(line)
                if m:
                    old_line_num = int(m.group(1))
                    new_line_num = int(m.group(2))
                    removed_lines_buffer = []
                    debug_log(f"Hunk header found. Starting old_line_num: {old_line_num}, new_line_num: {new_line_num}")
            elif old_line_num is None or new_line_num is None:
                continue
            elif line.startswith(" "):
                old_line_num += 1
                new_line_num += 1
            elif line.startswith("-"):
                debug_log(f"Removed line at old_line_num: {old_line_num}")
                removed_lines_buffer.append(old_line_num)
                old_line_num += 1
            elif line.startswith("+"):
                if removed_lines_buffer:
                    removal_line_num = removed_lines_buffer.pop(0)
                    blame_cmd = f'git blame -p -L {removal_line_num},{removal_line_num} HEAD^ -- "{file_path}"'
                    blame_output = run_command(blame_cmd)
                    m_time = re.search(r'author-time (\d+)', blame_output)
                    if m_time:
                        blame_timestamp = datetime.fromtimestamp(int(m_time.group(1)))
                        delta = commit_time - blame_timestamp
                        debug_log(f"Blame timestamp for {removal_line_num} in {file_path}: {blame_timestamp} (delta: {delta})")
                        if delta <= THIRTY_DAYS:
                            rewrite_count += 1
                            debug_log("Classified as rewrite")
                        else:
                            refactor_count += 1
                            debug_log("Classified as refactor")
                    new_line_num += 1
                else:
                    new_feature_count += 1
                    debug_log(f"Added line at new_line_num: {new_line_num} classified as new feature")
                    new_line_num += 1
        
        # Process remaining removals for this file
        for removal_line_num in removed_lines_buffer:
            blame_cmd = f'git blame -p -L {removal_line_num},{removal_line_num} HEAD^ -- "{file_path}"'
            blame_output = run_command(blame_cmd)
            m_time = re.search(r'author-time (\d+)', blame_output)
            if m_time:
                blame_timestamp = datetime.fromtimestamp(int(m_time.group(1)))
                delta = commit_time - blame_timestamp
                debug_log(f"Blame timestamp for removed line {removal_line_num} in {file_path}: {blame_timestamp} (delta: {delta})")
                if delta <= THIRTY_DAYS:
                    rewrite_count += 1
                    debug_log("Classified removed-only as rewrite")
                else:
                    refactor_count += 1
                    debug_log("Classified removed-only as refactor")
    
    return {
        "commitId": commit_hash,
        "repoId": repo_id,
        "organizationId": org_id,
        "workbreakdown": {
            "newFeature": new_feature_count,
            "refactor": refactor_count,
            "rewrite": rewrite_count
        }
    }

def generate_hmac_signature(data, secret_key):
    """Generate HMAC signature for the data."""
    # Convert data to JSON string if it's not already
    if isinstance(data, (dict, list)):
        data = json.dumps(data, sort_keys=True)
    
    # Create HMAC signature using SHA256
    signature = hmac.new(
        secret_key.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    debug_log(f"Generated HMAC signature: {signature}")
    return signature

if __name__ == "__main__":
    commits = get_push_commits()
    debug_log(f"Found {len(commits)} commits to analyze")
    
    # Array to store commit analysis results
    commit_analyses = []
    
    for commit in commits:
        result = analyze_specific_commit(commit)
        commit_analyses.append(result)
        
        # Print individual commit results in JSON format
        print(f"\nCommit Analysis:")
        print(result)
    
    # Print summary of all commits
    print("\nAnalysis Summary:")
    print("-" * 25)
    print(f"Total Commits Analyzed: {len(commit_analyses)}")
    print(f"Total New Features: {sum(c['workbreakdown']['newFeature'] for c in commit_analyses)}")
    print(f"Total Rewrites: {sum(c['workbreakdown']['rewrite'] for c in commit_analyses)}")
    print(f"Total Refactors: {sum(c['workbreakdown']['refactor'] for c in commit_analyses)}")

    # Send data to API
    api_url = os.environ.get('API_URL')
    secret_key = os.environ.get('HMAC_SECRET')

    debug_log(f"API URL: {api_url}")
    debug_log(f"Secret Key: {secret_key}")

    if api_url and secret_key:
        try:
            # Convert data to JSON string with consistent ordering
            json_data = json.dumps(commit_analyses, sort_keys=True)
            
            # Generate HMAC signature
            signature = generate_hmac_signature(json_data, secret_key)
            
            debug_log(f"Sending data to API: {api_url}")
            response = requests.post(
                api_url,
                data=json_data,  # Send the same JSON string used for HMAC
                headers={
                    'Content-Type': 'application/json',
                    'X-Signature': signature
                }
            )
            response.raise_for_status()
            print("Successfully sent commit analyses to API")
            debug_log(f"API Response: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending data to API: {str(e)}")
            exit(1)
    else:
        missing = []
        if not api_url:
            missing.append("API_URL")
        if not secret_key:
            missing.append("HMAC_SECRET")
        print(f"Missing required environment variables: {', '.join(missing)}")
        exit(1)
