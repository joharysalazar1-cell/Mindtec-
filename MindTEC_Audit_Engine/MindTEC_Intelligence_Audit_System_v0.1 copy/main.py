from pathlib import Path
import argparse
from src.audit_engine import run_profile

def main():
    parser = argparse.ArgumentParser(description="MindTEC independent data audit")
    parser.add_argument("--file", required=True, help="Ruta CSV o XLSX")
    args = parser.parse_args()
    result_path = run_profile(Path(args.file))
    print(f"\nAuditoría terminada. Resultados: {result_path}")

if __name__ == "__main__":
    main()
