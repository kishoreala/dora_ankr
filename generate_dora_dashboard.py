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
            <h1>🚀 DORA Metrics Dashboard - {team_name}</h1>
            <div class="meta">
                <strong>Cluster:</strong> {cluster} | 
                <strong>Period:</strong> Last {period} days | 
                <strong>Applications:</strong> {total_apps} |
                <strong>Generated:</strong> {generated_at}
            </div>
        </div>
        
        <!-- Alert Banners -->
        {alert_banners}
        
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
        
        <!-- Chart Compliance -->
        {chart_compliance_html}
        
        <!-- Operational Insights -->
        {operational_insights_html}
        
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


def generate_chart_compliance_html(insights: dict) -> str:
    """Generate HTML for Helm chart compliance"""
    html = ""
    
    chart_compliance = insights.get('chart_compliance', {})
    if chart_compliance.get('total_helm_apps', 0) == 0:
        return html
    
    total_helm = chart_compliance.get('total_helm_apps', 0)
    total_git = chart_compliance.get('total_git_apps', 0)
    total_charts = chart_compliance.get('total_charts', 0)
    apps_on_latest = chart_compliance.get('apps_on_latest', 0)
    apps_outdated = chart_compliance.get('apps_outdated', 0)
    
    html += """
    <div class="app-breakdown" style="border-left: 4px solid #8b5cf6;">
        <h2>📦 Helm Chart Compliance</h2>
        <p style="color: #718096; margin-bottom: 15px;">
            Tracking Helm chart versions across all applications
        </p>
        <div class="stats-row">
            <div class="stat-box">
                <div class="value">{}</div>
                <div class="label">Helm Apps</div>
            </div>
            <div class="stat-box">
                <div class="value">{}</div>
                <div class="label">Git Apps</div>
            </div>
            <div class="stat-box">
                <div class="value">{}</div>
                <div class="label">Chart Types</div>
            </div>
            <div class="stat-box">
                <div class="value" style="color: #10b981;">{}</div>
                <div class="label">Up-to-date</div>
            </div>
            <div class="stat-box">
                <div class="value" style="color: #f59e0b;">{}</div>
                <div class="label">Outdated</div>
            </div>
        </div>
    """.format(total_helm, total_git, total_charts, apps_on_latest, apps_outdated)
    
    # Chart Distribution Table
    chart_summary = chart_compliance.get('chart_summary', {})
    if chart_summary:
        html += """
        <h3 style="margin-top: 25px; margin-bottom: 15px; color: #2d3748;">📊 Chart Distribution</h3>
        <table class="app-table">
            <thead>
                <tr>
                    <th>Chart Name</th>
                    <th>Latest Version</th>
                    <th>Up-to-date</th>
                    <th>Outdated</th>
                    <th>Total Apps</th>
                </tr>
            </thead>
            <tbody>
        """
        
        # Sort by total apps
        sorted_charts = sorted(
            chart_summary.items(),
            key=lambda x: x[1]['total_apps'],
            reverse=True
        )
        
        for chart_name, data in sorted_charts[:15]:
            latest_version = data['latest_version']
            total_apps = data['total_apps']
            apps_current = data['apps_on_latest']
            apps_old = data['apps_outdated']
            
            status_color = '#10b981' if apps_old == 0 else '#f59e0b' if apps_old < total_apps * 0.3 else '#ef4444'
            
            html += f"""
                <tr>
                    <td><strong>{chart_name}</strong></td>
                    <td>{latest_version}</td>
                    <td style="color: #10b981;"><strong>{apps_current}</strong></td>
                    <td style="color: {status_color};"><strong>{apps_old}</strong></td>
                    <td>{total_apps}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        """
    
    # Outdated Apps Table
    outdated_apps = chart_compliance.get('outdated_apps', [])
    if outdated_apps:
        html += """
        <h3 style="margin-top: 25px; margin-bottom: 15px; color: #2d3748;">⚠️ Apps on Outdated Chart Versions</h3>
        <table class="app-table">
            <thead>
                <tr>
                    <th>Application</th>
                    <th>Namespace</th>
                    <th>Chart Name</th>
                    <th>Current Version</th>
                    <th>Latest Version</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for app in outdated_apps[:20]:
            html += f"""
                <tr>
                    <td><strong>{app['app_name']}</strong></td>
                    <td>{app['namespace']}</td>
                    <td>{app['chart_name']}</td>
                    <td style="color: #f59e0b;"><strong>{app['current_version']}</strong></td>
                    <td style="color: #10b981;">{app['latest_version']}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        """
    
    html += "</div>"
    return html


def generate_operational_insights_html(insights: dict) -> str:
    """Generate HTML for operational insights"""
    html = ""
    
    # Sync Performance Section
    sync_perf = insights.get('sync_performance', {})
    if sync_perf.get('avg_sync_seconds', 0) > 0:
        html += """
        <div class="app-breakdown" style="border-left: 4px solid #3b82f6;">
            <h2>⏱️ Sync Performance</h2>
            <p style="color: #718096; margin-bottom: 15px;">
                How long ArgoCD syncs take across all applications
            </p>
            <div class="stats-row">
                <div class="stat-box">
                    <div class="value">{}</div>
                    <div class="label">Average Sync Time</div>
                </div>
                <div class="stat-box">
                    <div class="value">{}</div>
                    <div class="label">P95 Sync Time</div>
                </div>
                <div class="stat-box">
                    <div class="value">{}</div>
                    <div class="label">P99 Sync Time</div>
                </div>
                <div class="stat-box">
                    <div class="value">{}</div>
                    <div class="label">Total Syncs</div>
                </div>
            </div>
        """.format(
            f"{sync_perf.get('avg_sync_seconds', 0)}s",
            f"{sync_perf.get('p95_sync_seconds', 0)}s",
            f"{sync_perf.get('p99_sync_seconds', 0)}s",
            sync_perf.get('total_syncs', 0)
        )
        
        slowest_apps = sync_perf.get('slowest_apps', [])
        if slowest_apps:
            html += """
            <h3 style="margin-top: 25px; margin-bottom: 15px; color: #2d3748;">🐌 Slowest Syncing Applications</h3>
            <table class="app-table">
                <thead>
                    <tr>
                        <th>Application</th>
                        <th>Avg Sync Time</th>
                        <th>Max Sync Time</th>
                        <th>Sync Count</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for app in slowest_apps[:10]:
                color = 'color: #ef4444;' if app['avg_seconds'] > 120 else 'color: #f59e0b;' if app['avg_seconds'] > 60 else ''
                html += f"""
                    <tr>
                        <td><strong>{app['app_name']}</strong></td>
                        <td style="{color}"><strong>{app['avg_seconds']}s</strong></td>
                        <td>{app['max_seconds']}s</td>
                        <td>{app['sync_count']}</td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
            """
        
        html += "</div>"
    
    # Namespace Breakdown Section
    ns_breakdown = insights.get('namespace_breakdown', {})
    namespaces = ns_breakdown.get('namespaces', {})
    if namespaces:
        html += """
        <div class="app-breakdown" style="border-left: 4px solid #8b5cf6;">
            <h2>📊 Performance by Namespace</h2>
            <p style="color: #718096; margin-bottom: 15px;">
                DORA metrics broken down by namespace/team
            </p>
            <table class="app-table">
                <thead>
                    <tr>
                        <th>Namespace</th>
                        <th>Apps</th>
                        <th>Deployments</th>
                        <th>Failure Rate</th>
                        <th>MTTR</th>
                        <th>Level</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for ns, data in list(namespaces.items())[:20]:
            level = data['dora_level']
            level_color = {
                'elite': '#10b981',
                'high': '#3b82f6',
                'medium': '#f59e0b',
                'low': '#ef4444'
            }.get(level, '#6b7280')
            
            failure_color = '' if data['failure_rate'] < 15 else 'color: #f59e0b;' if data['failure_rate'] < 30 else 'color: #ef4444;'
            
            html += f"""
                <tr>
                    <td><strong>{ns}</strong></td>
                    <td>{data['app_count']}</td>
                    <td>{data['total_deployments']}</td>
                    <td style="{failure_color}"><strong>{data['failure_rate']}%</strong></td>
                    <td>{data['avg_mttr_minutes']} min</td>
                    <td style="color: {level_color};"><strong>{level.upper()}</strong></td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
    
    # Stuck Syncs Section
    stuck = insights.get('stuck_syncs', {})
    if stuck.get('total_stuck', 0) > 0:
        html += """
        <div class="app-breakdown" style="border-left: 4px solid #ef4444;">
            <h2>⚠️ Apps Stuck in Sync ({} apps)</h2>
            <p style="color: #718096; margin-bottom: 15px;">
                Applications syncing for more than {} minutes
            </p>
            <table class="app-table">
                <thead>
                    <tr>
                        <th>Application</th>
                        <th>Time Stuck</th>
                        <th>Sync Status</th>
                        <th>Health Status</th>
                    </tr>
                </thead>
                <tbody>
        """.format(stuck['total_stuck'], stuck.get('threshold_minutes', 30))
        
        for app in stuck.get('apps', [])[:20]:
            hours = app['minutes_stuck'] / 60
            time_str = f"{hours:.1f} hours" if hours >= 1 else f"{app['minutes_stuck']} min"
            health_color = 'color: #ef4444;' if app['health_status'] != 'Healthy' else ''
            
            html += f"""
                    <tr>
                        <td><strong>{app['app_name']}</strong></td>
                        <td style="color: #ef4444;"><strong>{time_str}</strong></td>
                        <td>{app['sync_status']}</td>
                        <td style="{health_color}">{app['health_status']}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
    
    # Staleness Analysis
    staleness = insights.get('staleness_analysis', {})
    stale_apps = staleness.get('stale_apps', [])
    stable_apps = staleness.get('stable_apps', [])
    
    if stale_apps:
        html += """
        <div class="app-breakdown" style="border-left: 4px solid #f59e0b;">
            <h2>📅 Stale Applications ({} apps need attention)</h2>
            <p style="color: #718096; margin-bottom: 15px;">
                Applications with outdated deployments and issues (out of sync, unhealthy, or auto-sync disabled)
            </p>
            <table class="app-table">
                <thead>
                    <tr>
                        <th>Application</th>
                        <th>Days Since Deploy</th>
                        <th>Sync Status</th>
                        <th>Health Status</th>
                        <th>Auto-Sync</th>
                    </tr>
                </thead>
                <tbody>
        """.format(len(stale_apps))
        
        for app in stale_apps[:20]:
            sync_color = '' if app['sync_status'] == 'Synced' else 'color: #f59e0b;'
            health_color = '' if app['health_status'] == 'Healthy' else 'color: #ef4444;'
            auto_sync_text = '✓' if app['auto_sync_enabled'] else '✗'
            
            html += f"""
                    <tr>
                        <td><strong>{app['app_name']}</strong></td>
                        <td><strong>{app['days_since_deploy']}</strong> days</td>
                        <td style="{sync_color}">{app['sync_status']}</td>
                        <td style="{health_color}">{app['health_status']}</td>
                        <td>{auto_sync_text}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
    
    if stable_apps:
        html += """
        <div class="app-breakdown" style="border-left: 4px solid #10b981;">
            <h2>✅ Stable Applications ({} apps)</h2>
            <p style="color: #718096; margin-bottom: 15px;">
                Applications with old deployments but healthy and in sync
            </p>
            <table class="app-table">
                <thead>
                    <tr>
                        <th>Application</th>
                        <th>Days Since Deploy</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        """.format(len(stable_apps))
        
        for app in stable_apps[:15]:
            html += f"""
                    <tr>
                        <td><strong>{app['app_name']}</strong></td>
                        <td><strong>{app['days_since_deploy']}</strong> days</td>
                        <td style="color: #10b981;">Healthy & Synced</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
    
    return html


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
    
    # Generate operational insights HTML
    insights = report.get('operational_insights', {})
    operational_insights_html = generate_operational_insights_html(insights)
    
    # Generate chart compliance HTML
    chart_compliance_html = generate_chart_compliance_html(insights)
    
    # Generate alert banners
    alert_banners = ""
    
    # Stuck syncs alert
    stuck_syncs = insights.get('stuck_syncs', {})
    if stuck_syncs.get('total_stuck', 0) > 0:
        alert_banners += f"""
        <div class="alert-banner error">
            <strong>⚠️ Action Required:</strong> {stuck_syncs['total_stuck']} applications are stuck in sync for over {stuck_syncs.get('threshold_minutes', 30)} minutes
        </div>
        """
    
    # Stale apps alert
    staleness = insights.get('staleness_analysis', {})
    stale_count = len(staleness.get('stale_apps', []))
    if stale_count > 0:
        alert_banners += f"""
        <div class="alert-banner">
            <strong>📅 Attention:</strong> {stale_count} stale applications need review (out of sync or unhealthy)
        </div>
        """
    
    # Outdated charts alert
    chart_compliance = insights.get('chart_compliance', {})
    outdated_count = chart_compliance.get('apps_outdated', 0)
    if outdated_count > 0:
        alert_banners += f"""
        <div class="alert-banner">
            <strong>📦 Update Available:</strong> {outdated_count} applications are using outdated Helm chart versions
        </div>
        """
    
    # Fill template
    html = HTML_TEMPLATE.format(
        team_name=report.get('team_name', 'Team'),
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
        app_breakdown_html=app_breakdown_html,
        
        # Operational insights
        operational_insights_html=operational_insights_html,
        
        # Chart compliance
        chart_compliance_html=chart_compliance_html,
        
        # Alert banners
        alert_banners=alert_banners
    )
    
    # Write output
    if not output_file:
        output_file = json_file.replace('.json', '.html')
    
    with open(output_file, 'w', encoding='utf-8') as f:
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
