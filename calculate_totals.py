import os
import re
from collections import defaultdict

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(base_dir, "output", "cost_tracking.txt")
    out_file = os.path.join(base_dir, "output", "cost_totals.txt")

    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return

    # metrics structure: totals[key_alias][phase] = {"in": 0, "out": 0, "cost": 0.0}
    totals = defaultdict(lambda: defaultdict(lambda: {"in": 0, "out": 0, "cost": 0.0}))

    line_pattern = re.compile(
        r"\[.*?\]\s+"
        r"(?:\[(.*?)\]\s+)?"                # Optional phase [Parser] or [Generator]
        r"Model:\s+.*?\((.*?)\)\s+\|\s+"    # Key alias inside parenthesis
        r"Tokens:\s+(\d+)\s+In,\s+(\d+)\s+Out\s+\|\s+"
        r"Cost:\s+\$([\d\.]+)"
    )

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            m = line_pattern.search(line)
            if m:
                phase = m.group(1) or "Generator"
                key = m.group(2)
                in_toks = int(m.group(3))
                out_toks = int(m.group(4))
                cost = float(m.group(5))

                totals[key][phase]["in"] += in_toks
                totals[key][phase]["out"] += out_toks
                totals[key][phase]["cost"] += cost

    if not totals:
        print("No parsable data found in log file.")
        return

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("="*50 + "\n")
        f.write("           COST & TOKEN TOTALS\n")
        f.write("="*50 + "\n\n")

        grand_cost = 0.0
        
        for key, phases in totals.items():
            f.write(f"--- {key} ---\n")
            key_cost = 0.0
            for phase, metrics in phases.items():
                f.write(f"  [{phase}]\n")
                f.write(f"    Input Tokens : {metrics['in']:,}\n")
                f.write(f"    Output Tokens: {metrics['out']:,}\n")
                f.write(f"    Phase Cost   : ${metrics['cost']:.6f}\n\n")
                key_cost += metrics["cost"]
            f.write(f"  > Total {key} Cost: ${key_cost:.6f}\n\n")
            grand_cost += key_cost
            
        f.write("="*50 + "\n")
        f.write(f"GRAND TOTAL COST: ${grand_cost:.6f}\n")
        f.write("="*50 + "\n")

    print(f"Calculated totals and saved to {out_file}")

if __name__ == "__main__":
    main()
