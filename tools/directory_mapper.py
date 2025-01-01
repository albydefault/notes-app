from pathlib import Path
import argparse
import sys
from typing import List, Set

class DirectoryMapper:
    def __init__(self, ignore_patterns: Set[str] = None):
        self.ignore_patterns = ignore_patterns or {
            '__pycache__', '.git', '.idea', '.vscode', 
            '.env', 'venv', 'node_modules', '.pytest_cache',
            '.coverage', 'htmlcov', '*.pyc', '*.pyo', '*.pyd',
            '.DS_Store', 'Thumbs.db', 'data'
        }
        
    def should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored based on patterns."""
        return any(
            pattern in path.parts or 
            (pattern.startswith('*.') and path.suffix == pattern[1:])
            for pattern in self.ignore_patterns
        )
    
    def map_directory(self, root_path: Path, prefix: str = '', level: int = 0) -> List[str]:
        """Recursively map directory structure."""
        if self.should_ignore(root_path):
            return []
            
        result = []
        
        # Add current directory/file
        if level > 0:  # Don't add root directory as an entry
            is_last = prefix.endswith('└── ')
            indent = '    ' if is_last else '│   '
            result.append(f"{prefix}{root_path.name}")
            prefix = prefix.replace('└── ', indent).replace('├── ', indent)
        
        if root_path.is_dir():
            # Get all items in directory
            items = sorted(root_path.iterdir(), 
                         key=lambda x: (x.is_file(), x.name.lower()))
            
            # Filter out ignored items
            items = [item for item in items if not self.should_ignore(item)]
            
            # Process each item
            for i, item in enumerate(items):
                is_last_item = i == len(items) - 1
                new_prefix = prefix + ('└── ' if is_last_item else '├── ')
                result.extend(self.map_directory(item, new_prefix, level + 1))
        
        return result

def generate_directory_map(directory: str = ".", 
                         output_file: str = "directory_map.txt",
                         additional_ignores: List[str] = None) -> None:
    """Generate and save a directory map."""
    root = Path(directory).resolve()
    
    # Create mapper with combined ignore patterns
    ignore_patterns = set()
    if additional_ignores:
        ignore_patterns.update(additional_ignores)
    
    mapper = DirectoryMapper(ignore_patterns)
    
    # Generate map
    directory_map = mapper.map_directory(root)
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(directory_map))
        
    print(f"Directory map saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a directory structure map")
    parser.add_argument("--directory", "-d", default=".", 
                       help="Root directory to map (default: current directory)")
    parser.add_argument("--output", "-o", default="directory_map.txt",
                       help="Output file name (default: directory_map.txt)")
    parser.add_argument("--ignore", "-i", nargs="*", default=[],
                       help="Additional patterns to ignore")
    
    args = parser.parse_args()
    
    try:
        generate_directory_map(args.directory, args.output, args.ignore)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)