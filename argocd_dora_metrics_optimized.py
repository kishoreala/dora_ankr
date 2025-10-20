#!/usr/bin/env python3
"""
ArgoCD DORA Metrics Generator - OPTIMIZED VERSION

Optimizations:
- Parallel API calls using ThreadPoolExecutor
- Progress indicators
- Optional application filtering
- Configurable worker threads
- Better error handling

For large ArgoCD installations (1000+ applications)
"""

import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import sys
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
DAYS_TO_ANALYZE = 7

# Performance settings
MAX_WORKERS = 20  # Number of parallel threads (adjust based on ArgoCD server capacity)
PROGRESS_INTERVAL = 50  # Show progress every N apps

# Optional: Filter applications (leave empty to analyze all)
FILTER_CONFIG = {
    'namespaces': [],  # e.g., ['production', 'prod-*']
    'projects': [],    # e.g., ['platform', 'services']
    'exclude_namespaces': ['kube-system', 'kube-public'],  # Skip these
}

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


class ArgocdDoraMetricsOptimized:
    def __init__(self, cluster_name: str, argocd_url: str, token: str):
        self.cluster_name = cluster_name
        self.argocd_url = argocd_url.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self.lock = threading.Lock()
        self.api_call_count = 0
        
    def get_applications(self) -> List[Dict]:
        """Fetch all applications from ArgoCD with optional filtering"""
        try:
            url = f'{self.argocd_url}/api/v1/applications'
            response = requests.get(url, headers=self.headers, verify=False, timeout=30)
            response.raise_for_status()
            
            all_apps = response.json().get('items', [])
            print(f"✓ Fetched {len(all_apps)} total applications from API")
            
            # Apply filters if configured
            filtered_apps = self._filter_applications(all_apps)
            
            if len(filtered_apps) < len(all_apps):
                print(f"✓ Filtered to {len(filtered_apps)} applications based on configuration")
            
            return filtered_apps
            
        except Exception as e:
            print(f"❌ Error fetching applications from {self.cluster_name}: {e}")
            return []
    
    def _filter_applications(self, apps: List[Dict]) -> List[Dict]:
        """Filter applications based on FILTER_CONFIG"""
        if not any([FILTER_CONFIG['namespaces'], FILTER_CONFIG['projects'], 
                    FILTER_CONFIG['exclude_namespaces']]):
            return apps
        
        filtered = []
        for app in apps:
            metadata = app.get('metadata', {})
            namespace = metadata.get('namespace', '')
            
            # Check exclude list
            if any(ns in namespace for ns in FILTER_CONFIG['exclude_namespaces']):
                continue
            
            # Check namespace filter (if specified)
            if FILTER_CONFIG['namespaces']:
                if not any(ns in namespace for ns in FILTER_CONFIG['namespaces']):
                    continue
            
            # Check project filter (if specified)
            spec = app.get('spec', {})
            project = spec.get('project', '')
            if FILTER_CONFIG['projects']:
                if project not in FILTER_CONFIG['projects']:
                    continue
            
            filtered.append(app)
        
        return filtered
    
    def get_application_history(self, app_name: str) -> List[Dict]:
        """Fetch deployment history for an application"""
        try:
            with self.lock:
                self.api_call_count += 1
            
            url = f'{self.argocd_url}/api/v1/applications/{app_name}'
            response = requests.get(url, headers=self.headers, verify=False, timeout=10)
            response.raise_for_status()
            
            app_data = response.json()
            history = app_data.get('status', {}).get('history', [])
            return history
            
        except requests.exceptions.Timeout:
            print(f"⚠️  Timeout fetching history for {app_name}")
            return []
        except Exception as e:
            print(f"⚠️  Error fetching history for {app_name}: {e}")
            return []
    
    def get_operation_state(self, app_name: str) -> Dict:
        """Get current operation state of application"""
        try:
            url = f'{self.argocd_url}/api/v1/applications/{app_name}'
            response = requests.get(url, headers=self.headers, verify=False, timeout=10)
            response.raise_for_status()
            
            app_data = response.json()
            return app_data.get('status', {}).get('operationState', {})
        except Exception:
            return {}
    
    def process_single_app_history(self, app: Dict, start_date: datetime, end_date: datetime) -> Dict:
        """Process a single application's history - designed for parallel execution"""
        app_name = app.get('metadata', {}).get('name', 'unknown')
        history = self.get_application_history(app_name)
        
        result = {
            'app_name': app_name,
            'deployments': [],
            'failures': 0,
            'recovery_times': []
        }
        
        for i, deployment in enumerate(history):
            deployed_at_str = deployment.get('deployedAt')
            if not deployed_at_str:
                continue
            
            try:
                deployed_at = datetime.strptime(deployed_at_str, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                continue
            
            if start_date <= deployed_at <= end_date:
                result['deployments'].append({
                    'time': deployed_at,
                    'revision': deployment.get('revision', '')
                })
                
                # Check for quick rollback (failure indicator)
                if i < len(history) - 1:
                    next_deployment = history[i + 1]
                    next_deployed_at_str = next_deployment.get('deployedAt')
                    
                    if next_deployed_at_str:
                        try:
                            next_deployed_at = datetime.strptime(
                                next_deployed_at_str, '%Y-%m-%dT%H:%M:%SZ'
                            )
                            time_diff_hours = (next_deployed_at - deployed_at).total_seconds() / 3600
                            
                            if 0 < time_diff_hours < 1:
                                result['failures'] += 1
                                result['recovery_times'].append(time_diff_hours)
                        except ValueError:
                            continue
        
        return result
    
    def calculate_deployment_frequency(self, apps_data: List[Dict]) -> Dict:
        """
        Calculate Deployment Frequency (DORA Metric 1) - PARALLEL VERSION
        """
        print(f"\n📊 Calculating Deployment Frequency for {len(apps_data)} applications...")
        print(f"   Using {MAX_WORKERS} parallel workers")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        deployment_counts = defaultdict(int)
        app_deployment_counts = defaultdict(int)
        daily_deployments = defaultdict(int)
        
        processed = 0
        
        # Parallel processing
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self.process_single_app_history, app, start_date, end_date): app
                for app in apps_data
            }
            
            for future in as_completed(futures):
                processed += 1
                
                if processed % PROGRESS_INTERVAL == 0 or processed == len(apps_data):
                    print(f"   Progress: {processed}/{len(apps_data)} apps processed "
                          f"({(processed/len(apps_data)*100):.1f}%)")
                
                try:
                    result = future.result()
                    
                    app_name = result['app_name']
                    deployments = result['deployments']
                    
                    for deploy in deployments:
                        deployment_counts['total'] += 1
                        app_deployment_counts[app_name] += 1
                        
                        day_key = deploy['time'].strftime('%Y-%m-%d')
                        daily_deployments[day_key] += 1
                        
                except Exception as e:
                    print(f"   ⚠️  Error processing app: {e}")
        
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
        
        print(f"   ✓ Total API calls made: {self.api_call_count}")
        
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
        """Calculate Lead Time for Changes (DORA Metric 2)"""
        print(f"\n⏱️  Calculating Lead Time...")
        
        # Placeholder - requires Git integration
        return {
            'avg_lead_time_hours': 0,
            'median_lead_time_hours': 0,
            'p95_lead_time_hours': 0,
            'dora_level': 'unknown',
            'note': 'Lead time calculation requires Git integration'
        }
    
    def calculate_change_failure_rate(self, apps_data: List[Dict]) -> Dict:
        """
        Calculate Change Failure Rate (DORA Metric 3) - PARALLEL VERSION
        """
        print(f"\n❌ Calculating Change Failure Rate...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        total_deployments = 0
        failed_deployments = 0
        app_failure_rates = {}
        
        processed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self.process_single_app_history, app, start_date, end_date): app
                for app in apps_data
            }
            
            for future in as_completed(futures):
                processed += 1
                
                if processed % PROGRESS_INTERVAL == 0 or processed == len(apps_data):
                    print(f"   Progress: {processed}/{len(apps_data)} apps processed "
                          f"({(processed/len(apps_data)*100):.1f}%)")
                
                try:
                    result = future.result()
                    
                    app_name = result['app_name']
                    app_total = len(result['deployments'])
                    app_failed = result['failures']
                    
                    total_deployments += app_total
                    failed_deployments += app_failed
                    
                    if app_total > 0:
                        app_failure_rates[app_name] = round((app_failed / app_total) * 100, 2)
                        
                except Exception as e:
                    print(f"   ⚠️  Error processing app: {e}")
        
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
        Calculate Mean Time to Recovery (DORA Metric 4) - PARALLEL VERSION
        """
        print(f"\n🔧 Calculating Mean Time to Recovery...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        recovery_times = []
        app_mttr = {}
        
        processed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self.process_single_app_history, app, start_date, end_date): app
                for app in apps_data
            }
            
            for future in as_completed(futures):
                processed += 1
                
                if processed % PROGRESS_INTERVAL == 0 or processed == len(apps_data):
                    print(f"   Progress: {processed}/{len(apps_data)} apps processed "
                          f"({(processed/len(apps_data)*100):.1f}%)")
                
                try:
                    result = future.result()
                    
                    app_name = result['app_name']
                    app_recovery_times = result['recovery_times']
                    
                    recovery_times.extend(app_recovery_times)
                    
                    if app_recovery_times:
                        app_mttr[app_name] = round(
                            sum(app_recovery_times) / len(app_recovery_times), 2
                        )
                        
                except Exception as e:
                    print(f"   ⚠️  Error processing app: {e}")
        
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
        elif avg_mttr_hours < 168:
            level = 'medium'
        else:
            level = 'low'
        
        recovery_times_sorted = sorted(recovery_times)
        median_mttr = recovery_times_sorted[len(recovery_times_sorted) // 2]
        
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
        print(f"\n{'='*70}")
        print(f"🚀 Generating DORA Metrics for: {self.cluster_name}")
        print(f"   Time Period: Last {DAYS_TO_ANALYZE} days")
        print(f"   Parallel Workers: {MAX_WORKERS}")
        print(f"{'='*70}")
        
        start_time = datetime.now()
        
        apps = self.get_applications()
        print(f"\n✓ Found {len(apps)} applications to analyze")
        
        if not apps:
            print("❌ No applications found. Check your token and URL configuration.")
            return None
        
        # All metrics use the same parallel processing approach
        deployment_freq = self.calculate_deployment_frequency(apps)
        lead_time = self.calculate_lead_time(apps)
        failure_rate = self.calculate_change_failure_rate(apps)
        mttr = self.calculate_mttr(apps)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"✅ Report generation completed in {duration:.1f} seconds")
        print(f"   Total API calls: {self.api_call_count}")
        print(f"   Average: {self.api_call_count/duration:.1f} calls/second")
        print(f"{'='*70}")
        
        return {
            'cluster': self.cluster_name,
            'time_period_days': DAYS_TO_ANALYZE,
            'total_applications': len(apps),
            'generated_at': datetime.now().isoformat(),
            'generation_time_seconds': round(duration, 2),
            'api_calls_made': self.api_call_count,
            'metrics': {
                'deployment_frequency': deployment_freq,
                'lead_time_for_changes': lead_time,
                'change_failure_rate': failure_rate,
                'mean_time_to_recovery': mttr
            }
        }


def print_dora_summary(report: Dict):
    """Print a formatted summary of DORA metrics"""
    if not report:
        return
        
    metrics = report['metrics']
    
    print(f"\n{'='*80}")
    print(f"📊 DORA METRICS REPORT - {report['cluster'].upper()}")
    print(f"{'='*80}")
    print(f"Time Period: {report['time_period_days']} days")
    print(f"Total Applications: {report['total_applications']}")
    print(f"Generation Time: {report['generation_time_seconds']}s")
    print(f"API Calls Made: {report['api_calls_made']}")
    print(f"Generated: {report['generated_at']}")
    print(f"{'='*80}\n")
    
    # Deployment Frequency
    df = metrics['deployment_frequency']
    print("1. 📈 DEPLOYMENT FREQUENCY")
    print(f"   Total Deployments: {df['total_deployments']}")
    print(f"   Per Day: {df['deployments_per_day']}")
    print(f"   Per Week: {df['deployments_per_week']}")
    print(f"   Per Month: {df['deployments_per_month']}")
    print(f"   DORA Level: {df['dora_level'].upper()} - {df['dora_description']}")
    print()
    
    # Lead Time
    lt = metrics['lead_time_for_changes']
    print("2. ⏱️  LEAD TIME FOR CHANGES")
    print(f"   Average: {lt.get('avg_lead_time_hours', 0)} hours")
    print(f"   DORA Level: {lt['dora_level'].upper()}")
    if 'note' in lt:
        print(f"   Note: {lt['note']}")
    print()
    
    # Change Failure Rate
    cfr = metrics['change_failure_rate']
    print("3. ❌ CHANGE FAILURE RATE")
    print(f"   Total Deployments: {cfr['total_deployments']}")
    print(f"   Failed Deployments: {cfr['failed_deployments']}")
    print(f"   Failure Rate: {cfr['change_failure_rate']}%")
    print(f"   DORA Level: {cfr['dora_level'].upper()} - {cfr['dora_description']}")
    if 'note' in cfr:
        print(f"   Note: {cfr['note']}")
    print()
    
    # MTTR
    mttr = metrics['mean_time_to_recovery']
    print("4. 🔧 MEAN TIME TO RECOVERY (MTTR)")
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
        print(f"🏆 OVERALL DORA PERFORMANCE: {overall}")
        print(f"{'='*80}\n")


def save_report_json(report: Dict, filename: str):
    """Save report as JSON"""
    if not report:
        return
        
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f"✅ JSON report saved: {filename}")


def save_report_csv(report: Dict, filename: str):
    """Save report as CSV"""
    if not report:
        return
        
    metrics = report['metrics']
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        writer.writerow(['Metric', 'Value', 'DORA Level', 'Description'])
        
        df = metrics['deployment_frequency']
        writer.writerow([
            'Deployment Frequency (per day)',
            df['deployments_per_day'],
            df['dora_level'],
            df['dora_description']
        ])
        
        lt = metrics['lead_time_for_changes']
        writer.writerow([
            'Lead Time (hours)',
            lt.get('avg_lead_time_hours', 0),
            lt['dora_level'],
            lt.get('dora_description', '')
        ])
        
        cfr = metrics['change_failure_rate']
        writer.writerow([
            'Change Failure Rate (%)',
            cfr['change_failure_rate'],
            cfr['dora_level'],
            cfr['dora_description']
        ])
        
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
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║    ArgoCD DORA Metrics Generator - OPTIMIZED VERSION     ║
    ║                                                           ║
    ║  Optimized for large ArgoCD installations (1000+ apps)   ║
    ║  Features: Parallel processing, progress tracking        ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    all_reports = []
    
    for cluster_name, config in ARGOCD_CLUSTERS.items():
        try:
            dora = ArgocdDoraMetricsOptimized(
                cluster_name,
                config['url'],
                config['token']
            )
            
            report = dora.generate_dora_report()
            
            if not report:
                continue
                
            all_reports.append(report)
            
            print_dora_summary(report)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_file = f"dora_report_{cluster_name}_{timestamp}.json"
            csv_file = f"dora_report_{cluster_name}_{timestamp}.csv"
            
            save_report_json(report, json_file)
            save_report_csv(report, csv_file)
            
        except Exception as e:
            print(f"❌ Error processing cluster {cluster_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
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
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main()
