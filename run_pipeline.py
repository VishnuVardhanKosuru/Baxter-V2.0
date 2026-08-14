from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import sys
import litellm
from pathlib import Path

# Ensure agents is in path
BASE_DIR = Path(__file__).parent.resolve()
AGENTS_DIR = BASE_DIR / "agents"
if str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from doc_parser import parse_documents
from core.cs_agent import run_agent

def main():
    modules_dir = str(BASE_DIR / "input_modules")
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)
    
    print("="*60)
    print("  Stage 1: Parsing Documents")
    print("="*60)
    litellm.current_phase = "Parser"
    # The parse_documents function is synchronous
    json_paths = parse_documents(modules_dir, out_dir)
    print(f"Parsed {len(json_paths)} module JSON files.")
    
    print("\n" + "="*60)
    print("  Stage 2: Generating Artifacts")
    print("="*60)
    litellm.current_phase = "Generator"
    for json_path in json_paths:
        if not json_path: continue
        # Create a unique output folder for this module based on the JSON filename
        basename = os.path.basename(json_path)
        module_name = basename.replace("_knowledge.json", "").replace(".json", "")
        module_out_dir = os.path.join(out_dir, module_name)
        
        print(f"\nProcessing Module: {module_name}")
        print(f"Outputting artifacts to: {module_out_dir}")
        
        run_agent(stage1_json_path=json_path, out_dir_path=module_out_dir)
        
    print("\nPipeline Complete!")

    print("\n" + "="*60)
    print("  Stage 3: Calculating Cost Totals")
    print("="*60)
    try:
        import calculate_totals
        calculate_totals.main()
    except Exception as e:
        print(f"Failed to calculate totals: {e}")

if __name__ == "__main__":
    main()
