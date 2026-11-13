import React, {type ReactNode} from 'react';
import Head from '@docusaurus/Head';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';
import ThemedImage from '@theme/ThemedImage';
import CommandSnippet from '@site/src/components/landing/CommandSnippet';
import {
  IconAccounts,
  IconArrow,
  IconCheck,
  IconHistory,
  IconNetwork,
  IconScan,
  IconSheet,
  IconTag,
  IconTemplate,
} from '@site/src/components/landing/Icons';
// version.json lives at the repo root and is bumped by the release workflow.
import versionInfo from '../../../version.json';
import styles from '@site/src/components/landing/landing.module.css';

const VERSION = versionInfo.version;
const REPO = 'https://github.com/habhabhabs/inventag-aws';
const PAGE_TITLE = 'AWS inventory, tag checks and BOM reports';
const PAGE_DESCRIPTION =
  'InvenTag is an open-source Python CLI. It lists the resources in your AWS accounts, ' +
  'shows how each one is tagged and writes an Excel or Word bill of materials.';

// The templates guide: docs/templates/index.md
const TEMPLATES_LINK = '/docs/templates/';

// Commands from docs/getting-started/quick-start.md
const QUICK_START = [
  {cmd: 'python3 -m venv .venv && source .venv/bin/activate'},
  {cmd: 'pip install inventag-aws'},
  {cmd: 'inventag --create-excel --verbose'},
];

// Summary sheet layout written by BOMConverter._create_summary_sheet
// (inventag/reporting/converter.py): Service, Resource Count, Percentage,
// services sorted by name, then a TOTAL row. The numbers are sample data.
const SAMPLE_SUMMARY: [string, number][] = [
  ['EC2', 14],
  ['Lambda', 6],
  ['RDS', 3],
  ['S3', 9],
  ['VPC', 8],
];
const SAMPLE_TOTAL = SAMPLE_SUMMARY.reduce((n, [, c]) => n + c, 0);

// boto3 calls that appear in inventag/discovery (excerpt)
const API_CALLS = [
  ['resourcegroupstaggingapi', 'get_resources'],
  ['ec2', 'describe_instances'],
  ['s3', 'list_buckets'],
  ['rds', 'describe_db_instances'],
  ['lambda', 'list_functions'],
  ['ce', 'get_cost_and_usage'],
];

function StructuredData(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  const home = `${siteConfig.url}${siteConfig.baseUrl}`;
  const data = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'SoftwareApplication',
        '@id': `${home}#software`,
        name: 'InvenTag',
        description: PAGE_DESCRIPTION,
        url: home,
        applicationCategory: 'DeveloperApplication',
        applicationSubCategory: 'Command-line tool',
        operatingSystem: 'Linux, macOS, Windows',
        softwareVersion: VERSION,
        softwareRequirements: 'Python 3.11 or newer; AWS credentials with read-only permissions',
        license: 'https://opensource.org/licenses/MIT',
        isAccessibleForFree: true,
        offers: {'@type': 'Offer', price: '0', priceCurrency: 'USD'},
        image: `${home}img/social-card.png`,
        downloadUrl: REPO,
        releaseNotes: `${REPO}/releases/tag/v${VERSION}`,
      },
      {
        '@type': 'SoftwareSourceCode',
        '@id': `${home}#source`,
        name: 'inventag-aws',
        codeRepository: REPO,
        programmingLanguage: 'Python',
        runtimePlatform: 'Python 3',
        license: 'https://opensource.org/licenses/MIT',
        targetProduct: {'@id': `${home}#software`},
      },
      {
        '@type': 'WebSite',
        '@id': `${home}#website`,
        name: 'InvenTag',
        url: home,
        inLanguage: 'en',
      },
    ],
  };
  return (
    <Head>
      <script type="application/ld+json">{JSON.stringify(data)}</script>
    </Head>
  );
}

function Hero(): ReactNode {
  return (
    <header className={styles.hero}>
      <div className={styles.heroCopy}>
        <p className={styles.kicker}>
          <span>Open-source CLI for AWS</span>
          <span aria-hidden="true" className={styles.kickerDot} />
          <span>Python</span>
          <span aria-hidden="true" className={styles.kickerDot} />
          <span>MIT</span>
          <span aria-hidden="true" className={styles.kickerDot} />
          <Link className={styles.kickerLink} href={`${REPO}/releases/tag/v${VERSION}`}>
            v{VERSION}
            <span className="sr-only"> release notes</span>
          </Link>
        </p>
        <h1 className={styles.heroTitle}>
          See what runs in your AWS accounts. <em>Then hand over the&nbsp;report.</em>
        </h1>
        <p className={styles.heroLead}>
          InvenTag scans one AWS account or many. It lists the resources it finds and the tags on
          each one. Then it writes an Excel or Word report, a bill of materials, that anyone can read.
        </p>
        <div className={styles.actions}>
          <Link className="button button--primary button--lg" to="/docs/getting-started/quick-start">
            Run the quick start
            <IconArrow />
          </Link>
          <Link className="button button--secondary button--lg" to="/docs/getting-started/introduction">
            How it works
          </Link>
        </div>
        <p className={styles.heroNote}>
          A built-in guard lets through only read calls such as <code>List</code>, <code>Describe</code> and{' '}
          <code>Get</code>. Run it with a read-only IAM role as well:{' '}
          <Link to="/docs/user-guides/production-safety">see the permissions it needs</Link>.
        </p>
      </div>
      <div className={styles.heroAside}>
        <CommandSnippet
          title="Quick start"
          lines={QUICK_START}
          footnote={
            <>
              Installs <code>inventag-aws</code> from PyPI with pip. Uses your current AWS credentials. Writes{' '}
              <code>bom_output/multi_account_bom_&lt;timestamp&gt;.xlsx</code>. Cost Explorer requests
              are billed by AWS.
            </>
          }
        />
      </div>
    </header>
  );
}

function BomPreview(): ReactNode {
  return (
    <figure className={styles.preview} aria-labelledby="bom-preview-caption">
      <div className={styles.sheet}>
        <table className={styles.sheetTable}>
          <caption className="sr-only">Sample Summary sheet</caption>
          <thead>
            <tr>
              <th scope="col">Service</th>
              <th scope="col">Resource Count</th>
              <th scope="col">Percentage</th>
            </tr>
          </thead>
          <tbody>
            {SAMPLE_SUMMARY.map(([service, count]) => (
              <tr key={service}>
                <th scope="row">{service}</th>
                <td>{count}</td>
                <td>{((count / SAMPLE_TOTAL) * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">TOTAL</th>
              <td>{SAMPLE_TOTAL}</td>
              <td>100.0%</td>
            </tr>
          </tfoot>
        </table>
        <ul className={styles.sheetTabs} aria-label="Worksheets in the workbook">
          <li className={styles.sheetTabActive}>Summary</li>
          {SAMPLE_SUMMARY.map(([s]) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>
      <figcaption id="bom-preview-caption" className={styles.previewCaption}>
        <span className={styles.sampleBadge}>Sample data</span> The Summary sheet layout from{' '}
        <code>--create-excel</code>. Each service then gets its own sheet with one row per resource.
      </figcaption>
    </figure>
  );
}

type CellProps = {
  icon: ReactNode;
  title: string;
  flag?: string;
  children: ReactNode;
  link: string;
  linkLabel: string;
  className?: string;
  preview?: ReactNode;
};

function Cell({icon, title, flag, children, link, linkLabel, className, preview}: CellProps): ReactNode {
  return (
    <article className={`${styles.cell} ${className ?? ''}`}>
      <div className={styles.cellHead}>
        <span className={styles.cellIcon}>{icon}</span>
        {flag && <code className={styles.flag}>{flag}</code>}
      </div>
      <h3 className={styles.cellTitle}>{title}</h3>
      <div className={styles.cellBody}>{children}</div>
      {preview}
      <Link className={styles.cellLink} to={link}>
        {linkLabel}
        <IconArrow />
      </Link>
    </article>
  );
}

function Capabilities(): ReactNode {
  return (
    <section className={styles.section} aria-labelledby="capabilities">
      <div className={styles.sectionHead}>
        <p className={styles.eyebrow}>01 · What you get</p>
        <h2 id="capabilities" className={styles.sectionTitle}>
          One command. A report people can read.
        </h2>
        <p className={styles.sectionLead}>
          Everything below works in the CLI today. Where a feature is only partly done, the docs say so.
        </p>
      </div>
      <div className={styles.bento}>
        <Cell
          className={styles.span7}
          icon={<IconSheet />}
          title="Excel and Word reports"
          flag="--create-excel  --create-word"
          link="/docs/reference/cli"
          linkLabel="See every report option"
          preview={<BomPreview />}>
          <p>
            A summary sheet, then one sheet per service. Add a Word version for people who prefer documents.
            Files are saved in <code>bom_output/</code>.
          </p>
        </Cell>
        <Cell
          className={styles.span5}
          icon={<IconScan />}
          title="Read-only discovery"
          flag="--audit-output"
          link="/docs/user-guides/production-safety"
          linkLabel="Permissions and safety"
          preview={
            <figure className={styles.preview} aria-labelledby="api-caption">
              <ul className={styles.apiList}>
                {API_CALLS.map(([svc, op]) => (
                  <li key={op}>
                    <span className={styles.apiSvc}>{svc}</span>.{op}
                  </li>
                ))}
              </ul>
              <figcaption id="api-caption" className={styles.previewCaption}>
                Some of the boto3 calls in <code>inventag/discovery</code>.
              </figcaption>
            </figure>
          }>
          <p>
            Finds resources through the Resource Groups Tagging API, each service's own list and describe
            calls, and Cost Explorer. A guard blocks any AWS call that could change something. Add{' '}
            <code>--audit-output</code> to save a record of every call made.
          </p>
        </Cell>
        <Cell
          className={styles.span4}
          icon={<IconAccounts />}
          title="One account or many"
          flag="--accounts-file"
          link="/docs/examples/accounts-setup"
          linkLabel="Set up several accounts"
          preview={
            <pre className={styles.snippet} tabIndex={0}>
              <code>{`{
  "accounts": [{
    "account_id": "123456789012",
    "account_name": "Production",
    "profile_name": "prod",
    "regions": ["us-east-1"]
  }]
}`}</code>
            </pre>
          }>
          <p>
            Use AWS profiles, access keys or a role to assume. Accounts are scanned in parallel, four at a
            time by default.
          </p>
        </Cell>
        <Cell
          className={styles.span4}
          icon={<IconTag />}
          title="Your tags, your columns"
          flag="--tag-mappings"
          link="/docs/user-guides/configuration-examples"
          linkLabel="Map tags to columns"
          preview={
            <pre className={styles.snippet} tabIndex={0}>
              <code>{`tag_mappings:
  - tag: "Owner"
    name: "Resource Owner"
  - tag: "CostCenter"
    name: "Cost Center"`}</code>
            </pre>
          }>
          <p>Turn the tags your team agreed on into named columns in the default report. Add your own service descriptions too.</p>
        </Cell>
        <Cell
          className={styles.span4}
          icon={<IconHistory />}
          title="What changed since last time"
          link="/docs/architecture/state-management"
          linkLabel="How snapshots work"
          preview={
            <pre className={styles.snippet} tabIndex={0}>
              <code>{`bom_output/
├─ multi_account_bom_<timestamp>.xlsx
└─ state/
   └─ state_<timestamp>.json`}</code>
            </pre>
          }>
          <p>Each run saves a snapshot. The next run tells you what was added, removed or changed.</p>
        </Cell>
        <Cell
          className={styles.span6}
          icon={<IconTemplate />}
          title="Reusable templates"
          link={TEMPLATES_LINK}
          linkLabel="Browse the templates"
          preview={
            <ul className={styles.fileList} aria-label="Built-in templates">
              <li>
                <span>Report layouts</span>
                <code>standard-bom</code>
                <code>executive-summary</code>
              </li>
              <li>
                <span>Tag policies</span>
                <code>finops-cost-allocation</code>
                <code>security-baseline</code>
              </li>
              <li>
                <span>Run settings</span>
                <code>single-account</code>
                <code>ci-pipeline</code>
              </li>
            </ul>
          }>
          <p>
            Start from eight built-in templates: report layouts, tag policies and run settings. List them with{' '}
            <code>inventag templates list</code>, copy one into your project and change only what you need.
          </p>
        </Cell>
        <Cell
          className={styles.span3}
          icon={<IconNetwork />}
          title="Network and security sheets"
          flag="--enable-network-analysis"
          link="/docs/architecture/network-analysis"
          linkLabel="Network analysis">
          <p>
            Optional sheets for VPCs and subnets, and for security groups with{' '}
            <code>--enable-security-analysis</code>.
          </p>
        </Cell>
        <Cell
          className={styles.span3}
          icon={<IconCheck />}
          title="Tag policy checks"
          link="/docs/architecture/tag-compliance"
          linkLabel="Tag compliance">
          <p>Check for required tags and allowed values with a tag-policy template. Results go to a sheet, a Word section and a JSON file.</p>
        </Cell>
      </div>
    </section>
  );
}

const STEPS = [
  ['Credentials', 'Your default AWS credentials, a named profile, keys from an accounts file, or an assumed role.'],
  ['Discovery', 'For each account and region: the Tagging API, per-service read calls and Cost Explorer.'],
  ['Enrichment', 'Service attributes, your tag columns and descriptions, optional network and security analysis.'],
  ['Output', 'Excel and Word files in bom_output/, plus a snapshot the next run compares against.'],
];

function HowItWorks(): ReactNode {
  return (
    <section className={styles.section} aria-labelledby="how-it-works">
      <div className={styles.sectionHead}>
        <p className={styles.eyebrow}>02 · How a run works</p>
        <h2 id="how-it-works" className={styles.sectionTitle}>
          Four steps, left to right.
        </h2>
      </div>
      <ol className={styles.steps}>
        {STEPS.map(([title, text], i) => (
          <li key={title} className={styles.step}>
            <span className={styles.stepNo} aria-hidden="true">
              {String(i + 1).padStart(2, '0')}
            </span>
            <h3 className={styles.stepTitle}>{title}</h3>
            <p>{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Honest(): ReactNode {
  return (
    <section className={`${styles.section} ${styles.honest}`} aria-labelledby="before-you-rely">
      <div className={styles.honestGrid}>
        <div>
          <p className={styles.eyebrow}>03 · Before you rely on it</p>
          <h2 id="before-you-rely" className={styles.sectionTitle}>
            Plain about the edges.
          </h2>
        </div>
        <ul className={styles.honestList}>
          <li>
            Some options are not built yet. If you use one, the run stops with a clear &ldquo;not implemented
            yet&rdquo; message instead of ignoring it. The{' '}
            <Link to="/docs/getting-started/status">current status page</Link> lists what works today.
          </li>
          <li>
            By default, discovery calls Cost Explorer, and AWS charges for each Cost Explorer request. Read the{' '}
            <Link to="/docs/getting-started/status#costs">notes on cost</Link> before you scan many accounts.
          </li>
          <li>
            InvenTag has its own discovery code for 24 AWS services and has only been tested against mocked AWS,
            not a real account.
          </li>
          <li>
            It gathers evidence, such as a list of resources and how well they are tagged. It does not certify
            that you meet any compliance standard.
          </li>
        </ul>
      </div>
    </section>
  );
}

function Closing(): ReactNode {
  const mark = useBaseUrl('/img/logo.svg');
  const markDark = useBaseUrl('/img/logo-dark.svg');
  return (
    <section className={styles.closing} aria-labelledby="start">
      <div className={styles.closingInner}>
        <ThemedImage
          className={styles.closingMark}
          sources={{light: mark, dark: markDark}}
          alt=""
          width={56}
          height={56}
        />
        <h2 id="start" className={styles.closingTitle}>
          Start with one account. It takes about ten minutes.
        </h2>
        <div className={styles.actions}>
          <Link className="button button--primary button--lg" to="/docs/getting-started/quick-start">
            Run the quick start
            <IconArrow />
          </Link>
          <Link className="button button--secondary button--lg" href={REPO}>
            Source on GitHub
          </Link>
        </div>
        <p className={styles.disclaimer}>
          InvenTag is an independent open-source project. It is not affiliated with, endorsed by, or sponsored
          by Amazon Web Services.
        </p>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout title={PAGE_TITLE} description={PAGE_DESCRIPTION}>
      <StructuredData />
      <main className={styles.page}>
        <Hero />
        <Capabilities />
        <HowItWorks />
        <Honest />
        <Closing />
      </main>
    </Layout>
  );
}
