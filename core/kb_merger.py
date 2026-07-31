import json
from typing import Dict, List, Any
from datetime import datetime

class KBMerger:
    @staticmethod
    def merge(repo: str, ast_data: Dict[str, Any], sarif_data_list: List[Dict]) -> Dict[str, Any]:
        """Merge AST graph data and SARIF findings into the final KB Graph format."""
        
        nodes = ast_data.get("nodes", [])
        edges = ast_data.get("edges", [])
        
        kb = {
            "repo": repo,
            "scanned_at": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "total_vulnerabilities": 0,
            },
            "nodes": nodes,
            "edges": edges
        }

        # Index nodes by ID and name for fast lookup
        nodes_by_id = {n["id"]: n for n in nodes}
        func_nodes_by_name = {n.get("name"): n for n in nodes if n["type"] == "FUNCTION"}
        
        # 1. Resolve raw name target edges
        resolved_edges = []
        for edge in edges:
            if edge["type"] == "CALLS" and "://" not in edge["target"]:
                target_node = func_nodes_by_name.get(edge["target"])
                if target_node:
                    edge["target"] = target_node["id"]
                    resolved_edges.append(edge)
                # If we can't resolve it, it might be a built-in or external call, we can keep it as is or drop it.
                # Let's keep it as is for external context.
                else:
                    resolved_edges.append(edge)
            else:
                resolved_edges.append(edge)
                
        kb["edges"] = resolved_edges

        # 2. Process SARIF data
        for sarif in sarif_data_list:
            for run in sarif.get("runs", []):
                for result in run.get("results", []):
                    rule_id = result.get("ruleId")
                    message = result.get("message", {}).get("text")
                    level = result.get("level", "warning")
                    
                    cwe = ""
                    rule_index = result.get("ruleIndex", -1)
                    if rule_index >= 0:
                        try:
                            rule_meta = run["tool"]["driver"]["rules"][rule_index]
                            if "properties" in rule_meta and "tags" in rule_meta["properties"]:
                                cwes = [t for t in rule_meta["properties"]["tags"] if "external/cwe/" in t]
                                if cwes:
                                    cwe = cwes[0].split("/")[-1]
                        except IndexError:
                            pass

                    for location in result.get("locations", []):
                        phys_loc = location.get("physicalLocation", {})
                        art_loc = phys_loc.get("artifactLocation", {})
                        uri = art_loc.get("uri")
                        
                        if uri:
                            uri = uri.replace("\\", "/")
                            if uri.startswith("/"):
                                uri = uri[1:]

                            line = phys_loc.get("region", {}).get("startLine", -1)
                            
                            vuln = {
                                "rule_id": rule_id,
                                "level": level,
                                "cwe": cwe,
                                "message": message,
                                "line": line
                            }
                            
                            kb["summary"]["total_vulnerabilities"] += 1
                            
                            # Find the best node to attach this vulnerability to
                            attached = False
                            
                            # Try to find a function node that encompasses this line in this file
                            for node in nodes:
                                if node.get("file") == uri and node["type"] in ("FUNCTION", "CLASS"):
                                    line_start = node.get("line_start", -1)
                                    line_end = node.get("line_end", float('inf'))
                                    if line_start <= line <= line_end:
                                        node.setdefault("properties", {}).setdefault("vulnerabilities", []).append(vuln)
                                        attached = True
                                        break
                                        
                            # Fallback to the file node
                            if not attached:
                                file_id = f"file://{uri}"
                                file_node = nodes_by_id.get(file_id)
                                if file_node:
                                    file_node.setdefault("properties", {}).setdefault("vulnerabilities", []).append(vuln)
                                else:
                                    # Create file node if it somehow doesn't exist
                                    new_node = {
                                        "id": file_id,
                                        "type": "FILE",
                                        "name": uri.split("/")[-1],
                                        "properties": {"vulnerabilities": [vuln]}
                                    }
                                    nodes.append(new_node)
                                    nodes_by_id[file_id] = new_node

        return kb
