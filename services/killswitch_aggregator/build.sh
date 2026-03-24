#!/bin/bash
set -e

echo "Building killswitch_aggregator Lambda package..."

rm -rf package dist
mkdir -p package dist

pip3 install -r requirements.txt -t package/
cp handler.py package/

cd package
zip -r ../dist/killswitch_aggregator.zip . -q
cd ..

echo "✓ Package created: dist/killswitch_aggregator.zip"
