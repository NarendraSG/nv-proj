#!/usr/bin/env python3
# Per Commit Analysis - considered ONLY REMOVED lines cases in this
import subprocess
import re
from datetime import datetime, timedelta
import os

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
    file_path = file_path.lower()
    debug_log(f"Lowercase path: {file_path}")
    
    # Check if the file is in the ignored list
    if any(file_path.endswith(ignored.lower()) for ignored in IGNORED_FILES):
        debug_log(f"File matches ignored file pattern: {file_path}")
        return True
        
    # Check for ignored folders (add any folders you want to ignore)
    ignored_folders = {
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
    
    # Split the path and check if any part matches ignored folders
    path_parts = file_path.split('/')
    debug_log(f"Path parts: {path_parts}")
    
    # Check each part against ignored folders
    for part in path_parts:
        if part in ignored_folders:
            debug_log(f"Found ignored folder '{part}' in path")
            return True
    
    debug_log("Path is not ignored")
    return False

def analyze_specific_commit(commit_hash):
    """Analyzes a specific commit and returns analysis metrics."""
    debug_log(f"Analyzing commit: {commit_hash}")
    
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
    
    current_file = None
    hunk_header_regex = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
    
    lines = diff_output.splitlines()
    old_line_num = None
    new_line_num = None
    removed_lines_buffer = []
    only_removed = True  # Flag to check if hunk only has removals
    
    for i, line in enumerate(lines):
        debug_log(f"Processing line {i}: {line}")
        if line.startswith("diff --git"):
            m = re.search(r' b/(.+)$', line)
            if m:
                current_file = m.group(1)
                # Skip processing if file should be ignored
                if is_ignored_path(current_file):
                    debug_log(f"Skipping ignored path: {current_file}")
                    current_file = None
                    continue
                debug_log(f"Processing file: {current_file}")
        elif line.startswith('@@'):
            m = hunk_header_regex.match(line)
            if m:
                old_line_num = int(m.group(1))
                new_line_num = int(m.group(2))
                removed_lines_buffer = []
                only_removed = True  # Reset flag for new hunk
                debug_log(f"Hunk header found. Starting old_line_num: {old_line_num}, new_line_num: {new_line_num}")
        elif old_line_num is None or new_line_num is None:
            continue
        elif line.startswith(" "):
            old_line_num += 1
            new_line_num += 1
            only_removed = False
        elif line.startswith("-"):
            debug_log(f"Removed line at old_line_num: {old_line_num}")
            removed_lines_buffer.append(old_line_num)
            old_line_num += 1
        elif line.startswith("+"):
            only_removed = False
            if removed_lines_buffer:
                removal_line_num = removed_lines_buffer.pop(0)
                blame_cmd = f'git blame -p -L {removal_line_num},{removal_line_num} HEAD^ -- "{current_file}"'
                blame_output = run_command(blame_cmd)
                m_time = re.search(r'author-time (\d+)', blame_output)
                if m_time:
                    blame_timestamp = datetime.fromtimestamp(int(m_time.group(1)))
                    delta = commit_time - blame_timestamp
                    debug_log(f"Blame timestamp for {removal_line_num} in {current_file}: {blame_timestamp} (delta: {delta})")
                    if delta <= THIRTY_DAYS:
                        rewrite_count += 1
                        debug_log("Classified as rewrite")
                    else:
                        refactor_count += 1
                        debug_log("Classified as refactor")
                else:
                    debug_log("Could not extract author-time from blame output")
                new_line_num += 1
            else:
                new_feature_count += 1
                debug_log(f"Added line at new_line_num: {new_line_num} classified as new feature")
                new_line_num += 1
    
    # Process removals with no corresponding additions
    for removal_line_num in removed_lines_buffer:
        blame_cmd = f'git blame -p -L {removal_line_num},{removal_line_num} HEAD^ -- "{current_file}"'
        blame_output = run_command(blame_cmd)
        m_time = re.search(r'author-time (\d+)', blame_output)
        if m_time:
            blame_timestamp = datetime.fromtimestamp(int(m_time.group(1)))
            delta = commit_time - blame_timestamp
            debug_log(f"Blame timestamp for removed line {removal_line_num} in {current_file}: {blame_timestamp} (delta: {delta})")
            if delta <= THIRTY_DAYS:
                rewrite_count += 1
                debug_log("Classified removed-only as rewrite")
            else:
                refactor_count += 1
                debug_log("Classified removed-only as refactor")
    
    # Return a dictionary with the new format
    return {
        "commitId": commit_hash,
        "repoId": os.environ.get('REPO_ID', ''),
        "organizationId": os.environ.get('ORG_ID', ''),
        "workbreakdown": {
            "newFeature": new_feature_count,
            "refactor": refactor_count,
            "rewrite": rewrite_count
        }
    }

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
