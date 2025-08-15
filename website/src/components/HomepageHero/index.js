import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import styles from './styles.module.css';

// Import version from main branch (ensured by GitHub Action dependency)
let versionInfo;
try {
  // This requires version.json to be updated in main branch first
  // GitHub Action should fail if version.json is not available
  versionInfo = require('../../../../version.json');
} catch (error) {
  // This fallback should cause build failure in production
  throw new Error('version.json not found - ensure main branch version.json is updated before building docs');
}

function HomepageHero() {
  const {siteConfig} = useDocusaurusContext();
  
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <div className={styles.heroContent}>
          <div className={styles.heroText}>
            <div className={styles.heroTitle}>
              <h1 className="hero__title">
                🏷️ InvenTag
              </h1>
              <div className={styles.versionBadge}>
                <span>v{versionInfo.version}</span>
              </div>
            </div>
            <p className={styles.heroSubtitle}>
              The <strong>Most Comprehensive</strong> AWS Cloud Governance Platform
            </p>
            <p className={styles.heroDescription}>
              Discover, catalog, and analyze your AWS resources across multiple accounts with 
              production-grade safety, billing validation, and professional reporting.
            </p>
            
            <div className={styles.statsGrid}>
              <div className={styles.statItem}>
                <span className={styles.statNumber}>200+</span>
                <span className={styles.statLabel}>AWS Services</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statNumber}>Multi</span>
                <span className={styles.statLabel}>Account Support</span>
              </div>
              <div className={styles.statItem}>
                <span className={styles.statNumber}>Real-time</span>
                <span className={styles.statLabel}>Billing Validation</span>
              </div>
            </div>

            <div className={styles.heroFeatures}>
              <div className={styles.featureItem}>
                <span className={styles.featureIcon}>🛡️</span>
                <span>Enterprise Security & Production Safety</span>
              </div>
              <div className={styles.featureItem}>
                <span className={styles.featureIcon}>💰</span>
                <span>Billing-Validated Service Discovery</span>
              </div>
              <div className={styles.featureItem}>
                <span className={styles.featureIcon}>📊</span>
                <span>Professional Excel/Word BOM Reports</span>
              </div>
              <div className={styles.featureItem}>
                <span className={styles.featureIcon}>🔍</span>
                <span>ResourceGroupsTagging + Cost Explorer</span>
              </div>
            </div>

            <div className={styles.buttons}>
              <Link
                className="button button--secondary button--lg"
                to="/docs/getting-started/quick-start">
                🚀 Get Started Now
              </Link>
              <Link
                className="button button--outline button--secondary button--lg"
                to="/docs/getting-started/introduction">
                📖 Documentation
              </Link>
              <Link
                className="button button--outline button--secondary button--lg"
                to="/docs/examples/advanced-usage">
                📋 See Examples
              </Link>
              <Link
                className="button button--outline button--secondary button--lg"
                href="https://github.com/habhabhabs/inventag-aws">
                💻 View on GitHub
              </Link>
            </div>

            <div className={styles.quickCommand}>
              <div className={styles.commandTitle}>Try it now:</div>
              <div className={styles.commandBox}>
                <code>git clone https://github.com/habhabhabs/inventag-aws.git</code>
                <button 
                  className={styles.copyButton}
                  onClick={() => navigator.clipboard.writeText('git clone https://github.com/habhabhabs/inventag-aws.git')}
                  title="Copy to clipboard"
                >
                  📋
                </button>
              </div>
            </div>
          </div>
          
          <div className={styles.heroVisual}>
            <div className={styles.heroChart}>
              <div className={styles.chartTitle}>
                <span className={styles.chartIcon}>💰</span>
                Billing-Validated Discovery
              </div>
              <div className={styles.comparisonChart}>
                <div className={styles.chartRow}>
                  <span className={styles.chartLabel}>Manual Audits</span>
                  <div className={styles.chartBar}>
                    <div className={styles.chartFill} style={{width: '30%', backgroundColor: '#ef4444'}}></div>
                    <span className={styles.chartValue}>Incomplete</span>
                  </div>
                </div>
                <div className={styles.chartRow}>
                  <span className={styles.chartLabel}>InvenTag v{versionInfo.version}</span>
                  <div className={styles.chartBar}>
                    <div className={styles.chartFill} style={{width: '95%', backgroundColor: '#22c55e'}}></div>
                    <span className={styles.chartValue}>Cost-Validated ✨</span>
                  </div>
                </div>
              </div>
            </div>

            <div className={styles.tagIcon}>
              <svg width="140" height="140" viewBox="0 0 140 140" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <linearGradient id="heroTagGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style={{stopColor: '#60a5fa', stopOpacity: 1}} />
                    <stop offset="50%" style={{stopColor: '#3b82f6', stopOpacity: 1}} />
                    <stop offset="100%" style={{stopColor: '#1e40af', stopOpacity: 1}} />
                  </linearGradient>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
                    <feMerge> 
                      <feMergeNode in="coloredBlur"/>
                      <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                  </filter>
                  <filter id="shadow">
                    <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="rgba(0,0,0,0.3)"/>
                  </filter>
                </defs>
                
                {/* Main tag shape with enhanced styling */}
                <path 
                  d="M25 25h50l35 35-35 35H25V25z" 
                  fill="url(#heroTagGradient)" 
                  stroke="white" 
                  strokeWidth="4"
                  filter="url(#shadow)"
                />
                {/* Tag hole */}
                <circle cx="50" cy="70" r="10" fill="white"/>
                
                {/* AWS service icons around the tag */}
                <g className={styles.awsIcons}>
                  {/* EC2 */}
                  <rect x="85" y="30" width="8" height="8" rx="2" fill="rgba(255,255,255,0.9)"/>
                  {/* S3 */}
                  <circle cx="100" cy="45" r="4" fill="rgba(255,255,255,0.8)"/>
                  {/* RDS */}
                  <ellipse cx="110" cy="60" rx="5" ry="3" fill="rgba(255,255,255,0.85)"/>
                  {/* Lambda */}
                  <path d="M85 75 L95 85 L90 90 L80 80 Z" fill="rgba(255,255,255,0.8)"/>
                  {/* More services */}
                  <circle cx="105" cy="85" r="3" fill="rgba(255,255,255,0.7)"/>
                  <rect x="95" y="25" width="6" height="6" rx="1" fill="rgba(255,255,255,0.75)"/>
                </g>
                
                {/* Animated discovery rays */}
                <g className={styles.discoveryRays}>
                  <line x1="70" y1="40" x2="85" y2="30" stroke="rgba(255,255,255,0.6)" strokeWidth="2">
                    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="2s" repeatCount="indefinite"/>
                  </line>
                  <line x1="70" y1="70" x2="100" y2="45" stroke="rgba(255,255,255,0.6)" strokeWidth="2">
                    <animate attributeName="opacity" values="0.8;0.3;0.8" dur="2.5s" repeatCount="indefinite"/>
                  </line>
                  <line x1="70" y1="85" x2="85" y2="80" stroke="rgba(255,255,255,0.6)" strokeWidth="2">
                    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="3s" repeatCount="indefinite"/>
                  </line>
                </g>
                
                {/* Animated particles representing discovered resources */}
                <circle cx="35" cy="35" r="2" fill="#93c5fd" opacity="0.6">
                  <animate attributeName="opacity" values="0.6;1;0.6" dur="2s" repeatCount="indefinite"/>
                </circle>
                <circle cx="75" cy="75" r="1.5" fill="#93c5fd" opacity="0.4">
                  <animate attributeName="opacity" values="0.4;0.8;0.4" dur="3s" repeatCount="indefinite"/>
                </circle>
                <circle cx="90" cy="20" r="1" fill="#93c5fd" opacity="0.5">
                  <animate attributeName="opacity" values="0.5;0.9;0.5" dur="2.5s" repeatCount="indefinite"/>
                </circle>
              </svg>
            </div>
            
            <div className={styles.badges}>
              <div className={styles.badge}>
                <span className={styles.badgeIcon}>⚡</span>
                <span>CI/CD Ready</span>
              </div>
              <div className={styles.badge}>
                <span className={styles.badgeIcon}>🏢</span>
                <span>Enterprise Grade</span>
              </div>
              <div className={styles.badge}>
                <span className={styles.badgeIcon}>☁️</span>
                <span>AWS Native</span>
              </div>
              <div className={styles.badge}>
                <span className={styles.badgeIcon}>💰</span>
                <span>Cost Validated</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default HomepageHero;