import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class KBMerger:
    @staticmethod
    def merge(repo: str, ast_data: Dict[str, Any], sarif_data_list: Optional[List[Dict]] = None, structural_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Merge AST graph data, structural CodeQL data, and SARIF findings into the final KB Graph format."""
        
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
        class_nodes_by_name = {n.get("name"): n for n in nodes if n["type"] == "CLASS"}
        func_nodes_by_name = {n.get("name"): n for n in nodes if n["type"] == "FUNCTION"}
        
        # 1. Resolve Class Roles & attach to Class and Function nodes
        for node in nodes:
            if node["type"] == "CLASS":
                annotations = [a.upper() for a in node.get("annotations", [])]
                ann_str = " ".join(annotations)
                if "SERVICE" in ann_str:
                    node["class_role"] = "SERVICE"
                elif "REPOSITORY" in ann_str or "MAPPER" in ann_str:
                    node["class_role"] = "REPOSITORY"
                elif "CONTROLLER" in ann_str or "RESTCONTROLLER" in ann_str:
                    node["class_role"] = "CONTROLLER"
                elif "ENTITY" in ann_str or "TABLE" in ann_str:
                    node["class_role"] = "ENTITY"
                elif "COMPONENT" in ann_str or "BEAN" in ann_str:
                    node["class_role"] = "COMPONENT"
                else:
                    node["class_role"] = "GENERAL"

        for node in nodes:
            if node["type"] == "FUNCTION":
                c_name = node.get("class_name")
                if c_name and c_name in class_nodes_by_name:
                    node["class_role"] = class_nodes_by_name[c_name].get("class_role", "GENERAL")
                    node["class_annotations"] = class_nodes_by_name[c_name].get("annotations", [])

        # 2. Resolve raw name target edges
        resolved_edges = []
        for edge in edges:
            if edge["type"] == "CALLS" and "://" not in edge["target"]:
                target_node = func_nodes_by_name.get(edge["target"])
                if target_node:
                    edge["target"] = target_node["id"]
                    resolved_edges.append(edge)
                else:
                    resolved_edges.append(edge)
            else:
                resolved_edges.append(edge)
                
        kb["edges"] = resolved_edges

        # 3. Merge CodeQL Structural Data (if available)
        if structural_data:
            # Method signatures
            for sig in structural_data.get("method_signatures", []):
                m_name = sig.get("method_name")
                ret_type = sig.get("return_type")
                if m_name and m_name in func_nodes_by_name:
                    func_nodes_by_name[m_name]["return_type_qualified"] = ret_type

            # Call graph
            for call in structural_data.get("call_graph", []):
                callee_method = call.get("callee_method")
                callee_class = call.get("callee_class")
                callee_ret = call.get("callee_return_type")
                for edge in kb["edges"]:
                    if edge["type"] == "CALLS" and (edge["target"] == callee_method or edge["target"].endswith("/" + str(callee_method))):
                        edge["callee_class"] = callee_class
                        edge["callee_return_type"] = callee_ret

            # Annotation values
            for ann in structural_data.get("annotation_values", []):
                m_name = ann.get("method_name")
                if m_name and m_name in func_nodes_by_name:
                    func_nodes_by_name[m_name].setdefault("annotation_values", []).append({
                        "annotation": ann.get("annotation_name"),
                        "element": ann.get("element_name"),
                        "value": ann.get("element_value")
                    })

        # 4. PAUSED: Process SARIF vulnerability data (commented out)
        # if sarif_data_list:
        #     for sarif in sarif_data_list:
        #         for run in sarif.get("runs", []):
        #             for result in run.get("results", []):
        #                 ...

        return kb
