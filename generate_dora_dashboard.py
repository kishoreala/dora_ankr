#!/usr/bin/env python3
"""
ArgoCD DORA Metrics - HTML Dashboard Generator

Generates an interactive HTML dashboard from DORA metrics JSON reports
"""

import json
import sys
from datetime import datetime
from pathlib import Path


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DORA Metrics Dashboard - {cluster}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            color: #2d3748;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header .meta {{
            color: #718096;
            font-size: 1.1em;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }}
        
        .metric-card h2 {{
            color: #2d3748;
            font-size: 1.2em;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
        }}
        
        .metric-card h2 .icon {{
            font-size: 1.5em;
            margin-right: 10px;
        }}
        
        .metric-value {{
            font-size: 3em;
            font-weight: bold;
            margin: 15px 0;
        }}
        
        .metric-label {{
            color: #718096;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .dora-level {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
            margin-top: 10px;
        }}
        
        .dora-elite {{
            background: #10b981;
            color: white;
        }}
        
        .dora-high {{
            background: #3b82f6;
            color: white;
        }}
        
        .dora-medium {{
            background: #f59e0b;
            color: white;
        }}
        
        .dora-low {{
            background: #ef4444;
            color: white;
        }}
        
        .dora-unknown {{
            background: #6b7280;
            color: white;
        }}
        
        .chart-container {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .chart-container h2 {{
            color: #2d3748;
            margin-bottom: 20px;
        }}
        
        .overall-assessment {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .overall-assessment h2 {{
            color: #2d3748;
            font-size: 1.5em;
            margin-bottom: 15px;
        }}
        
        .overall-assessment .level {{
            font-size: 3.5em;
            font-weight: bold;
            margin: 20px 0;
        }}
        
        .app-breakdown {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .app-breakdown h2 {{
            color: #2d3748;
            margin-bottom: 20px;
        }}
        
        .app-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .app-table th {{
            background: #f7fafc;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #2d3748;
            border-bottom: 2px solid #e2e8f0;
        }}
        
        .app-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        .app-table tr:hover {{
            background: #f7fafc;
        }}
        
        .footer {{
            text-align: center;
            color: white;
            padding: 20px;
            font-size: 0.9em;
        }}
        
        .trend-indicator {{
            display: inline-block;
            margin-left: 10px;
            font-size: 0.8em;
        }}
        
        .trend-up {{
            color: #10b981;
        }}
        
        .trend-down {{
            color: #ef4444;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 DORA Metrics Dashboard</h1>
            <div class="meta">
                <strong>Cluster:</strong> {cluster} | 
                <strong>Period:</strong> Last {period} days | 
                <strong>Applications:</strong> {total_apps} |
                <strong>Generated:</strong> {generated_at}
            </div>
        </div>
        
        <div class="metrics-grid">
            <!-- Deployment Frequency Card -->
            <div class="metric-card">
                <h2><span class="icon">📈</span> Deployment Frequency</h2>
                <div class="metric-value" style="color: {df_color};">{df_value}</div>
                <div class="metric-label">Deployments per Day</div>
                <div class="dora-level dora-{df_level}">{df_level_text}</div>
                <div style="margin-top: 15px; color: #718096;">
                    <div>Per Week: <strong>{df_week}</strong></div>
                    <div>Per Month: <strong>{df_month}</strong></div>
                    <div>Total: <strong>{df_total}</strong></div>
                </div>
            </div>
            
            <!-- Lead Time Card -->
            <div class="metric-card">
                <h2><span class="icon">⏱️</span> Lead Time for Changes</h2>
                <div class="metric-value" style="color: {lt_color};">{lt_value}</div>
                <div class="metric-label">Average Hours</div>
                <div class="dora-level dora-{lt_level}">{lt_level_text}</div>
                {lt_note}
            </div>
            
            <!-- Change Failure Rate Card -->
            <div class="metric-card">
                <h2><span class="icon">❌</span> Change Failure Rate</h2>
                <div class="metric-value" style="color: {cfr_color};">{cfr_value}%</div>
                <div class="metric-label">Failed Deployments</div>
                <div class="dora-level dora-{cfr_level}">{cfr_level_text}</div>
                <div style="margin-top: 15px; color: #718096;">
                    <div>Failed: <strong>{cfr_failed}</strong> / <strong>{cfr_total}</strong></div>
                </div>
            </div>
            
            <!-- MTTR Card -->
            <div class="metric-card">
                <h2><span class="icon">🔧</span> Mean Time to Recovery</h2>
                <div class="metric-value" style="color: {mttr_color};">{mttr_value}</div>
                <div class="metric-label">Average Hours</div>
                <div class="dora-level dora-{mttr_level}">{mttr_level_text}</div>
                <div style="margin-top: 15px; color: #718096;">
                    <div>Minutes: <strong>{mttr_minutes}</strong></div>
                    <div>Incidents: <strong>{mttr_incidents}</strong></div>
                </div>
            </div>
        </div>
        
        <div class="overall-assessment">
            <h2>Overall DORA Performance</h2>
            <div class="level" style="color: {overall_color};">{overall_level}</div>
            <p style="color: #718096; font-size: 1.1em;">{overall_description}</p>
        </div>
        
        <!-- Charts -->
        <div class="chart-container">
            <h2>📊 Daily Deployment Trend</h2>
            <canvas id="deploymentChart"></canvas>
        </div>
        
        <!-- App Breakdown -->
        {app_breakdown_html}
        
        <div class="footer">
            Generated by ArgoCD DORA Metrics Generator | {generated_at}
        </div>
    </div>
    
    <script>
        // Deployment Trend Chart
        const dailyData = {daily_data};
        const ctx = document.getElementById('deploymentChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: Object.keys(dailyData),
                datasets: [{{
                    label: 'Deployments',
                    data: Object.values(dailyData),
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""


def get_level_color(level: str) -> str:
    """Get color for DORA level"""
    colors = {
        'elite': '#10b981',
        'high': '#3b82f6',
        'medium': '#f59e0b',
        'low': '#ef4444',
        'unknown': '#6b7280'
    }
    return colors.get(level, '#6b7280')


def generate_app_breakdown_html(metrics: dict) -> str:
    """Generate HTML for application breakdown tables"""
    html = ""
    
    # Deployment frequency breakdown
    df_breakdown = metrics.get('deployment_frequency', {}).get('app_breakdown', {})
    if df_breakdown:
        html += """
        <div class="app-breakdown">
            <h2>📱 Top Applications by Deployment Count</h2>
            <table class="app-table">
                <thead>
                    <tr>
                        <th>Application</th>
                        <th>Deployments</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        sorted_apps = sorted(df_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]
        for app, count in sorted_apps:
            html += f"""
                    <tr>
                        <td>{app}</td>
                        <td><strong>{count}</strong></td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
    
    # Failure rate breakdown
    cfr_breakdown = metrics.get('change_failure_rate', {}).get('app_breakdown', {})
    if cfr_breakdown:
        html += """
        <div class="app-breakdown">
            <h2>⚠️ Applications by Failure Rate</h2>
            <table class="app-table">
                <thead>
                    <tr>
                        <th>Application</th>
                        <th>Failure Rate</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        sorted_apps = sorted(cfr_breakdown.items(), key=lambda x: x[1], reverse=True)[:10]
        for app, rate in sorted_apps:
            color = 'color: #10b981;' if rate < 15 else 'color: #ef4444;' if rate > 30 else ''
            html += f"""
                    <tr>
                        <td>{app}</td>
                        <td style="{color}"><strong>{rate}%</strong></td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
    
    return html


def generate_dashboard(json_file: str, output_file: str = None):
    """Generate HTML dashboard from JSON report"""
    
    # Load JSON report
    with open(json_file, 'r') as f:
        report = json.load(f)
    
    metrics = report['metrics']
    
    # Extract deployment frequency data
    df = metrics['deployment_frequency']
    df_level = df['dora_level']
    df_color = get_level_color(df_level)
    
    # Extract lead time data
    lt = metrics['lead_time_for_changes']
    lt_level = lt['dora_level']
    lt_color = get_level_color(lt_level)
    lt_note = f"<div style='margin-top: 10px; color: #718096; font-size: 0.85em;'>{lt.get('note', '')}</div>" if 'note' in lt else ""
    
    # Extract change failure rate data
    cfr = metrics['change_failure_rate']
    cfr_level = cfr['dora_level']
    cfr_color = get_level_color(cfr_level)
    
    # Extract MTTR data
    mttr = metrics['mean_time_to_recovery']
    mttr_level = mttr['dora_level']
    mttr_color = get_level_color(mttr_level)
    
    # Calculate overall level
    levels = [df_level, lt_level, cfr_level, mttr_level]
    level_scores = {'elite': 4, 'high': 3, 'medium': 2, 'low': 1, 'unknown': 0}
    valid_levels = [l for l in levels if l != 'unknown']
    
    if valid_levels:
        avg_score = sum(level_scores[l] for l in valid_levels) / len(valid_levels)
        if avg_score >= 3.5:
            overall_level = 'ELITE'
        elif avg_score >= 2.5:
            overall_level = 'HIGH'
        elif avg_score >= 1.5:
            overall_level = 'MEDIUM'
        else:
            overall_level = 'LOW'
    else:
        overall_level = 'UNKNOWN'
    
    overall_color = get_level_color(overall_level.lower())
    
    overall_descriptions = {
        'ELITE': 'Your team is performing at the highest level! Keep up the excellent work.',
        'HIGH': 'Strong performance across most metrics. Focus on areas for improvement.',
        'MEDIUM': 'Good progress, but there\'s room for optimization.',
        'LOW': 'Consider focusing on improving deployment practices and reliability.'
    }
    
    # Generate app breakdown HTML
    app_breakdown_html = generate_app_breakdown_html(metrics)
    
    # Fill template
    html = HTML_TEMPLATE.format(
        cluster=report['cluster'].upper(),
        period=report['time_period_days'],
        total_apps=report['total_applications'],
        generated_at=datetime.fromisoformat(report['generated_at']).strftime('%Y-%m-%d %H:%M:%S'),
        
        # Deployment Frequency
        df_value=df['deployments_per_day'],
        df_week=df['deployments_per_week'],
        df_month=df['deployments_per_month'],
        df_total=df['total_deployments'],
        df_level=df_level,
        df_level_text=df_level.upper(),
        df_color=df_color,
        
        # Lead Time
        lt_value=lt.get('avg_lead_time_hours', 0),
        lt_level=lt_level,
        lt_level_text=lt_level.upper(),
        lt_color=lt_color,
        lt_note=lt_note,
        
        # Change Failure Rate
        cfr_value=cfr['change_failure_rate'],
        cfr_failed=cfr['failed_deployments'],
        cfr_total=cfr['total_deployments'],
        cfr_level=cfr_level,
        cfr_level_text=cfr_level.upper(),
        cfr_color=cfr_color,
        
        # MTTR
        mttr_value=mttr.get('avg_mttr_hours', 0),
        mttr_minutes=mttr.get('avg_mttr_minutes', 0),
        mttr_incidents=mttr.get('incidents_recovered', 0),
        mttr_level=mttr_level,
        mttr_level_text=mttr_level.upper(),
        mttr_color=mttr_color,
        
        # Overall
        overall_level=overall_level,
        overall_color=overall_color,
        overall_description=overall_descriptions.get(overall_level, ''),
        
        # Charts data
        daily_data=json.dumps(df.get('daily_breakdown', {})),
        
        # App breakdown
        app_breakdown_html=app_breakdown_html
    )
    
    # Write output
    if not output_file:
        output_file = json_file.replace('.json', '.html')
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"✅ Dashboard generated: {output_file}")
    return output_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_dora_dashboard.py <report.json> [output.html]")
        print("\nExample:")
        print("  python3 generate_dora_dashboard.py dora_report_production_20260115.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(json_file).exists():
        print(f"❌ Error: File not found: {json_file}")
        sys.exit(1)
    
    generate_dashboard(json_file, output_file)


if __name__ == '__main__':
    main()
