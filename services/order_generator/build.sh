#!/bin/bash
set -e

echo "Building order_generator Lambda package..."

# Clean previous build
rm -rf package dist
mkdir -p package dist

# Install dependencies
pip3 install -r requirements.txt -t package/

# Copy handler
cp handler.py package/

# Create zip
cd package
zip -r ../dist/order_generator.zip . -q
cd ..

echo "✓ Package created: dist/order_generator.zip"
