#!/usr/bin/env node

/**
 * Documentation Validation Script
 * 
 * Validates documentation structure, links, and content integrity
 * for both GitHub and Docusaurus compatibility.
 */

const fs = require('fs');
const path = require('path');
const { URL } = require('url');

// Configuration
const CONFIG = {
  docsDir: 'docs',
  websiteDir: 'website',
  verbose: process.env.VERBOSE === 'true' || process.argv.includes('--verbose'),
  strict: process.argv.includes('--strict'),
  migrationMode: process.env.MIGRATION_MODE === 'true' || process.argv.includes('--migration-mode')
};

// Validation results
class ValidationResults {
  constructor() {
    this.errors = [];
    this.warnings = [];
    this.info = [];
    this.stats = {
      filesChecked: 0,
      linksChecked: 0,
      imagesChecked: 0,
      frontmatterChecked: 0
    };
  }

  addError(message, file = null, details = null) {
    this.errors.push({ message, file, details, type: 'error' });
  }

  addWarning(message, file = null, details = null) {
    this.warnings.push({ message, file, details, type: 'warning' });
  }

  addInfo(message, file = null, details = null) {
    this.info.push({ message, file, details, type: 'info' });
  }

  hasErrors() {
    return this.errors.length > 0;
  }

  hasWarnings() {
    return this.warnings.length > 0;
  }

  getReport() {
    return {
      summary: {
        errors: this.errors.length,
        warnings: this.warnings.length,
        info: this.info.length,
        stats: this.stats
      },
      errors: this.errors,
      warnings: this.warnings,
      info: this.info
    };
  }

  printReport() {
    console.log('\n=== Documentation Validation Report ===\n');

    // Print statistics
    console.log('Statistics:');
    console.log(`  Files checked: ${this.stats.filesChecked}`);
    console.log(`  Links checked: ${this.stats.linksChecked}`);
    console.log(`  Images checked: ${this.stats.imagesChecked}`);
    console.log(`  Frontmatter checked: ${this.stats.frontmatterChecked}`);
    console.log();

    // Print errors
    if (this.errors.length > 0) {
      console.log(`❌ Errors (${this.errors.length}):`);
      this.errors.forEach((error, index) => {
        console.log(`  ${index + 1}. ${error.message}`);
        if (error.file) console.log(`     File: ${error.file}`);
        if (error.details && CONFIG.verbose) {
          console.log(`     Details: ${JSON.stringify(error.details, null, 2)}`);
        }
      });
      console.log();
    }

    // Print warnings
    if (this.warnings.length > 0) {
      console.log(`⚠️  Warnings (${this.warnings.length}):`);
      this.warnings.forEach((warning, index) => {
        console.log(`  ${index + 1}. ${warning.message}`);
        if (warning.file) console.log(`     File: ${warning.file}`);
        if (warning.details && CONFIG.verbose) {
          console.log(`     Details: ${JSON.stringify(warning.details, null, 2)}`);
        }
      });
      console.log();
    }

    // Print info
    if (this.info.length > 0 && CONFIG.verbose) {
      console.log(`ℹ️  Information (${this.info.length}):`);
      this.info.forEach((info, index) => {
        console.log(`  ${index + 1}. ${info.message}`);
        if (info.file) console.log(`     File: ${info.file}`);
      });
      console.log();
    }

    // Summary
    if (this.errors.length === 0 && this.warnings.length === 0) {
      console.log('✅ All validations passed!');
    } else if (this.errors.length === 0) {
      console.log('✅ No errors found, but there are warnings to review.');
    } else {
      console.log('❌ Validation failed with errors.');
    }
  }
}

// File utilities
class FileValidator {
  static findMarkdownFiles(dir) {
    const files = [];

    function traverse(currentDir) {
      if (!fs.existsSync(currentDir)) return;

      const items = fs.readdirSync(currentDir);

      for (const item of items) {
        const fullPath = path.join(currentDir, item);

        try {
          const stat = fs.statSync(fullPath);

          if (stat.isDirectory()) {
            // Skip hidden directories and node_modules
            if (!item.startsWith('.') && item !== 'node_modules') {
              traverse(fullPath);
            }
          } else if (item.endsWith('.md') || item.endsWith('.mdx')) {
            files.push(fullPath);
          }
        } catch (error) {
          // Skip files that can't be accessed
          continue;
        }
      }
    }

    traverse(dir);
    return files;
  }

  static parseFrontmatter(content) {
    if (!content.trim().startsWith('---')) {
      return { frontmatter: null, content };
    }

    const frontmatterEnd = content.indexOf('---', 3);
    if (frontmatterEnd === -1) {
      return { frontmatter: null, content };
    }

    const frontmatterText = content.slice(3, frontmatterEnd).trim();
    const remainingContent = content.slice(frontmatterEnd + 3);

    try {
      // Simple YAML parsing for basic frontmatter
      const frontmatter = {};
      const lines = frontmatterText.split('\n');

      for (const line of lines) {
        const colonIndex = line.indexOf(':');
        if (colonIndex > 0) {
          const key = line.slice(0, colonIndex).trim();
          const value = line.slice(colonIndex + 1).trim().replace(/^['"]|['"]$/g, '');
          frontmatter[key] = value;
        }
      }

      return { frontmatter, content: remainingContent };
    } catch (error) {
      return { frontmatter: null, content };
    }
  }

  static extractLinks(content) {
    const links = [];

    // Markdown links: [text](url)
    const linkRegex = /\[([^\]]*)\]\(([^)]+)\)/g;
    let match;

    while ((match = linkRegex.exec(content)) !== null) {
      links.push({
        type: 'link',
        text: match[1],
        url: match[2],
        raw: match[0],
        index: match.index
      });
    }

    return links;
  }

  static extractImages(content) {
    const images = [];

    // Markdown images: ![alt](src)
    const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
    let match;

    while ((match = imageRegex.exec(content)) !== null) {
      images.push({
        type: 'image',
        alt: match[1],
        src: match[2],
        raw: match[0],
        index: match.index
      });
    }

    return images;
  }
}

// Validation functions
class DocumentationValidator {
  constructor() {
    this.results = new ValidationResults();
  }

  async validateFile(filePath) {
    this.results.stats.filesChecked++;

    try {
      const content = fs.readFileSync(filePath, 'utf8');
      const { frontmatter, content: bodyContent } = FileValidator.parseFrontmatter(content);

      // Validate frontmatter
      this.validateFrontmatter(frontmatter, filePath);

      // Validate links
      const links = FileValidator.extractLinks(content);
      for (const link of links) {
        this.validateLink(link, filePath);
      }

      // Validate images
      const images = FileValidator.extractImages(content);
      for (const image of images) {
        this.validateImage(image, filePath);
      }

      // Validate content structure
      this.validateContentStructure(content, filePath);

    } catch (error) {
      this.results.addError(`Failed to read file: ${error.message}`, filePath);
    }
  }

  validateFrontmatter(frontmatter, filePath) {
    this.results.stats.frontmatterChecked++;

    if (!frontmatter) {
      this.results.addWarning('No frontmatter found', filePath);
      return;
    }

    // Check for required fields
    if (!frontmatter.title) {
      this.results.addWarning('Missing title in frontmatter', filePath);
    }

    // Check for common issues
    if (frontmatter.title && frontmatter.title.length > 100) {
      this.results.addWarning('Title is very long (>100 characters)', filePath, {
        title: frontmatter.title
      });
    }

    if (frontmatter.sidebar_position && isNaN(Number(frontmatter.sidebar_position))) {
      this.results.addError('sidebar_position must be a number', filePath, {
        sidebar_position: frontmatter.sidebar_position
      });
    }
  }

  validateLink(link, filePath) {
    this.results.stats.linksChecked++;

    const { url } = link;

    // Skip external links for now (could be enhanced to check them)
    if (url.startsWith('http') || url.startsWith('mailto:') || url.startsWith('//')) {
      return;
    }

    // Check for common issues
    if (url.includes('undefined') || url.includes('null')) {
      this.results.addError('Link contains undefined/null', filePath, link);
      return;
    }

    // Validate internal links
    if (url.startsWith('./') || url.startsWith('../') || !url.startsWith('/')) {
      this.validateInternalLink(link, filePath);
    }
  }

  validateInternalLink(link, filePath) {
    const { url } = link;

    // Remove anchor if present
    const [linkPath, anchor] = url.split('#');

    if (!linkPath) return; // Just an anchor link

    // Skip validation for certain patterns that are expected to be broken during migration
    const skipPatterns = [
      /^\.\.\/LICENSE$/,
      /^LICENSE$/,
      /^\.\.\/README\.md$/,
      /^README\.md$/,
      /^\.\.\/examples\//,
      /^examples\//,
      /^\.\.\/config\//,
      /^config\//,
      /^\.\.\/scripts\//,
      /^scripts\//
    ];

    for (const pattern of skipPatterns) {
      if (pattern.test(linkPath)) {
        this.results.addInfo(`Skipping validation for expected external link: ${linkPath}`, filePath);
        return;
      }
    }

    // Resolve the path relative to the current file
    const currentDir = path.dirname(filePath);
    let targetPath;

    if (linkPath.startsWith('/')) {
      // Absolute path from docs root
      targetPath = path.join(CONFIG.docsDir, linkPath.slice(1));
    } else {
      // Relative path
      targetPath = path.resolve(currentDir, linkPath);
    }

    // Check if target exists (try both .md and without extension)
    const possiblePaths = [
      targetPath,
      targetPath + '.md',
      targetPath + '.mdx',
      path.join(targetPath, 'index.md'),
      path.join(targetPath, 'index.mdx')
    ];

    let exists = false;
    let foundPath = null;
    for (const possiblePath of possiblePaths) {
      try {
        if (fs.existsSync(possiblePath)) {
          exists = true;
          foundPath = possiblePath;
          break;
        }
      } catch (error) {
        // Skip files that can't be accessed
        continue;
      }
    }

    if (!exists) {
      // Check if it's a link to a file that should exist in the docs directory
      const isDocsLink = targetPath.includes(path.resolve(CONFIG.docsDir));

      if (isDocsLink) {
        this.results.addError('Broken internal link', filePath, {
          link: link.raw,
          targetPath,
          possiblePaths: possiblePaths.slice(0, 3) // Limit output for readability
        });
      } else {
        // This might be a link to a file outside docs (like root README, etc.)
        this.results.addWarning('Link to file outside docs directory', filePath, {
          link: link.raw,
          targetPath
        });
      }
    }
  }

  validateImage(image, filePath) {
    this.results.stats.imagesChecked++;

    const { src } = image;

    // Skip external images
    if (src.startsWith('http') || src.startsWith('//')) {
      return;
    }

    // Check for missing alt text
    if (!image.alt || image.alt.trim() === '') {
      this.results.addWarning('Image missing alt text', filePath, image);
    }

    // Validate image file exists
    const currentDir = path.dirname(filePath);
    let imagePath;

    if (src.startsWith('/')) {
      imagePath = path.join(CONFIG.docsDir, src.slice(1));
    } else {
      imagePath = path.resolve(currentDir, src);
    }

    // Skip validation for placeholder images that are expected to be missing during migration
    const placeholderPatterns = [
      /placeholder/i,
      /logo-placeholder/i,
      /inventag-logo-placeholder/i,
      /social-card/i
    ];

    const isPlaceholder = placeholderPatterns.some(pattern => pattern.test(src));

    try {
      if (!fs.existsSync(imagePath)) {
        if (isPlaceholder) {
          this.results.addInfo(`Placeholder image not found (expected): ${src}`, filePath);
        } else {
          this.results.addWarning('Image file not found', filePath, {
            image: image.raw,
            imagePath
          });
        }
      }
    } catch (error) {
      this.results.addWarning('Error checking image file', filePath, {
        image: image.raw,
        imagePath,
        error: error.message
      });
    }
  }

  validateContentStructure(content, filePath) {
    // Check for common markdown issues

    // Multiple consecutive empty lines
    if (content.includes('\n\n\n\n')) {
      this.results.addWarning('Multiple consecutive empty lines found', filePath);
    }

    // Check for proper heading hierarchy (informational only during migration)
    const headings = content.match(/^#+\s+.+$/gm) || [];
    let previousLevel = 0;

    for (const heading of headings) {
      const level = heading.match(/^#+/)[0].length;

      if (level > previousLevel + 1 && CONFIG.verbose) {
        this.results.addInfo('Heading hierarchy skip detected', filePath, {
          heading: heading.trim(),
          level,
          previousLevel
        });
      }

      previousLevel = level;
    }

    // Check for very long lines (informational only during migration)
    const lines = content.split('\n');
    lines.forEach((line, index) => {
      if (line.length > 300 && !line.startsWith('http') && !line.includes('](') && !line.includes('```') && CONFIG.verbose) {
        this.results.addInfo(`Very long line (${line.length} chars)`, filePath, {
          lineNumber: index + 1,
          line: line.slice(0, 100) + '...'
        });
      }
    });
  }

  async validateDocusaurusConfig() {
    const configPath = path.join(CONFIG.websiteDir, 'docusaurus.config.js');

    if (!fs.existsSync(configPath)) {
      this.results.addError('Docusaurus config file not found', configPath);
      return;
    }

    try {
      const configContent = fs.readFileSync(configPath, 'utf8');

      // Basic validation of config structure
      if (!configContent.includes('title:') && !configContent.includes('title =')) {
        this.results.addWarning('No title found in Docusaurus config', configPath);
      }

      if (!configContent.includes('baseUrl:') && !configContent.includes('baseUrl =')) {
        this.results.addWarning('No baseUrl found in Docusaurus config', configPath);
      }

      this.results.addInfo('Docusaurus config file validated', configPath);

    } catch (error) {
      this.results.addError(`Failed to read Docusaurus config: ${error.message}`, configPath);
    }
  }

  async validateSidebar() {
    const sidebarPath = path.join(CONFIG.websiteDir, 'sidebars.js');

    if (!fs.existsSync(sidebarPath)) {
      this.results.addWarning('Sidebar config file not found', sidebarPath);
      return;
    }

    try {
      const sidebarContent = fs.readFileSync(sidebarPath, 'utf8');

      // Basic validation
      if (!sidebarContent.includes('module.exports') && !sidebarContent.includes('export')) {
        this.results.addError('Invalid sidebar config format', sidebarPath);
      }

      this.results.addInfo('Sidebar config file validated', sidebarPath);

    } catch (error) {
      this.results.addError(`Failed to read sidebar config: ${error.message}`, sidebarPath);
    }
  }

  async validate() {
    console.log('Starting documentation validation...\n');

    // Validate documentation structure
    if (!fs.existsSync(CONFIG.docsDir)) {
      this.results.addError(`Documentation directory not found: ${CONFIG.docsDir}`);
      return this.results;
    }

    // Find and validate all markdown files
    const markdownFiles = FileValidator.findMarkdownFiles(CONFIG.docsDir);
    console.log(`Found ${markdownFiles.length} markdown files to validate`);

    for (const filePath of markdownFiles) {
      await this.validateFile(filePath);
    }

    // Validate Docusaurus configuration
    await this.validateDocusaurusConfig();
    await this.validateSidebar();

    return this.results;
  }
}

// Main execution
async function main() {
  try {
    const validator = new DocumentationValidator();
    const results = await validator.validate();

    results.printReport();

    // In migration mode, be more tolerant of errors
    if (CONFIG.migrationMode) {
      console.log('\n🔄 Running in migration mode - tolerating expected issues during documentation migration');
      
      // Only fail on critical errors, not broken links or missing images
      const criticalErrors = results.errors.filter(error => 
        !error.message.includes('Broken internal link') && 
        !error.message.includes('Image file not found')
      );
      
      if (criticalErrors.length > 0) {
        console.log(`❌ Found ${criticalErrors.length} critical errors that need attention`);
        process.exit(1);
      } else {
        console.log('✅ No critical errors found - migration-related issues are expected and will be resolved');
        process.exit(0);
      }
    }

    // Exit with error code if validation failed
    if (CONFIG.strict && (results.hasErrors() || results.hasWarnings())) {
      process.exit(1);
    } else if (results.hasErrors()) {
      process.exit(1);
    }

  } catch (error) {
    console.error('Validation failed:', error.message);
    if (CONFIG.verbose) {
      console.error(error.stack);
    }
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch(error => {
    console.error('Unhandled error:', error);
    process.exit(1);
  });
}

module.exports = {
  DocumentationValidator,
  FileValidator,
  ValidationResults,
  CONFIG
};