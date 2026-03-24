#!/bin/bash
set -e

echo "Building operator_console Lambda package..."

rm -rf package dist
mkdir -p package dist

pip3 install -r requirements.txt -t package/
cp handler.py package/

cd package
zip -r ../dist/operator_console.zip . -q
cd ..

echo "✓ Package created: dist/operator_console.zip"
