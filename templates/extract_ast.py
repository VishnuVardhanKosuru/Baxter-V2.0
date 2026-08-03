#!/usr/bin/env python3
import os
import json
import argparse
from pathlib import Path
import tree_sitter

# Tree-sitter setup
LANG_MAP = {}

try:
    import tree_sitter_python
    LANG_MAP[".py"] = ("python", tree_sitter_python)
except ImportError: pass

try:
    import tree_sitter_javascript
    LANG_MAP[".js"] = ("javascript", tree_sitter_javascript)
    LANG_MAP[".jsx"] = ("javascript", tree_sitter_javascript)
except ImportError: pass

try:
    import tree_sitter_typescript
    LANG_MAP[".ts"] = ("typescript", tree_sitter_typescript)
    LANG_MAP[".tsx"] = ("tsx", tree_sitter_typescript)
except ImportError: pass

try:
    import tree_sitter_java
    LANG_MAP[".java"] = ("java", tree_sitter_java)
except ImportError: pass

try:
    import tree_sitter_go
    LANG_MAP[".go"] = ("go", tree_sitter_go)
except ImportError: pass

try:
    import tree_sitter_ruby
    LANG_MAP[".rb"] = ("ruby", tree_sitter_ruby)
except ImportError: pass

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
                    "line_end": node.end_point[0] + 1,
                    "body": extract_node_text(node, source_bytes)
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
                    "line_end": node.end_point[0] + 1,
                    "body": extract_node_text(node, source_bytes)
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
    
    def extract_annotations(node):
        annotations = []
        for child in node.children:
            if child.type in ('marker_annotation', 'annotation'):
                annotations.append(extract_node_text(child, source_bytes))
            elif child.type == 'modifiers':
                for mod_child in child.children:
                    if mod_child.type in ('marker_annotation', 'annotation'):
                        annotations.append(extract_node_text(mod_child, source_bytes))
        return annotations

    def traverse(node, current_context_id=None, current_class_name=""):
        if node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                class_name = extract_node_text(name_node, source_bytes)
                class_id = f"class://{rel_path}/{class_name}"
                
                class_annotations = extract_annotations(node)
                fields = []
                constructors = []
                
                body_node = node.child_by_field_name('body')
                if body_node:
                    for child in body_node.children:
                        if child.type == 'field_declaration':
                            field_type_node = child.child_by_field_name('type')
                            type_str = extract_node_text(field_type_node, source_bytes) if field_type_node else ""
                            declarator = child.child_by_field_name('declarator')
                            if declarator:
                                var_name_node = declarator.child_by_field_name('name')
                                name_str = extract_node_text(var_name_node, source_bytes) if var_name_node else extract_node_text(declarator, source_bytes)
                            else:
                                name_str = extract_node_text(child, source_bytes)
                            fields.append({"name": name_str, "type": type_str})
                        elif child.type == 'constructor_declaration':
                            c_params = []
                            c_params_node = child.child_by_field_name('parameters')
                            if c_params_node:
                                c_params = [extract_node_text(c, source_bytes) for c in c_params_node.children if c.is_named]
                            constructors.append({"params": c_params})

                # Check preceding comment for class Javadoc, walking back past annotations
                class_javadoc = ""
                curr = node.prev_sibling
                while curr:
                    if curr.type in ('block_comment', 'comment'):
                        comm_text = extract_node_text(curr, source_bytes)
                        if comm_text.startswith("/**"):
                            class_javadoc = comm_text
                        break
                    elif curr.type in ('package_declaration', 'import_declaration', 'class_declaration', 'interface_declaration', 'enum_declaration'):
                        break
                    curr = curr.prev_sibling

                all_nodes.append({
                    "id": class_id,
                    "type": "CLASS",
                    "name": class_name,
                    "file": rel_path,
                    "annotations": class_annotations,
                    "fields": fields,
                    "constructors": constructors,
                    "javadoc": class_javadoc,
                    "docstring": class_javadoc,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1
                })
                source_id = current_context_id or file_id
                all_edges.append({"source": source_id, "target": class_id, "type": "DEFINES"})
                
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_context_id=class_id, current_class_name=class_name)
                return

        elif node.type == 'method_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = extract_node_text(name_node, source_bytes)
                func_id = f"func://{rel_path}/{func_name}"
                
                return_type_node = node.child_by_field_name('type')
                return_type = extract_node_text(return_type_node, source_bytes) if return_type_node else ""

                params = []
                params_node = node.child_by_field_name('parameters')
                if params_node:
                    params = [extract_node_text(c, source_bytes) for c in params_node.children if c.is_named]

                method_annotations = extract_annotations(node)

                throws_list = []
                for child in node.children:
                    if child.type == 'throws':
                        for t_child in child.children:
                            if t_child.is_named:
                                throws_list.append(extract_node_text(t_child, source_bytes))

                # Check preceding comment for Javadoc, walking back past annotations
                javadoc = ""
                curr = node.prev_sibling
                while curr:
                    if curr.type in ('block_comment', 'comment'):
                        comm_text = extract_node_text(curr, source_bytes)
                        if comm_text.startswith("/**"):
                            javadoc = comm_text
                        break
                    elif curr.type in ('field_declaration', 'method_declaration', 'constructor_declaration', 'class_declaration'):
                        break
                    curr = curr.prev_sibling

                all_nodes.append({
                    "id": func_id,
                    "type": "FUNCTION",
                    "name": func_name,
                    "file": rel_path,
                    "class_name": current_class_name,
                    "return_type": return_type,
                    "parameters": params,
                    "annotations": method_annotations,
                    "throws": throws_list,
                    "javadoc": javadoc,
                    "docstring": javadoc,
                    "decorators": method_annotations,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                    "body": extract_node_text(node, source_bytes)
                })
                source_id = current_context_id or file_id
                all_edges.append({"source": source_id, "target": func_id, "type": "DEFINES"})
                
                body_node = node.child_by_field_name('body')
                if body_node:
                    for child in body_node.children:
                        traverse(child, current_context_id=func_id, current_class_name=current_class_name)
                return
                
        elif node.type == 'method_invocation' and current_context_id:
            name_node = node.child_by_field_name('name')
            object_node = node.child_by_field_name('object')
            args_node = node.child_by_field_name('arguments')
            
            if name_node:
                called_name = extract_node_text(name_node, source_bytes)
                obj_name = extract_node_text(object_node, source_bytes) if object_node else ""
                args_list = []
                if args_node:
                    args_list = [extract_node_text(c, source_bytes) for c in args_node.children if c.is_named]
                
                all_edges.append({
                    "source": current_context_id,
                    "target": called_name,
                    "object": obj_name,
                    "arguments": args_list,
                    "type": "CALLS"
                })
                
        for child in node.children:
            traverse(child, current_context_id, current_class_name)
            
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
