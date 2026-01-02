#!/bin/bash

# Frontend Code Quality Check Script
# This script checks code formatting using Prettier

echo "========================================="
echo "Frontend Code Quality Check"
echo "========================================="
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

# Run Prettier check
echo "🎨 Checking code formatting with Prettier..."
if npm run format:check; then
    echo "✅ All frontend files are properly formatted!"
    exit 0
else
    echo ""
    echo "❌ Some files need formatting."
    echo "💡 Run 'npm run format' to auto-format all files."
    exit 1
fi
