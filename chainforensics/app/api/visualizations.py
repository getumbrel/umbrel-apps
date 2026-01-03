"""
ChainForensics - Visualizations API
Endpoints for generating visual representations of blockchain data.
"""
import logging
from typing import Optional, Dict, List
import json

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import HTMLResponse

from app.core.tracer import get_tracer
from app.core.timeline import get_timeline_generator
from app.core.bitcoin_rpc import get_rpc, BitcoinRPCError
from app.core.privacy_analysis import get_privacy_analyzer
from app.api.models import EnhancedPrivacyScore, RiskItem, AttackVector, FactorCategory

logger = logging.getLogger("chainforensics.api.visualizations")

router = APIRouter()


@router.get("/timeline/ascii")
async def get_ascii_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30),
    width: int = Query(100, ge=60, le=200)
):
    """
    Generate ASCII timeline visualization.
    
    Returns a text-based timeline showing UTXO flow with:
    - Date markers
    - Value bars
    - CoinJoin indicators
    - Flow connections
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        ascii_timeline = timeline_gen.generate_ascii_timeline(trace.to_dict(), width)
        
        return Response(
            content=ascii_timeline,
            media_type="text/plain; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"Error generating ASCII timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/html")
async def get_html_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30)
):
    """
    Generate interactive HTML timeline with D3.js.
    
    Returns a standalone HTML page with:
    - Visual timeline bars
    - Hover details
    - CoinJoin highlighting
    - Responsive design
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        html = timeline_gen.generate_html_timeline(trace.to_dict())
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        logger.error(f"Error generating HTML timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/mermaid")
async def get_mermaid_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30)
):
    """
    Generate Mermaid.js timeline diagram.
    
    Returns Mermaid markdown that can be rendered by compatible tools.
    Claude can render these diagrams directly.
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        mermaid = timeline_gen.generate_mermaid_timeline(trace.to_dict())
        
        return {
            "txid": txid,
            "direction": direction,
            "format": "mermaid",
            "diagram": mermaid
        }
        
    except Exception as e:
        logger.error(f"Error generating Mermaid timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/json")
async def get_json_timeline(
    txid: str,
    vout: int = Query(0, ge=0),
    direction: str = Query("forward", regex="^(forward|backward)$"),
    max_depth: int = Query(10, ge=1, le=30)
):
    """
    Generate timeline data as JSON.
    
    Returns structured data for custom visualization.
    """
    try:
        tracer = get_tracer()
        timeline_gen = get_timeline_generator()
        
        if direction == "forward":
            trace = await tracer.trace_forward(txid, vout, max_depth)
        else:
            trace = await tracer.trace_backward(txid, max_depth)
        
        timeline = timeline_gen.generate_timeline(trace.to_dict())
        
        return timeline.to_dict()
        
    except Exception as e:
        logger.error(f"Error generating JSON timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flow-diagram/mermaid")
async def get_mermaid_flow_diagram(
    txid: str,
    depth: int = Query(3, ge=1, le=10),
    direction: str = Query("both", regex="^(forward|backward|both)$")
):
    """
    Generate Mermaid flow diagram showing UTXO connections.
    
    Creates a graph visualization with:
    - Transaction nodes
    - UTXO edges with values
    - CoinJoin highlighting
    """
    try:
        rpc = get_rpc()
        tracer = get_tracer()
        
        lines = ["```mermaid", "graph LR"]
        
        tx = await rpc.get_raw_transaction(txid, True)
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction not found: {txid}")
        
        # Style definitions
        lines.append("    classDef coinjoin fill:#f85149,stroke:#da3633")
        lines.append("    classDef unspent fill:#238636,stroke:#2ea043")
        lines.append("    classDef coinbase fill:#a371f7,stroke:#8957e5")
        
        visited_txids = set()
        
        async def add_transaction_to_graph(tx_data: dict, current_depth: int, direction_flag: str):
            if current_depth > depth:
                return
            
            current_txid = tx_data.get("txid", "")
            if current_txid in visited_txids:
                return
            visited_txids.add(current_txid)
            
            short_txid = current_txid[:8]
            
            # Check CoinJoin
            from app.core.coinjoin import get_detector
            detector = get_detector()
            cj_result = detector.analyze_transaction(tx_data)
            is_coinjoin = cj_result.score > 0.5
            
            # Node styling
            node_class = ""
            if is_coinjoin:
                node_class = ":::coinjoin"
            
            # Add node
            node_label = f"{short_txid}"
            if is_coinjoin:
                node_label = f"🔀 {short_txid}"
            
            lines.append(f'    TX_{short_txid}["{node_label}"]{node_class}')
            
            # Process based on direction
            if direction_flag in ["backward", "both"]:
                # Add inputs
                for vin in tx_data.get("vin", [])[:5]:
                    if "coinbase" in vin:
                        cb_id = f"CB_{current_txid[:6]}"
                        lines.append(f'    {cb_id}["⛏️ Coinbase"]:::coinbase --> TX_{short_txid}')
                    elif "txid" in vin:
                        prev_txid = vin["txid"]
                        prev_short = prev_txid[:8]
                        lines.append(f'    TX_{prev_short} --> TX_{short_txid}')
            
            if direction_flag in ["forward", "both"]:
                # Add outputs
                for vout_data in tx_data.get("vout", [])[:5]:
                    value = vout_data.get("value", 0)
                    vout_idx = vout_data.get("n", 0)
                    
                    # Check if spent
                    utxo_status = await rpc.get_tx_out(current_txid, vout_idx)
                    
                    out_id = f"OUT_{short_txid}_{vout_idx}"
                    if utxo_status:
                        lines.append(f'    TX_{short_txid} --> {out_id}["{value:.4f} BTC"]:::unspent')
                    else:
                        lines.append(f'    TX_{short_txid} --> {out_id}["{value:.4f} BTC"]')
        
        await add_transaction_to_graph(tx, 0, direction)
        
        lines.append("```")
        
        return {
            "txid": txid,
            "depth": depth,
            "direction": direction,
            "format": "mermaid",
            "diagram": "\n".join(lines)
        }
        
    except Exception as e:
        logger.error(f"Error generating flow diagram: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/json")
async def get_graph_json(
    txid: str,
    direction: str = Query("both", regex="^(forward|backward|both)$"),
    max_depth: int = Query(5, ge=1, le=15)
):
    """
    Export UTXO graph as JSON for external visualization tools.
    
    Returns nodes and edges in a format compatible with:
    - D3.js force graphs
    - Gephi (convert to GraphML)
    - NetworkX
    """
    try:
        tracer = get_tracer()
        
        nodes = []
        edges = []
        node_ids = set()
        
        if direction in ["forward", "both"]:
            forward = await tracer.trace_forward(txid, 0, max_depth)
            for node in forward.nodes:
                if node.txid not in node_ids:
                    node_ids.add(node.txid)
                    nodes.append({
                        "id": node.txid,
                        "type": "transaction",
                        "value_btc": node.value_btc,
                        "status": node.status.value,
                        "coinjoin_score": node.coinjoin_score,
                        "block_height": node.block_height
                    })
            
            for edge in forward.edges:
                edges.append({
                    "source": edge.from_txid,
                    "target": edge.to_txid,
                    "value": edge.value_sats,
                    "vout": edge.from_vout,
                    "vin": edge.to_vin
                })
        
        if direction in ["backward", "both"]:
            backward = await tracer.trace_backward(txid, max_depth)
            for node in backward.nodes:
                if node.txid not in node_ids:
                    node_ids.add(node.txid)
                    nodes.append({
                        "id": node.txid,
                        "type": "coinbase" if node.status.value == "coinbase" else "transaction",
                        "value_btc": node.value_btc,
                        "status": node.status.value,
                        "coinjoin_score": node.coinjoin_score,
                        "block_height": node.block_height
                    })
            
            for edge in backward.edges:
                edge_id = f"{edge.from_txid}-{edge.to_txid}"
                if not any(f"{e['source']}-{e['target']}" == edge_id for e in edges):
                    edges.append({
                        "source": edge.from_txid,
                        "target": edge.to_txid,
                        "value": edge.value_sats,
                        "vout": edge.from_vout,
                        "vin": edge.to_vin
                    })
        
        return {
            "txid": txid,
            "direction": direction,
            "max_depth": max_depth,
            "graph": {
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating graph JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/html")
async def get_interactive_graph(
    txid: str,
    direction: str = Query("both", regex="^(forward|backward|both)$"),
    max_depth: int = Query(5, ge=1, le=10),
    show_communities: bool = Query(False, description="Color nodes by Louvain community")
):
    """
    Generate interactive force-directed graph visualization.

    With show_communities=true, nodes are colored by community clusters
    detected using the Louvain algorithm (enterprise-grade graph analytics).

    Returns standalone HTML with D3.js force graph.
    """
    try:
        # Get graph data
        graph_data = await get_graph_json(txid, direction, max_depth)

        # Community detection feature removed (igraph dependency removed)
        # Always set show_communities to False for graceful degradation
        if show_communities:
            logger.info("Community detection requested but graph analytics module removed - using default coloring")
            show_communities = False

        graph_json = json.dumps(graph_data["graph"])
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChainForensics - UTXO Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            overflow: hidden;
        }}
        #graph {{ width: 100vw; height: 100vh; }}
        .node {{ cursor: pointer; }}
        .node circle {{ stroke: #fff; stroke-width: 1.5px; }}
        .node.coinjoin circle {{ fill: #f85149; }}
        .node.unspent circle {{ fill: #238636; }}
        .node.coinbase circle {{ fill: #a371f7; }}
        .node.default circle {{ fill: #58a6ff; }}
        /* Community colors (color-blind friendly palette) */
        .node.community-0 circle {{ fill: #4285F4; }}
        .node.community-1 circle {{ fill: #EA4335; }}
        .node.community-2 circle {{ fill: #FBBC04; }}
        .node.community-3 circle {{ fill: #34A853; }}
        .node.community-4 circle {{ fill: #9C27B0; }}
        .node.community-5 circle {{ fill: #FF6F00; }}
        .node.community-6 circle {{ fill: #00BCD4; }}
        .node.community-7 circle {{ fill: #E91E63; }}
        .link {{ stroke: #30363d; stroke-opacity: 0.6; }}
        .node text {{
            fill: #c9d1d9;
            font-size: 10px;
            pointer-events: none;
        }}
        .tooltip {{
            position: absolute;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 10px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        .info-panel {{
            position: fixed;
            top: 10px;
            left: 10px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px;
            z-index: 100;
        }}
        .info-panel h2 {{ color: #58a6ff; margin-bottom: 10px; }}
        .legend {{ margin-top: 10px; }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="info-panel">
        <h2>🔗 UTXO Graph</h2>
        <p>TX: {txid[:16]}...</p>
        <p>Nodes: {graph_data["graph"]["node_count"]}</p>
        <p>Edges: {graph_data["graph"]["edge_count"]}</p>
        <div class="legend">
            {'<p style="margin-bottom: 8px; color: #58a6ff;">Community Colors (Louvain)</p>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #4285F4;"></div><span>Community 1</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #EA4335;"></div><span>Community 2</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #FBBC04;"></div><span>Community 3</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #34A853;"></div><span>Community 4</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #9C27B0;"></div><span>Community 5</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #FF6F00;"></div><span>Community 6</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #00BCD4;"></div><span>Community 7</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #E91E63;"></div><span>Community 8</span></div>' if show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #f85149;"></div><span>CoinJoin</span></div>' if not show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #238636;"></div><span>Unspent</span></div>' if not show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #a371f7;"></div><span>Coinbase</span></div>' if not show_communities else ''}
            {'<div class="legend-item"><div class="legend-color" style="background: #58a6ff;"></div><span>Transaction</span></div>' if not show_communities else ''}
        </div>
    </div>
    
    <div id="graph"></div>
    <div class="tooltip" id="tooltip"></div>
    
    <script>
        const data = {graph_json};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("#graph")
            .append("svg")
            .attr("width", width)
            .attr("height", height);
        
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.edges).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
        
        const link = svg.append("g")
            .selectAll("line")
            .data(data.edges)
            .join("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.max(1, Math.log10(d.value / 100000000) + 2));
        
        const node = svg.append("g")
            .selectAll("g")
            .data(data.nodes)
            .join("g")
            .attr("class", d => {{
                // Community coloring if enabled
                if ({str(show_communities).lower()} && d.community_id !== undefined) {{
                    return `node community-${{d.community_id % 8}}`;
                }}
                // Default coloring by transaction type
                if (d.coinjoin_score > 0.5) return "node coinjoin";
                if (d.status === "unspent") return "node unspent";
                if (d.type === "coinbase") return "node coinbase";
                return "node default";
            }})
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        node.append("circle")
            .attr("r", d => Math.max(8, Math.log10(d.value_btc * 100000000) * 2));
        
        node.append("text")
            .attr("dx", 12)
            .attr("dy", 4)
            .text(d => d.id.substring(0, 8) + "...");
        
        const tooltip = d3.select("#tooltip");
        
        node.on("mouseover", (event, d) => {{
            const communityInfo = {str(show_communities).lower()} && d.community_id !== undefined
                ? `<br><strong>Community:</strong> ${{d.community_id + 1}}`
                : '';

            tooltip.style("opacity", 1)
                .html(`
                    <strong>TXID:</strong> ${{d.id.substring(0, 24)}}...<br>
                    <strong>Value:</strong> ${{d.value_btc.toFixed(8)}} BTC<br>
                    <strong>Status:</strong> ${{d.status}}<br>
                    <strong>CoinJoin:</strong> ${{(d.coinjoin_score * 100).toFixed(0)}}%${{communityInfo}}
                `)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px");
        }})
        .on("mouseout", () => {{
            tooltip.style("opacity", 0);
        }});
        
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});
        
        function dragstarted(event) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }}
        
        function dragged(event) {{
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }}
        
        function dragended(event) {{
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }}
    </script>
</body>
</html>'''
        
        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Error generating interactive graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/privacy-scorecard", response_class=HTMLResponse)
async def get_privacy_scorecard(
    txid: str = Query(..., description="Transaction ID"),
    vout: int = Query(..., description="Output index"),
    max_depth: int = Query(10, ge=1, le=50, description="Maximum trace depth")
):
    """
    Generate interactive HTML privacy scorecard with comprehensive analysis.

    Visual report includes:
    - Large score indicator with color coding (RED/YELLOW/GREEN)
    - Critical risks section highlighted in red
    - Attack surface breakdown with vulnerability scores
    - Privacy factors organized by category with visual cards
    - Prioritized recommendations checklist
    - Comparative benchmark visualization
    - Assessment limitations disclaimer

    This scorecard provides a professional, print-ready privacy assessment
    suitable for sharing with auditors or for personal records.
    """
    try:
        logger.info(f"Generating privacy scorecard for {txid[:16]}..., vout={vout}")

        # Get enhanced privacy analysis
        analyzer = get_privacy_analyzer()
        privacy_data = await analyzer.analyze_utxo_privacy_enhanced(txid, vout, max_depth)

        # Generate HTML
        html = _generate_scorecard_html(privacy_data, txid, vout)

        logger.info(f"Scorecard generated successfully: score={privacy_data.overall_score}")

        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Scorecard generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate privacy scorecard: {str(e)}"
        )


def _generate_scorecard_html(privacy_data: EnhancedPrivacyScore, txid: str, vout: int) -> str:
    """Generate comprehensive HTML scorecard with all sections."""

    # Determine score color class
    score_class = "score-red"
    if privacy_data.overall_score >= 70:
        score_class = "score-green"
    elif privacy_data.overall_score >= 40:
        score_class = "score-yellow"

    # Render critical risks section
    risks_html = _render_risk_items(privacy_data.critical_risks)
    if not risks_html:
        risks_html = '<p style="color: #22c55e; font-size: 16px;">✓ No critical risks detected</p>'

    # Render warnings section
    warnings_html = _render_risk_items(privacy_data.warnings)
    if not warnings_html:
        warnings_html = '<p style="color: #22c55e; font-size: 16px;">✓ No warnings</p>'

    # Render attack vectors
    attack_vectors_html = _render_attack_vectors(privacy_data.attack_vectors)
    if not attack_vectors_html:
        attack_vectors_html = '<p>No significant attack vectors detected - good privacy practices detected.</p>'

    # Render privacy factors
    factors_html = _render_privacy_factors(privacy_data.privacy_factors)

    # Render recommendations
    recommendations_html = _render_recommendations(privacy_data.recommendations)
    if not recommendations_html:
        recommendations_html = '<p>No specific recommendations at this time. Continue good privacy practices.</p>'

    # Render benchmarks
    benchmarks_html = ""
    if privacy_data.privacy_context:
        benchmarks_html = _render_benchmarks(privacy_data.privacy_context)

    # Render limitations
    limitations_html = "".join(f"<li>{lim}</li>" for lim in privacy_data.assessment_limitations)

    # Full HTML template
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Scorecard - {txid}:{vout}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .scorecard {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        .header h1 {{ margin: 0 0 10px 0; color: #1a1a1a; font-size: 32px; font-weight: 700; }}
        .utxo-info {{
            font-family: 'Courier New', monospace;
            color: #666;
            font-size: 13px;
            margin-bottom: 25px;
            background: #f5f5f5;
            padding: 10px;
            border-radius: 4px;
            word-break: break-all;
        }}
        .score-circle {{
            display: inline-block;
            width: 180px;
            height: 180px;
            border-radius: 50%;
            line-height: 180px;
            font-size: 64px;
            font-weight: bold;
            color: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin: 20px 0;
        }}
        .score-green {{ background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }}
        .score-yellow {{ background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%); }}
        .score-red {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }}
        .summary-box {{
            margin: 25px auto;
            padding: 20px;
            background: linear-gradient(to right, #f8f9fa 0%, #ffffff 100%);
            border-left: 4px solid #667eea;
            border-radius: 6px;
            max-width: 900px;
            font-size: 16px;
            line-height: 1.7;
            color: #333;
        }}
        .confidence-badge {{
            display: inline-block;
            background: #f0f0f0;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            margin-top: 15px;
            border: 1px solid #ddd;
        }}
        .section {{
            margin: 40px 0;
            padding: 30px;
            background: #fafafa;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
        }}
        .section h2 {{
            margin: 0 0 20px 0;
            color: #1a1a1a;
            font-size: 24px;
            font-weight: 700;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        .risk-item {{
            padding: 20px;
            margin: 15px 0;
            border-left: 5px solid;
            border-radius: 6px;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .risk-item h3 {{ margin: 0 0 10px 0; font-size: 18px; font-weight: 600; }}
        .risk-item p {{ margin: 8px 0; line-height: 1.6; }}
        .risk-item .confidence {{ font-size: 13px; color: #666; font-weight: 600; }}
        .risk-item .remediation {{
            margin-top: 12px;
            padding: 12px;
            background: #f9fafb;
            border-radius: 4px;
            font-size: 14px;
        }}
        .risk-CRITICAL {{ border-color: #ef4444; background: #fef2f2; }}
        .risk-CRITICAL h3 {{ color: #dc2626; }}
        .risk-HIGH {{ border-color: #f59e0b; background: #fffbeb; }}
        .risk-HIGH h3 {{ color: #d97706; }}
        .risk-MEDIUM {{ border-color: #eab308; background: #fefce8; }}
        .risk-MEDIUM h3 {{ color: #ca8a04; }}
        .risk-LOW {{ border-color: #3b82f6; background: #eff6ff; }}
        .risk-LOW h3 {{ color: #2563eb; }}
        .attack-vector {{
            display: inline-block;
            margin: 15px;
            padding: 20px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            width: calc(50% - 30px);
            vertical-align: top;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            min-width: 300px;
        }}
        .attack-vector h3 {{ margin: 0 0 15px 0; color: #1a1a1a; font-size: 16px; font-weight: 600; }}
        .vulnerability-bar-container {{
            background: #f0f0f0;
            height: 24px;
            border-radius: 4px;
            overflow: hidden;
            margin: 12px 0;
        }}
        .vulnerability-bar {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 8px;
            color: white;
            font-weight: 600;
            font-size: 12px;
        }}
        .attack-vector p {{ margin: 8px 0; font-size: 14px; line-height: 1.5; }}
        .attack-vector .example {{
            background: #f9fafb;
            padding: 12px;
            border-radius: 4px;
            font-size: 13px;
            color: #555;
            margin-top: 10px;
        }}
        .recommendation {{
            padding: 20px;
            margin: 15px 0;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .recommendation h3 {{ margin: 0 0 12px 0; font-size: 16px; font-weight: 600; }}
        .recommendation p {{ margin: 6px 0; line-height: 1.6; }}
        .recommendation strong {{ color: #1a1a1a; }}
        .priority-HIGH {{ border-left: 5px solid #ef4444; }}
        .priority-MEDIUM {{ border-left: 5px solid #eab308; }}
        .priority-LOW {{ border-left: 5px solid #3b82f6; }}
        .factor-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }}
        .factor-card {{
            padding: 20px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .factor-card h3 {{ margin: 0 0 15px 0; font-size: 17px; color: #1a1a1a; font-weight: 600; }}
        .factor-card .score {{ font-size: 24px; font-weight: 700; margin-bottom: 12px; }}
        .factor-card ul {{ margin: 10px 0; padding-left: 20px; }}
        .factor-card li {{ margin: 6px 0; line-height: 1.4; }}
        .factor-card .summary {{
            margin-top: 15px;
            padding: 12px;
            background: #f9fafb;
            border-radius: 4px;
            color: #555;
            font-size: 14px;
        }}
        .factor-positive {{ border-left: 5px solid #22c55e; }}
        .factor-negative {{ border-left: 5px solid #ef4444; }}
        .factor-neutral {{ border-left: 5px solid #94a3b8; }}
        .disclaimer {{
            margin-top: 40px;
            padding: 25px;
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 8px;
            color: #856404;
            line-height: 1.8;
        }}
        .disclaimer strong {{ font-size: 16px; }}
        .benchmark-bar {{
            margin: 12px 0;
        }}
        .benchmark-label {{
            font-size: 14px;
            margin-bottom: 6px;
            font-weight: 500;
        }}
        .benchmark-bar-bg {{
            background: #f0f0f0;
            height: 24px;
            border-radius: 4px;
            overflow: hidden;
        }}
        .benchmark-bar-fill {{
            height: 100%;
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-weight: 600;
            font-size: 12px;
        }}
        @media print {{
            body {{ background: white; padding: 0; }}
            .scorecard {{ box-shadow: none; }}
        }}
        @media (max-width: 768px) {{
            .scorecard {{ padding: 20px; }}
            .attack-vector {{ width: 100%; margin: 10px 0; }}
            .factor-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="scorecard">
        <!-- Header with Score -->
        <div class="header">
            <h1>🔒 Privacy Scorecard</h1>
            <div class="utxo-info">
                <strong>UTXO:</strong> {txid}:{vout}
            </div>
            <div class="{score_class} score-circle">
                {privacy_data.overall_score}
            </div>
            <div class="summary-box">
                {privacy_data.summary}
            </div>
            <div class="confidence-badge">
                <strong>Assessment Confidence:</strong> {privacy_data.assessment_confidence * 100:.0f}%
            </div>
        </div>

        <!-- Critical Risks -->
        <div class="section">
            <h2>🚨 Critical Risks</h2>
            {risks_html}
        </div>

        <!-- Warnings -->
        <div class="section">
            <h2>⚠️ Warnings</h2>
            {warnings_html}
        </div>

        <!-- Attack Surface -->
        <div class="section">
            <h2>🎯 Attack Surface</h2>
            <p style="margin-bottom: 20px; color: #555; line-height: 1.6;">
                These are specific attack vectors an adversary could use to track and deanonymize this UTXO:
            </p>
            <div style="text-align: center;">
                {attack_vectors_html}
            </div>
        </div>

        <!-- Privacy Factors -->
        <div class="section">
            <h2>📊 Privacy Factors Breakdown</h2>
            <div class="factor-grid">
                {factors_html}
            </div>
        </div>

        <!-- Recommendations -->
        <div class="section">
            <h2>✅ Recommended Actions</h2>
            {recommendations_html}
        </div>

        <!-- Comparative Context -->
        {f'<div class="section"><h2>📈 How You Compare</h2>{benchmarks_html}</div>' if benchmarks_html else ''}

        <!-- Limitations -->
        <div class="section">
            <h2>⚠️ Assessment Limitations</h2>
            <ul style="line-height: 2; padding-left: 25px;">
                {limitations_html}
            </ul>
        </div>

        <!-- Disclaimer -->
        <div class="disclaimer">
            <strong>⚠️ IMPORTANT DISCLAIMER:</strong><br><br>
            This privacy assessment is for <strong>educational and research purposes only</strong>.
            It uses heuristic analysis and cannot detect all possible privacy attacks.
            <strong>Do NOT rely on this tool for operational security decisions.</strong>
            Actual privacy may be better or worse than indicated.
            Consult a security professional for critical applications.
            <br><br>
            Generated by ChainForensics v1.2.0 - Advanced Blockchain Analytics
        </div>
    </div>
</body>
</html>'''

    return html


def _render_risk_items(risk_items: List[RiskItem]) -> str:
    """Render list of risk items as HTML."""
    html = ""
    for risk in risk_items:
        html += f'''
        <div class="risk-item risk-{risk.severity.value}">
            <h3>{risk.severity.value}: {risk.title}</h3>
            <p>{risk.description}</p>
            <p class="confidence"><strong>Detection Confidence:</strong> {risk.detection_confidence * 100:.0f}%</p>
            {f'<div class="remediation"><strong>🛠️ Remediation:</strong> {risk.remediation}</div>' if risk.remediation else ''}
        </div>
        '''
    return html


def _render_attack_vectors(attack_vectors: Dict[str, AttackVector]) -> str:
    """Render attack vectors as HTML cards."""
    html = ""
    for vector_name, vector in attack_vectors.items():
        vuln_width = int(vector.vulnerability_score * 100)
        bar_color = "#ef4444" if vuln_width > 70 else "#eab308" if vuln_width > 40 else "#22c55e"

        html += f'''
        <div class="attack-vector">
            <h3>{vector.vector_name}</h3>
            <div class="vulnerability-bar-container">
                <div class="vulnerability-bar" style="width: {vuln_width}%; background: {bar_color};">
                    {vuln_width}%
                </div>
            </div>
            <p><strong>Vulnerability Score:</strong> {vector.vulnerability_score * 100:.0f}%</p>
            <p><strong>Explanation:</strong> {vector.explanation}</p>
            <div class="example">
                <strong>Example Attack:</strong> {vector.example}
            </div>
        </div>
        '''
    return html


def _render_privacy_factors(privacy_factors: Dict[str, FactorCategory]) -> str:
    """Render privacy factors as cards."""
    html = ""
    for category_name, category in privacy_factors.items():
        impact_class = "factor-positive" if category.score_impact > 0 else "factor-negative" if category.score_impact < 0 else "factor-neutral"
        impact_sign = "+" if category.score_impact > 0 else ""
        impact_color = "#22c55e" if category.score_impact > 0 else "#ef4444" if category.score_impact < 0 else "#94a3b8"

        factors_list = ""
        for factor in category.factors:
            factor_sign = "+" if factor.impact > 0 else ""
            factors_list += f"<li>{factor.factor}: <strong>{factor_sign}{factor.impact}</strong> points</li>"

        html += f'''
        <div class="factor-card {impact_class}">
            <h3>{category.category_name}</h3>
            <div class="score" style="color: {impact_color};">{impact_sign}{category.score_impact} points</div>
            <ul>
                {factors_list}
            </ul>
            <div class="summary">{category.summary}</div>
        </div>
        '''
    return html


def _render_recommendations(recommendations: List) -> str:
    """Render recommendations as items."""
    html = ""
    for rec in recommendations:
        html += f'''
        <div class="recommendation priority-{rec.priority}">
            <h3>{rec.priority} Priority</h3>
            <p><strong>Action:</strong> {rec.action}</p>
            <p><strong>Expected Improvement:</strong> {rec.expected_improvement}</p>
            {f'<p><strong>Difficulty:</strong> {rec.difficulty}</p>' if rec.difficulty else ''}
        </div>
        '''
    return html


def _render_benchmarks(privacy_context) -> str:
    """Render privacy benchmark comparison."""
    html = f'<p style="font-size: 16px; margin-bottom: 20px;"><strong>Your Score:</strong> {privacy_context.your_score}/100</p>'

    for name, score in privacy_context.benchmarks.items():
        bar_color = "#22c55e" if score >= 70 else "#eab308" if score >= 40 else "#ef4444"
        is_yours = (score == privacy_context.your_score)
        highlight_style = "font-weight: bold; font-size: 15px;" if is_yours else ""

        html += f'''
        <div class="benchmark-bar">
            <div class="benchmark-label" style="{highlight_style}">
                {name.replace('_', ' ').title()}: {score}/100
                {' 👈 YOU ARE HERE' if is_yours else ''}
            </div>
            <div class="benchmark-bar-bg">
                <div class="benchmark-bar-fill" style="width: {score}%; background: {bar_color};">
                    {score}
                </div>
            </div>
        </div>
        '''

    html += f'<p style="margin-top: 20px; color: #555; line-height: 1.7;">{privacy_context.interpretation}</p>'
    return html


# =========================================================================
# NEW ENHANCED VISUALIZATIONS (Phase 6)
# =========================================================================

@router.get("/sankey", response_class=HTMLResponse)
async def get_sankey_diagram(
    txid: str,
    vout: int = Query(0, ge=0),
    depth: int = Query(5, ge=1, le=10)
):
    """
    Sankey flow diagram showing value flow.

    Visualizes:
    - Value splitting (1 input → 5 CoinJoin outputs)
    - Value merging (5 inputs → 1 consolidated output)
    - Peeling chains (decreasing flow width)
    - Change vs payment flows

    Width = value (BTC)
    Color = CoinJoin (red), Exchange (orange), Regular (blue)
    """
    try:
        tracer = get_tracer()
        trace = await tracer.trace_forward(txid, vout, depth)

        # Build Sankey data
        nodes = []
        links = []
        node_map = {}

        for i, node in enumerate(trace.nodes):
            node_id = f"{node.txid}:{node.vout}"
            node_map[node_id] = i

            # Determine category
            category = "regular"
            if node.coinjoin_score and node.coinjoin_score > 0.5:
                category = "coinjoin"
            elif node.status == "UNSPENT":
                category = "unspent"

            nodes.append({
                "name": f"{node.txid[:8]}...",
                "category": category,
                "value_btc": node.value_sats / 100_000_000
            })

        for edge in trace.edges:
            source_id = f"{edge.from_txid}:{edge.from_vout}"
            target_id = f"{edge.to_txid}:{edge.to_vin}"

            if source_id in node_map and target_id in node_map:
                links.append({
                    "source": node_map[source_id],
                    "target": node_map[target_id],
                    "value": edge.value_sats / 100_000_000  # Convert to BTC
                })

        html = _generate_sankey_html(nodes, links, txid, vout)
        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Sankey diagram failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _generate_sankey_html(nodes, links, txid, vout):
    """Generate standalone HTML with D3-sankey."""
    nodes_json = json.dumps(nodes)
    links_json = json.dumps(links)

    return f'''<!DOCTYPE html>
<html>
<head>
    <title>Sankey Flow - {txid[:16]}...:{vout}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/d3-sankey@0.12"></script>
    <style>
        body {{
            background: #0d1117;
            color: #c9d1d9;
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            overflow: hidden;
        }}
        #chart {{ width: 100vw; height: 100vh; }}
        .node rect {{ stroke: #fff; stroke-width: 2px; }}
        .node.regular rect {{ fill: #58a6ff; }}
        .node.coinjoin rect {{ fill: #f85149; }}
        .node.unspent rect {{ fill: #238636; }}
        .link {{ fill: none; stroke: #30363d; stroke-opacity: 0.5; }}
        .link:hover {{ stroke-opacity: 0.8; }}
        .title {{
            position: absolute;
            top: 20px;
            left: 20px;
            font-size: 24px;
            font-weight: 600;
        }}
        .legend {{
            position: absolute;
            top: 70px;
            left: 20px;
            background: #161b22;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #30363d;
        }}
        .legend-item {{
            margin: 8px 0;
            display: flex;
            align-items: center;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            margin-right: 10px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="title">💰 Value Flow Analysis: {txid[:16]}...:{vout}</div>
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #58a6ff;"></div>
            <span>Regular Transaction</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #f85149;"></div>
            <span>CoinJoin</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #238636;"></div>
            <span>Unspent</span>
        </div>
    </div>
    <div id="chart"></div>

    <script>
        const data = {{
            nodes: {nodes_json},
            links: {links_json}
        }};

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#chart")
            .append("svg")
            .attr("width", width)
            .attr("height", height);

        const sankey = d3.sankey()
            .nodeWidth(15)
            .nodePadding(10)
            .extent([[1, 50], [width - 1, height - 50]]);

        const {{nodes, links}} = sankey(data);

        // Links
        svg.append("g")
            .selectAll("path")
            .data(links)
            .join("path")
            .attr("class", "link")
            .attr("d", d3.sankeyLinkHorizontal())
            .attr("stroke-width", d => Math.max(1, d.width))
            .append("title")
            .text(d => `${{d.source.name}} → ${{d.target.name}}\\n${{d.value.toFixed(8)}} BTC`);

        // Nodes
        const node = svg.append("g")
            .selectAll("g")
            .data(nodes)
            .join("g")
            .attr("class", d => `node ${{d.category}}`);

        node.append("rect")
            .attr("x", d => d.x0)
            .attr("y", d => d.y0)
            .attr("height", d => d.y1 - d.y0)
            .attr("width", d => d.x1 - d.x0)
            .append("title")
            .text(d => `${{d.name}}\\n${{d.value_btc.toFixed(8)}} BTC`);

        node.append("text")
            .attr("x", d => d.x0 - 6)
            .attr("y", d => (d.y1 + d.y0) / 2)
            .attr("dy", "0.35em")
            .attr("text-anchor", "end")
            .text(d => d.name)
            .filter(d => d.x0 < width / 2)
            .attr("x", d => d.x1 + 6)
            .attr("text-anchor", "start")
            .style("fill", "#c9d1d9")
            .style("font-size", "12px");
    </script>
</body>
</html>'''


@router.get("/tree", response_class=HTMLResponse)
async def get_tree_visualization(
    txid: str,
    vout: int = Query(0, ge=0),
    depth: int = Query(10, ge=1, le=20)
):
    """
    Hierarchical tree layout showing peeling chain structure.

    Shows:
    - Root = initial UTXO (top)
    - Trunk = change outputs (peeling path, highlighted in red)
    - Branches = payment outputs (side branches)
    - Leaves = endpoints (unspent or depth limit)

    Perfect for visualizing systematic spend-down patterns.
    """
    try:
        tracer = get_tracer()
        trace = await tracer.trace_forward(txid, vout, depth)
        peeling = tracer.detect_peeling_chain(trace)

        # Build tree structure
        tree_data = _build_tree_from_trace(trace, peeling)

        html = _generate_tree_html(tree_data, txid, vout, peeling)
        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Tree visualization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _build_tree_from_trace(trace, peeling):
    """Convert TraceResult to hierarchical tree structure."""
    if not trace.nodes:
        return {"name": "No data", "value": 0, "children": []}

    # Root node
    root_node = trace.nodes[0]
    peeling_txids = set(peeling.get("transactions", []))

    root = {
        "name": f"{root_node.txid[:8]}...",
        "value": root_node.value_sats,
        "is_peeling": root_node.txid in peeling_txids,
        "is_unspent": root_node.status == "UNSPENT",
        "children": []
    }

    # Build children from edges
    # Group edges by source
    children_map = {}
    for edge in trace.edges:
        if edge.from_txid not in children_map:
            children_map[edge.from_txid] = []

        # Find target node
        target_node = next((n for n in trace.nodes if n.txid == edge.to_txid), None)
        if target_node:
            children_map[edge.from_txid].append({
                "name": f"{target_node.txid[:8]}...",
                "value": target_node.value_sats,
                "is_peeling": target_node.txid in peeling_txids,
                "is_unspent": target_node.status == "UNSPENT",
                "children": []
            })

    # Add children to root
    if root_node.txid in children_map:
        root["children"] = children_map[root_node.txid]

    return root


def _generate_tree_html(tree_data, txid, vout, peeling):
    """Generate D3.js tree visualization."""
    tree_json = json.dumps(tree_data)
    has_peeling = peeling.get("is_peeling_chain", False)

    # Build warning HTML separately to avoid nested f-string issues
    warning_html = f'''<div class="warning">
        ⚠️ PEELING CHAIN DETECTED<br>
        Length: {peeling.get("chain_length", 0)} transactions<br>
        Confidence: {peeling.get("confidence_percent", 0)}%
    </div>''' if has_peeling else ''

    return f'''<!DOCTYPE html>
<html>
<head>
    <title>Transaction Tree - {txid[:16]}...:{vout}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            background: #0d1117;
            color: #c9d1d9;
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}
        .node circle {{
            fill: #58a6ff;
            stroke: #fff;
            stroke-width: 2px;
        }}
        .node.peeling circle {{
            fill: #f85149;
            stroke-width: 3px;
        }}
        .node.unspent circle {{
            fill: #238636;
        }}
        .link {{
            fill: none;
            stroke: #30363d;
            stroke-width: 2px;
        }}
        .link.peeling {{
            stroke: #f85149;
            stroke-width: 3px;
        }}
        .node text {{
            fill: #c9d1d9;
            font-size: 12px;
        }}
        .warning {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: #f85149;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-weight: bold;
            max-width: 300px;
        }}
    </style>
</head>
<body>
    {warning_html}

    <svg id="tree"></svg>

    <script>
        const data = {tree_json};

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#tree")
            .attr("width", width)
            .attr("height", height);

        const tree = d3.tree()
            .size([width - 100, height - 100]);

        const root = d3.hierarchy(data);
        tree(root);

        // Links
        svg.append("g")
            .selectAll("path")
            .data(root.links())
            .join("path")
            .attr("class", d => d.target.data.is_peeling ? "link peeling" : "link")
            .attr("d", d3.linkVertical()
                .x(d => d.x + 50)
                .y(d => d.y + 50));

        // Nodes
        const node = svg.append("g")
            .selectAll("g")
            .data(root.descendants())
            .join("g")
            .attr("class", d => {{
                let classes = ["node"];
                if (d.data.is_peeling) classes.push("peeling");
                if (d.data.is_unspent) classes.push("unspent");
                return classes.join(" ");
            }})
            .attr("transform", d => `translate(${{d.x + 50}},${{d.y + 50}})`);

        node.append("circle")
            .attr("r", d => Math.max(6, Math.log10(d.data.value) * 1.5))
            .append("title")
            .text(d => `${{d.data.name}}\\n${{(d.data.value / 100000000).toFixed(8)}} BTC`);

        node.append("text")
            .attr("dy", "0.31em")
            .attr("x", d => d.children ? -12 : 12)
            .attr("text-anchor", d => d.children ? "end" : "start")
            .text(d => d.data.name);
    </script>
</body>
</html>'''


@router.get("/attack-heatmap", response_class=HTMLResponse)
async def get_attack_heatmap(
    txid: str,
    vout: int = Query(0, ge=0),
    max_depth: int = Query(10, ge=1, le=50)
):
    """
    Heat map showing attack surface vulnerabilities.

    Grid layout:
    - Rows: Attack vector types (timing, amount, wallet, etc.)
    - Columns: Vulnerability score bars (0-100%)
    - Color: Red (70-100%), Yellow (40-69%), Green (0-39%)
    - Tooltip: Detailed explanation + example attack

    Visual summary of privacy risks at a glance.
    """
    try:
        analyzer = get_privacy_analyzer()
        privacy = await analyzer.analyze_utxo_privacy_enhanced(txid, vout, max_depth)

        html = _generate_heatmap_html(privacy.attack_vectors, txid, vout, privacy.overall_score)
        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Attack heatmap failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _generate_heatmap_html(attack_vectors, txid, vout, overall_score):
    """Generate attack surface heat map."""
    vectors_json = json.dumps({
        name: {
            "name": v.vector_name,
            "score": v.vulnerability_score,
            "explanation": v.explanation,
            "example": v.example
        }
        for name, v in attack_vectors.items()
    })

    # Determine overall risk color
    risk_color = "#22c55e" if overall_score >= 70 else "#eab308" if overall_score >= 40 else "#ef4444"
    risk_text = "LOW RISK" if overall_score >= 70 else "MODERATE RISK" if overall_score >= 40 else "HIGH RISK"

    return f'''<!DOCTYPE html>
<html>
<head>
    <title>Attack Surface - {txid[:16]}...:{vout}</title>
    <style>
        body {{
            background: #0d1117;
            color: #c9d1d9;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 40px;
            margin: 0;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
        }}
        .title {{
            font-size: 32px;
            font-weight: 600;
        }}
        .overall-score {{
            background: {risk_color};
            color: white;
            padding: 20px 30px;
            border-radius: 8px;
            font-size: 24px;
            font-weight: bold;
            text-align: center;
        }}
        .overall-score .score {{
            font-size: 48px;
            display: block;
        }}
        .vector {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
            transition: transform 0.2s;
        }}
        .vector:hover {{
            transform: translateY(-2px);
            border-color: #58a6ff;
        }}
        .vector-name {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #58a6ff;
        }}
        .bar-container {{
            background: #21262d;
            height: 50px;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 15px;
        }}
        .bar {{
            height: 100%;
            display: flex;
            align-items: center;
            padding: 0 20px;
            color: white;
            font-weight: bold;
            font-size: 18px;
            transition: width 0.5s ease;
        }}
        .bar.high {{ background: linear-gradient(90deg, #ef4444, #dc2626); }}
        .bar.medium {{ background: linear-gradient(90deg, #eab308, #ca8a04); }}
        .bar.low {{ background: linear-gradient(90deg, #22c55e, #16a34a); }}
        .explanation {{
            font-size: 14px;
            color: #8b949e;
            margin-bottom: 15px;
            line-height: 1.6;
        }}
        .example {{
            background: #0d1117;
            padding: 15px;
            border-radius: 6px;
            font-size: 13px;
            border-left: 3px solid #58a6ff;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">🎯 Attack Surface Analysis</div>
        <div class="overall-score">
            <span class="score">{overall_score}/100</span>
            <span>{risk_text}</span>
        </div>
    </div>
    <div style="color: #8b949e; margin-bottom: 30px;">
        Transaction: {txid[:16]}...:{vout}
    </div>
    <div id="vectors"></div>

    <script>
        const vectors = {vectors_json};
        const container = document.getElementById("vectors");

        Object.entries(vectors).forEach(([key, vector]) => {{
            const score = Math.round(vector.score * 100);
            const colorClass = score >= 70 ? "high" : score >= 40 ? "medium" : "low";

            const vectorDiv = document.createElement("div");
            vectorDiv.className = "vector";
            vectorDiv.innerHTML = `
                <div class="vector-name">${{vector.name}}</div>
                <div class="bar-container">
                    <div class="bar ${{colorClass}}" style="width: ${{score}}%">
                        ${{score}}% Vulnerable
                    </div>
                </div>
                <div class="explanation"><strong>Explanation:</strong> ${{vector.explanation}}</div>
                <div class="example"><strong>Example Attack:</strong> ${{vector.example}}</div>
            `;
            container.appendChild(vectorDiv);
        }});
    </script>
</body>
</html>'''
