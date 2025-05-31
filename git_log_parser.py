# git_log_parser.py

import subprocess
import os
from git_graph_data import CommitNode # Assuming git_graph_data.py is in the same directory or accessible

# Delimiters for parsing git log output
FIELD_SEP = "\x01"
ENTRY_SEP = "\x02"

# Git log format string
# %H: commit hash
# %P: parent hashes (space separated)
# %d: decorations (references)
# %an: author name
# %ae: author email
# %ad: author date (ISO 8601 strict)
# %s: subject
# %b: body (this must be the last field before ENTRY_SEP)
GIT_LOG_FORMAT = f"%H{FIELD_SEP}%P{FIELD_SEP}%d{FIELD_SEP}%an{FIELD_SEP}%ae{FIELD_SEP}%ad{FIELD_SEP}%s{FIELD_SEP}%b{ENTRY_SEP}"

def _parse_references(raw_refs_str: str) -> list[str]:
    """
    Parses the raw decoration string from git log %d.
    Example: " (HEAD -> main, tag: v1.1, origin/master, master)"
    Output: ['HEAD -> main', 'tag: v1.1', 'origin/master', 'master']
    """
    if not raw_refs_str.strip():
        return []

    # Remove surrounding parentheses if they exist
    if raw_refs_str.startswith(" (") and raw_refs_str.endswith(")"):
        content = raw_refs_str[2:-1]
    else:
        content = raw_refs_str.strip()

    if not content:
        return []

    return [ref.strip() for ref in content.split(",")]

def parse_git_log(repo_path: str = ".") -> list[CommitNode]:
    """
    Fetches git log from the specified repository path and parses it into CommitNode objects.
    """
    git_log_command = [
        "git",
        "log",
        "--all",
        "--date=iso-strict", # Consistent date format
        f"--pretty=format:{GIT_LOG_FORMAT}",
    ]

    try:
        # Ensure the repo_path is a valid git directory by running a benign command first
        subprocess.run(["git", "-C", repo_path, "rev-parse", "--is-inside-work-tree"],
                       check=True, capture_output=True, text=True)

        result = subprocess.run(git_log_command, cwd=repo_path, check=True, capture_output=True, text=True, encoding='utf-8')
        log_output = result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing git log: {e}")
        print(f"Stderr: {e.stderr}")
        return []
    except FileNotFoundError:
        print("Git command not found. Please ensure Git is installed and in your PATH.")
        return []

    commits_map: dict[str, CommitNode] = {}
    commit_list_ordered: list[CommitNode] = [] # To maintain the order from git log (generally topo)

    if not log_output.strip():
        return []

    entries = log_output.strip().split(ENTRY_SEP)

    for entry in entries:
        if not entry.strip():
            continue

        parts = entry.strip().split(FIELD_SEP)
        if len(parts) < 7: # sha, parents, refs, author, email, date, subject (body can be empty)
            # print(f"Skipping malformed entry: {entry}") # For debugging
            continue

        sha = parts[0]
        parent_hashes_str = parts[1]
        raw_refs = parts[2]
        author_name = parts[3]
        author_email = parts[4]
        author_date = parts[5]
        subject = parts[6]
        # Body is parts[7] if it exists, otherwise it's an empty string if the commit message has no body.
        # The split by ENTRY_SEP handles this correctly. If subject was the last thing, parts[7] might be missing.
        # However, our GIT_LOG_FORMAT always includes %b, so it should produce an empty string for parts[7] if no body.
        # Let's assume for now the split gives enough parts or an empty string for body if it's missing.
        # The logic below assumes `subject` is the primary message if `body` is empty or consists only of newlines.
        # For simplicity in this step, we'll primarily use the subject as 'message'.
        # A more sophisticated approach might combine subject and body.

        message = subject # For now, use subject as the main message

        node = CommitNode(
            sha=sha,
            message=message,
            author_name=author_name,
            author_email=author_email,
            author_date=author_date
        )

        if parent_hashes_str:
            node.parents = parent_hashes_str.split()

        node.references = _parse_references(raw_refs)

        commits_map[sha] = node
        commit_list_ordered.append(node)

    # Populate children information
    for sha, node in commits_map.items():
        for parent_sha in node.parents:
            if parent_sha in commits_map:
                parent_node = commits_map[parent_sha]
                parent_node.children.append(sha)
            # Else: parent is outside the fetched log range (e.g. --max-count)

    return commit_list_ordered

if __name__ == '__main__':
    # Example usage:
    # Create a dummy git repository for testing if one doesn't exist
    # For a real test, run this script from within a git repository directory

    # Simple test with the current directory
    print(f"Attempting to parse git log for repository: {os.getcwd()}")
    commit_nodes = parse_git_log(".") # Use current directory

    if commit_nodes:
        print(f"Successfully parsed {len(commit_nodes)} commits.")
        for i, node in enumerate(commit_nodes[:5]): # Print first 5 commits
            print(f"--- Commit {i+1} ---")
            print(f"  SHA: {node.sha}")
            print(f"  Parents: {node.parents}")
            print(f"  Children: {node.children}")
            print(f"  References: {node.references}")
            print(f"  Author: {node.author_name} <{node.author_email}> on {node.author_date}")
            print(f"  Message: {node.message}")
        if len(commit_nodes) > 5:
            print("...")
    else:
        print("No commits parsed. Ensure you are in a git repository or provide a valid path.")

    # To test with a specific known repository (if you have one cloned):
    # test_repo_path = "../some-other-repo" # Adjust path as needed
    # if os.path.isdir(os.path.join(test_repo_path, ".git")):
    #     print(f"Attempting to parse git log for repository: {test_repo_path}")
    #     commit_nodes_specific = parse_git_log(test_repo_path)
    #     if commit_nodes_specific:
    #         print(f"Successfully parsed {len(commit_nodes_specific)} commits from {test_repo_path}.")
    #         # print(commit_nodes_specific[0])
    #     else:
    #         print(f"No commits parsed from {test_repo_path}.")
    # else:
    #     print(f"Test repository path {test_repo_path} not found or not a git repository.")
