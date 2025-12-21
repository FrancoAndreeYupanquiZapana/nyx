# setup.py (ponlo en la carpeta NYX/)
import os
import sys

def create_structure():
    """Crea estructura de carpetas mínima"""
    folders = [
        "src/core",
        "src/detectors/hands",
        "src/actions",
        "src/ui",
        "config",
        "assets"
    ]
    
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"✓ {folder}")
    
    # Crear __init__.py vacíos
    init_files = [
        "src/__init__.py",
        "src/core/__init__.py",
        "src/detectors/__init__.py",
        "src/detectors/hands/__init__.py",
        "src/actions/__init__.py",
        "src/ui/__init__.py"
    ]
    
    for init_file in init_files:
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("# Auto-generated\n")
            print(f"✓ {init_file}")
    
    print("\n✅ Estructura lista!")
    print("\nEjecuta:")
    print("  python src/main.py")

if __name__ == "__main__":
    create_structure()