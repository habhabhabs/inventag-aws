#!/usr/bin/env node

/**
 * Documentation Site Performance Monitoring Script
 * Monitors site health, performance, and availability
 */

const https = require('https');
const http = require('http');
const url = require('url');
const fs = require('fs');
const path = require('path');

// Configuration
const CONFIG = {
  siteUrl: process.env.SITE_URL || 'https://habhabhabs.github.io/inventag-aws/',
  timeout: 10000,
  maxRetries: 3,
  retryDelay: 2000,
  outputDir: '.monitoring',
  verbose: process.argv.includes('--verbose') || process.env.VERBOSE === 'true'
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
  log(`\n${'='.repeat(60)}`, 'cyan');
  log(`${title}`, 'cyan');
  log(`${'='.repeat(60)}`, 'cyan');
}

// Monitoring results
const results = {
  timestamp: new Date().toISOString(),
  siteUrl: CONFIG.siteUrl,
  tests: {
    availability: null,
    performance: null,
    search: null,
    assets: null,
    mobile: null
  },
  metrics: {
    responseTime: null,
    contentSize: null,
    searchIndexSize: null,
    statusCode: null
  },
  issues: [],
  recommendations: []
};

async function makeRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const protocol = parsedUrl.protocol === 'https:' ? https : http;
    
    const requestOptions = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
      path: parsedUrl.pathname + parsedUrl.search,
      method: options.method || 'GET',
      timeout: CONFIG.timeout,
      headers: {
        'User-Agent': 'InvenTag-Documentation-Monitor/1.0',
        ...options.headers
      }
    };

    const req = protocol.request(requestOptions, (res) => {
      let data = '';
      
      res.on('data', (chunk) => {
        data += chunk;
      });
      
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          data: data,
          responseTime: Date.now() - startTime
        });
      });
    });

    const startTime = Date.now();
    
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    
    req.end();
  });
}

async function testSiteAvailability() {
  logSection('Site Availability Test');
  
  try {
    log(`Testing: ${CONFIG.siteUrl}`, 'blue');
    
    const response = await makeRequest(CONFIG.siteUrl);
    
    results.metrics.statusCode = response.statusCode;
    results.metrics.responseTime = response.responseTime;
    results.metrics.contentSize = response.data.length;
    
    if (response.statusCode === 200) {
      log(`✅ Site is accessible (${response.statusCode})`, 'green');
      log(`⏱️ Response time: ${response.responseTime}ms`, 'blue');
      log(`📊 Content size: ${Math.round(response.data.length / 1024)}KB`, 'blue');
      
      results.tests.availability = {
        status: 'pass',
        statusCode: response.statusCode,
        responseTime: response.responseTime,
        contentSize: response.data.length
      };
      
      // Performance thresholds
      if (response.responseTime > 3000) {
        results.issues.push(`Slow response time: ${response.responseTime}ms (>3s)`);
        results.recommendations.push('Consider optimizing server response time or using a CDN');
      }
      
      return response;
    } else {
      log(`❌ Site returned status ${response.statusCode}`, 'red');
      results.tests.availability = {
        status: 'fail',
        statusCode: response.statusCode,
        error: `HTTP ${response.statusCode}`
      };
      results.issues.push(`Site returned non-200 status: ${response.statusCode}`);
      return null;
    }
  } catch (error) {
    log(`❌ Site is not accessible: ${error.message}`, 'red');
    results.tests.availability = {
      status: 'fail',
      error: error.message
    };
    results.issues.push(`Site unavailable: ${error.message}`);
    return null;
  }
}

async function testPerformance() {
  logSection('Performance Test');
  
  const performanceTests = [
    { name: 'Homepage', url: CONFIG.siteUrl },
    { name: 'Search Page', url: `${CONFIG.siteUrl}search` },
    { name: 'Documentation Page', url: `${CONFIG.siteUrl}getting-started/introduction` }
  ];
  
  const performanceResults = [];
  
  for (const test of performanceTests) {
    try {
      log(`Testing ${test.name}: ${test.url}`, 'blue');
      
      const startTime = Date.now();
      const response = await makeRequest(test.url);
      const responseTime = Date.now() - startTime;
      
      if (response.statusCode === 200) {
        log(`  ✅ ${test.name}: ${responseTime}ms`, 'green');
        performanceResults.push({
          name: test.name,
          url: test.url,
          responseTime: responseTime,
          status: 'pass'
        });
      } else {
        log(`  ❌ ${test.name}: HTTP ${response.statusCode}`, 'red');
        performanceResults.push({
          name: test.name,
          url: test.url,
          status: 'fail',
          statusCode: response.statusCode
        });
      }
    } catch (error) {
      log(`  ❌ ${test.name}: ${error.message}`, 'red');
      performanceResults.push({
        name: test.name,
        url: test.url,
        status: 'fail',
        error: error.message
      });
    }
  }
  
  results.tests.performance = {
    status: performanceResults.every(r => r.status === 'pass') ? 'pass' : 'fail',
    results: performanceResults
  };
  
  // Calculate average response time
  const validResults = performanceResults.filter(r => r.responseTime);
  if (validResults.length > 0) {
    const avgResponseTime = validResults.reduce((sum, r) => sum + r.responseTime, 0) / validResults.length;
    log(`📈 Average response time: ${Math.round(avgResponseTime)}ms`, 'blue');
    
    if (avgResponseTime > 2000) {
      results.recommendations.push('Consider optimizing page load times - average response time exceeds 2 seconds');
    }
  }
}

async function testSearchFunctionality() {
  logSection('Search Functionality Test');
  
  try {
    const searchIndexUrl = `${CONFIG.siteUrl}search-index.json`;
    log(`Testing search index: ${searchIndexUrl}`, 'blue');
    
    const response = await makeRequest(searchIndexUrl);
    
    if (response.statusCode === 200) {
      const searchIndexSize = response.data.length;
      results.metrics.searchIndexSize = searchIndexSize;
      
      log(`✅ Search index accessible`, 'green');
      log(`📊 Search index size: ${Math.round(searchIndexSize / 1024)}KB`, 'blue');
      
      // Parse and validate search index
      try {
        const searchIndex = JSON.parse(response.data);
        if (searchIndex.documents && searchIndex.documents.length > 0) {
          log(`📄 Indexed documents: ${searchIndex.documents.length}`, 'green');
          
          results.tests.search = {
            status: 'pass',
            indexSize: searchIndexSize,
            documentCount: searchIndex.documents.length
          };
        } else {
          log(`⚠️ Search index appears to be empty`, 'yellow');
          results.tests.search = {
            status: 'warning',
            indexSize: searchIndexSize,
            issue: 'Empty search index'
          };
          results.issues.push('Search index is empty or malformed');
        }
      } catch (parseError) {
        log(`❌ Invalid search index format`, 'red');
        results.tests.search = {
          status: 'fail',
          error: 'Invalid JSON format'
        };
        results.issues.push('Search index contains invalid JSON');
      }
    } else {
      log(`❌ Search index not accessible (${response.statusCode})`, 'red');
      results.tests.search = {
        status: 'fail',
        statusCode: response.statusCode
      };
      results.issues.push(`Search functionality unavailable (HTTP ${response.statusCode})`);
    }
  } catch (error) {
    log(`❌ Search functionality test failed: ${error.message}`, 'red');
    results.tests.search = {
      status: 'fail',
      error: error.message
    };
    results.issues.push(`Search functionality error: ${error.message}`);
  }
}

async function testAssets() {
  logSection('Assets Test');
  
  const assetTests = [
    { name: 'Favicon', url: `${CONFIG.siteUrl}img/favicon.svg` },
    { name: 'Logo', url: `${CONFIG.siteUrl}img/logo.svg` },
    { name: 'CSS Bundle', url: `${CONFIG.siteUrl}assets/css/styles.*.css` }  // Wildcard - we'll test if any CSS exists
  ];
  
  const assetResults = [];
  
  // Test specific assets
  for (const asset of assetTests.slice(0, 2)) {  // Skip CSS bundle for now
    try {
      log(`Testing ${asset.name}: ${asset.url}`, 'blue');
      
      const response = await makeRequest(asset.url);
      
      if (response.statusCode === 200) {
        log(`  ✅ ${asset.name}: Available (${Math.round(response.data.length / 1024)}KB)`, 'green');
        assetResults.push({
          name: asset.name,
          status: 'pass',
          size: response.data.length
        });
      } else {
        log(`  ⚠️ ${asset.name}: HTTP ${response.statusCode}`, 'yellow');
        assetResults.push({
          name: asset.name,
          status: 'warning',
          statusCode: response.statusCode
        });
      }
    } catch (error) {
      log(`  ⚠️ ${asset.name}: ${error.message}`, 'yellow');
      assetResults.push({
        name: asset.name,
        status: 'warning',
        error: error.message
      });
    }
  }
  
  results.tests.assets = {
    status: assetResults.some(r => r.status === 'fail') ? 'fail' : 'pass',
    results: assetResults
  };
}

async function testMobileResponsiveness() {
  logSection('Mobile Responsiveness Test');
  
  try {
    log('Testing mobile viewport configuration...', 'blue');
    
    const response = await makeRequest(CONFIG.siteUrl);
    
    if (response.statusCode === 200) {
      const content = response.data;
      
      // Check for mobile viewport meta tag
      if (content.includes('viewport') && content.includes('width=device-width')) {
        log('✅ Mobile viewport meta tag found', 'green');
        
        results.tests.mobile = {
          status: 'pass',
          viewport: true
        };
      } else {
        log('❌ Mobile viewport meta tag missing', 'red');
        
        results.tests.mobile = {
          status: 'fail',
          viewport: false
        };
        
        results.issues.push('Missing mobile viewport meta tag');
        results.recommendations.push('Add <meta name="viewport" content="width=device-width, initial-scale=1.0"> for mobile responsiveness');
      }
      
      // Check for responsive CSS indicators
      if (content.includes('@media') || content.includes('responsive')) {
        log('✅ Responsive design indicators found', 'green');
      } else {
        log('⚠️ No obvious responsive design indicators', 'yellow');
        results.recommendations.push('Consider adding responsive CSS media queries');
      }
    }
  } catch (error) {
    log(`❌ Mobile responsiveness test failed: ${error.message}`, 'red');
    results.tests.mobile = {
      status: 'fail',
      error: error.message
    };
  }
}

function generateReport() {
  logSection('Monitoring Report');
  
  // Create output directory
  if (!fs.existsSync(CONFIG.outputDir)) {
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });
  }
  
  // Generate summary
  const totalTests = Object.keys(results.tests).length;
  const passedTests = Object.values(results.tests).filter(test => test?.status === 'pass').length;
  const failedTests = Object.values(results.tests).filter(test => test?.status === 'fail').length;
  const warningTests = Object.values(results.tests).filter(test => test?.status === 'warning').length;
  
  log(`\nTest Summary:`, 'cyan');
  log(`✅ Passed: ${passedTests}/${totalTests}`, 'green');
  log(`⚠️ Warnings: ${warningTests}/${totalTests}`, 'yellow');
  log(`❌ Failed: ${failedTests}/${totalTests}`, 'red');
  
  if (results.issues.length > 0) {
    log(`\nIssues Found:`, 'red');
    results.issues.forEach((issue, index) => {
      log(`  ${index + 1}. ${issue}`, 'red');
    });
  }
  
  if (results.recommendations.length > 0) {
    log(`\nRecommendations:`, 'yellow');
    results.recommendations.forEach((rec, index) => {
      log(`  ${index + 1}. ${rec}`, 'yellow');
    });
  }
  
  // Save detailed report
  const reportPath = path.join(CONFIG.outputDir, `monitoring-report-${new Date().toISOString().split('T')[0]}.json`);
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));
  
  log(`\nDetailed report saved to: ${reportPath}`, 'blue');
  
  // Overall health score
  const healthScore = Math.round((passedTests / totalTests) * 100);
  log(`\n🏥 Overall Health Score: ${healthScore}%`, healthScore >= 80 ? 'green' : healthScore >= 60 ? 'yellow' : 'red');
  
  return {
    healthScore,
    passedTests,
    failedTests,
    warningTests,
    totalTests
  };
}

// Main execution
async function main() {
  log('InvenTag Documentation Site Monitoring', 'cyan');
  log(`Target URL: ${CONFIG.siteUrl}`, 'blue');
  log(`Timeout: ${CONFIG.timeout}ms`, 'blue');
  log(`Started at: ${results.timestamp}`, 'blue');
  
  try {
    // Run all tests
    await testSiteAvailability();
    await testPerformance();
    await testSearchFunctionality();
    await testAssets();
    await testMobileResponsiveness();
    
    // Generate report
    const summary = generateReport();
    
    // Exit with appropriate code
    if (summary.failedTests > 0) {
      log(`\n❌ Monitoring completed with ${summary.failedTests} failed test(s)`, 'red');
      process.exit(1);
    } else if (summary.warningTests > 0) {
      log(`\n⚠️ Monitoring completed with ${summary.warningTests} warning(s)`, 'yellow');
      process.exit(0);
    } else {
      log(`\n✅ All monitoring tests passed!`, 'green');
      process.exit(0);
    }
    
  } catch (error) {
    log(`\n❌ Monitoring failed: ${error.message}`, 'red');
    console.error(error.stack);
    process.exit(1);
  }
}

// Handle command line arguments
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`
InvenTag Documentation Site Monitoring

Usage: node scripts/monitor-site-performance.js [options]

Options:
  --help, -h          Show this help message
  --verbose           Enable verbose output
  
Environment Variables:
  SITE_URL           Site URL to monitor (default: https://habhabhabs.github.io/inventag-aws/)
  VERBOSE            Enable verbose output (true/false)

Examples:
  node scripts/monitor-site-performance.js                    # Monitor default site
  SITE_URL=https://example.com node scripts/monitor-site-performance.js  # Monitor custom URL
  node scripts/monitor-site-performance.js --verbose         # Verbose monitoring
`);
  process.exit(0);
}

// Run the monitoring
main();