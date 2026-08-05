import sys
import os
import json
import argparse

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Knowledge Graph</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js" crossorigin="anonymous"></script>
    <style type="text/css">
        body, html { margin: 0; padding: 0; width: 100%; height: 100%; background-color: #ffffff; overflow: hidden; font-family: sans-serif; }
        #mynetwork { width: 100%; height: 100%; }
    </style>
</head>
<body>
<div id="mynetwork"></div>
<div id="errorBox" style="color:red; background:white; position:absolute; top:0; left:0; z-index:9999; padding:20px; display:none; font-weight:bold;"></div>

<script id="nodes-data" type="application/json">
XXX_NODES_XXX
</script>
<script id="edges-data" type="application/json">
XXX_EDGES_XXX
</script>

<script type="text/javascript">
    window.onerror = function(msg, url, lineNo, columnNo, error) {
        var errBox = document.getElementById("errorBox");
        errBox.style.display = "block";
        errBox.innerHTML += "JS Error: " + msg + " at line " + lineNo + "<br>";
        return false;
    };
    
    var nodesData = JSON.parse(document.getElementById("nodes-data").textContent);
    var edgesData = JSON.parse(document.getElementById("edges-data").textContent);
    var nodes = new vis.DataSet(nodesData);
    var edges = new vis.DataSet(edgesData);
    var container = document.getElementById('mynetwork');
    var data = { nodes: nodes, edges: edges };
    var options = {
      layout: {
        hierarchical: {
          enabled: false,
          direction: "UD",
          sortMethod: "directed",
          nodeSpacing: 200,
          treeSpacing: 250,
          levelSeparation: 150
        }
      },
      edges: {
        smooth: { type: "cubicBezier", forceDirection: "none", roundness: 0.4 },
        color: { color: "#000000", highlight: "#444444" },
        width: 1.5,
        arrows: { to: { enabled: true, scaleFactor: 0.5 } }
      },
      physics: {
        barnesHut: {
          gravitationalConstant: -10000,
          centralGravity: 0.3,
          springLength: 150,
          springConstant: 0.04,
          damping: 0.09,
          avoidOverlap: 0.2
        },
        minVelocity: 0.75,
        solver: "barnesHut"
      }
    };
    var network = new vis.Network(container, data, options);
</script>
</body>
</html>
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help="Input kb.json file path")
    parser.add_argument('--output', default='graph.html', help="Output HTML file path")
    args = parser.parse_args()

    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {args.input}: {e}")
        return

    # Calculate in-degree for functions
    in_degrees = {}
    for edge in data.get('edges', []):
        in_degrees[edge['target']] = in_degrees.get(edge['target'], 0) + 1

    valid_node_ids = set()
    vis_nodes = []
    for node in data.get('nodes', []):
        node_id = node.get('id')
        if not node_id: continue
        
        valid_node_ids.add(node_id)
            
        node_type = node.get('type', 'UNKNOWN')
        label = f"{node_type}\\n{node.get('name', 'unnamed')}"
        
        shape = "dot"
        size = 15
        font_size = 14
        border_width = 2
        color = "#673ab7" # Deep Purple for functions
        
        if node_type == "FILE":
            color = "#ffb347" # orange
            shape = "box"
            font_size = 20
        elif node_type == "CLASS":
            color = "#77dd77" # green
            shape = "diamond"
            size = 25
            font_size = 18
        elif node_type == "FUNCTION":
            indeg = in_degrees.get(node_id, 0)
            size = min(40, 15 + (indeg * 5))
            
        title = json.dumps(node, indent=2)
        if node.get("properties", {}).get("vulnerabilities"):
            color = "#ff6961"
            shape = "star"
            size = 40
            border_width = 4
            title = "VULNERABLE!\\n\\n" + title

        vis_nodes.append({
            "id": node_id,
            "label": label,
            "title": title,
            "color": color,
            "shape": shape,
            "size": size,
            "borderWidth": border_width,
            "font": {"size": font_size, "color": "#333333"}
        })

    vis_edges = []
    for edge in data.get('edges', []):
        source = edge.get('source')
        target = edge.get('target')
        if not source or not target: continue
        
        # Prevent vis.js crash: Only add edge if both nodes actually exist in our dataset
        if source not in valid_node_ids or target not in valid_node_ids:
            continue
            
        vis_edges.append({
            "from": source,
            "to": target,
            "label": edge.get('type', '')
        })

    html_out = HTML_TEMPLATE.replace("XXX_NODES_XXX", json.dumps(vis_nodes)).replace("XXX_EDGES_XXX", json.dumps(vis_edges))
    
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_out)
        
    print(f"Graph visualization saved to {args.output}")

if __name__ == "__main__":
    main()
