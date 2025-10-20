#!/bin/bash
# Quick Start Script for ArgoCD DORA Metrics

echo "=========================================="
echo "ArgoCD DORA Metrics - Quick Start"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

echo "✅ Python 3 found"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip3 install requests --quiet

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Check if configuration is set
echo ""
echo "🔧 Configuration Check"
echo "======================================"

if grep -q "YOUR_PROD_TOKEN_HERE" argocd_dora_metrics.py; then
    echo "⚠️  WARNING: You need to configure your ArgoCD tokens"
    echo ""
    echo "Edit argocd_dora_metrics.py and update:"
    echo "  1. ARGOCD_CLUSTERS dictionary with your URLs"
    echo "  2. Add your ArgoCD API tokens"
    echo ""
    echo "To generate ArgoCD token:"
    echo "  argocd login argocd.yourcompany.com"
    echo "  argocd account generate-token --account admin"
    echo ""
    exit 1
fi

echo "✅ Configuration appears to be set"

# Run the metrics generator
echo ""
echo "🚀 Generating DORA Metrics Report..."
echo "======================================"
python3 argocd_dora_metrics.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Reports generated successfully!"
    echo ""
    
    # Find the latest JSON report
    latest_json=$(ls -t dora_report_*.json 2>/dev/null | head -1)
    
    if [ -n "$latest_json" ]; then
        echo "📊 Generating HTML Dashboard..."
        python3 generate_dora_dashboard.py "$latest_json"
        
        if [ $? -eq 0 ]; then
            latest_html=$(ls -t dora_report_*.html 2>/dev/null | head -1)
            echo ""
            echo "🎉 Success! Generated files:"
            echo "  📄 JSON Report: $latest_json"
            echo "  🌐 HTML Dashboard: $latest_html"
            echo ""
            echo "To view the dashboard:"
            echo "  open $latest_html"
            echo "  # or"
            echo "  python3 -m http.server 8000"
            echo "  # then visit http://localhost:8000/$latest_html"
        fi
    fi
else
    echo "❌ Failed to generate reports"
    echo "Check the error messages above"
    exit 1
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Review the HTML dashboard in your browser"
echo "2. Schedule regular report generation with cron"
echo "3. Integrate with your monitoring/dashboard tools"
echo "4. Track metrics over time to measure improvements"
echo ""
