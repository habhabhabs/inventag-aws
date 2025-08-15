#!/bin/bash
set -e

# InvenTag Documentation Version Creation Script
# Creates a new documentation version and tags the release

if [ $# -eq 0 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 v4.3.0"
    echo ""
    echo "Available git tags:"
    git tag --list --sort=-version:refname | head -10
    exit 1
fi

VERSION="$1"
echo "🚀 Creating documentation version: $VERSION"

# Ensure we're in the right directory
if [ ! -f "website/docusaurus.config.js" ]; then
    echo "❌ Error: Must run from InvenTag AWS root directory"
    exit 1
fi

# Check if tag already exists
if git tag --list | grep -q "^$VERSION$"; then
    echo "ℹ️  Git tag $VERSION already exists"
else
    echo "📦 Creating git tag: $VERSION"
    git tag "$VERSION"
    echo "✅ Git tag created"
fi

# Navigate to website directory
cd website

echo "📚 Creating Docusaurus documentation version..."
npm run docusaurus -- docs:version "$VERSION"

# Update the current version label in docusaurus.config.js
echo "🔄 Updating current version label..."
NEXT_MAJOR=$(echo $VERSION | sed 's/v//' | awk -F'.' '{print "v" ($1+1) ".0.0-dev"}')
sed -i '' "s/v[0-9]*\.[0-9]*\.[0-9]*-dev (Current)/$NEXT_MAJOR (Current)/" docusaurus.config.js

echo "✅ Documentation version $VERSION created successfully!"
echo ""
echo "📋 Summary:"
echo "  - Git tag: $VERSION (created/exists)"
echo "  - Documentation version: $VERSION" 
echo "  - Next dev version: $NEXT_MAJOR"
echo ""
echo "📝 Next steps:"
echo "  1. Commit the versioned documentation:"
echo "     git add ."
echo "     git commit -m 'docs: create documentation version $VERSION'"
echo "  2. Push tags and changes:"
echo "     git push origin main --tags"
echo "  3. Test the versioned docs:"
echo "     cd website && npm start"