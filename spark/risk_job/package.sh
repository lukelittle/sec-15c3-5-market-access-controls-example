#!/bin/bash
set -e

echo "Packaging Spark risk detection job..."

rm -rf dist
mkdir -p dist

# Copy Python file
cp risk_detector.py dist/

# Create zip for dependencies if needed
cd dist
zip -r risk_detector.zip risk_detector.py
cd ..

echo "✓ Spark job packaged: dist/risk_detector.zip"
