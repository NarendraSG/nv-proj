#!/usr/bin/env python3
# Per Commit Analysis
import subprocess
import re
from datetime import datetime, timedelta

# Set DEBUG to True to enable debug logs.
DEBUG = True
afsghgfjg
gdfghr


# Define the 30-day threshold
THIRTY_DAYS = timedelta(days=30)
# THIRTY_DAYS = timedelta(seconds=200)

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

def analyze_commit():
    commit_time = get_commit_timestamp()
    # Get the diff for the latest commit (comparing HEAD^ to HEAD)
    diff_output = run_command("git diff HEAD^ HEAD")
    debug_log("Diff output received")
    
    # Counters for our classifications
    new_feature_count = 0
    rewrite_count = 0
    refactor_count = 0

    current_file = None
    # Regex to match the hunk header: @@ -old_start,old_count +new_start,new_count @@ ...
    hunk_header_regex = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
    
    # Process the diff line by line
    lines = diff_output.splitlines()
    
    # Variables to track the current hunk's line numbers
    old_line_num = None
    new_line_num = None
    # Buffer to hold removal line numbers (from the old version) for pairing with additions
    removed_lines_buffer = []
    
    for i, line in enumerate(lines):
        debug_log(f"Processing line {i}: {line}")
        if line.startswith("diff --git"):
            # New file diff; extract the new file path.
            m = re.search(r' b/(.+)$', line)
            if m:
                current_file = m.group(1)
                debug_log(f"Found new file: {current_file}")
        elif line.startswith('@@'):
            # New hunk header: reset the line number counters.
            m = hunk_header_regex.match(line)
            if m:
                old_line_num = int(m.group(1))
                new_line_num = int(m.group(3))
                removed_lines_buffer = []  # Reset for the new hunk
                debug_log(f"Hunk header found. Starting old_line_num: {old_line_num}, new_line_num: {new_line_num}")
        # Skip processing lines if we haven't encountered a hunk header yet
        elif old_line_num is None or new_line_num is None:
            debug_log("Skipping line because no hunk header has been encountered yet.")
            continue
        elif line.startswith(" "):
            # Context line: both line numbers increment.
            old_line_num += 1
            new_line_num += 1
        elif line.startswith("-"):
            # A removed line from the old file; record its line number.
            debug_log(f"Removed line at old_line_num: {old_line_num}")
            removed_lines_buffer.append(old_line_num)
            old_line_num += 1
        elif line.startswith("+"):
            # An added line.
            if removed_lines_buffer:
                # If there is a pending removal, treat this as a modification.
                removal_line_num = removed_lines_buffer.pop(0)
                debug_log(f"Added line with paired removal from old_line_num: {removal_line_num}")
                # Use porcelain mode (-p) so that the output includes 'author-time'
                blame_cmd = f'git blame -p -L {removal_line_num},{removal_line_num} HEAD^ -- "{current_file}"'
                blame_output = run_command(blame_cmd)
                # Extract the author-time from the blame output.
                m_time = re.search(r'author-time (\d+)', blame_output)
                if m_time:
                    blame_timestamp = datetime.fromtimestamp(int(m_time.group(1)))
                    delta = commit_time - blame_timestamp
                    debug_log(f"Blame timestamp for line {removal_line_num} in {current_file}: {blame_timestamp} (delta: {delta})")
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
                # No matching removal: count as a new feature (pure addition)
                new_feature_count += 1
                debug_log(f"Added line at new_line_num: {new_line_num} classified as new feature")
                new_line_num += 1

    # Output the results
    print("Commit Analysis Report:")
    print("-----------------------")
    print("New Features (new lines added):", new_feature_count)
    print("Rewrites (modified code written ≤ 30 days ago):", rewrite_count)
    print("Refactors (modified code written > 30 days ago):", refactor_count)

if __name__ == "__main__":
    analyze_commit()