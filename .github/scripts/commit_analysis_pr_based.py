#!/usr/bin/env python3

# PR Based Commit Analysis
import subprocess
import re
from datetime import datetime, timedelta

DEBUG = True
THIRTY_DAYS = timedelta(days=30)

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
    """Fetches all commits in the current PR, excluding merge commits, and appends one more old commit."""
    base_branch = run_command("git merge-base origin/main HEAD").strip()
    commit_list = run_command(f"git log --no-merges --pretty=format:'%H' {base_branch}..HEAD").splitlines()
    debug_log(f"Commit list (excluding merges): {commit_list}")
    
    # Append one more old commit if possible
    if commit_list:
        oldest_commit = run_command(f"git log --no-merges --pretty=format:'%H' -n 1 {commit_list[-1]}^ --").strip()
        if oldest_commit:
            commit_list.append(oldest_commit)
            debug_log(f"Appended older commit: {oldest_commit}")
    
    return commit_list

def get_commit_timestamp(commit_hash):
    """Gets the commit timestamp of a given commit."""
    ts_str = run_command(f"git show -s --format=%ct {commit_hash}")
    commit_ts = datetime.fromtimestamp(int(ts_str))
    debug_log(f"Commit {commit_hash} timestamp: {commit_ts}")
    return commit_ts

def analyze_commit(commit1, commit2):
    commit_time = get_commit_timestamp(commit1)
    diff_output = run_command(f"git diff {commit2} {commit1}")
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
            m = re.search(r' b/(.+)$', line)
            if m:
                current_file = m.group(1)
                debug_log(f"Found new file: {current_file}")
        elif hunk_header_regex.match(line):
            removed_lines_buffer = []
        elif line.startswith("-"):
            removed_lines_buffer.append(line)
        elif line.startswith("+"):
            if removed_lines_buffer:
                removal_line = removed_lines_buffer.pop(0)
                blame_cmd = f'git blame -p -L 1,1 {commit2} -- "{current_file}"'
                blame_output = run_command(blame_cmd)
                m_time = re.search(r'author-time (\d+)', blame_output)
                if m_time:
                    blame_timestamp = datetime.fromtimestamp(int(m_time.group(1)))
                    delta = commit_time - blame_timestamp
                    if delta <= THIRTY_DAYS:
                        rewrite_count += 1
                    else:
                        refactor_count += 1
                else:
                    debug_log("Could not extract author-time from blame output")
            else:
                new_feature_count += 1
    
    print(f"Commit Pair: {commit2} -> {commit1}")
    print("New Features:", new_feature_count)
    print("Rewrites:", rewrite_count)
    print("Refactors:", refactor_count)
    print("-------------------------------------")

if __name__ == "__main__":
    commits = get_commit_list()
    for i in range(len(commits) - 1):
        analyze_commit(commits[i], commits[i + 1])
