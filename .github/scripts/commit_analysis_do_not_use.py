#!/usr/bin/env python3
import subprocess
import re
from datetime import datetime, timedelta

# Set DEBUG to True to enable debug logs.
DEBUG = True

# Define the 30-day threshold
THIRTY_DAYS = timedelta(seconds=200)

def debug_log(message):
    if DEBUG:
        print("[DEBUG]", message)

def run_command(cmd):
    """Runs a shell command and returns its output as text."""
    debug_log(f"Running command: {cmd}")
    try:
        output = subprocess.check_output(cmd, shell=True, text=True).strip()
        debug_log(f"Command output: {output}")
        return output
    except subprocess.CalledProcessError as e:
        debug_log(f"Command failed: {e}")
        return ""

def get_commit_list():
    """Gets a list of commit hashes in the latest push."""
    base_commit = run_command("git merge-base origin/main HEAD")  # Find common ancestor
    latest_commit = run_command("git rev-parse HEAD")
    commit_list = run_command(f"git rev-list {base_commit}..{latest_commit}").splitlines()
    commit_list.reverse()  # Process commits in chronological order
    debug_log(f"Commits in push: {commit_list}")
    return commit_list

def get_commit_timestamp(commit):
    """Gets the commit timestamp for a given commit."""
    ts_str = run_command(f"git show -s --format=%ct {commit}")
    commit_ts = datetime.fromtimestamp(int(ts_str))
    debug_log(f"Commit {commit} timestamp: {commit_ts}")
    return commit_ts

def analyze_commit(commit):
    commit_time = get_commit_timestamp(commit)
    diff_output = run_command(f"git diff {commit}^ {commit}")
    debug_log("Diff output received")
    
    new_feature_count = 0
    rewrite_count = 0
    refactor_count = 0
    
    current_file = None
    hunk_header_regex = re.compile(r'^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@')
    
    lines = diff_output.splitlines()
    removed_lines_buffer = []
    
    for line in lines:
        if line.startswith("diff --git"):
            match = re.search(r' b/(.+)$', line)
            if match:
                current_file = match.group(1)
                debug_log(f"Found new file: {current_file}")
        elif line.startswith('@@'):
            removed_lines_buffer = []
        elif line.startswith("-"):
            removed_lines_buffer.append(line)
        elif line.startswith("+"):
            if removed_lines_buffer:
                blame_cmd = f'git blame -p -L 1,1 {commit}^ -- "{current_file}"'
                blame_output = run_command(blame_cmd)
                blame_time_match = re.search(r'author-time (\d+)', blame_output)
                if blame_time_match:
                    blame_timestamp = datetime.fromtimestamp(int(blame_time_match.group(1)))
                    delta = commit_time - blame_timestamp
                    if delta <= THIRTY_DAYS:
                        rewrite_count += 1
                    else:
                        refactor_count += 1
                removed_lines_buffer.pop(0)
            else:
                new_feature_count += 1
    
    print(f"Commit {commit} Analysis Report:")
    print("-------------------------------")
    print("New Features (new lines added):", new_feature_count)
    print("Rewrites (modified code written ≤ 30 days ago):", rewrite_count)
    print("Refactors (modified code written > 30 days ago):", refactor_count)
    print()

if __name__ == "__main__":
    commits = get_commit_list()
    for commit in commits:
        analyze_commit(commit)














        
