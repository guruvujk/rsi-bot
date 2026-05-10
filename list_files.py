import os

def print_tree(startpath):
    print(f"\n📂 Current Structure: {os.path.basename(os.getcwd())}")
    print("=" * 40)
    for root, dirs, files in os.walk(startpath):
        # Ignore the virtual environment folder to keep it clean
        if 'venv' in dirs:
            dirs.remove('venv')
        if '.git' in dirs:
            dirs.remove('.git')
            
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print(f'{indent}├── {os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print(f'{subindent}└── {f}')

if __name__ == "__main__":
    print_tree(os.getcwd())