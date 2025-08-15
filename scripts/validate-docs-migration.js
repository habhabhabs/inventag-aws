#!/usr/bin/env node

/**
 * Migration-Friendly Documentation Validation Script
 * 
 * A simplified validation script that's tolerant of common issues
 * during documentation migration from GitHub to Docusaurus.
 */

const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  docsDir: 'docs',
  websiteDir: 'website',
  verbose: process.env.VERBOSE === 'true' || process.argv.includes('--verbose')
};

// Simple validation results
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

  addError(message, file = null) {
    this.errors.push({ message, file, type: 'error' });
  }

  addWarning(message, file = null) {
    this.warnings.push({ message, file, type: 'warning' });
  }

  addInfo(message, file = null) {
    this.info.push({ message, file, type: 'info' });
  }

  hasErrors() {
    return this.errors.length > 0;
  }

  hasWarnings() {
    return this.warnings.length > 0;
  }

  printReport() {
    console.log('\n=== Migration-Friendly Documentation Validation Report ===\n');
    
    // Print statistics
    console.log('Statistics:');
    console.log(`  Files checked: ${this.stats.filesChecked}`);
    console.log(`  Links checked: ${this.stats.linksChecked}`);
    console.log(`  Images checked: ${this.stats.imagesChecked}`);
    console.log(`  Frontmatter checked: ${this.stats.frontmatterChecked}`);
    console.log();

    // Print critical errors only
    if (this.errors.length > 0) {
      console.log(`❌ Critical Errors (${this.errors.length}):`);
      this.errors.forEach((error, index) => {
        console.log(`  ${index + 1}. ${error.message}`);
        if (error.file) console.log(`     File: ${error.file}`);
      });
      console.log();
    }

    // Print warnings (but don't fail on them in migration mode)
    if (this.warnings.length > 0) {
      console.log(`⚠️  Migration Warnings (${this.warnings.length}) - These are expected during migration:`);
      if (CONFIG.verbose) {
        this.warnings.slice(0, 10).forEach((warning, index) => {
          console.log(`  ${index + 1}. ${warning.message}`);
          if (warning.file) console.log(`     File: ${warning.file}`);
        });
        if (this.warnings.length > 10) {
          console.log(`  ... and ${this.warnings.length - 10} more warnings`);
        }
      } else {
        console.log(`  Use --verbose to see details. Most common: broken links to files outside docs/, missing placeholder images.`);
      }
      console.log();
    }

    // Summary
    if (this.errors.length === 0) {
      console.log('✅ No critical errors found! Migration-related warnings are expected and will be resolved.');
    } else {
      console.log('❌ Critical errors found that need attention.');
    }
  }
}

// Simple file utilities
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
            if (!item.startsWith('.') && item !== 'node_modules') {
              traverse(fullPath);
            }
          } else if (item.endsWith('.md') || item.endsWith('.mdx')) {
            files.push(fullPath);
          }
        } catch (error) {
          continue;
        }
      }
    }
    
    traverse(dir);
    return files;
  }

  static extractLinks(content) {
    const links = [];
    const linkRegex = /\[([^\]]*)\]\(([^)]+)\)/g;
    let match;
    
    while ((match = linkRegex.exec(content)) !== null) {
      links.push({
        text: match[1],
        url: match[2],
        raw: match[0]
      });
    }
    
    return links;
  }

  static extractImages(content) {
    const images = [];
    const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
    let match;
    
    while ((match = imageRegex.exec(content)) !== null) {
      images.push({
        alt: match[1],
        src: match[2],
        raw: match[0]
      });
    }
    
    return images;
  }
}

// Migration-friendly validator
class MigrationValidator {
  constructor() {
    this.results = new ValidationResults();
  }

  async validateFile(filePath) {
    this.results.stats.filesChecked++;
    
    try {
      const content = fs.readFileSync(filePath, 'utf8');
      
      // Check for critical issues only
      this.validateCriticalIssues(content, filePath);
      
      // Check links (but be tolerant)
      const links = FileValidator.extractLinks(content);
      for (const link of links) {
        this.validateLinkTolerant(link, filePath);
      }
      
      // Check images (but be tolerant)
      const images = FileValidator.extractImages(content);
      for (const image of images) {
        this.validateImageTolerant(image, filePath);
      }
      
      // Check frontmatter exists
      this.validateFrontmatter(content, filePath);
      
    } catch (error) {
      this.results.addError(`Failed to read file: ${error.message}`, filePath);
    }
  }

  validateCriticalIssues(content, filePath) {
    // Only check for truly critical issues that would break the build
    
    // Check for malformed frontmatter
    if (content.trim().startsWith('---')) {
      const frontmatterEnd = content.indexOf('---', 3);
      if (frontmatterEnd === -1) {
        this.results.addError('Malformed frontmatter - missing closing ---', filePath);
      }
    }
    
    // Check for completely empty files
    if (content.trim().length === 0) {
      this.results.addError('File is completely empty', filePath);
    }
  }

  validateLinkTolerant(link, filePath) {
    this.results.stats.linksChecked++;
    
    const { url } = link;
    
    // Skip external links
    if (url.startsWith('http') || url.startsWith('mailto:') || url.startsWith('//')) {
      return;
    }
    
    // Skip known migration-related broken links
    const expectedBrokenPatterns = [
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
    
    for (const pattern of expectedBrokenPatterns) {
      if (pattern.test(url)) {
        this.results.addInfo(`Expected broken link during migration: ${url}`, filePath);
        return;
      }
    }
    
    // Only check links within docs directory
    if (url.startsWith('./') || url.startsWith('../') || !url.startsWith('/')) {
      const [linkPath] = url.split('#');
      if (!linkPath) return; // Just an anchor
      
      const currentDir = path.dirname(filePath);
      let targetPath;
      
      if (linkPath.startsWith('/')) {
        targetPath = path.join(CONFIG.docsDir, linkPath.slice(1));
      } else {
        targetPath = path.resolve(currentDir, linkPath);
      }
      
      // Check if it's supposed to be within docs
      const isDocsLink = targetPath.includes(path.resolve(CONFIG.docsDir));
      
      if (isDocsLink) {
        const possiblePaths = [
          targetPath,
          targetPath + '.md',
          targetPath + '.mdx',
          path.join(targetPath, 'index.md'),
          path.join(targetPath, 'index.mdx')
        ];
        
        let exists = false;
        for (const possiblePath of possiblePaths) {
          try {
            if (fs.existsSync(possiblePath)) {
              exists = true;
              break;
            }
          } catch (error) {
            continue;
          }
        }
        
        if (!exists) {
          this.results.addWarning(`Broken internal docs link: ${url}`, filePath);
        }
      } else {
        this.results.addWarning(`Link to file outside docs: ${url}`, filePath);
      }
    }
  }

  validateImageTolerant(image, filePath) {
    this.results.stats.imagesChecked++;
    
    const { src } = image;
    
    // Skip external images
    if (src.startsWith('http') || src.startsWith('//')) {
      return;
    }
    
    // Skip known placeholder images
    const placeholderPatterns = [
      /placeholder/i,
      /logo-placeholder/i,
      /inventag-logo-placeholder/i,
      /social-card/i
    ];
    
    const isPlaceholder = placeholderPatterns.some(pattern => pattern.test(src));
    
    if (isPlaceholder) {
      this.results.addInfo(`Placeholder image (expected to be missing): ${src}`, filePath);
      return;
    }
    
    // Check if image exists
    const currentDir = path.dirname(filePath);
    let imagePath;
    
    if (src.startsWith('/')) {
      imagePath = path.join(CONFIG.docsDir, src.slice(1));
    } else {
      imagePath = path.resolve(currentDir, src);
    }
    
    try {
      if (!fs.existsSync(imagePath)) {
        this.results.addWarning(`Image file not found: ${src}`, filePath);
      }
    } catch (error) {
      this.results.addWarning(`Error checking image: ${src}`, filePath);
    }
  }

  validateFrontmatter(content, filePath) {
    this.results.stats.frontmatterChecked++;
    
    if (!content.trim().startsWith('---')) {
      this.results.addInfo('No frontmatter found (will be added by transformation)', filePath);
    }
  }

  async validateDocusaurusConfig() {
    const configPath = path.join(CONFIG.websiteDir, 'docusaurus.config.js');
    
    if (!fs.existsSync(configPath)) {
      this.results.addError('Docusaurus config file not found', configPath);
      return;
    }

    try {
      const configContent = fs.readFileSync(configPath, 'utf8');
      
      if (!configContent.includes('title:') && !configContent.includes('title =')) {
        this.results.addError('No title found in Docusaurus config', configPath);
      }
      
    } catch (error) {
      this.results.addError(`Failed to read Docusaurus config: ${error.message}`, configPath);
    }
  }

  async validate() {
    console.log('Starting migration-friendly documentation validation...\n');
    
    // Check docs directory exists
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

    return this.results;
  }
}

// Main execution
async function main() {
  try {
    const validator = new MigrationValidator();
    const results = await validator.validate();
    
    results.printReport();
    
    // Only fail on critical errors, not warnings
    if (results.hasErrors()) {
      console.log('\n❌ Critical errors found - these need to be fixed before deployment');
      process.exit(1);
    } else {
      console.log('\n✅ No critical errors found - ready for migration!');
      process.exit(0);
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
  MigrationValidator,
  FileValidator,
  ValidationResults,
  CONFIG
};