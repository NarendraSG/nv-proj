#!/usr/bin/env python3
import subprocess
import re
from datetime import datetime, timedelta

# Define the 30-day threshold
THIRTY_DAYS = timedelta(days=30)

def run_command(cmd):
    """Runs a shell command and returns its output as text."""
    return subprocess.check_output(cmd, shell=True, text=True)

def get_commit_timestamp():
    """Gets the commit timestamp of HEAD."""
    ts_str = run_command("git show -s --format=%ct HEAD").strip()
    return datetime.fromtimestamp(int(ts_str))

def analyze_commit():
    commit_time = get_commit_timestamp()
    # Get the diff for the latest commit (comparing HEAD^ to HEAD)
    diff_output = run_command("git diff HEAD^ HEAD")
    
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
    
    for line in lines:
        if line.startswith("diff --git"):
            # New file diff; extract the new file path.
            m = re.search(r' b/(.+)$', line)
            if m:
                current_file = m.group(1)
        elif line.startswith('@@'):
            # New hunk header: reset the line number counters.
            m = hunk_header_regex.match(line)
            if m:
                old_line_num = int(m.group(1))
                new_line_num = int(m.group(3))
                removed_lines_buffer = []  # Reset for the new hunk
        # Skip processing lines if we haven't encountered a hunk header yet
        elif old_line_num is None or new_line_num is None:
            continue
        elif line.startswith(" "):
            # Context line: both line numbers increment.
            old_line_num += 1
            new_line_num += 1
        elif line.startswith("-"):
            # A removed line from the old file; record its line number.
            removed_lines_buffer.append(old_line_num)
            old_line_num += 1
        elif line.startswith("+"):
            # An added line.
            if removed_lines_buffer:
                # If there is a pending removal, treat this as a modification.
                removal_line_num = removed_lines_buffer.pop(0)
                # Run git blame on the HEAD^ version for the original file at the specific line.
                blame_cmd = f'git blame -L {removal_line_num},{removal_line_num} HEAD^ -- "{current_file}"'
                blame_output = run_command(blame_cmd)
                # Extract the author-time from the blame output.
                m_time = re.search(r'author-time (\d+)', blame_output)
                if m_time:
                    blame_timestamp = datetime.fromtimestamp(int(m_time.group(1)))
                    delta = commit_time - blame_timestamp
                    if delta <= THIRTY_DAYS:
                        rewrite_count += 1
                    else:
                        refactor_count += 1
                new_line_num += 1
            else:
                # No matching removal: count as a new feature (pure addition)
                new_feature_count += 1
                new_line_num += 1

    # Output the results
    print("Commit Analysis Report:")
    print("-----------------------")
    print("New Features (new lines added):", new_feature_count)
    print("Rewrites (modified code written ≤ 30 days ago):", rewrite_count)
    print("Refactors (modified code written > 30 days ago):", refactor_count)

if __name__ == "__main__":
    analyze_commit()