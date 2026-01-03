"""
ChainForensics - Timeline Generator
Creates visual timeline representations of UTXO flows.
"""
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger("chainforensics.timeline")


@dataclass
class TimelineEvent:
    """Single event in a timeline."""
    timestamp: datetime
    block_height: int
    txid: str
    event_type: str  # 'receive', 'send', 'split', 'coinjoin', 'consolidate'
    value_btc: float
    description: str
    related_txids: List[str] = field(default_factory=list)
    address: Optional[str] = None
    coinjoin_score: float = 0.0
    children: List["TimelineEvent"] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "block_height": self.block_height,
            "txid": self.txid,
            "event_type": self.event_type,
            "value_btc": self.value_btc,
            "description": self.description,
            "related_txids": self.related_txids,
            "address": self.address,
            "coinjoin_score": self.coinjoin_score,
            "children": [c.to_dict() for c in self.children]
        }


@dataclass
class Timeline:
    """Complete timeline for UTXO analysis."""
    start_txid: str
    start_vout: int
    events: List[TimelineEvent] = field(default_factory=list)
    total_value_btc: float = 0.0
    date_range: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
    coinjoin_events: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "start_txid": self.start_txid,
            "start_vout": self.start_vout,
            "events": [e.to_dict() for e in self.events],
            "total_value_btc": self.total_value_btc,
            "date_range": {
                "start": self.date_range[0].isoformat() if self.date_range[0] else None,
                "end": self.date_range[1].isoformat() if self.date_range[1] else None
            },
            "coinjoin_events": self.coinjoin_events,
            "event_count": len(self.events)
        }


class TimelineGenerator:
    """Generates timeline visualizations from trace data."""
    
    MAX_BAR_WIDTH = 40
    
    def __init__(self):
        pass
    
    def generate_timeline(self, trace_result: Dict) -> Timeline:
        """
        Generate a timeline from trace results.
        """
        start_txid = trace_result.get("start_txid", "")
        start_vout = trace_result.get("start_vout", 0)
        
        timeline = Timeline(
            start_txid=start_txid,
            start_vout=start_vout
        )
        
        nodes = trace_result.get("nodes", [])
        if not nodes:
            return timeline
        
        # Sort nodes by block time
        sorted_nodes = sorted(
            [n for n in nodes if n.get("block_time")],
            key=lambda x: x.get("block_time", "")
        )
        
        # Track max value for bar scaling
        max_value = max((n.get("value_btc", 0) for n in sorted_nodes), default=1)
        
        # Group events by date
        events_by_date = defaultdict(list)
        for node in sorted_nodes:
            if node.get("block_time"):
                date_key = node["block_time"][:10]  # YYYY-MM-DD
                events_by_date[date_key].append(node)
        
        # Create timeline events
        for date_str in sorted(events_by_date.keys()):
            day_events = events_by_date[date_str]
            
            for node in day_events:
                event_type = self._determine_event_type(node, trace_result)
                description = self._generate_description(node, event_type)
                
                event = TimelineEvent(
                    timestamp=datetime.fromisoformat(node["block_time"].replace("Z", "+00:00")) if node.get("block_time") else None,
                    block_height=node.get("block_height", 0),
                    txid=node.get("txid", ""),
                    event_type=event_type,
                    value_btc=node.get("value_btc", 0),
                    description=description,
                    address=node.get("address"),
                    coinjoin_score=node.get("coinjoin_score", 0)
                )
                
                timeline.events.append(event)
                timeline.total_value_btc += node.get("value_btc", 0)
                
                if node.get("coinjoin_score", 0) > 0.5:
                    timeline.coinjoin_events += 1
        
        # Set date range
        if timeline.events:
            timestamps = [e.timestamp for e in timeline.events if e.timestamp]
            if timestamps:
                timeline.date_range = (min(timestamps), max(timestamps))
        
        return timeline
    
    def _determine_event_type(self, node: Dict, trace_result: Dict) -> str:
        """Determine the type of event."""
        if node.get("coinjoin_score", 0) > 0.7:
            return "coinjoin"
        
        status = node.get("status", "")
        if status == "coinbase":
            return "mining"
        elif status == "unspent":
            return "receive"
        
        # Check for splits/consolidations by looking at transaction structure
        # This would require the full transaction data
        return "transfer"
    
    def _generate_description(self, node: Dict, event_type: str) -> str:
        """Generate human-readable description."""
        value = node.get("value_btc", 0)
        address = node.get("address", "")[:16] + "..." if node.get("address") else "unknown"
        
        if event_type == "coinjoin":
            score = node.get("coinjoin_score", 0)
            return f"CoinJoin ({score*100:.0f}% confidence)"
        elif event_type == "mining":
            return f"Mining reward"
        elif event_type == "receive":
            return f"Received to {address}"
        else:
            return f"Transfer"
    
    def generate_ascii_timeline(self, trace_result: Dict, max_width: int = 80) -> str:
        """
        Generate ASCII timeline visualization.
        
        Example output:
        2023-01-15 │ ████████████████████ 5.0 BTC ← Exchange withdrawal
                   │
        2023-01-16 │ ██████████ 2.5 BTC ──┬── Split tx
                   │ ██████████ 2.5 BTC ──┘
                   │
        2023-02-01 │ ██ 0.5 BTC ──────────── Spent (merchant?)
                   │ ████████ 2.0 BTC ────── 🔀 CoinJoin (Whirlpool)
                   │
        2023-02-01 │ █ 0.01 BTC × 200 ────── Mixed outputs (tracking lost)
        """
        timeline = self.generate_timeline(trace_result)
        
        if not timeline.events:
            return "No timeline events to display."
        
        # Find max value for scaling
        max_value = max((e.value_btc for e in timeline.events), default=1)
        
        lines = []
        lines.append("=" * max_width)
        lines.append("UTXO TIMELINE")
        lines.append(f"Start: {timeline.start_txid[:16]}...:{timeline.start_vout}")
        lines.append("=" * max_width)
        lines.append("")
        
        # Group events by date
        events_by_date = defaultdict(list)
        for event in timeline.events:
            if event.timestamp:
                date_key = event.timestamp.strftime("%Y-%m-%d")
                events_by_date[date_key].append(event)
        
        bar_width = self.MAX_BAR_WIDTH
        current_date = None
        
        for date_str in sorted(events_by_date.keys()):
            day_events = events_by_date[date_str]
            
            for i, event in enumerate(day_events):
                # Date column
                if date_str != current_date:
                    date_display = date_str
                    current_date = date_str
                else:
                    date_display = " " * 10
                
                # Value bar
                bar_length = int((event.value_btc / max_value) * bar_width) if max_value > 0 else 1
                bar_length = max(1, bar_length)
                bar = "█" * bar_length
                
                # Value display
                if event.value_btc >= 0.1:
                    value_str = f"{event.value_btc:.2f} BTC"
                elif event.value_btc >= 0.001:
                    value_str = f"{event.value_btc:.4f} BTC"
                else:
                    value_str = f"{int(event.value_btc * 100_000_000)} sats"
                
                # Event icon and description
                if event.event_type == "coinjoin":
                    icon = "🔀"
                    desc = f"CoinJoin ({event.coinjoin_score*100:.0f}%)"
                elif event.event_type == "mining":
                    icon = "⛏️"
                    desc = "Coinbase (mining)"
                elif event.event_type == "receive":
                    icon = "📥"
                    desc = event.description
                else:
                    icon = "📤"
                    desc = event.description
                
                # Build the line
                line = f"{date_display} │ {bar:<{bar_width}} {value_str:<15} {icon} {desc}"
                lines.append(line)
            
            # Add separator between dates
            lines.append(" " * 10 + " │")
        
        # Summary
        lines.append("=" * max_width)
        lines.append(f"Total Events: {len(timeline.events)}")
        lines.append(f"CoinJoin Events: {timeline.coinjoin_events}")
        if timeline.date_range[0] and timeline.date_range[1]:
            lines.append(f"Date Range: {timeline.date_range[0].strftime('%Y-%m-%d')} to {timeline.date_range[1].strftime('%Y-%m-%d')}")
        lines.append("=" * max_width)
        
        return "\n".join(lines)
    
    def generate_mermaid_timeline(self, trace_result: Dict) -> str:
        """Generate Mermaid.js timeline diagram."""
        timeline = self.generate_timeline(trace_result)
        
        if not timeline.events:
            return "```mermaid\ntimeline\n    title No events to display\n```"
        
        lines = ["```mermaid", "timeline", f"    title UTXO Timeline - {timeline.start_txid[:16]}..."]
        
        # Group by date
        events_by_date = defaultdict(list)
        for event in timeline.events:
            if event.timestamp:
                date_key = event.timestamp.strftime("%Y-%m-%d")
                events_by_date[date_key].append(event)
        
        for date_str in sorted(events_by_date.keys()):
            lines.append(f"    section {date_str}")
            for event in events_by_date[date_str]:
                emoji = "🔀" if event.event_type == "coinjoin" else "📦"
                lines.append(f"        {emoji} {event.value_btc:.4f} BTC : {event.description[:30]}")
        
        lines.append("```")
        return "\n".join(lines)
    
    def generate_html_timeline(self, trace_result: Dict) -> str:
        """Generate interactive HTML timeline with D3.js."""
        timeline = self.generate_timeline(trace_result)
        
        events_json = [e.to_dict() for e in timeline.events]
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChainForensics Timeline</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #58a6ff;
            margin-bottom: 10px;
        }}
        .timeline-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .event {{
            display: flex;
            margin-bottom: 20px;
            padding: 15px;
            background: #161b22;
            border-radius: 8px;
            border-left: 4px solid #58a6ff;
        }}
        .event.coinjoin {{
            border-left-color: #f85149;
        }}
        .event-date {{
            width: 120px;
            font-weight: bold;
            color: #8b949e;
        }}
        .event-bar {{
            flex: 1;
            margin: 0 15px;
        }}
        .bar {{
            height: 24px;
            background: linear-gradient(90deg, #238636, #2ea043);
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        .event.coinjoin .bar {{
            background: linear-gradient(90deg, #f85149, #da3633);
        }}
        .event-details {{
            width: 300px;
        }}
        .event-value {{
            font-size: 1.2em;
            font-weight: bold;
            color: #58a6ff;
        }}
        .event-desc {{
            color: #8b949e;
            font-size: 0.9em;
        }}
        .event-txid {{
            font-family: monospace;
            font-size: 0.75em;
            color: #6e7681;
            margin-top: 5px;
        }}
        .summary {{
            background: #161b22;
            padding: 20px;
            border-radius: 8px;
            margin-top: 30px;
        }}
        .summary h2 {{
            color: #58a6ff;
            margin-bottom: 15px;
        }}
        .stat {{
            display: inline-block;
            margin-right: 30px;
        }}
        .stat-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #c9d1d9;
        }}
        .stat-label {{
            color: #8b949e;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔗 ChainForensics Timeline</h1>
        <p>UTXO: {timeline.start_txid[:32]}...:{timeline.start_vout}</p>
    </div>
    
    <div class="timeline-container" id="timeline"></div>
    
    <div class="summary">
        <h2>Summary</h2>
        <div class="stat">
            <div class="stat-value">{len(timeline.events)}</div>
            <div class="stat-label">Total Events</div>
        </div>
        <div class="stat">
            <div class="stat-value">{timeline.coinjoin_events}</div>
            <div class="stat-label">CoinJoin Events</div>
        </div>
        <div class="stat">
            <div class="stat-value">{timeline.total_value_btc:.4f}</div>
            <div class="stat-label">Total BTC</div>
        </div>
    </div>
    
    <script>
        const events = {events_json};
        const maxValue = Math.max(...events.map(e => e.value_btc)) || 1;
        
        const container = d3.select('#timeline');
        
        events.forEach(event => {{
            const div = container.append('div')
                .attr('class', 'event' + (event.coinjoin_score > 0.5 ? ' coinjoin' : ''));
            
            // Date
            const date = event.timestamp ? new Date(event.timestamp).toLocaleDateString() : 'Unknown';
            div.append('div')
                .attr('class', 'event-date')
                .text(date);
            
            // Bar
            const barContainer = div.append('div')
                .attr('class', 'event-bar');
            
            const barWidth = Math.max(5, (event.value_btc / maxValue) * 100);
            barContainer.append('div')
                .attr('class', 'bar')
                .style('width', barWidth + '%');
            
            // Details
            const details = div.append('div')
                .attr('class', 'event-details');
            
            const icon = event.event_type === 'coinjoin' ? '🔀' : 
                         event.event_type === 'mining' ? '⛏️' : '📦';
            
            details.append('div')
                .attr('class', 'event-value')
                .text(icon + ' ' + event.value_btc.toFixed(8) + ' BTC');
            
            details.append('div')
                .attr('class', 'event-desc')
                .text(event.description);
            
            details.append('div')
                .attr('class', 'event-txid')
                .text(event.txid.substring(0, 32) + '...');
        }});
    </script>
</body>
</html>'''
        
        return html
    
    def generate_detailed_ascii(
        self,
        transactions: List[Dict],
        max_width: int = 100
    ) -> str:
        """
        Generate detailed ASCII timeline from raw transaction list.
        Shows splits, consolidations, and flow.
        """
        if not transactions:
            return "No transactions to display."
        
        # Sort by block time
        sorted_txs = sorted(
            [tx for tx in transactions if tx.get("blocktime")],
            key=lambda x: x.get("blocktime", 0)
        )
        
        if not sorted_txs:
            return "No dated transactions to display."
        
        # Find max output value for scaling
        all_values = []
        for tx in sorted_txs:
            for out in tx.get("vout", []):
                all_values.append(out.get("value", 0))
        
        max_value = max(all_values) if all_values else 1
        bar_width = 30
        
        lines = []
        lines.append("╔" + "═" * (max_width - 2) + "╗")
        lines.append("║" + " UTXO FLOW TIMELINE ".center(max_width - 2) + "║")
        lines.append("╠" + "═" * (max_width - 2) + "╣")
        
        current_date = None
        
        for tx in sorted_txs:
            timestamp = datetime.utcfromtimestamp(tx.get("blocktime", 0))
            date_str = timestamp.strftime("%Y-%m-%d")
            time_str = timestamp.strftime("%H:%M")
            txid = tx.get("txid", "unknown")[:16]
            
            # Date header
            if date_str != current_date:
                if current_date is not None:
                    lines.append("║" + " " * (max_width - 2) + "║")
                lines.append("║" + f" 📅 {date_str} ".ljust(max_width - 2) + "║")
                lines.append("║" + "─" * (max_width - 2) + "║")
                current_date = date_str
            
            # Check if coinjoin
            from app.core.coinjoin import CoinJoinDetector
            detector = CoinJoinDetector()
            cj_result = detector.analyze_transaction(tx)
            is_coinjoin = cj_result.score > 0.5
            
            # Transaction header
            icon = "🔀" if is_coinjoin else "📦"
            cj_label = f" (CoinJoin {cj_result.score*100:.0f}%)" if is_coinjoin else ""
            lines.append("║" + f" {time_str} │ {icon} {txid}...{cj_label}".ljust(max_width - 2) + "║")
            
            # Outputs
            outputs = tx.get("vout", [])
            for i, out in enumerate(outputs[:10]):  # Limit display
                value = out.get("value", 0)
                bar_len = int((value / max_value) * bar_width) if max_value > 0 else 1
                bar_len = max(1, bar_len)
                bar = "█" * bar_len
                
                # Address
                script = out.get("scriptPubKey", {})
                addr = script.get("address", "unknown")
                addr_short = addr[:20] + "..." if len(addr) > 20 else addr
                
                # Value formatting
                if value >= 0.1:
                    val_str = f"{value:.4f} BTC"
                else:
                    val_str = f"{int(value * 100_000_000):,} sats"
                
                # Connection symbol
                if len(outputs) > 1:
                    if i == 0:
                        conn = "┬"
                    elif i == len(outputs) - 1 or i == 9:
                        conn = "└"
                    else:
                        conn = "├"
                else:
                    conn = "─"
                
                line = f"        │ {bar:<{bar_width}} {val_str:<15} ─{conn}── {addr_short}"
                lines.append("║" + line.ljust(max_width - 2)[:max_width-2] + "║")
            
            if len(outputs) > 10:
                lines.append("║" + f"        │ ... and {len(outputs) - 10} more outputs".ljust(max_width - 2) + "║")
        
        lines.append("╚" + "═" * (max_width - 2) + "╝")
        
        return "\n".join(lines)


# Singleton instance
_timeline_generator: Optional[TimelineGenerator] = None


def get_timeline_generator() -> TimelineGenerator:
    """Get or create timeline generator instance."""
    global _timeline_generator
    if _timeline_generator is None:
        _timeline_generator = TimelineGenerator()
    return _timeline_generator
