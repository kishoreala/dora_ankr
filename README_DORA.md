# ArgoCD DORA Metrics Configuration

## Setup Instructions

### 1. Update Cluster Configuration

Edit `argocd_dora_metrics.py` and update the `ARGOCD_CLUSTERS` dictionary:

```python
ARGOCD_CLUSTERS = {
    'production': {
        'url': 'https://argocd.prod.yourcompany.com',
        'token': 'YOUR_ARGOCD_TOKEN_HERE'
    },
    'staging': {
        'url': 'https://argocd.staging.yourcompany.com',
        'token': 'YOUR_ARGOCD_TOKEN_HERE'
    }
}
```

### 2. Generate ArgoCD API Token

```bash
# Login to ArgoCD
argocd login argocd.yourcompany.com

# Generate token (expires in 1 year)
argocd account generate-token --account admin --expires-in 8760h

# Or create a project-specific token
argocd proj role create-token PROJECT_NAME ROLE_NAME
```

### 3. Install Dependencies

```bash
pip install requests
```

### 4. Run the Script

```bash
# Basic usage
python3 argocd_dora_metrics.py

# With custom time period (edit DAYS_TO_ANALYZE in script)
python3 argocd_dora_metrics.py
```

## Configuration Options

### Time Period
Change the analysis window in the script:
```python
DAYS_TO_ANALYZE = 30  # Default: last 30 days
```

### DORA Performance Levels
The script uses industry-standard DORA levels:

**Deployment Frequency:**
- Elite: Multiple deploys per day
- High: Once per day to once per week
- Medium: Once per week to once per month  
- Low: Fewer than once per month

**Lead Time for Changes:**
- Elite: < 1 hour
- High: < 1 day
- Medium: < 1 week
- Low: > 1 week

**Change Failure Rate:**
- Elite: < 15%
- High: 15-30%
- Medium: 30-45%
- Low: > 45%

**Mean Time to Recovery:**
- Elite: < 1 hour
- High: < 1 day
- Medium: < 1 week
- Low: > 1 week

## Output Files

The script generates three types of files:

1. **JSON Report**: `dora_report_{cluster}_{timestamp}.json`
   - Complete detailed metrics
   - Machine-readable format
   - Includes per-app breakdowns

2. **CSV Report**: `dora_report_{cluster}_{timestamp}.csv`
   - Summary metrics
   - Easy to import to Excel/Sheets
   - Great for trending over time

3. **Combined Report**: `dora_report_combined_{timestamp}.json`
   - All clusters in one file
   - For cross-cluster comparison

## Example Output

```
================================================================================
DORA METRICS REPORT - PRODUCTION
================================================================================
Time Period: 30 days
Total Applications: 45
Generated: 2026-01-15T10:30:00

1. DEPLOYMENT FREQUENCY
   Total Deployments: 342
   Per Day: 11.4
   Per Week: 79.8
   Per Month: 342.0
   DORA Level: ELITE - Multiple deploys per day

2. LEAD TIME FOR CHANGES
   Average: 0.8 hours
   DORA Level: ELITE
   Note: Lead time requires Git commit data integration

3. CHANGE FAILURE RATE
   Total Deployments: 342
   Failed Deployments: 28
   Failure Rate: 8.19%
   DORA Level: ELITE - < 15%

4. MEAN TIME TO RECOVERY (MTTR)
   Average: 0.45 hours (27 minutes)
   Median: 0.3 hours
   Incidents Recovered: 28
   DORA Level: ELITE

================================================================================
OVERALL DORA PERFORMANCE: ELITE
================================================================================
```

## Scheduling with Cron

Generate reports automatically:

```bash
# Edit crontab
crontab -e

# Run daily at 9 AM
0 9 * * * cd /path/to/script && python3 argocd_dora_metrics.py >> /var/log/dora_metrics.log 2>&1

# Run weekly on Monday at 8 AM
0 8 * * 1 cd /path/to/script && python3 argocd_dora_metrics.py

# Run monthly on 1st at 7 AM
0 7 1 * * cd /path/to/script && python3 argocd_dora_metrics.py
```

## Integration with Dashboards

### Grafana Integration

1. Store reports in a time-series database
2. Create Grafana dashboard with panels for each metric
3. Set up alerts for degrading metrics

### Custom Dashboard

Use the JSON output to build custom dashboards:

```python
import json

# Load report
with open('dora_report_production_20260115.json') as f:
    data = json.load(f)

metrics = data['metrics']
deployment_freq = metrics['deployment_frequency']['deployments_per_day']
cfr = metrics['change_failure_rate']['change_failure_rate']
# ... visualize as needed
```

## Limitations & Notes

### Lead Time for Changes
- Requires Git commit timestamp data
- Currently shows placeholder values
- **Enhancement needed**: Integrate with Git API to get actual commit times

### Change Failure Rate
- Detects failures based on quick rollbacks (<1 hour)
- May not catch all failures
- **Enhancement**: Integrate with monitoring/alerting systems

### Mean Time to Recovery
- Based on deployment frequency patterns
- Assumes quick re-deploys indicate incident recovery
- **Enhancement**: Integrate with incident management systems (PagerDuty, Jira)

## Troubleshooting

### SSL Certificate Errors
If you encounter SSL errors:
```python
# The script already disables SSL warnings, but if needed:
import requests
requests.packages.urllib3.disable_warnings()
```

### Authentication Issues
```bash
# Verify token works
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://argocd.example.com/api/v1/applications
```

### No Data Returned
- Check that applications have deployment history
- Verify time period (DAYS_TO_ANALYZE) covers deployments
- Ensure API token has read permissions

## Advanced Usage

### Filter Specific Applications

Modify the script to filter by namespace or labels:

```python
def get_applications(self, namespace=None, labels=None):
    url = f'{self.argocd_url}/api/v1/applications'
    if namespace:
        url += f'?namespace={namespace}'
    # Add filtering logic
```

### Export to External Systems

```python
# Send to Slack
import requests
webhook_url = 'YOUR_SLACK_WEBHOOK'
requests.post(webhook_url, json={'text': f'DORA Report: {summary}'})

# Send to Datadog
from datadog import api
api.Metric.send(metric='dora.deployment_frequency', points=value)
```

## Next Steps

1. **Enhance Lead Time Calculation**: Integrate with Git API
2. **Improve Failure Detection**: Add monitoring system integration
3. **Add Trending**: Store historical data for trend analysis
4. **Create Visualizations**: Build Grafana dashboards
5. **Set Up Alerts**: Alert on degrading DORA metrics
