# InvenTag Documentation Maintenance Guide

This guide provides comprehensive information for maintaining and developing the InvenTag Docusaurus documentation site.

## Before you merge a docs change

```bash
cd website
npm ci
npm run build          # must succeed; broken links are printed as warnings
npm run check:links    # fails on broken links/anchors in the homepage or current docs
```

Optional, needs Playwright with Chromium (not a site dependency):

```bash
npm run serve -- --port 4173 --no-open &   # serves build/ under /inventag-aws/
npm run check:a11y -- --base http://localhost:4173/inventag-aws --shots ../screenshots
```

`check:a11y` tests text contrast (4.5:1) in light and dark mode, horizontal
scrolling at 320 and 390px, 44px touch targets, visible keyboard focus and
`prefers-reduced-motion`, and saves screenshots.

Archived versions (`versioned_docs/`) are snapshots and still contain old
broken links; they are reported but don't fail the check. Only edit them if a
build breaks.

## Logo, favicon and social card

Sources and the generator live in [`brand/`](brand/README.md):

```bash
npm run brand          # = python3 brand/generate_brand_assets.py
```

## Analytics

`docusaurus.config.js` enables Google Analytics 4 (`gtag`). As configured it
loads on every page view without asking for consent. See the review notes in
the pull request that introduced this section before relying on it in regions
that require consent.

## 🏗️ Architecture Overview

The InvenTag documentation uses Docusaurus v3.8.1 with a dual-platform approach:
- **GitHub**: Native markdown rendering for repository browsing
- **Docusaurus**: Enhanced web interface with search, navigation, and theming

### Directory Structure
```
website/                    # Docusaurus site configuration
├── docusaurus.config.js   # Main configuration file
├── sidebars.js            # Navigation structure
├── src/                   # Custom components and CSS
│   └── css/
│       └── custom.css     # Custom styling and branding
├── static/                # Static assets (images, icons)
│   └── img/
├── build/                 # Generated static site (auto-generated)
└── node_modules/          # Dependencies

../docs/                   # Documentation content (single source of truth)
├── index.md              # Homepage content
├── getting-started/      # Quick start guides
├── user-guides/          # User documentation
├── architecture/         # Technical architecture docs
├── development/          # Developer documentation
├── examples/             # Configuration examples
└── assets/               # Shared assets and images
```

## 🚀 Development Workflow

### Prerequisites
- Node.js >= 18.0.0
- npm (comes with Node.js)

### Quick Start Commands (from project root)
```bash
# Install dependencies
npm run docs:install

# Start development server with hot-reload
npm run docs:start

# Build production site
npm run docs:build

# Serve built site locally
npm run docs:serve

# Clear build cache
npm run docs:clear
```

### Development Server
The development server runs on `http://localhost:3000` with:
- **Hot reload**: Automatically refreshes on file changes
- **Live editing**: See changes instantly as you type
- **Search functionality**: Local search works in development mode
- **Responsive preview**: Test mobile/desktop layouts

## 📝 Content Management

### Adding New Documentation

1. **Create markdown files** in the appropriate `../docs/` subdirectory
2. **Add frontmatter** to each file:
   ```yaml
   ---
   title: "Page Title"
   description: "Brief description for SEO"
   ---
   ```
3. **Update navigation** in `sidebars.js` if needed
4. **Test locally** with `npm run docs:start`

### Markdown Guidelines

- Use GitHub-flavored markdown for compatibility
- Include descriptive alt text for images
- Use relative paths for internal links
- Follow consistent heading hierarchy (H1 → H2 → H3)

### Asset Management

- Place images in `../docs/assets/`
- Use relative paths: `![Alt text](./assets/image.png)`
- Optimize images for web (recommend < 500KB)
- Support both light/dark themes when possible

## 🔧 Configuration Management

### Main Configuration (`docusaurus.config.js`)

Key configuration areas:
- **Site metadata**: Title, tagline, favicon
- **Deployment settings**: GitHub Pages configuration
- **Theme configuration**: Navigation, footer, search
- **Plugin configuration**: Search, analytics (when added)

### Sidebar Configuration (`sidebars.js`)

Controls navigation structure:
- **Auto-generated**: Automatically creates navigation from file structure
- **Manual configuration**: Custom navigation with specific ordering
- **Categories**: Organized sections with collapsible groups

### Custom Styling (`src/css/custom.css`)

InvenTag branding includes:
- Custom color scheme and CSS variables
- Responsive design improvements
- Code syntax highlighting themes
- Custom component styling

## 🔍 Search Configuration

The site uses `@easyops-cn/docusaurus-search-local` for local search:
- **Automatic indexing**: Rebuilds search index on each build
- **Technical term optimization**: Configured for AWS/cloud terminology
- **Keyboard shortcuts**: Search with `/` or `Ctrl+K`
- **Contextual results**: Shows relevant snippets and sections

## 🚀 Deployment and CI/CD

### GitHub Actions Workflow

Located in `.github/workflows/docs-deploy.yml`:
- **Triggers**: Push to main branch, manual dispatch
- **Node.js setup**: Uses Node.js 20 with dependency caching
- **Build process**: Runs from `website/` directory
- **Deployment**: Automatically deploys to GitHub Pages

### Manual Deployment

```bash
# Build and deploy (from website directory)
cd website
npm run build
npm run deploy
```

### Pipeline Validation

```bash
# Safe validation (dry-run)
npm run docs:pipeline:safe

# Full pipeline (transform, validate, build)
npm run docs:pipeline
```

## 🛠️ Maintenance Tasks

### Regular Maintenance

1. **Dependency updates**: Monthly npm audit and updates
2. **Link validation**: Check for broken links quarterly
3. **Performance monitoring**: Monitor build times and site speed
4. **Content review**: Quarterly documentation accuracy review

### Updating Dependencies

```bash
cd website
npm audit
npm update
npm run build  # Test after updates
```

## 🚨 Troubleshooting

### Common Issues and Solutions

#### Build Failures
**Problem**: Site fails to build or deploy
**Solutions**:
1. Check Node.js version: `node --version` (requires >= 18.0.0)
2. Clear build cache: `npm run docs:clear`
3. Reinstall dependencies: `cd website && rm -rf node_modules package-lock.json && npm install`
4. Check GitHub Actions logs for specific errors

#### Broken Links
**Problem**: Warning about broken links during build
**Solutions**:
1. Run link validation: `npm run docs:validate`
2. Check for typos in markdown links
3. Ensure referenced files exist in the correct location
4. Use relative paths for internal links

#### Search Not Working
**Problem**: Search functionality not working or returning no results
**Solutions**:
1. Rebuild the site: `npm run docs:build`
2. Check search index exists: `build/search-index.json`
3. Clear browser cache and rebuild
4. Verify search plugin configuration in `docusaurus.config.js`

#### Development Server Issues
**Problem**: `npm run docs:start` fails or port conflicts
**Solutions**:
1. Check if port 3000 is already in use: `lsof -i :3000`
2. Kill existing processes: `pkill -f docusaurus`
3. Use different port: `npm run docs:start -- --port 3001`
4. Clear cache and restart: `npm run docs:clear && npm run docs:start`

#### Performance Issues
**Problem**: Slow build times or large bundle size
**Solutions**:
1. Optimize images in `docs/assets/`
2. Check for unnecessary dependencies
3. Use `npm run docs:build --analyze` to analyze bundle size
4. Increase Node.js memory: `NODE_OPTIONS="--max-old-space-size=4096"`

#### Content Formatting Issues
**Problem**: Markdown not rendering correctly
**Solutions**:
1. Check frontmatter syntax
2. Ensure proper heading hierarchy (H1 → H2 → H3)
3. Validate markdown syntax
4. Check for special characters that need escaping

## 🤝 Contributor Guidelines

### For Documentation Contributors

1. **Follow the style guide**: Consistent formatting and structure
2. **Test changes locally**: Always test with `npm run docs:start`
3. **Validate before committing**: Run `npm run docs:validate`
4. **Use descriptive commit messages**: Follow conventional commits format

### For Developers

1. **Configuration changes**: Test thoroughly before deploying
2. **Plugin updates**: Test compatibility with existing content
3. **Theme modifications**: Ensure mobile responsiveness
4. **Performance**: Monitor bundle size and build times

### Content Style Guidelines

- Use clear, concise language
- Include code examples where helpful
- Add screenshots for UI-related documentation
- Keep line lengths reasonable (80-100 characters)
- Use consistent terminology throughout

## 📈 CI/CD Pipeline Maintenance

### GitHub Actions Workflow

The documentation deployment pipeline includes:

1. **Dependency Installation**: Caches npm dependencies for faster builds
2. **Build Process**: Runs `npm run build` in the website directory
3. **Link Validation**: Checks for broken internal and external links
4. **Deployment**: Automatically deploys to GitHub Pages on success

### Pipeline Monitoring

- Monitor build times and look for performance degradation
- Set up notifications for failed deployments
- Review GitHub Actions usage to stay within limits
- Regularly update GitHub Actions versions

### Debugging Pipeline Issues

1. **Check GitHub Actions logs** for specific error messages
2. **Test locally** to reproduce build issues
3. **Verify dependencies** are properly locked in `package-lock.json`
4. **Check GitHub Pages settings** if deployment succeeds but site doesn't update

## 🚨 Emergency Procedures

### Site Down/Build Failures
1. Check GitHub Actions logs for errors
2. Revert recent changes if necessary
3. Deploy previous working version
4. Debug issues in development environment

### Content Issues
1. Use `npm run docs:validate:strict` for comprehensive checking
2. Check Docusaurus build logs for specific errors
3. Test problematic pages in isolation

### Recovery Procedures

If the documentation site is completely broken:

1. **Rollback**: Revert to last known good commit
2. **Emergency fix**: Create hotfix branch with minimal changes
3. **Test thoroughly**: Validate fix in development environment
4. **Deploy carefully**: Monitor deployment process closely

## 📚 Additional Resources

- [Docusaurus Documentation](https://docusaurus.io/docs)
- [Markdown Guide](https://www.markdownguide.org/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)

## 🔄 Migration Status

This documentation site is part of an ongoing migration from pure GitHub markdown to Docusaurus. Current status:

✅ **Completed Tasks:**
- Docusaurus project structure
- Dual-platform compatibility
- Navigation and sidebar configuration
- Content migration and reorganization
- Asset management system
- GitHub Actions deployment
- CI/CD transformation pipeline
- Custom styling and branding
- Search functionality
- Development workflow setup
- Maintenance documentation

⏳ **Remaining Tasks:**
- Automated testing and validation
- Analytics and monitoring
- Complete migration testing
- Project documentation updates

---

For questions or issues, please refer to the troubleshooting section above or create an issue in the GitHub repository.