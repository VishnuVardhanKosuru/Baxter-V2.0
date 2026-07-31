import os
import argparse
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
from core.github_client import GitHubClient

def build_tree_string(tree_data, prefix=""):
    """
    Recursively builds a string representation of the git tree.
    (This is a simplified version, as the GitHub API returns a flat list with full paths when recursive=1 is used).
    """
    # Create a nested dictionary structure from the flat list
    file_tree = {}
    for item in tree_data:
        parts = item['path'].split('/')
        current = file_tree
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        
        if item['type'] == 'tree':
            if parts[-1] not in current or not isinstance(current[parts[-1]], dict):
                current[parts[-1]] = {}
        else:
            current[parts[-1]] = item['type']

    lines = []
    
    def print_tree(d, pfx=""):
        items = list(d.items())
        for i, (name, val) in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            
            if isinstance(val, dict):
                lines.append(f"{pfx}{connector}{name}/")
                extension = "    " if is_last else "│   "
                print_tree(val, pfx + extension)
            else:
                lines.append(f"{pfx}{connector}{name}")

    print_tree(file_tree)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='supriya-daita/LibraryManagementSystem', help="GitHub repo owner/name")
    parser.add_argument('--out', default='repo_structure.txt', help="Output text file path")
    args = parser.parse_args()

    load_dotenv()
    gh_pat = os.getenv("GITHUB_PAT")
    if not gh_pat:
         print("Ensure GITHUB_PAT is set in .env")
         return

    owner, repo_name = args.repo.split('/')
    gh_client = GitHubClient(gh_pat)
    
    print(f"Fetching repository structure for {args.repo}...")
    
    # 1. Get default branch latest commit
    try:
        latest_sha = gh_client.get_latest_commit(owner, repo_name)
    except Exception as e:
        print(f"Error fetching latest commit: {e}")
        return

    # 2. Get git tree recursively
    try:
        response = gh_client.get(f"/repos/{owner}/{repo_name}/git/trees/{latest_sha}?recursive=1")
        tree_items = response.get("tree", [])
    except Exception as e:
        print(f"Error fetching tree: {e}")
        return

    # 3. Build string and save
    tree_str = f"Repository Structure: {args.repo} (SHA: {latest_sha[:7]})\n"
    tree_str += "=" * 50 + "\n"
    tree_str += build_tree_string(tree_items)
    
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(tree_str)
        
    print(f"Successfully saved {len(tree_items)} items to {args.out}")

if __name__ == "__main__":
    main()
