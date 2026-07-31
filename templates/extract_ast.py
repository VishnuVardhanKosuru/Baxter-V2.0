#!/usr/bin/env python3
import os
import json
import argparse
from pathlib import Path
import tree_sitter

# Tree-sitter setup
try:
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_java
    import tree_sitter_go
    import tree_sitter_ruby
except ImportError:
    print("Warning: Some tree-sitter grammars not installed.")

# Language mapping
LANG_MAP = {
    ".py": ("python", tree_sitter_python),
    ".js": ("javascript", tree_sitter_javascript),
    ".jsx": ("javascript", tree_sitter_javascript),
    ".ts": ("typescript", tree_sitter_typescript),
    ".tsx": ("tsx", tree_sitter_typescript),
    ".java": ("java", tree_sitter_java),
    ".go": ("go", tree_sitter_go),
    ".rb": ("ruby", tree_sitter_ruby)
}

def get_parser(ext):
    if ext not in LANG_MAP:
        return None, None
    lang_name, module = LANG_MAP[ext]
    try:
        language = tree_sitter.Language(module.language())
        parser = tree_sitter.Parser(language)
        return lang_name, parser
    except AttributeError:
        try:
             language = tree_sitter.Language(module.language(), lang_name)
             parser = tree_sitter.Parser()
             parser.set_language(language)
             return lang_name, parser
        except Exception:
             return None, None
    except Exception:
        return None, None

def extract_node_text(node, source_bytes):
    if not node: return ""
    return source_bytes[node.start_byte:node.end_byte].decode('utf8', 'ignore')

def process_python(tree, source_bytes, rel_path, all_nodes, all_edges):
    file_id = f"file://{rel_path}"
    
    def traverse(node, current_context_id=None):
        if node.type == 'function_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = extract_node_text(name_node, source_bytes)
                func_id = f"func://{rel_path}/{func_name}"
                
                params = []
                params_node = node.child_by_field_name('parameters')
                if params_node:
                    for child in params_node.children:
                        if child.type in ('identifier', 'typed_parameter'):
                            params.append(extract_node_text(child, source_bytes))
                            
                docstring = ""
                body_node = node.child_by_field_name('body')
                if body_node and body_node.children:
                    first_stmt = body_node.children[0]
                    if first_stmt.type == 'expression_statement':
                        string_node = first_stmt.children[0]
                        if string_node.type == 'string':
                            docstring = extract_node_text(string_node, source_bytes).strip('\'"')
                            
                decorators = []
                for child in node.children:
                    if child.type == 'decorator':
                        decorators.append(extract_node_text(child, source_bytes))

                all_nodes.append({
                    "id": func_id,
                    "type": "FUNCTION",
                    "name": func_name,
                    "file": rel_path,
                    "parameters": params,
                    "docstring": docstring,
                    "decorators": decorators,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1
                })
                
                all_edges.append({"source": file_id, "target": func_id, "type": "DEFINES"})
                if current_context_id:
                    all_edges.append({"source": current_context_id, "target": func_id, "type": "CONTAINS"})
                
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_context_id=func_id)
                return

        elif node.type == 'class_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = extract_node_text(name_node, source_bytes)
                class_id = f"class://{rel_path}/{class_name}"
                
                all_nodes.append({
                    "id": class_id,
                    "type": "CLASS",
                    "name": class_name,
                    "file": rel_path,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1
                })
                all_edges.append({"source": file_id, "target": class_id, "type": "DEFINES"})
                
                body_node = node.child_by_field_name('body')
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_context_id=class_id)
                return
                
        elif node.type == 'call' and current_context_id:
            func_node = node.child_by_field_name('function')
            if func_node:
                called_name = extract_node_text(func_node, source_bytes)
                all_edges.append({
                    "source": current_context_id,
                    "target": called_name,
                    "type": "CALLS"
                })
                
        for child in node.children:
            traverse(child, current_context_id)
            
    traverse(tree.root_node)

def process_js_ts(tree, source_bytes, rel_path, all_nodes, all_edges):
    file_id = f"file://{rel_path}"
    
    def traverse(node, current_context_id=None):
        if node.type in ('function_declaration', 'method_definition', 'arrow_function'):
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = extract_node_text(name_node, source_bytes)
                func_id = f"func://{rel_path}/{func_name}"
                
                params = []
                params_node = node.child_by_field_name('parameters')
                if params_node:
                    for child in params_node.children:
                        if child.type in ('identifier', 'formal_parameters', 'required_parameter'):
                            params.append(extract_node_text(child, source_bytes))

                all_nodes.append({
                    "id": func_id,
                    "type": "FUNCTION",
                    "name": func_name,
                    "file": rel_path,
                    "parameters": params,
                    "docstring": "",
                    "decorators": [],
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1
                })
                all_edges.append({"source": file_id, "target": func_id, "type": "DEFINES"})
                
                body_node = node.child_by_field_name('body')
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_context_id=func_id)
                return
                
        elif node.type == 'call_expression' and current_context_id:
            func_node = node.child_by_field_name('function')
            if func_node:
                called_name = extract_node_text(func_node, source_bytes)
                all_edges.append({
                    "source": current_context_id,
                    "target": called_name,
                    "type": "CALLS"
                })
                
        for child in node.children:
            traverse(child, current_context_id)
            
    traverse(tree.root_node)

def process_java(tree, source_bytes, rel_path, all_nodes, all_edges):
    file_id = f"file://{rel_path}"
    
    def traverse(node, current_context_id=None):
        if node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = extract_node_text(name_node, source_bytes)
                class_id = f"class://{rel_path}/{class_name}"
                
                all_nodes.append({
                    "id": class_id,
                    "type": "CLASS",
                    "name": class_name,
                    "file": rel_path,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1
                })
                source_id = current_context_id or file_id
                all_edges.append({"source": source_id, "target": class_id, "type": "DEFINES"})
                
                body_node = node.child_by_field_name('body')
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_context_id=class_id)
                return

        elif node.type == 'method_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = extract_node_text(name_node, source_bytes)
                func_id = f"func://{rel_path}/{func_name}"
                
                params = []
                params_node = node.child_by_field_name('parameters')
                if params_node:
                    params = [extract_node_text(c, source_bytes) for c in params_node.children if c.is_named]

                all_nodes.append({
                    "id": func_id,
                    "type": "FUNCTION",
                    "name": func_name,
                    "file": rel_path,
                    "parameters": params,
                    "docstring": "",
                    "decorators": [],
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1
                })
                source_id = current_context_id or file_id
                all_edges.append({"source": source_id, "target": func_id, "type": "DEFINES"})
                
                body_node = node.child_by_field_name('body')
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_context_id=func_id)
                return
                
        elif node.type == 'method_invocation' and current_context_id:
            name_node = node.child_by_field_name('name')
            if name_node:
                called_name = extract_node_text(name_node, source_bytes)
                all_edges.append({
                    "source": current_context_id,
                    "target": called_name,
                    "type": "CALLS"
                })
                
        for child in node.children:
            traverse(child, current_context_id)
            
    traverse(tree.root_node)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help="Output JSON file path")
    args = parser.parse_args()

    all_nodes = []
    all_edges = []
    
    for root, _, files in os.walk('.'):
        if '.git' in root:
            continue
            
        for file in files:
            path = Path(root) / file
            ext = path.suffix
            
            lang_name, ts_parser = get_parser(ext)
            if not ts_parser:
                continue
                
            try:
                with open(path, 'rb') as f:
                    source_bytes = f.read()
            except Exception as e:
                print(f"Skipping {path}: {e}")
                continue
                
            tree = ts_parser.parse(source_bytes)
            rel_path = str(path.relative_to('.')).replace('\\', '/')
            
            # Add file node
            all_nodes.append({
                "id": f"file://{rel_path}",
                "type": "FILE",
                "name": path.name,
                "properties": {
                    "language": lang_name,
                    "size_bytes": len(source_bytes),
                }
            })
            
            if lang_name == "python":
                process_python(tree, source_bytes, rel_path, all_nodes, all_edges)
            elif lang_name in ("javascript", "typescript", "tsx"):
                process_js_ts(tree, source_bytes, rel_path, all_nodes, all_edges)
            elif lang_name == "java":
                process_java(tree, source_bytes, rel_path, all_nodes, all_edges)
            else:
                pass

    graph = {
        "nodes": all_nodes,
        "edges": all_edges
    }

    with open(args.output, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"Extracted AST Graph: {len(all_nodes)} nodes, {len(all_edges)} edges to {args.output}")

if __name__ == "__main__":
    main()
