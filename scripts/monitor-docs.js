#!/usr/bin/env node

/**
 * Documentation Monitoring and Health Check Script
 * 
 * Monitors documentation health, tracks transformation metrics,
 * and provides comprehensive logging for the CI/CD pipeline.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const CONFIG = {
  docsDir: 'docs',
  websiteDir: 'website',
  logDir: '.docs-logs',
  metricsFile: 'docs-metrics.json',
  healthCheckFile: 'docs-health.json',
  verbose: process.env.VERBOSE === 'true' || process.argv.includes('--verbose')
};

// Metrics collector
class MetricsCollector {
  constructor() {
    this.metrics = {
      timestamp: new Date().toISOString(),
      build: {
        startTime: null,
        endTime: null,
        duration: null,
        success: false,
        errors: [],
        warnings: []
      },
      transformation: {
        filesProcessed: 0,
        filesTransformed: 0,
        transformationsApplied: 0,
        errors: 0,
        warnings: 0
      },
      validation: {
        filesChecked: 0,
        linksChecked: 0,
        imagesChecked: 0,
        errors: 0,
        warnings: 0
      },
      content: {
        totalFiles: 0,
        totalSize: 0,
        averageFileSize: 0,
        largestFile: null,
        smallestFile: null
      },
      performance: {
        buildSize: null,
        buildTime: null,
        transformationTime: null,
        validationTime: null
      }
    };
  }

  startBuild() {
    this.metrics.build.startTime = new Date().toISOString();
  }

  endBuild(success = true) {
    this.metrics.build.endTime = new Date().toISOString();
    this.metrics.build.success = success;
    
    if (this.metrics.build.startTime) {
      const start = new Date(this.metrics.build.startTime);
      const end = new Date(this.metrics.build.endTime);
      this.metrics.build.duration = end - start;
      this.metrics.performance.buildTime = this.metrics.build.duration;
    }
  }

  addBuildError(error) {
    this.metrics.build.errors.push({
      message: error,
      timestamp: new Date().toISOString()
    });
  }

  addBuildWarning(warning) {
    this.metrics.build.warnings.push({
      message: warning,
      timestamp: new Date().toISOString()
    });
  }

  updateTransformationMetrics(stats) {
    Object.assign(this.metrics.transformation, stats);
  }

  updateValidationMetrics(stats) {
    Object.assign(this.metrics.validation, stats);
  }

  updateContentMetrics() {
    try {
      const files = this.findMarkdownFiles(CONFIG.docsDir);
      let totalSize = 0;
      let largestFile = { path: null, size: 0 };
      let smallestFile = { path: null, size: Infinity };

      for (const filePath of files) {
        const stats = fs.statSync(filePath);
        const size = stats.size;
        totalSize += size;

        if (size > largestFile.size) {
          largestFile = { path: filePath, size };
        }
        if (size < smallestFile.size) {
          smallestFile = { path: filePath, size };
        }
      }

      this.metrics.content = {
        totalFiles: files.length,
        totalSize,
        averageFileSize: files.length > 0 ? Math.round(totalSize / files.length) : 0,
        largestFile: largestFile.path ? largestFile : null,
        smallestFile: smallestFile.path && smallestFile.size < Infinity ? smallestFile : null
      };
    } catch (error) {
      console.error('Failed to update content metrics:', error.message);
    }
  }

  updatePerformanceMetrics() {
    try {
      // Check build size if build directory exists
      const buildDir = path.join(CONFIG.websiteDir, 'build');
      if (fs.existsSync(buildDir)) {
        const buildSize = this.getDirectorySize(buildDir);
        this.metrics.performance.buildSize = buildSize;
      }
    } catch (error) {
      console.error('Failed to update performance metrics:', error.message);
    }
  }

  findMarkdownFiles(dir) {
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

  getDirectorySize(dirPath) {
    let totalSize = 0;
    
    function traverse(currentPath) {
      try {
        const stats = fs.statSync(currentPath);
        
        if (stats.isDirectory()) {
          const items = fs.readdirSync(currentPath);
          for (const item of items) {
            traverse(path.join(currentPath, item));
          }
        } else {
          totalSize += stats.size;
        }
      } catch (error) {
        // Skip files that can't be accessed
      }
    }
    
    traverse(dirPath);
    return totalSize;
  }

  saveMetrics() {
    try {
      if (!fs.existsSync(CONFIG.logDir)) {
        fs.mkdirSync(CONFIG.logDir, { recursive: true });
      }
      
      const metricsPath = path.join(CONFIG.logDir, CONFIG.metricsFile);
      fs.writeFileSync(metricsPath, JSON.stringify(this.metrics, null, 2));
      
      console.log(`Metrics saved to: ${metricsPath}`);
    } catch (error) {
      console.error('Failed to save metrics:', error.message);
    }
  }

  getMetrics() {
    return this.metrics;
  }
}

// Health checker
class HealthChecker {
  constructor() {
    this.health = {
      timestamp: new Date().toISOString(),
      overall: 'unknown',
      checks: {
        docsDirectory: { status: 'unknown', message: '' },
        websiteDirectory: { status: 'unknown', message: '' },
        docusaurusConfig: { status: 'unknown', message: '' },
        sidebarConfig: { status: 'unknown', message: '' },
        dependencies: { status: 'unknown', message: '' },
        buildOutput: { status: 'unknown', message: '' }
      }
    };
  }

  async runHealthChecks() {
    console.log('Running documentation health checks...\n');

    // Check docs directory
    this.checkDocsDirectory();
    
    // Check website directory
    this.checkWebsiteDirectory();
    
    // Check Docusaurus config
    this.checkDocusaurusConfig();
    
    // Check sidebar config
    this.checkSidebarConfig();
    
    // Check dependencies
    await this.checkDependencies();
    
    // Check build output
    this.checkBuildOutput();
    
    // Determine overall health
    this.determineOverallHealth();
    
    return this.health;
  }

  checkDocsDirectory() {
    try {
      if (!fs.existsSync(CONFIG.docsDir)) {
        this.health.checks.docsDirectory = {
          status: 'error',
          message: 'Documentation directory not found'
        };
        return;
      }

      const files = fs.readdirSync(CONFIG.docsDir);
      const mdFiles = files.filter(f => f.endsWith('.md') || f.endsWith('.mdx'));
      
      if (mdFiles.length === 0) {
        this.health.checks.docsDirectory = {
          status: 'warning',
          message: 'No markdown files found in docs directory'
        };
      } else {
        this.health.checks.docsDirectory = {
          status: 'healthy',
          message: `Found ${mdFiles.length} markdown files`
        };
      }
    } catch (error) {
      this.health.checks.docsDirectory = {
        status: 'error',
        message: `Error checking docs directory: ${error.message}`
      };
    }
  }

  checkWebsiteDirectory() {
    try {
      if (!fs.existsSync(CONFIG.websiteDir)) {
        this.health.checks.websiteDirectory = {
          status: 'error',
          message: 'Website directory not found'
        };
        return;
      }

      const packageJsonPath = path.join(CONFIG.websiteDir, 'package.json');
      if (!fs.existsSync(packageJsonPath)) {
        this.health.checks.websiteDirectory = {
          status: 'error',
          message: 'package.json not found in website directory'
        };
        return;
      }

      this.health.checks.websiteDirectory = {
        status: 'healthy',
        message: 'Website directory structure is valid'
      };
    } catch (error) {
      this.health.checks.websiteDirectory = {
        status: 'error',
        message: `Error checking website directory: ${error.message}`
      };
    }
  }

  checkDocusaurusConfig() {
    try {
      const configPath = path.join(CONFIG.websiteDir, 'docusaurus.config.js');
      
      if (!fs.existsSync(configPath)) {
        this.health.checks.docusaurusConfig = {
          status: 'error',
          message: 'Docusaurus config file not found'
        };
        return;
      }

      const configContent = fs.readFileSync(configPath, 'utf8');
      
      // Basic validation
      const requiredFields = ['title', 'url', 'baseUrl'];
      const missingFields = requiredFields.filter(field => 
        !configContent.includes(`${field}:`) && !configContent.includes(`${field} =`)
      );

      if (missingFields.length > 0) {
        this.health.checks.docusaurusConfig = {
          status: 'warning',
          message: `Missing required fields: ${missingFields.join(', ')}`
        };
      } else {
        this.health.checks.docusaurusConfig = {
          status: 'healthy',
          message: 'Docusaurus configuration is valid'
        };
      }
    } catch (error) {
      this.health.checks.docusaurusConfig = {
        status: 'error',
        message: `Error checking Docusaurus config: ${error.message}`
      };
    }
  }

  checkSidebarConfig() {
    try {
      const sidebarPath = path.join(CONFIG.websiteDir, 'sidebars.js');
      
      if (!fs.existsSync(sidebarPath)) {
        this.health.checks.sidebarConfig = {
          status: 'warning',
          message: 'Sidebar config file not found'
        };
        return;
      }

      const sidebarContent = fs.readFileSync(sidebarPath, 'utf8');
      
      if (!sidebarContent.includes('module.exports') && !sidebarContent.includes('export')) {
        this.health.checks.sidebarConfig = {
          status: 'error',
          message: 'Invalid sidebar config format'
        };
      } else {
        this.health.checks.sidebarConfig = {
          status: 'healthy',
          message: 'Sidebar configuration is valid'
        };
      }
    } catch (error) {
      this.health.checks.sidebarConfig = {
        status: 'error',
        message: `Error checking sidebar config: ${error.message}`
      };
    }
  }

  async checkDependencies() {
    try {
      const packageJsonPath = path.join(CONFIG.websiteDir, 'package.json');
      
      if (!fs.existsSync(packageJsonPath)) {
        this.health.checks.dependencies = {
          status: 'error',
          message: 'package.json not found'
        };
        return;
      }

      // Check if node_modules exists
      const nodeModulesPath = path.join(CONFIG.websiteDir, 'node_modules');
      if (!fs.existsSync(nodeModulesPath)) {
        this.health.checks.dependencies = {
          status: 'warning',
          message: 'node_modules not found - dependencies may not be installed'
        };
        return;
      }

      this.health.checks.dependencies = {
        status: 'healthy',
        message: 'Dependencies appear to be installed'
      };
    } catch (error) {
      this.health.checks.dependencies = {
        status: 'error',
        message: `Error checking dependencies: ${error.message}`
      };
    }
  }

  checkBuildOutput() {
    try {
      const buildPath = path.join(CONFIG.websiteDir, 'build');
      
      if (!fs.existsSync(buildPath)) {
        this.health.checks.buildOutput = {
          status: 'info',
          message: 'Build output not found (not yet built)'
        };
        return;
      }

      const indexPath = path.join(buildPath, 'index.html');
      if (!fs.existsSync(indexPath)) {
        this.health.checks.buildOutput = {
          status: 'error',
          message: 'Build output missing index.html'
        };
        return;
      }

      this.health.checks.buildOutput = {
        status: 'healthy',
        message: 'Build output appears valid'
      };
    } catch (error) {
      this.health.checks.buildOutput = {
        status: 'error',
        message: `Error checking build output: ${error.message}`
      };
    }
  }

  determineOverallHealth() {
    const checks = Object.values(this.health.checks);
    const errorCount = checks.filter(c => c.status === 'error').length;
    const warningCount = checks.filter(c => c.status === 'warning').length;

    if (errorCount > 0) {
      this.health.overall = 'unhealthy';
    } else if (warningCount > 0) {
      this.health.overall = 'degraded';
    } else {
      this.health.overall = 'healthy';
    }
  }

  saveHealth() {
    try {
      if (!fs.existsSync(CONFIG.logDir)) {
        fs.mkdirSync(CONFIG.logDir, { recursive: true });
      }
      
      const healthPath = path.join(CONFIG.logDir, CONFIG.healthCheckFile);
      fs.writeFileSync(healthPath, JSON.stringify(this.health, null, 2));
      
      console.log(`Health check results saved to: ${healthPath}`);
    } catch (error) {
      console.error('Failed to save health check results:', error.message);
    }
  }

  printHealthReport() {
    console.log('\n=== Documentation Health Report ===\n');
    
    console.log(`Overall Health: ${this.getHealthEmoji(this.health.overall)} ${this.health.overall.toUpperCase()}\n`);
    
    console.log('Individual Checks:');
    for (const [checkName, result] of Object.entries(this.health.checks)) {
      const emoji = this.getHealthEmoji(result.status);
      console.log(`  ${emoji} ${checkName}: ${result.status} - ${result.message}`);
    }
    
    console.log(`\nTimestamp: ${this.health.timestamp}`);
  }

  getHealthEmoji(status) {
    switch (status) {
      case 'healthy': return '✅';
      case 'warning': return '⚠️';
      case 'error': return '❌';
      case 'degraded': return '🟡';
      case 'unhealthy': return '🔴';
      case 'info': return 'ℹ️';
      default: return '❓';
    }
  }

  getHealth() {
    return this.health;
  }
}

// Main monitoring function
async function monitor() {
  console.log('Starting documentation monitoring...\n');
  
  const metrics = new MetricsCollector();
  const healthChecker = new HealthChecker();
  
  try {
    // Start monitoring
    metrics.startBuild();
    
    // Update content metrics
    metrics.updateContentMetrics();
    
    // Run health checks
    const health = await healthChecker.runHealthChecks();
    
    // Update performance metrics
    metrics.updatePerformanceMetrics();
    
    // End monitoring
    metrics.endBuild(health.overall !== 'unhealthy');
    
    // Save results
    metrics.saveMetrics();
    healthChecker.saveHealth();
    
    // Print reports
    if (CONFIG.verbose) {
      healthChecker.printHealthReport();
      
      console.log('\n=== Metrics Summary ===');
      const metricsData = metrics.getMetrics();
      console.log(`Content: ${metricsData.content.totalFiles} files, ${Math.round(metricsData.content.totalSize / 1024)}KB total`);
      console.log(`Build time: ${metricsData.performance.buildTime || 'N/A'}ms`);
      console.log(`Build size: ${metricsData.performance.buildSize ? Math.round(metricsData.performance.buildSize / 1024) + 'KB' : 'N/A'}`);
    }
    
    // Exit with appropriate code
    if (health.overall === 'unhealthy') {
      console.log('\n🔴 Documentation health check failed');
      process.exit(1);
    } else if (health.overall === 'degraded') {
      console.log('\n🟡 Documentation health check passed with warnings');
      process.exit(0);
    } else {
      console.log('\n✅ Documentation health check passed');
      process.exit(0);
    }
    
  } catch (error) {
    console.error('Monitoring failed:', error.message);
    if (CONFIG.verbose) {
      console.error(error.stack);
    }
    
    metrics.addBuildError(error.message);
    metrics.endBuild(false);
    metrics.saveMetrics();
    
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  monitor().catch(error => {
    console.error('Unhandled error:', error);
    process.exit(1);
  });
}

module.exports = {
  MetricsCollector,
  HealthChecker,
  CONFIG
};