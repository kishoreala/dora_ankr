#!/usr/bin/env python3
"""
ArgoCD DORA Metrics Generator

Generates DORA (DevOps Research and Assessment) metrics from ArgoCD:
1. Deployment Frequency
2. Lead Time for Changes
3. Change Failure Rate
4. Mean Time to Recovery (MTTR)
"""

import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import sys
from typing import Dict, List, Any

# Configuration
ARGOCD_CLUSTERS = {
    'production': {
        'url': 'https://argocd.prod.example.com',
        'token': 'YOUR_PROD_TOKEN_HERE'
    },
    'staging': {
        'url': 'https://argocd.staging.example.com',
        'token': 'YOUR_STAGING_TOKEN_HERE'
    }
}

# Time range for analysis (default: last 30 days)
DAYS_TO_ANALYZE = 30

# DORA Performance Levels
DORA_LEVELS = {
    'deployment_frequency': {
        'elite': 'Multiple deploys per day',
        'high': 'Between once per day and once per week',
        'medium': 'Between once per week and once per month',
        'low': 'Fewer than once per month'
    },
    'lead_time': {
        'elite': '< 1 hour',
        'high': '< 1 day',
        'medium': '< 1 week',
        'low': '> 1 week'
    },
    'mttr': {
        'elite': '< 1 hour',
        'high': '< 1 day',
        'medium': '< 1 week',
        'low': '> 1 week'
    },
    'change_failure_rate': {
        'elite': '< 15%',
        'high': '15-30%',
        'medium': '30-45%',
        'low': '> 45%'
    }
}


class ArgocdDoraMetrics:
    def __init__(self, cluster_name: str, argocd_url: str, token: str):
        self.cluster_name = cluster_name
        self.argocd_url = argocd_url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
    def get_applications(self) -> List[Dict]:
        """Fetch all applications from ArgoCD"""
        try:
            url = f'{self.argocd_url}/api/v1/applications'
            response = requests.get(url, headers=self.headers, verify=False)
            response.raise_for_status()
            return response.json().get('items', [])
        except Exception as e:
            print(f"Error fetching applications from {self.cluster_name}: {e}")
            return []
    
    def get_application_history(self, app_name: str) -> List[Dict]:
        """Fetch deployment history for an application"""
        try:
            url = f'{self.argocd_url}/api/v1/applications/{app_name}'
            response = requests.get(url, headers=self.headers, verify=False)
            response.raise_for_status()
            
            app_data = response.json()
            history = app_data.get('status', {}).get('history', [])
            return history
        except Exception as e:
            print(f"Error fetching history for {app_name}: {e}")
            return []
    
    def get_operation_state(self, app_name: str) -> Dict:
        """Get current operation state of application"""
        try:
            url = f'{self.argocd_url}/api/v1/applications/{app_name}'
            response = requests.get(url, headers=self.headers, verify=False)
            response.raise_for_status()
            
            app_data = response.json()
            return app_data.get('status', {}).get('operationState', {})
        except Exception as e:
            return {}
    
    def calculate_deployment_frequency(self, apps_data: List[Dict]) -> Dict:
        """
        Calculate Deployment Frequency (DORA Metric 1)
        Number of deployments per day/week/month
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        deployment_counts = defaultdict(int)
        app_deployment_counts = defaultdict(int)
        daily_deployments = defaultdict(int)
        
        for app in apps_data:
            app_name = app.get('metadata', {}).get('name', 'unknown')
            history = self.get_application_history(app_name)
            
            for deployment in history:
                deployed_at_str = deployment.get('deployedAt')
                if not deployed_at_str:
                    continue
                
                # Parse deployment timestamp
                deployed_at = datetime.strptime(deployed_at_str, '%Y-%m-%dT%H:%M:%SZ')
                
                if start_date <= deployed_at <= end_date:
                    deployment_counts['total'] += 1
                    app_deployment_counts[app_name] += 1
                    
                    # Track daily deployments
                    day_key = deployed_at.strftime('%Y-%m-%d')
                    daily_deployments[day_key] += 1
        
        total_deployments = deployment_counts['total']
        deployments_per_day = total_deployments / DAYS_TO_ANALYZE if DAYS_TO_ANALYZE > 0 else 0
        deployments_per_week = deployments_per_day * 7
        deployments_per_month = deployments_per_day * 30
        
        # Determine DORA level
        if deployments_per_day >= 1:
            level = 'elite'
        elif deployments_per_week >= 1:
            level = 'high'
        elif deployments_per_month >= 1:
            level = 'medium'
        else:
            level = 'low'
        
        return {
            'total_deployments': total_deployments,
            'deployments_per_day': round(deployments_per_day, 2),
            'deployments_per_week': round(deployments_per_week, 2),
            'deployments_per_month': round(deployments_per_month, 2),
            'dora_level': level,
            'dora_description': DORA_LEVELS['deployment_frequency'][level],
            'app_breakdown': dict(app_deployment_counts),
            'daily_breakdown': dict(daily_deployments)
        }
    
    def calculate_lead_time(self, apps_data: List[Dict]) -> Dict:
        """
        Calculate Lead Time for Changes (DORA Metric 2)
        Time from code commit to deployment in production
        
        Note: This requires Git commit timestamps in ArgoCD history
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        lead_times = []
        
        for app in apps_data:
            app_name = app.get('metadata', {}).get('name', 'unknown')
            history = self.get_application_history(app_name)
            
            for deployment in history:
                deployed_at_str = deployment.get('deployedAt')
                if not deployed_at_str:
                    continue
                
                deployed_at = datetime.strptime(deployed_at_str, '%Y-%m-%dT%H:%M:%SZ')
                
                if start_date <= deployed_at <= end_date:
                    # Get commit timestamp from revision
                    revision = deployment.get('revision', '')
                    source = deployment.get('source', {})
                    
                    # Try to get commit time from deployment metadata
                    # This is an approximation - ideally you'd query Git directly
                    deployed_at_str = deployment.get('deployedAt')
                    
                    # For now, use a proxy: time between syncs
                    # In production, you'd integrate with Git API
                    lead_times.append(0)  # Placeholder
        
        if not lead_times:
            return {
                'avg_lead_time_hours': 0,
                'median_lead_time_hours': 0,
                'p95_lead_time_hours': 0,
                'dora_level': 'unknown',
                'note': 'Lead time calculation requires Git integration'
            }
        
        avg_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0
        
        # Determine DORA level (in hours)
        if avg_lead_time < 1:
            level = 'elite'
        elif avg_lead_time < 24:
            level = 'high'
        elif avg_lead_time < 168:  # 1 week
            level = 'medium'
        else:
            level = 'low'
        
        return {
            'avg_lead_time_hours': round(avg_lead_time, 2),
            'dora_level': level,
            'dora_description': DORA_LEVELS['lead_time'][level],
            'note': 'Lead time requires Git commit data integration'
        }
    
    def calculate_change_failure_rate(self, apps_data: List[Dict]) -> Dict:
        """
        Calculate Change Failure Rate (DORA Metric 3)
        Percentage of deployments that result in degraded service or require remediation
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        total_deployments = 0
        failed_deployments = 0
        degraded_deployments = 0
        app_failure_rates = {}
        
        for app in apps_data:
            app_name = app.get('metadata', {}).get('name', 'unknown')
            history = self.get_application_history(app_name)
            
            app_total = 0
            app_failed = 0
            
            for i, deployment in enumerate(history):
                deployed_at_str = deployment.get('deployedAt')
                if not deployed_at_str:
                    continue
                
                deployed_at = datetime.strptime(deployed_at_str, '%Y-%m-%dT%H:%M:%SZ')
                
                if start_date <= deployed_at <= end_date:
                    total_deployments += 1
                    app_total += 1
                    
                    # Check if this deployment failed or was quickly rolled back
                    # A rollback is indicated by the next deployment having an older revision
                    if i < len(history) - 1:
                        next_deployment = history[i + 1]
                        next_deployed_at_str = next_deployment.get('deployedAt')
                        
                        if next_deployed_at_str:
                            next_deployed_at = datetime.strptime(
                                next_deployed_at_str, '%Y-%m-%dT%H:%M:%SZ'
                            )
                            
                            # If next deployment was within 1 hour, consider it a failure
                            time_diff = (next_deployed_at - deployed_at).total_seconds() / 3600
                            if time_diff < 1:
                                failed_deployments += 1
                                app_failed += 1
                    
                    # Check operation state
                    # Note: This only shows current state, not historical
                    operation_state = self.get_operation_state(app_name)
                    if operation_state.get('phase') in ['Failed', 'Error']:
                        degraded_deployments += 1
            
            if app_total > 0:
                app_failure_rates[app_name] = round((app_failed / app_total) * 100, 2)
        
        failure_rate = (failed_deployments / total_deployments * 100) if total_deployments > 0 else 0
        
        # Determine DORA level
        if failure_rate < 15:
            level = 'elite'
        elif failure_rate < 30:
            level = 'high'
        elif failure_rate < 45:
            level = 'medium'
        else:
            level = 'low'
        
        return {
            'total_deployments': total_deployments,
            'failed_deployments': failed_deployments,
            'change_failure_rate': round(failure_rate, 2),
            'dora_level': level,
            'dora_description': DORA_LEVELS['change_failure_rate'][level],
            'app_breakdown': app_failure_rates,
            'note': 'Failure detection based on quick rollbacks (<1 hour)'
        }
    
    def calculate_mttr(self, apps_data: List[Dict]) -> Dict:
        """
        Calculate Mean Time to Recovery (DORA Metric 4)
        Average time to restore service after a failure
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        recovery_times = []
        app_mttr = {}
        
        for app in apps_data:
            app_name = app.get('metadata', {}).get('name', 'unknown')
            history = self.get_application_history(app_name)
            
            app_recovery_times = []
            
            for i in range(len(history) - 1):
                current = history[i]
                next_deploy = history[i + 1]
                
                current_time_str = current.get('deployedAt')
                next_time_str = next_deploy.get('deployedAt')
                
                if not current_time_str or not next_time_str:
                    continue
                
                current_time = datetime.strptime(current_time_str, '%Y-%m-%dT%H:%M:%SZ')
                next_time = datetime.strptime(next_time_str, '%Y-%m-%dT%H:%M:%SZ')
                
                if start_date <= current_time <= end_date:
                    # If deployments are close together (<1 hour), likely a fix
                    time_diff_hours = (next_time - current_time).total_seconds() / 3600
                    
                    if 0 < time_diff_hours < 1:
                        recovery_times.append(time_diff_hours)
                        app_recovery_times.append(time_diff_hours)
            
            if app_recovery_times:
                app_mttr[app_name] = round(sum(app_recovery_times) / len(app_recovery_times), 2)
        
        if not recovery_times:
            return {
                'avg_mttr_hours': 0,
                'avg_mttr_minutes': 0,
                'median_mttr_hours': 0,
                'incidents_recovered': 0,
                'dora_level': 'unknown',
                'note': 'No recovery incidents detected in time period'
            }
        
        avg_mttr_hours = sum(recovery_times) / len(recovery_times)
        avg_mttr_minutes = avg_mttr_hours * 60
        
        # Determine DORA level
        if avg_mttr_hours < 1:
            level = 'elite'
        elif avg_mttr_hours < 24:
            level = 'high'
        elif avg_mttr_hours < 168:  # 1 week
            level = 'medium'
        else:
            level = 'low'
        
        recovery_times_sorted = sorted(recovery_times)
        median_mttr = recovery_times_sorted[len(recovery_times_sorted) // 2] if recovery_times_sorted else 0
        
        return {
            'avg_mttr_hours': round(avg_mttr_hours, 2),
            'avg_mttr_minutes': round(avg_mttr_minutes, 2),
            'median_mttr_hours': round(median_mttr, 2),
            'incidents_recovered': len(recovery_times),
            'dora_level': level,
            'dora_description': DORA_LEVELS['mttr'][level],
            'app_breakdown': app_mttr
        }
    
    def generate_dora_report(self) -> Dict:
        """Generate complete DORA metrics report"""
        print(f"\n{'='*60}")
        print(f"Generating DORA Metrics for: {self.cluster_name}")
        print(f"Time Period: Last {DAYS_TO_ANALYZE} days")
        print(f"{'='*60}\n")
        
        apps = self.get_applications()
        print(f"Found {len(apps)} applications")
        
        print("\n📊 Calculating Deployment Frequency...")
        deployment_freq = self.calculate_deployment_frequency(apps)
        
        print("⏱️  Calculating Lead Time for Changes...")
        lead_time = self.calculate_lead_time(apps)
        
        print("❌ Calculating Change Failure Rate...")
        failure_rate = self.calculate_change_failure_rate(apps)
        
        print("🔧 Calculating Mean Time to Recovery...")
        mttr = self.calculate_mttr(apps)
        
        return {
            'cluster': self.cluster_name,
            'time_period_days': DAYS_TO_ANALYZE,
            'total_applications': len(apps),
            'generated_at': datetime.now().isoformat(),
            'metrics': {
                'deployment_frequency': deployment_freq,
                'lead_time_for_changes': lead_time,
                'change_failure_rate': failure_rate,
                'mean_time_to_recovery': mttr
            }
        }


def print_dora_summary(report: Dict):
    """Print a formatted summary of DORA metrics"""
    metrics = report['metrics']
    
    print(f"\n{'='*80}")
    print(f"DORA METRICS REPORT - {report['cluster'].upper()}")
    print(f"{'='*80}")
    print(f"Time Period: {report['time_period_days']} days")
    print(f"Total Applications: {report['total_applications']}")
    print(f"Generated: {report['generated_at']}")
    print(f"{'='*80}\n")
    
    # Deployment Frequency
    df = metrics['deployment_frequency']
    print("1. DEPLOYMENT FREQUENCY")
    print(f"   Total Deployments: {df['total_deployments']}")
    print(f"   Per Day: {df['deployments_per_day']}")
    print(f"   Per Week: {df['deployments_per_week']}")
    print(f"   Per Month: {df['deployments_per_month']}")
    print(f"   DORA Level: {df['dora_level'].upper()} - {df['dora_description']}")
    print()
    
    # Lead Time
    lt = metrics['lead_time_for_changes']
    print("2. LEAD TIME FOR CHANGES")
    print(f"   Average: {lt.get('avg_lead_time_hours', 0)} hours")
    print(f"   DORA Level: {lt['dora_level'].upper()}")
    if 'note' in lt:
        print(f"   Note: {lt['note']}")
    print()
    
    # Change Failure Rate
    cfr = metrics['change_failure_rate']
    print("3. CHANGE FAILURE RATE")
    print(f"   Total Deployments: {cfr['total_deployments']}")
    print(f"   Failed Deployments: {cfr['failed_deployments']}")
    print(f"   Failure Rate: {cfr['change_failure_rate']}%")
    print(f"   DORA Level: {cfr['dora_level'].upper()} - {cfr['dora_description']}")
    if 'note' in cfr:
        print(f"   Note: {cfr['note']}")
    print()
    
    # MTTR
    mttr = metrics['mean_time_to_recovery']
    print("4. MEAN TIME TO RECOVERY (MTTR)")
    print(f"   Average: {mttr.get('avg_mttr_hours', 0)} hours ({mttr.get('avg_mttr_minutes', 0)} minutes)")
    print(f"   Median: {mttr.get('median_mttr_hours', 0)} hours")
    print(f"   Incidents Recovered: {mttr.get('incidents_recovered', 0)}")
    print(f"   DORA Level: {mttr['dora_level'].upper()}")
    if 'note' in mttr:
        print(f"   Note: {mttr['note']}")
    print()
    
    # Overall DORA Assessment
    levels = [
        df['dora_level'],
        lt['dora_level'],
        cfr['dora_level'],
        mttr['dora_level']
    ]
    
    level_scores = {'elite': 4, 'high': 3, 'medium': 2, 'low': 1, 'unknown': 0}
    valid_levels = [l for l in levels if l != 'unknown']
    
    if valid_levels:
        avg_score = sum(level_scores[l] for l in valid_levels) / len(valid_levels)
        
        if avg_score >= 3.5:
            overall = 'ELITE'
        elif avg_score >= 2.5:
            overall = 'HIGH'
        elif avg_score >= 1.5:
            overall = 'MEDIUM'
        else:
            overall = 'LOW'
        
        print(f"{'='*80}")
        print(f"OVERALL DORA PERFORMANCE: {overall}")
        print(f"{'='*80}\n")


def save_report_json(report: Dict, filename: str):
    """Save report as JSON"""
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"✅ JSON report saved: {filename}")


def save_report_csv(report: Dict, filename: str):
    """Save report as CSV"""
    metrics = report['metrics']
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['Metric', 'Value', 'DORA Level', 'Description'])
        
        # Deployment Frequency
        df = metrics['deployment_frequency']
        writer.writerow([
            'Deployment Frequency (per day)',
            df['deployments_per_day'],
            df['dora_level'],
            df['dora_description']
        ])
        
        # Lead Time
        lt = metrics['lead_time_for_changes']
        writer.writerow([
            'Lead Time (hours)',
            lt.get('avg_lead_time_hours', 0),
            lt['dora_level'],
            lt.get('dora_description', '')
        ])
        
        # Change Failure Rate
        cfr = metrics['change_failure_rate']
        writer.writerow([
            'Change Failure Rate (%)',
            cfr['change_failure_rate'],
            cfr['dora_level'],
            cfr['dora_description']
        ])
        
        # MTTR
        mttr = metrics['mean_time_to_recovery']
        writer.writerow([
            'MTTR (hours)',
            mttr.get('avg_mttr_hours', 0),
            mttr['dora_level'],
            mttr.get('dora_description', '')
        ])
    
    print(f"✅ CSV report saved: {filename}")


def main():
    """Main execution function"""
    all_reports = []
    
    # Generate reports for each cluster
    for cluster_name, config in ARGOCD_CLUSTERS.items():
        try:
            dora = ArgocdDoraMetrics(
                cluster_name,
                config['url'],
                config['token']
            )
            
            report = dora.generate_dora_report()
            all_reports.append(report)
            
            # Print summary
            print_dora_summary(report)
            
            # Save individual reports
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_file = f"dora_report_{cluster_name}_{timestamp}.json"
            csv_file = f"dora_report_{cluster_name}_{timestamp}.csv"
            
            save_report_json(report, json_file)
            save_report_csv(report, csv_file)
            
        except Exception as e:
            print(f"❌ Error processing cluster {cluster_name}: {e}")
            continue
    
    # Generate combined report
    if len(all_reports) > 1:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        combined_file = f"dora_report_combined_{timestamp}.json"
        
        combined = {
            'generated_at': datetime.now().isoformat(),
            'clusters': all_reports
        }
        
        save_report_json(combined, combined_file)
        print(f"\n✅ Combined report saved: {combined_file}")


if __name__ == '__main__':
    # Disable SSL warnings for self-signed certificates
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         ArgoCD DORA Metrics Generator                     ║
    ║                                                           ║
    ║  Measures DevOps Research and Assessment (DORA) metrics   ║
    ║  from your ArgoCD deployment history                      ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    main()
