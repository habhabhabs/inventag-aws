import clsx from 'clsx';
import Heading from '@theme/Heading';
import Link from '@docusaurus/Link';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: '🛡️ Production Safety & Security',
    icon: '🛡️',
    description: (
      <>
        Enterprise-grade security validation with built-in compliance standards 
        (SOC 2, PCI, HIPAA, GDPR). Read-only enforcement, audit logging, and 
        real-time risk assessment ensure your AWS environment stays secure.
      </>
    ),
    link: '/docs/user-guides/production-safety',
    linkText: 'Security Guide'
  },
  {
    title: '📊 Professional BOM Generation',
    icon: '📊',
    description: (
      <>
        Generate comprehensive Bill of Materials reports in Excel, Word, and Google Docs 
        formats. Logical column ordering, service-specific sheets, and professional 
        formatting for enterprise reporting needs.
      </>
    ),
    link: '/docs/user-guides/cli-user-guide',
    linkText: 'BOM Guide'
  },
  {
    title: '🔍 Multi-Account Discovery',
    icon: '🔍',
    description: (
      <>
        Comprehensive resource scanning across multiple AWS accounts with parallel 
        processing. Cross-account roles, interactive setup, and flexible credential 
        management for complex enterprise environments.
      </>
    ),
    link: '/docs/examples/accounts-setup',
    linkText: 'Setup Guide'
  },
  {
    title: '🌐 Advanced Analysis Suite',
    icon: '🌐',
    description: (
      <>
        Network security analysis, cost optimization insights, and security posture 
        assessment. Automated tag compliance checking and comprehensive change tracking 
        with delta detection.
      </>
    ),
    link: '/docs/user-guides/configuration-examples',
    linkText: 'Analysis Features'
  },
  {
    title: '🏷️ Tag Compliance Checking',
    icon: '🏷️',
    description: (
      <>
        Automated validation against organizational tagging policies. Custom tag 
        mappings, compliance reporting, and governance enforcement to maintain 
        consistent resource organization.
      </>
    ),
    link: '/docs/architecture/tag-compliance',
    linkText: 'Tag Compliance'
  },
  {
    title: '⚡ CI/CD Ready',
    icon: '⚡',
    description: (
      <>
        Easy integration with automated workflows, S3 upload support, and 
        comprehensive API for custom integrations. Built for modern DevOps 
        and infrastructure-as-code practices.
      </>
    ),
    link: '/docs/examples/cicd-integration',
    linkText: 'CI/CD Examples'
  },
];

function Feature({icon, title, description, link, linkText}) {
  return (
    <div className={clsx('col col--4')}>
      <div className={styles.featureCard}>
        <div className={styles.featureIcon}>
          <span className={styles.iconEmoji}>{icon}</span>
        </div>
        <div className={styles.featureContent}>
          <Heading as="h3" className={styles.featureTitle}>{title}</Heading>
          <p className={styles.featureDescription}>{description}</p>
          <Link
            className={clsx('button button--outline button--primary', styles.featureLink)}
            to={link}>
            {linkText} →
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  // Split features into rows of 3
  const featuresInRows = [];
  for (let i = 0; i < FeatureList.length; i += 3) {
    featuresInRows.push(FeatureList.slice(i, i + 3));
  }

  return (
    <section className={styles.features}>
      <div className="container">
        {featuresInRows.map((row, rowIdx) => (
          <div 
            className={clsx('row', styles.featureRow)} 
            key={rowIdx}
            style={{
              marginBottom: rowIdx < featuresInRows.length - 1 ? '4rem' : '0'
            }}
          >
            {row.map((props, idx) => (
              <Feature key={`${rowIdx}-${idx}`} {...props} />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}
