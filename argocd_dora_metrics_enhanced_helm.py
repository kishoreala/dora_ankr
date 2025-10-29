#!/usr/bin/env python3
"""
ArgoCD DORA Metrics Generator - ENHANCED VERSION

Complete Feature Set:
- Parallel API calls with ThreadPoolExecutor
- Actual ArgoCD failure status detection (not timing-based)
- Infinite sync detection
- Staleness analysis (stable vs stale apps)
- Progress indicators
- Optional application filtering
- Configurable worker threads

For large ArgoCD installations (1000+ applications)
"""

import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import sys
from typing import Dict, List, Any, Tuple
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

# Team/Organization Name (appears in dashboard header)
TEAM_NAME = "Platform Engineering Team"  # ← CHANGE THIS TO YOUR TEAM NAME

# Time range for analysis
DAYS_TO_ANALYZE = 7

# Performance settings
MAX_WORKERS = 20
PROGRESS_INTERVAL = 50

# Staleness thresholds (in days)
STALENESS_THRESHOLDS = {
    'critical': 180,  # 6 months
    'warning': 90,    # 3 months
    'info': 30        # 1 month
}

# Infinite sync threshold (in minutes)
STUCK_SYNC_THRESHOLD_MINUTES = 30

# Optional: Filter applications
FILTER_CONFIG = {
    'namespaces': [],
    'projects': [],
    'exclude_namespaces': ['kube-system', 'kube-public'],
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


class ArgocdDoraMetricsEnhanced:
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
            
            if any(ns in namespace for ns in FILTER_CONFIG['exclude_namespaces']):
                continue
            
            if FILTER_CONFIG['namespaces']:
                if not any(ns in namespace for ns in FILTER_CONFIG['namespaces']):
                    continue
            
            spec = app.get('spec', {})
            project = spec.get('project', '')
            if FILTER_CONFIG['projects']:
                if project not in FILTER_CONFIG['projects']:
                    continue
            
            filtered.append(app)
        
        return filtered
    
    def get_application_details(self, app_name: str) -> Dict:
        """Fetch complete application details including current state and history"""
        try:
            with self.lock:
                self.api_call_count += 1
            
            url = f'{self.argocd_url}/api/v1/applications/{app_name}'
            response = requests.get(url, headers=self.headers, verify=False, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.Timeout:
            print(f"⚠️  Timeout fetching details for {app_name}")
            return {}
        except Exception as e:
            print(f"⚠️  Error fetching details for {app_name}: {e}")
            return {}
    
    def check_stuck_in_sync(self, app_data: Dict) -> Tuple[bool, int]:
        """Check if application is stuck in infinite sync"""
        operation_state = app_data.get('status', {}).get('operationState', {})
        
        phase = operation_state.get('phase', '')
        started_at_str = operation_state.get('startedAt', '')
        
        if phase in ['Running', 'Progressing'] and started_at_str:
            try:
                started_at = datetime.strptime(started_at_str, '%Y-%m-%dT%H:%M:%SZ')
                minutes_running = (datetime.now() - started_at).total_seconds() / 60
                
                if minutes_running > STUCK_SYNC_THRESHOLD_MINUTES:
                    return True, int(minutes_running)
            except ValueError:
                pass
        
        return False, 0
    
    def analyze_staleness(self, app_data: Dict) -> Dict:
        """Analyze if application is stale or just stable"""
        history = app_data.get('status', {}).get('history', [])
        sync_status = app_data.get('status', {}).get('sync', {}).get('status', 'Unknown')
        health_status = app_data.get('status', {}).get('health', {}).get('status', 'Unknown')
        
        # Get automated sync status
        spec = app_data.get('spec', {})
        auto_sync_enabled = spec.get('syncPolicy', {}).get('automated') is not None
        
        # Get last deployment time
        last_deployed = None
        days_since_deploy = 0
        
        if history:
            last_deployed_str = history[0].get('deployedAt', '')
            if last_deployed_str:
                try:
                    last_deployed = datetime.strptime(last_deployed_str, '%Y-%m-%dT%H:%M:%SZ')
                    days_since_deploy = (datetime.now() - last_deployed).days
                except ValueError:
                    pass
        
        # Determine category
        category = 'recent'
        is_problematic = False
        
        if days_since_deploy >= STALENESS_THRESHOLDS['critical']:
            if sync_status == 'Synced' and health_status == 'Healthy':
                category = 'stable'
            else:
                category = 'stale'
                is_problematic = True
        elif days_since_deploy >= STALENESS_THRESHOLDS['warning']:
            if sync_status != 'Synced' or health_status != 'Healthy' or not auto_sync_enabled:
                category = 'stale'
                is_problematic = True
            else:
                category = 'stable'
        elif days_since_deploy >= STALENESS_THRESHOLDS['info']:
            category = 'active'
        
        return {
            'days_since_deploy': days_since_deploy,
            'last_deployed': last_deployed_str if history else 'Never',
            'sync_status': sync_status,
            'health_status': health_status,
            'auto_sync_enabled': auto_sync_enabled,
            'category': category,
            'is_problematic': is_problematic
        }
    
    def process_single_app(self, app: Dict, start_date: datetime, end_date: datetime) -> Dict:
        """Process a single application - get all data in one call"""
        app_name = app.get('metadata', {}).get('name', 'unknown')
        namespace = app.get('metadata', {}).get('namespace', 'default')
        app_data = self.get_application_details(app_name)
        
        if not app_data:
            return {
                'app_name': app_name,
                'namespace': namespace,
                'error': True,
                'deployments': [],
                'failures': [],
                'recovery_times': [],
                'sync_durations': []
            }
        
        history = app_data.get('status', {}).get('history', [])
        
        result = {
            'app_name': app_name,
            'namespace': namespace,
            'error': False,
            'deployments': [],
            'failures': [],
            'recovery_times': [],
            'sync_durations': [],
            'current_sync_status': app_data.get('status', {}).get('sync', {}).get('status', 'Unknown'),
            'current_health_status': app_data.get('status', {}).get('health', {}).get('status', 'Unknown'),
        }
        
        # Check if stuck in sync
        is_stuck, minutes_stuck = self.check_stuck_in_sync(app_data)
        result['stuck_in_sync'] = is_stuck
        result['stuck_minutes'] = minutes_stuck
        
        # Analyze staleness
        staleness = self.analyze_staleness(app_data)
        result['staleness'] = staleness
        
        # Process deployment history
        previous_failed = False
        failure_time = None
        
        for i, deployment in enumerate(history):
            deployed_at_str = deployment.get('deployedAt')
            if not deployed_at_str:
                continue
            
            try:
                deployed_at = datetime.strptime(deployed_at_str, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                continue
            
            if start_date <= deployed_at <= end_date:
                # Calculate sync duration
                operation_state = deployment.get('operationState', {})
                started_at_str = operation_state.get('startedAt', '')
                finished_at_str = operation_state.get('finishedAt', deployed_at_str)
                
                if started_at_str and finished_at_str:
                    try:
                        started_at = datetime.strptime(started_at_str, '%Y-%m-%dT%H:%M:%SZ')
                        finished_at = datetime.strptime(finished_at_str, '%Y-%m-%dT%H:%M:%SZ')
                        sync_duration_seconds = (finished_at - started_at).total_seconds()
                        if sync_duration_seconds > 0:
                            result['sync_durations'].append(sync_duration_seconds)
                    except ValueError:
                        pass
                
                # Check actual failure status from ArgoCD
                phase = operation_state.get('phase', '')
                
                # Actual failure detection based on ArgoCD status
                is_failed = phase in ['Failed', 'Error']
                
                # Also check if sync result shows failure
                sync_result = deployment.get('syncResult', {})
                if sync_result:
                    # If resources have errors
                    resources = sync_result.get('resources', [])
                    has_errors = any(r.get('status') in ['Failed', 'Error'] for r in resources)
                    if has_errors:
                        is_failed = True
                
                deployment_info = {
                    'time': deployed_at,
                    'revision': deployment.get('revision', ''),
                    'phase': phase,
                    'is_failed': is_failed
                }
                
                result['deployments'].append(deployment_info)
                
                if is_failed:
                    result['failures'].append(deployment_info)
                    previous_failed = True
                    failure_time = deployed_at
                elif previous_failed and failure_time:
                    # This deployment came after a failure - calculate recovery time
                    recovery_hours = (deployed_at - failure_time).total_seconds() / 3600
                    result['recovery_times'].append(recovery_hours)
                    previous_failed = False
                    failure_time = None
        
        return result
    
    def calculate_deployment_frequency(self, apps_data: List[Dict]) -> Dict:
        """Calculate Deployment Frequency (DORA Metric 1)"""
        print(f"\n📈 Calculating Deployment Frequency for {len(apps_data)} applications...")
        print(f"   Using {MAX_WORKERS} parallel workers")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        deployment_counts = defaultdict(int)
        app_deployment_counts = defaultdict(int)
        daily_deployments = defaultdict(int)
        
        processed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self.process_single_app, app, start_date, end_date): app
                for app in apps_data
            }
            
            for future in as_completed(futures):
                processed += 1
                
                if processed % PROGRESS_INTERVAL == 0 or processed == len(apps_data):
                    print(f"   Progress: {processed}/{len(apps_data)} apps "
                          f"({(processed/len(apps_data)*100):.1f}%)")
                
                try:
                    result = future.result()
                    
                    if result.get('error'):
                        continue
                    
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
        
        return {
            'avg_lead_time_hours': 0,
            'median_lead_time_hours': 0,
            'p95_lead_time_hours': 0,
            'dora_level': 'unknown',
            'note': 'Lead time calculation requires Git integration'
        }
    
    def calculate_change_failure_rate(self, processed_results: List[Dict]) -> Dict:
        """Calculate Change Failure Rate (DORA Metric 3) using actual ArgoCD status"""
        print(f"\n❌ Calculating Change Failure Rate (using actual failure status)...")
        
        total_deployments = 0
        failed_deployments = 0
        app_failure_rates = {}
        
        for result in processed_results:
            if result.get('error'):
                continue
            
            app_name = result['app_name']
            deployments = result['deployments']
            failures = result['failures']
            
            app_total = len(deployments)
            app_failed = len(failures)
            
            total_deployments += app_total
            failed_deployments += app_failed
            
            if app_total > 0:
                app_failure_rates[app_name] = round((app_failed / app_total) * 100, 2)
        
        failure_rate = (failed_deployments / total_deployments * 100) if total_deployments > 0 else 0
        
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
            'note': 'Using actual ArgoCD failure status (Failed, Error phases)'
        }
    
    def calculate_mttr(self, processed_results: List[Dict]) -> Dict:
        """Calculate Mean Time to Recovery (DORA Metric 4) based on actual failures"""
        print(f"\n🔧 Calculating Mean Time to Recovery (based on actual failures)...")
        
        recovery_times = []
        app_mttr = {}
        
        for result in processed_results:
            if result.get('error'):
                continue
            
            app_name = result['app_name']
            app_recovery_times = result['recovery_times']
            
            recovery_times.extend(app_recovery_times)
            
            if app_recovery_times:
                app_mttr[app_name] = round(
                    sum(app_recovery_times) / len(app_recovery_times), 2
                )
        
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
            'app_breakdown': app_mttr,
            'note': 'Based on actual ArgoCD failure detection'
        }
    
    def analyze_stuck_syncs(self, processed_results: List[Dict]) -> Dict:
        """Analyze applications stuck in infinite sync"""
        print(f"\n⚠️  Analyzing apps stuck in sync...")
        
        stuck_apps = []
        
        for result in processed_results:
            if result.get('error'):
                continue
            
            if result.get('stuck_in_sync', False):
                stuck_apps.append({
                    'app_name': result['app_name'],
                    'minutes_stuck': result.get('stuck_minutes', 0),
                    'sync_status': result.get('current_sync_status', 'Unknown'),
                    'health_status': result.get('current_health_status', 'Unknown')
                })
        
        # Sort by time stuck (longest first)
        stuck_apps.sort(key=lambda x: x['minutes_stuck'], reverse=True)
        
        return {
            'total_stuck': len(stuck_apps),
            'apps': stuck_apps,
            'threshold_minutes': STUCK_SYNC_THRESHOLD_MINUTES
        }
    
    def analyze_application_staleness(self, processed_results: List[Dict]) -> Dict:
        """Analyze application staleness (stable vs stale)"""
        print(f"\n📅 Analyzing application staleness...")
        
        stable_apps = []
        stale_apps = []
        active_apps = []
        recent_apps = []
        
        for result in processed_results:
            if result.get('error'):
                continue
            
            staleness = result.get('staleness', {})
            app_info = {
                'app_name': result['app_name'],
                'days_since_deploy': staleness.get('days_since_deploy', 0),
                'last_deployed': staleness.get('last_deployed', 'Never'),
                'sync_status': staleness.get('sync_status', 'Unknown'),
                'health_status': staleness.get('health_status', 'Unknown'),
                'auto_sync_enabled': staleness.get('auto_sync_enabled', False)
            }
            
            category = staleness.get('category', 'recent')
            
            if category == 'stable':
                stable_apps.append(app_info)
            elif category == 'stale':
                stale_apps.append(app_info)
            elif category == 'active':
                active_apps.append(app_info)
            else:
                recent_apps.append(app_info)
        
        # Sort by days since deploy
        stable_apps.sort(key=lambda x: x['days_since_deploy'], reverse=True)
        stale_apps.sort(key=lambda x: x['days_since_deploy'], reverse=True)
        
        return {
            'stable_apps': stable_apps,
            'stale_apps': stale_apps,
            'active_apps': active_apps,
            'recent_apps': recent_apps,
            'thresholds': STALENESS_THRESHOLDS
        }
    
    def analyze_sync_duration(self, processed_results: List[Dict]) -> Dict:
        """Analyze sync duration performance"""
        print(f"\n⏱️  Analyzing sync duration performance...")
        
        sync_durations = []
        app_sync_durations = {}
        
        for result in processed_results:
            if result.get('error'):
                continue
            
            app_name = result['app_name']
            app_durations = result.get('sync_durations', [])
            
            if app_durations:
                sync_durations.extend(app_durations)
                app_sync_durations[app_name] = {
                    'avg_seconds': round(sum(app_durations) / len(app_durations), 1),
                    'max_seconds': round(max(app_durations), 1),
                    'min_seconds': round(min(app_durations), 1),
                    'count': len(app_durations)
                }
        
        if not sync_durations:
            return {
                'avg_sync_seconds': 0,
                'median_sync_seconds': 0,
                'p95_sync_seconds': 0,
                'p99_sync_seconds': 0,
                'slowest_apps': [],
                'note': 'No sync duration data available'
            }
        
        sync_durations.sort()
        count = len(sync_durations)
        
        avg_sync = sum(sync_durations) / count
        median_sync = sync_durations[count // 2]
        p95_index = int(count * 0.95)
        p99_index = int(count * 0.99)
        p95_sync = sync_durations[p95_index] if p95_index < count else sync_durations[-1]
        p99_sync = sync_durations[p99_index] if p99_index < count else sync_durations[-1]
        
        # Get slowest apps
        slowest_apps = sorted(
            app_sync_durations.items(),
            key=lambda x: x[1]['avg_seconds'],
            reverse=True
        )[:10]
        
        slowest_apps_list = [
            {
                'app_name': app,
                'avg_seconds': data['avg_seconds'],
                'max_seconds': data['max_seconds'],
                'sync_count': data['count']
            }
            for app, data in slowest_apps
        ]
        
        return {
            'avg_sync_seconds': round(avg_sync, 1),
            'median_sync_seconds': round(median_sync, 1),
            'p95_sync_seconds': round(p95_sync, 1),
            'p99_sync_seconds': round(p99_sync, 1),
            'total_syncs': count,
            'slowest_apps': slowest_apps_list
        }
    
    def analyze_by_namespace(self, processed_results: List[Dict]) -> Dict:
        """Break down metrics by namespace"""
        print(f"\n📊 Analyzing metrics by namespace...")
        
        namespace_data = defaultdict(lambda: {
            'deployments': 0,
            'failures': 0,
            'recovery_times': [],
            'apps': set()
        })
        
        for result in processed_results:
            if result.get('error'):
                continue
            
            app_name = result['app_name']
            # Extract namespace from app name (format: namespace/app or just app)
            namespace = result.get('namespace', 'default')
            
            namespace_data[namespace]['apps'].add(app_name)
            namespace_data[namespace]['deployments'] += len(result.get('deployments', []))
            namespace_data[namespace]['failures'] += len(result.get('failures', []))
            namespace_data[namespace]['recovery_times'].extend(result.get('recovery_times', []))
        
        # Calculate metrics per namespace
        namespace_metrics = {}
        
        for ns, data in namespace_data.items():
            total_deploys = data['deployments']
            total_failures = data['failures']
            recovery_times = data['recovery_times']
            
            if total_deploys == 0:
                continue
            
            failure_rate = (total_failures / total_deploys * 100) if total_deploys > 0 else 0
            avg_mttr = sum(recovery_times) / len(recovery_times) if recovery_times else 0
            
            # Determine DORA level for namespace
            if failure_rate < 15:
                level = 'elite'
            elif failure_rate < 30:
                level = 'high'
            elif failure_rate < 45:
                level = 'medium'
            else:
                level = 'low'
            
            namespace_metrics[ns] = {
                'app_count': len(data['apps']),
                'total_deployments': total_deploys,
                'failed_deployments': total_failures,
                'failure_rate': round(failure_rate, 2),
                'avg_mttr_hours': round(avg_mttr, 2),
                'avg_mttr_minutes': round(avg_mttr * 60, 2),
                'dora_level': level
            }
        
        # Sort by deployment count
        sorted_namespaces = sorted(
            namespace_metrics.items(),
            key=lambda x: x[1]['total_deployments'],
            reverse=True
        )
        
        return {
            'namespaces': dict(sorted_namespaces),
            'total_namespaces': len(namespace_metrics)
        }
    
    def analyze_chart_compliance(self, apps_data: List[Dict]) -> Dict:
        """Analyze Helm chart versions and compliance"""
        print(f"\n📦 Analyzing Helm chart compliance...")
        
        helm_apps = []
        git_apps = []
        chart_distribution = defaultdict(lambda: defaultdict(lambda: {
            'apps': [],
            'count': 0
        }))
        
        for app in apps_data:
            app_name = app.get('metadata', {}).get('name', 'unknown')
            namespace = app.get('metadata', {}).get('namespace', 'default')
            source = app.get('spec', {}).get('source', {})
            
            if 'chart' in source:
                # This is a Helm chart app
                chart_name = source.get('chart', 'unknown')
                chart_version = source.get('targetRevision', 'unknown')
                chart_repo = source.get('repoURL', 'unknown')
                release_name = source.get('helm', {}).get('releaseName', app_name)
                
                app_info = {
                    'app_name': app_name,
                    'namespace': namespace,
                    'chart_name': chart_name,
                    'chart_version': chart_version,
                    'chart_repo': chart_repo,
                    'release_name': release_name
                }
                
                helm_apps.append(app_info)
                chart_distribution[chart_name][chart_version]['apps'].append(app_info)
                chart_distribution[chart_name][chart_version]['count'] += 1
            else:
                # This is a Git repo app
                git_repo = source.get('repoURL', 'unknown')
                branch = source.get('targetRevision', 'unknown')
                path = source.get('path', '/')
                
                git_apps.append({
                    'app_name': app_name,
                    'namespace': namespace,
                    'git_repo': git_repo,
                    'branch': branch,
                    'path': path
                })
        
        # Analyze each chart for version distribution
        chart_summary = {}
        for chart_name, versions in chart_distribution.items():
            version_list = list(versions.keys())
            
            # Sort versions (newest first, assuming semantic versioning)
            try:
                version_list_sorted = sorted(
                    version_list,
                    key=lambda v: [int(x) if x.isdigit() else x for x in v.split('.')],
                    reverse=True
                )
            except:
                version_list_sorted = sorted(version_list, reverse=True)
            
            latest_version = version_list_sorted[0] if version_list_sorted else 'unknown'
            total_apps = sum(v['count'] for v in versions.values())
            apps_on_latest = versions[latest_version]['count']
            apps_outdated = total_apps - apps_on_latest
            
            chart_summary[chart_name] = {
                'latest_version': latest_version,
                'total_apps': total_apps,
                'apps_on_latest': apps_on_latest,
                'apps_outdated': apps_outdated,
                'versions': {
                    ver: {
                        'count': data['count'],
                        'is_latest': ver == latest_version,
                        'apps': data['apps']
                    }
                    for ver, data in versions.items()
                }
            }
        
        # Find all apps on outdated versions
        outdated_apps = []
        for chart_name, summary in chart_summary.items():
            latest = summary['latest_version']
            for version, data in summary['versions'].items():
                if version != latest:
                    for app in data['apps']:
                        outdated_apps.append({
                            'app_name': app['app_name'],
                            'namespace': app['namespace'],
                            'chart_name': chart_name,
                            'current_version': version,
                            'latest_version': latest,
                            'chart_repo': app['chart_repo']
                        })
        
        # Sort outdated apps by chart name then app name
        outdated_apps.sort(key=lambda x: (x['chart_name'], x['app_name']))
        
        print(f"   ✓ Found {len(helm_apps)} Helm apps, {len(git_apps)} Git apps")
        print(f"   ✓ Tracked {len(chart_summary)} unique charts")
        print(f"   ✓ {len(outdated_apps)} apps on outdated chart versions")
        
        return {
            'total_helm_apps': len(helm_apps),
            'total_git_apps': len(git_apps),
            'total_charts': len(chart_summary),
            'apps_on_latest': sum(s['apps_on_latest'] for s in chart_summary.values()),
            'apps_outdated': len(outdated_apps),
            'chart_summary': chart_summary,
            'outdated_apps': outdated_apps,
            'helm_apps_detail': helm_apps,
            'git_apps_detail': git_apps
        }
    
    def generate_dora_report(self) -> Dict:
        """Generate complete DORA metrics report with all enhancements"""
        print(f"\n{'='*70}")
        print(f"🚀 Generating Enhanced DORA Metrics for: {self.cluster_name}")
        print(f"   Time Period: Last {DAYS_TO_ANALYZE} days")
        print(f"   Parallel Workers: {MAX_WORKERS}")
        print(f"   Stuck Sync Threshold: {STUCK_SYNC_THRESHOLD_MINUTES} minutes")
        print(f"{'='*70}")
        
        start_time = datetime.now()
        
        apps = self.get_applications()
        print(f"\n✓ Found {len(apps)} applications to analyze")
        
        if not apps:
            print("❌ No applications found. Check your token and URL configuration.")
            return None
        
        # Process all apps once and store results
        print(f"\n🔄 Processing all applications in parallel...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS_TO_ANALYZE)
        
        processed_results = []
        processed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(self.process_single_app, app, start_date, end_date): app
                for app in apps
            }
            
            for future in as_completed(futures):
                processed += 1
                
                if processed % PROGRESS_INTERVAL == 0 or processed == len(apps):
                    print(f"   Progress: {processed}/{len(apps)} apps "
                          f"({(processed/len(apps)*100):.1f}%)")
                
                try:
                    result = future.result()
                    processed_results.append(result)
                except Exception as e:
                    print(f"   ⚠️  Error: {e}")
        
        # Calculate all metrics using processed results
        deployment_freq = self.calculate_deployment_frequency(apps)
        lead_time = self.calculate_lead_time(apps)
        failure_rate = self.calculate_change_failure_rate(processed_results)
        mttr = self.calculate_mttr(processed_results)
        stuck_syncs = self.analyze_stuck_syncs(processed_results)
        staleness = self.analyze_application_staleness(processed_results)
        sync_performance = self.analyze_sync_duration(processed_results)
        namespace_breakdown = self.analyze_by_namespace(processed_results)
        chart_compliance = self.analyze_chart_compliance(apps)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"✅ Report generation completed in {duration:.1f} seconds")
        print(f"   Total API calls: {self.api_call_count}")
        print(f"   Average: {self.api_call_count/duration:.1f} calls/second")
        print(f"{'='*70}")
        
        return {
            'team_name': TEAM_NAME,
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
            },
            'operational_insights': {
                'stuck_syncs': stuck_syncs,
                'staleness_analysis': staleness,
                'sync_performance': sync_performance,
                'namespace_breakdown': namespace_breakdown,
                'chart_compliance': chart_compliance
            }
        }


def print_dora_summary(report: Dict):
    """Print a formatted summary of DORA metrics"""
    if not report:
        return
        
    metrics = report['metrics']
    insights = report.get('operational_insights', {})
    
    print(f"\n{'='*80}")
    print(f"📊 DORA METRICS REPORT - {report['cluster'].upper()}")
    print(f"{'='*80}")
    print(f"Time Period: {report['time_period_days']} days")
    print(f"Total Applications: {report['total_applications']}")
    print(f"Generation Time: {report['generation_time_seconds']}s")
    print(f"API Calls Made: {report['api_calls_made']}")
    print(f"Generated: {report['generated_at']}")
    print(f"{'='*80}\n")
    
    # DORA Metrics
    df = metrics['deployment_frequency']
    print("1. 📈 DEPLOYMENT FREQUENCY")
    print(f"   Total Deployments: {df['total_deployments']}")
    print(f"   Per Day: {df['deployments_per_day']}")
    print(f"   DORA Level: {df['dora_level'].upper()} - {df['dora_description']}")
    print()
    
    lt = metrics['lead_time_for_changes']
    print("2. ⏱️  LEAD TIME FOR CHANGES")
    print(f"   DORA Level: {lt['dora_level'].upper()}")
    print(f"   Note: {lt['note']}")
    print()
    
    cfr = metrics['change_failure_rate']
    print("3. ❌ CHANGE FAILURE RATE")
    print(f"   Total Deployments: {cfr['total_deployments']}")
    print(f"   Failed Deployments: {cfr['failed_deployments']}")
    print(f"   Failure Rate: {cfr['change_failure_rate']}%")
    print(f"   DORA Level: {cfr['dora_level'].upper()} - {cfr['dora_description']}")
    print(f"   Note: {cfr['note']}")
    print()
    
    mttr = metrics['mean_time_to_recovery']
    print("4. 🔧 MEAN TIME TO RECOVERY (MTTR)")
    print(f"   Average: {mttr.get('avg_mttr_hours', 0)} hours ({mttr.get('avg_mttr_minutes', 0)} minutes)")
    print(f"   Incidents Recovered: {mttr.get('incidents_recovered', 0)}")
    print(f"   DORA Level: {mttr['dora_level'].upper()}")
    print(f"   Note: {mttr['note']}")
    print()
    
    # Operational Insights
    print(f"{'='*80}")
    print("🔍 OPERATIONAL INSIGHTS")
    print(f"{'='*80}\n")
    
    # Stuck Syncs
    stuck = insights.get('stuck_syncs', {})
    print(f"⚠️  APPS STUCK IN SYNC (>{stuck.get('threshold_minutes', 30)} minutes): {stuck.get('total_stuck', 0)}")
    if stuck.get('apps'):
        for app in stuck['apps'][:10]:
            hours = app['minutes_stuck'] / 60
            print(f"   - {app['app_name']}: {hours:.1f} hours (Health: {app['health_status']})")
    else:
        print("   ✓ No apps stuck in sync")
    print()
    
    # Staleness
    staleness = insights.get('staleness_analysis', {})
    stale_apps = staleness.get('stale_apps', [])
    stable_apps = staleness.get('stable_apps', [])
    
    print(f"📅 APPLICATION STALENESS ANALYSIS")
    print(f"   ⚠️  Stale (Needs Attention): {len(stale_apps)}")
    if stale_apps:
        for app in stale_apps[:5]:
            print(f"      - {app['app_name']}: {app['days_since_deploy']} days "
                  f"(Sync: {app['sync_status']}, Health: {app['health_status']})")
    
    print(f"   ✅ Stable (Old but Healthy): {len(stable_apps)}")
    if stable_apps:
        for app in stable_apps[:5]:
            print(f"      - {app['app_name']}: {app['days_since_deploy']} days "
                  f"(Sync: {app['sync_status']}, Health: {app['health_status']})")
    print()
    
    # Sync Performance
    sync_perf = insights.get('sync_performance', {})
    print(f"⏱️  SYNC PERFORMANCE")
    print(f"   Average Sync Time: {sync_perf.get('avg_sync_seconds', 0)} seconds")
    print(f"   P95 Sync Time: {sync_perf.get('p95_sync_seconds', 0)} seconds")
    print(f"   P99 Sync Time: {sync_perf.get('p99_sync_seconds', 0)} seconds")
    slowest = sync_perf.get('slowest_apps', [])
    if slowest:
        print(f"   🐌 Slowest Apps:")
        for app in slowest[:5]:
            print(f"      - {app['app_name']}: {app['avg_seconds']}s avg (max: {app['max_seconds']}s)")
    print()
    
    # Namespace Breakdown
    ns_breakdown = insights.get('namespace_breakdown', {})
    namespaces = ns_breakdown.get('namespaces', {})
    if namespaces:
        print(f"📊 PERFORMANCE BY NAMESPACE ({ns_breakdown.get('total_namespaces', 0)} namespaces)")
        for ns, data in list(namespaces.items())[:10]:
            print(f"   {ns}:")
            print(f"      Apps: {data['app_count']}, Deploys: {data['total_deployments']}, "
                  f"Failure Rate: {data['failure_rate']}%, Level: {data['dora_level'].upper()}")
    print()
    
    # Chart Compliance
    chart_compliance = insights.get('chart_compliance', {})
    if chart_compliance.get('total_helm_apps', 0) > 0:
        print(f"📦 HELM CHART COMPLIANCE")
        print(f"   Total Helm Apps: {chart_compliance['total_helm_apps']}")
        print(f"   Total Git Apps: {chart_compliance['total_git_apps']}")
        print(f"   Unique Charts: {chart_compliance['total_charts']}")
        print(f"   ✅ Up-to-date: {chart_compliance['apps_on_latest']} apps")
        print(f"   ⚠️  Outdated: {chart_compliance['apps_outdated']} apps")
        
        chart_summary = chart_compliance.get('chart_summary', {})
        if chart_summary:
            print(f"   \n   Most Used Charts:")
            sorted_charts = sorted(
                chart_summary.items(),
                key=lambda x: x[1]['total_apps'],
                reverse=True
            )
            for chart_name, data in sorted_charts[:5]:
                outdated_count = data['apps_outdated']
                status_icon = "⚠️" if outdated_count > 0 else "✅"
                print(f"      {status_icon} {chart_name}: {data['total_apps']} apps "
                      f"(latest: {data['latest_version']}, {outdated_count} outdated)")
        
        outdated_apps = chart_compliance.get('outdated_apps', [])
        if outdated_apps:
            print(f"   \n   🔴 Critical Updates Needed:")
            for app in outdated_apps[:5]:
                print(f"      - {app['app_name']}: {app['chart_name']} "
                      f"{app['current_version']} → {app['latest_version']}")
    print()
    
    # Overall Assessment
    levels = [df['dora_level'], lt['dora_level'], cfr['dora_level'], mttr['dora_level']]
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


def save_operational_insights_csv(report: Dict, filename: str):
    """Save operational insights as separate CSV"""
    if not report:
        return
    
    insights = report.get('operational_insights', {})
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Stuck Syncs
        writer.writerow(['APPS STUCK IN SYNC'])
        writer.writerow(['App Name', 'Minutes Stuck', 'Hours Stuck', 'Sync Status', 'Health Status'])
        
        stuck = insights.get('stuck_syncs', {})
        for app in stuck.get('apps', []):
            writer.writerow([
                app['app_name'],
                app['minutes_stuck'],
                round(app['minutes_stuck'] / 60, 2),
                app['sync_status'],
                app['health_status']
            ])
        
        writer.writerow([])
        writer.writerow(['STALE APPLICATIONS (Need Attention)'])
        writer.writerow(['App Name', 'Days Since Deploy', 'Last Deployed', 'Sync Status', 'Health Status', 'Auto-Sync'])
        
        staleness = insights.get('staleness_analysis', {})
        for app in staleness.get('stale_apps', []):
            writer.writerow([
                app['app_name'],
                app['days_since_deploy'],
                app['last_deployed'],
                app['sync_status'],
                app['health_status'],
                app['auto_sync_enabled']
            ])
        
        writer.writerow([])
        writer.writerow(['STABLE APPLICATIONS (Old but Healthy)'])
        writer.writerow(['App Name', 'Days Since Deploy', 'Last Deployed', 'Sync Status', 'Health Status'])
        
        for app in staleness.get('stable_apps', []):
            writer.writerow([
                app['app_name'],
                app['days_since_deploy'],
                app['last_deployed'],
                app['sync_status'],
                app['health_status']
            ])
    
    print(f"✅ Operational insights CSV saved: {filename}")


def main():
    """Main execution function"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║    ArgoCD DORA Metrics Generator - ENHANCED VERSION      ║
    ║                                                           ║
    ║  Features:                                                ║
    ║  • Actual failure detection (not timing-based)           ║
    ║  • Infinite sync detection                                ║
    ║  • Staleness analysis (stable vs stale)                   ║
    ║  • Parallel processing for 3200+ apps                     ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    all_reports = []
    
    for cluster_name, config in ARGOCD_CLUSTERS.items():
        try:
            dora = ArgocdDoraMetricsEnhanced(
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
            insights_file = f"dora_insights_{cluster_name}_{timestamp}.csv"
            
            save_report_json(report, json_file)
            save_report_csv(report, csv_file)
            save_operational_insights_csv(report, insights_file)
            
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
