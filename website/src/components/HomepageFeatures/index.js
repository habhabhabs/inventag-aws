import clsx from 'clsx';
import Heading from '@theme/Heading';
import Link from '@docusaurus/Link';
import styles from './styles.module.css';

// Every line here should be something the code does today. If you add a
// feature, add the flag or file that proves it in `cli`.
const FeatureList = [
  {
    title: 'Read-only discovery',
    cli: 'List* · Describe* · Get*',
    description: (
      <>
        Finds resources through the Resource Groups Tagging API, per-service
        List/Describe/Get calls and Cost Explorer. Give it a read-only IAM
        policy; the docs list the permissions.
      </>
    ),
    link: '/docs/user-guides/production-safety',
    linkText: 'Permissions and safety',
  },
  {
    title: 'Excel and Word reports',
    cli: '--create-excel --create-word',
    description: (
      <>
        A summary sheet plus one sheet per service, with your own tag columns
        (<code>--tag-mappings</code>) and service descriptions
        (<code>--service-descriptions</code>).
      </>
    ),
    link: '/docs/user-guides/cli-user-guide',
    linkText: 'CLI guide',
  },
  {
    title: 'One account or many',
    cli: '--accounts-file accounts.json',
    description: (
      <>
        AWS profiles, access keys or an assumed cross-account role. Accounts run
        in parallel, four at a time by default.
      </>
    ),
    link: '/docs/examples/accounts-setup',
    linkText: 'Account setup',
  },
  {
    title: 'Network and security sheets',
    cli: '--enable-network-analysis',
    description: (
      <>
        Optional extra sheets for VPCs and subnets, and for security groups
        (<code>--enable-security-analysis</code>).
      </>
    ),
    link: '/docs/architecture/network-analysis',
    linkText: 'Network analysis',
  },
  {
    title: 'Tag compliance',
    cli: 'tag_compliance_checker.py --config',
    description: (
      <>
        Check resources against your own policy file: required tags and allowed
        values. Today this runs as a separate script, not a flag on the main CLI.
      </>
    ),
    link: '/docs/architecture/tag-compliance',
    linkText: 'Tag compliance',
  },
  {
    title: 'Change tracking',
    cli: 'bom_output/state/',
    description: (
      <>
        Each run saves a snapshot. The next run reports what was added, removed
        or changed since then.
      </>
    ),
    link: '/docs/architecture/state-management',
    linkText: 'State management',
  },
];

function Feature({title, cli, description, link, linkText}) {
  return (
    <article className={styles.featureCard}>
      <p className={styles.cli}>{cli}</p>
      <Heading as="h3" className={styles.featureTitle}>{title}</Heading>
      <p className={styles.featureDescription}>{description}</p>
      <Link className={clsx('button button--outline button--primary', styles.featureLink)} to={link}>
        {linkText}
      </Link>
    </article>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features} aria-labelledby="what-it-does">
      <div className="container">
        <Heading as="h2" id="what-it-does" className={styles.sectionTitle}>What it does</Heading>
        <div className={styles.grid}>
          {FeatureList.map((props) => (
            <Feature key={props.title} {...props} />
          ))}
        </div>
        <p className={styles.disclaimer}>
          InvenTag is an independent open-source project. It is not affiliated with,
          endorsed by, or sponsored by Amazon Web Services.
        </p>
      </div>
    </section>
  );
}
