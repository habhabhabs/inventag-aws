#!/usr/bin/env node

/**
 * Comprehensive documentation testing script
 * Tests dual-platform compatibility, markdown linting, link validation, and performance
 */

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

// Configuration
const CONFIG = {
  docsDir: 'docs',
  websiteDir: 'website',
  testPort: 3002,
  verbose: process.argv.includes('--verbose') || process.env.VERBOSE === 'true',
  skipExternal: process.argv.includes('--skip-external'),
  maxFiles: process.argv.includes('--quick') ? 10 : 999
};

// Color codes for console output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logSection(title) {
  log(`\n${'='.repeat(50)}`, 'cyan');
  log(`${title}`, 'cyan');
  log(`${'='.repeat(50)}`, 'cyan');
}

function logSubsection(title) {
  log(`\n--- ${title} ---`, 'blue');
}

// Test results tracking
const results = {
  markdown: { passed: 0, failed: 0, warnings: 0 },
  links: { passed: 0, failed: 0, warnings: 0 },
  frontmatter: { passed: 0, failed: 0, warnings: 0 },
  dualPlatform: { passed: 0, failed: 0, warnings: 0 },
  performance: { passed: 0, failed: 0, warnings: 0 }
};

async function runCommand(command, cwd = process.cwd(), suppressErrors = false) {
  try {
    const output = execSync(command, { 
      cwd, 
      encoding: 'utf8',
      stdio: suppressErrors ? 'pipe' : 'inherit'
    });
    return { success: true, output };
  } catch (error) {
    if (!suppressErrors) {
      log(`Command failed: ${command}`, 'red');
      log(error.message, 'red');
    }
    return { success: false, error: error.message };
  }
}

async function checkDependencies() {
  logSection('Checking Dependencies');
  
  const dependencies = [
    { name: 'Node.js', command: 'node --version' },
    { name: 'npm', command: 'npm --version' },
    { name: 'markdownlint', command: 'npx markdownlint --version', install: 'npm install -g markdownlint-cli' },
    { name: 'markdown-link-check', command: 'npx markdown-link-check --version', install: 'npm install -g markdown-link-check' }
  ];
  
  for (const dep of dependencies) {
    const result = await runCommand(dep.command, process.cwd(), true);
    if (result.success) {
      log(`✅ ${dep.name}: Available`, 'green');
    } else {
      log(`❌ ${dep.name}: Missing`, 'red');
      if (dep.install) {
        log(`   Install with: ${dep.install}`, 'yellow');
      }
    }
  }
}

async function testMarkdownLinting() {
  logSection('Markdown Linting');
  
  // Create markdownlint configuration
  const markdownlintConfig = {
    "MD013": {
      "line_length": 120,
      "code_blocks": false,
      "tables": false
    },
    "MD033": false, // Allow HTML
    "MD041": false, // Don't require H1 to be first line (due to frontmatter)
    "MD001": false, // Allow header increments
    "MD025": false, // Allow multiple H1s
    "MD034": false  // Allow bare URLs
  };
  
  const configPath = '.markdownlint.json';
  fs.writeFileSync(configPath, JSON.stringify(markdownlintConfig, null, 2));
  
  try {
    log('Running markdownlint on documentation files...', 'blue');
    const result = await runCommand(`npx markdownlint ${CONFIG.docsDir} --config ${configPath}`, process.cwd(), true);
    
    if (result.success) {
      log('✅ Markdown linting passed', 'green');
      results.markdown.passed++;
    } else {
      log('⚠️ Markdown linting completed with warnings:', 'yellow');
      console.log(result.error);
      results.markdown.warnings++;
    }
  } catch (error) {
    log(`❌ Markdown linting failed: ${error.message}`, 'red');
    results.markdown.failed++;
  } finally {
    // Clean up config file
    if (fs.existsSync(configPath)) {
      fs.unlinkSync(configPath);
    }
  }
}

async function validateFrontmatter() {
  logSection('Frontmatter Validation');
  
  const markdownFiles = getAllMarkdownFiles(CONFIG.docsDir);
  log(`Found ${markdownFiles.length} markdown files to check`, 'blue');
  
  for (const file of markdownFiles.slice(0, CONFIG.maxFiles)) {
    logSubsection(`Checking: ${file}`);
    
    try {
      const content = fs.readFileSync(file, 'utf8');
      const lines = content.split('\n');
      
      if (lines[0] === '---') {
        // Find end of frontmatter
        let endIndex = -1;
        for (let i = 1; i < lines.length; i++) {
          if (lines[i] === '---') {
            endIndex = i;
            break;
          }
        }
        
        if (endIndex > 0) {
          const frontmatter = lines.slice(1, endIndex);
          const hasTitle = frontmatter.some(line => line.startsWith('title:'));
          const hasDescription = frontmatter.some(line => line.startsWith('description:'));
          
          if (hasTitle) {
            log('  ✅ Has title', 'green');
            results.frontmatter.passed++;
          } else {
            log('  ⚠️ Missing title', 'yellow');
            results.frontmatter.warnings++;
          }
          
          if (hasDescription) {
            log('  ✅ Has description', 'green');
          } else {
            log('  ℹ️ No description (recommended)', 'blue');
          }
        } else {
          log('  ❌ Malformed frontmatter', 'red');
          results.frontmatter.failed++;
        }
      } else {
        log('  ⚠️ No frontmatter', 'yellow');
        results.frontmatter.warnings++;
      }
    } catch (error) {
      log(`  ❌ Error reading file: ${error.message}`, 'red');
      results.frontmatter.failed++;
    }
  }
}

async function validateLinks() {
  logSection('Link Validation');
  
  if (CONFIG.skipExternal) {
    log('Skipping external link validation (--skip-external flag)', 'yellow');
    return;
  }
  
  // Create link check configuration
  const linkCheckConfig = {
    "ignorePatterns": [
      { "pattern": "^http://localhost" },
      { "pattern": "^https://localhost" },
      { "pattern": "^#" }
    ],
    "timeout": "10s",
    "retryOn429": true,
    "retryCount": 2,
    "fallbackRetryDelay": "5s"
  };
  
  const configPath = '.markdown-link-check.json';
  fs.writeFileSync(configPath, JSON.stringify(linkCheckConfig, null, 2));
  
  try {
    const markdownFiles = getAllMarkdownFiles(CONFIG.docsDir);
    log(`Checking links in ${Math.min(markdownFiles.length, CONFIG.maxFiles)} files...`, 'blue');
    
    for (const file of markdownFiles.slice(0, CONFIG.maxFiles)) {
      logSubsection(`Checking links in: ${file}`);
      
      const result = await runCommand(`npx markdown-link-check "${file}" --config ${configPath} --quiet`, process.cwd(), true);
      
      if (result.success) {
        log('  ✅ All links valid', 'green');
        results.links.passed++;
      } else {
        log('  ⚠️ Some links failed validation', 'yellow');
        if (CONFIG.verbose) {
          console.log(result.error);
        }
        results.links.warnings++;
      }
    }
  } catch (error) {
    log(`❌ Link validation failed: ${error.message}`, 'red');
    results.links.failed++;
  } finally {
    // Clean up config file
    if (fs.existsSync(configPath)) {
      fs.unlinkSync(configPath);
    }
  }
}

async function testDualPlatformCompatibility() {
  logSection('Dual-Platform Compatibility Testing');
  
  const markdownFiles = getAllMarkdownFiles(CONFIG.docsDir);
  log(`Testing dual-platform compatibility for ${markdownFiles.length} files`, 'blue');
  
  for (const file of markdownFiles.slice(0, CONFIG.maxFiles)) {
    logSubsection(`Testing: ${file}`);
    
    try {
      const content = fs.readFileSync(file, 'utf8');
      let compatible = true;
      const issues = [];
      
      // Check for GitHub-specific features that might not work in Docusaurus
      if (content.includes('<details>')) {
        issues.push('Uses <details> tags (GitHub-specific, may need Docusaurus equivalent)');
      }
      
      // Check for relative links (should work in both)
      const relativeLinks = content.match(/\]\(\.\.\//g) || [];
      if (relativeLinks.length > 0) {
        log(`  ✅ Uses ${relativeLinks.length} relative links (dual-platform compatible)`, 'green');
      }
      
      // Check for absolute GitHub links (should be relative)
      const absoluteGitHubLinks = content.match(/https:\/\/github\.com\/[^)]+\.md/g) || [];
      if (absoluteGitHubLinks.length > 0) {
        issues.push(`Contains ${absoluteGitHubLinks.length} absolute GitHub links (should be relative)`);
        compatible = false;
      }
      
      // Check for proper image references
      const imageRefs = content.match(/!\[[^\]]*\]\([^)]+\)/g) || [];
      const badImageRefs = imageRefs.filter(ref => ref.includes('http://') || ref.includes('https://'));
      if (badImageRefs.length > 0) {
        issues.push(`Contains ${badImageRefs.length} external image references (should be local)`);
        compatible = false;
      }
      
      if (compatible && issues.length === 0) {
        log('  ✅ Dual-platform compatible', 'green');
        results.dualPlatform.passed++;
      } else {
        if (issues.length > 0) {
          log('  ⚠️ Potential compatibility issues:', 'yellow');
          issues.forEach(issue => log(`    - ${issue}`, 'yellow'));
          results.dualPlatform.warnings++;
        } else {
          log('  ✅ Compatible with minor notes', 'green');
          results.dualPlatform.passed++;
        }
      }
    } catch (error) {
      log(`  ❌ Error analyzing file: ${error.message}`, 'red');
      results.dualPlatform.failed++;
    }
  }
}

async function testPerformance() {
  logSection('Performance Testing');
  
  log('Building documentation site...', 'blue');
  const buildResult = await runCommand('npm run build', CONFIG.websiteDir);
  
  if (!buildResult.success) {
    log('❌ Build failed, skipping performance tests', 'red');
    results.performance.failed++;
    return;
  }
  
  log('✅ Build successful', 'green');
  
  // Analyze build output
  const buildDir = path.join(CONFIG.websiteDir, 'build');
  if (fs.existsSync(buildDir)) {
    const buildSize = await runCommand(`du -sh ${buildDir}`, process.cwd(), true);
    const htmlCount = await runCommand(`find ${buildDir} -name "*.html" | wc -l`, process.cwd(), true);
    const cssCount = await runCommand(`find ${buildDir} -name "*.css" | wc -l`, process.cwd(), true);
    const jsCount = await runCommand(`find ${buildDir} -name "*.js" | wc -l`, process.cwd(), true);
    
    log(`Build Analysis:`, 'blue');
    log(`  - Build size: ${buildSize.output?.trim() || 'unknown'}`);
    log(`  - HTML files: ${htmlCount.output?.trim() || 'unknown'}`);
    log(`  - CSS files: ${cssCount.output?.trim() || 'unknown'}`);
    log(`  - JS files: ${jsCount.output?.trim() || 'unknown'}`);
    
    // Check for search index
    const searchIndexPath = path.join(buildDir, 'search-index.json');
    if (fs.existsSync(searchIndexPath)) {
      const searchIndexSize = fs.statSync(searchIndexPath).size;
      log(`  - Search index: ${Math.round(searchIndexSize / 1024)}KB`, 'green');
      
      if (searchIndexSize > 1000) {
        log('  ✅ Search index populated', 'green');
        results.performance.passed++;
      } else {
        log('  ⚠️ Search index may be incomplete', 'yellow');
        results.performance.warnings++;
      }
    } else {
      log('  ❌ Search index not found', 'red');
      results.performance.failed++;
    }
    
    // Check for mobile viewport
    const indexPath = path.join(buildDir, 'index.html');
    if (fs.existsSync(indexPath)) {
      const indexContent = fs.readFileSync(indexPath, 'utf8');
      if (indexContent.includes('viewport') && indexContent.includes('width=device-width')) {
        log('  ✅ Mobile viewport configured', 'green');
        results.performance.passed++;
      } else {
        log('  ⚠️ Mobile viewport not properly configured', 'yellow');
        results.performance.warnings++;
      }
    }
  }
}

function getAllMarkdownFiles(dir) {
  const files = [];
  
  function traverse(currentDir) {
    const items = fs.readdirSync(currentDir);
    
    for (const item of items) {
      const fullPath = path.join(currentDir, item);
      const stat = fs.statSync(fullPath);
      
      if (stat.isDirectory() && !item.startsWith('.') && item !== 'node_modules') {
        traverse(fullPath);
      } else if (stat.isFile() && item.endsWith('.md')) {
        files.push(fullPath);
      }
    }
  }
  
  traverse(dir);
  return files;
}

function displayResults() {
  logSection('Test Results Summary');
  
  const categories = [
    { name: 'Markdown Linting', key: 'markdown' },
    { name: 'Frontmatter Validation', key: 'frontmatter' },
    { name: 'Link Validation', key: 'links' },
    { name: 'Dual-Platform Compatibility', key: 'dualPlatform' },
    { name: 'Performance Testing', key: 'performance' }
  ];
  
  let totalPassed = 0;
  let totalFailed = 0;
  let totalWarnings = 0;
  
  for (const category of categories) {
    const result = results[category.key];
    totalPassed += result.passed;
    totalFailed += result.failed;
    totalWarnings += result.warnings;
    
    log(`${category.name}:`, 'blue');
    log(`  ✅ Passed: ${result.passed}`, 'green');
    log(`  ⚠️ Warnings: ${result.warnings}`, 'yellow');
    log(`  ❌ Failed: ${result.failed}`, 'red');
  }
  
  log(`\nOverall Results:`, 'cyan');
  log(`  ✅ Total Passed: ${totalPassed}`, 'green');
  log(`  ⚠️ Total Warnings: ${totalWarnings}`, 'yellow');
  log(`  ❌ Total Failed: ${totalFailed}`, 'red');
  
  if (totalFailed === 0) {
    log(`\n🎉 All tests passed! ${totalWarnings > 0 ? `(${totalWarnings} warnings)` : ''}`, 'green');
    process.exit(0);
  } else {
    log(`\n💥 ${totalFailed} test(s) failed!`, 'red');
    process.exit(1);
  }
}

// Main execution
async function main() {
  log('InvenTag Documentation Testing Suite', 'cyan');
  log(`Configuration:`, 'blue');
  log(`  - Docs directory: ${CONFIG.docsDir}`);
  log(`  - Website directory: ${CONFIG.websiteDir}`);
  log(`  - Max files to test: ${CONFIG.maxFiles}`);
  log(`  - Skip external links: ${CONFIG.skipExternal}`);
  log(`  - Verbose: ${CONFIG.verbose}`);
  
  try {
    await checkDependencies();
    await testMarkdownLinting();
    await validateFrontmatter();
    await validateLinks();
    await testDualPlatformCompatibility();
    await testPerformance();
    
    displayResults();
  } catch (error) {
    log(`\n❌ Testing suite failed: ${error.message}`, 'red');
    process.exit(1);
  }
}

// Handle command line arguments
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`
InvenTag Documentation Testing Suite

Usage: node scripts/test-docs.js [options]

Options:
  --help, -h          Show this help message
  --verbose           Enable verbose output
  --skip-external     Skip external link validation
  --quick             Test only first 10 files of each type
  
Examples:
  node scripts/test-docs.js                    # Run all tests
  node scripts/test-docs.js --verbose          # Run with detailed output
  node scripts/test-docs.js --quick            # Quick test (limited files)
  node scripts/test-docs.js --skip-external    # Skip external link checks
`);
  process.exit(0);
}

// Run the main function
main();