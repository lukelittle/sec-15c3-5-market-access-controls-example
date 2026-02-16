#!/bin/bash
set -e

echo "Building order_router Lambda package..."

rm -rf package dist
mkdir -p package dist

pip install -r requirements.txt -t package/
cp handler.py package/

cd package
zip -r ../dist/order_router.zip . -q
cd ..

echo "✓ Package created: dist/order_router.zip"
