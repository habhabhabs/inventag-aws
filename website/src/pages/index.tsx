import React, {type ReactNode} from 'react';
import Head from '@docusaurus/Head';
import Link from '@docusaurus/Link';
import Layout from '@theme/Layout';
import Translate, {translate} from '@docusaurus/Translate';
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
const PYPI = 'https://pypi.org/project/inventag-aws/';
const pageTitle = (): string => translate({id: 'home.pageTitle', message: 'AWS inventory, tag checks and BOM reports'});
const pageDescription = (): string =>
  translate({
    id: 'home.pageDescription',
    message:
      'InvenTag is an open-source Python CLI. It lists the resources in your AWS accounts, shows how each one is tagged and writes an Excel or Word bill of materials.',
  });

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
  const {siteConfig, i18n} = useDocusaurusContext();
  const home = `${siteConfig.url}${siteConfig.baseUrl}`;
  const data = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'SoftwareApplication',
        '@id': `${home}#software`,
        name: 'InvenTag',
        description: pageDescription(),
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
        installUrl: PYPI, // pip install inventag-aws
        sameAs: [REPO, PYPI],
        author: {'@type': 'Organization', name: 'InvenTag contributors'},
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
        inLanguage: i18n.currentLocale,
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
          <span>
            <Translate id="home.kicker">Open-source CLI for AWS</Translate>
          </span>
          <span aria-hidden="true" className={styles.kickerDot} />
          <span>Python</span>
          <span aria-hidden="true" className={styles.kickerDot} />
          <span>MIT</span>
          <span aria-hidden="true" className={styles.kickerDot} />
          <Link className={styles.kickerLink} href={`${REPO}/releases/tag/v${VERSION}`}>
            v{VERSION}
            <span className="sr-only">
              {' '}
              <Translate id="home.releaseNotes">release notes</Translate>
            </span>
          </Link>
        </p>
        <h1 className={styles.heroTitle}>
          <Translate
            id="home.heroTitle"
            values={{emphasis: <em>{translate({id: 'home.heroTitleEm', message: 'Then hand over the\u00a0report.'})}</em>}}>
            {'See what runs in your AWS accounts. {emphasis}'}
          </Translate>
        </h1>
        <p className={styles.heroLead}>
          <Translate id="home.heroLead">
            InvenTag scans one AWS account or many. It lists the resources it finds and the tags on each one. Then it writes an Excel or Word report, a bill of materials, that anyone can read.
          </Translate>
        </p>
        <div className={styles.actions}>
          <Link className="button button--primary button--lg" to="/docs/getting-started/quick-start">
            <Translate id="home.runQuickStart">Run the quick start</Translate>
            <IconArrow />
          </Link>
          <Link className="button button--secondary button--lg" to="/docs/getting-started/introduction">
            <Translate id="home.howItWorks">How it works</Translate>
          </Link>
        </div>
        <p className={styles.heroNote}>
          <Translate
            id="home.heroNote"
            values={{
              list: <code>List</code>,
              describe: <code>Describe</code>,
              get: <code>Get</code>,
              link: (
                <Link to="/docs/user-guides/production-safety">
                  {translate({id: 'home.heroNoteLink', message: 'see the permissions it needs'})}
                </Link>
              ),
            }}>
            {'A built-in guard lets through only read calls such as {list}, {describe} and {get}. Run it with a read-only IAM role as well: {link}.'}
          </Translate>
        </p>
      </div>
      <div className={styles.heroAside}>
        <CommandSnippet
          title={translate({id: 'home.quickStartTitle', message: 'Quick start'})}
          lines={QUICK_START}
          footnote={
            <Translate
              id="home.snippetFootnote"
              values={{
                pkg: <code>inventag-aws</code>,
                file: <code>bom_output/multi_account_bom_&lt;timestamp&gt;.xlsx</code>,
              }}>
              {'Installs {pkg} from PyPI with pip. Uses your current AWS credentials. Writes {file}. Cost Explorer requests are billed by AWS.'}
            </Translate>
          }
        />
        <p className={styles.heroFlow}>
          <span aria-hidden="true" className={styles.heroFlowLine} />
          <Translate id="home.heroFlow">The report it writes</Translate>
        </p>
        <BomPreview />
      </div>
    </header>
  );
}

function BomPreview(): ReactNode {
  return (
    <figure className={styles.preview} aria-labelledby="bom-preview-caption">
      <div className={styles.sheet}>
        <table className={styles.sheetTable}>
          <caption className="sr-only">
            <Translate id="home.sheetCaption">Sample Summary sheet</Translate>
          </caption>
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
        <ul className={styles.sheetTabs} aria-label={translate({id: 'home.sheetTabs', message: 'Worksheets in the workbook'})}>
          <li className={styles.sheetTabActive}>Summary</li>
          {SAMPLE_SUMMARY.map(([s]) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>
      <figcaption id="bom-preview-caption" className={styles.previewCaption}>
        <span className={styles.sampleBadge}>
          <Translate id="home.sampleData">Sample data</Translate>
        </span>{' '}
        <Translate id="home.sheetNote" values={{flag: <code>--create-excel</code>}}>
          {'The Summary sheet layout from {flag}. Each service then gets its own sheet with one row per resource.'}
        </Translate>
      </figcaption>
    </figure>
  );
}

function DocOutlinePreview(): ReactNode {
  return (
    <figure className={styles.preview} aria-labelledby="doc-outline-caption">
      <div className={styles.outline} role="group" aria-label={translate({id: 'home.docCaption', message: 'Sample Word document outline'})}>
        <p className={styles.outlineTitle}>AWS Resource Inventory - BOM Report</p>
        <ul className={styles.outlineList}>
          <li>
            Executive Summary
            <ul>
              <li>Service Summary</li>
            </ul>
          </li>
          <li>
            Detailed Resource Inventory
            <ul>
              {SAMPLE_SUMMARY.map(([service, count]) => (
                <li key={service}>
                  {service.toUpperCase()} Resources ({count})
                </li>
              ))}
            </ul>
          </li>
          <li>Report Information</li>
        </ul>
      </div>
      <figcaption id="doc-outline-caption" className={styles.previewCaption}>
        <span className={styles.sampleBadge}>
          <Translate id="home.sampleData">Sample data</Translate>
        </span>{' '}
        <Translate id="home.docNote" values={{flag: <code>--create-word</code>}}>
          {'The outline of the Word document from {flag}. Each service section lists up to 50 resources by default.'}
        </Translate>
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
        <p className={styles.eyebrow}>
          <Translate id="home.cap.eyebrow">01 · What you get</Translate>
        </p>
        <h2 id="capabilities" className={styles.sectionTitle}>
          <Translate id="home.cap.title">One command. A report people can read.</Translate>
        </h2>
        <p className={styles.sectionLead}>
          <Translate id="home.cap.lead">
            Everything below works in the CLI today. Where a feature is only partly done, the docs say so.
          </Translate>
        </p>
      </div>
      <div className={styles.bento}>
        <Cell
          className={styles.span7}
          icon={<IconSheet />}
          title={translate({id: 'home.c1.title', message: 'Excel and Word reports'})}
          flag="--create-excel  --create-word"
          link="/docs/reference/cli"
          linkLabel={translate({id: 'home.c1.link', message: 'See every report option'})}
          preview={<DocOutlinePreview />}>
          <p>
            <Translate id="home.c1.body" values={{dir: <code>bom_output/</code>}}>
              {'A summary sheet, then one sheet per service. Add a Word version for people who prefer documents. Files are saved in {dir}.'}
            </Translate>
          </p>
        </Cell>
        <Cell
          className={styles.span5}
          icon={<IconScan />}
          title={translate({id: 'home.c2.title', message: 'Read-only discovery'})}
          flag="--audit-output"
          link="/docs/user-guides/production-safety"
          linkLabel={translate({id: 'home.c2.link', message: 'Permissions and safety'})}
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
                <Translate id="home.c2.caption" values={{dir: <code>inventag/discovery</code>}}>
                  {'Some of the boto3 calls in {dir}.'}
                </Translate>
              </figcaption>
            </figure>
          }>
          <p>
            <Translate id="home.c2.body" values={{flag: <code>--audit-output</code>}}>
              {"Finds resources through the Resource Groups Tagging API, each service's own list and describe calls, and Cost Explorer. A guard blocks any AWS call that could change something, and values that often hold secrets are masked. Add {flag} to save a record of every call made."}
            </Translate>
          </p>
        </Cell>
        <Cell
          className={styles.span4}
          icon={<IconAccounts />}
          title={translate({id: 'home.c3.title', message: 'One account or many'})}
          flag="--accounts-file"
          link="/docs/examples/accounts-setup"
          linkLabel={translate({id: 'home.c3.link', message: 'Inventory every account in an organization'})}
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
            <Translate id="home.c3.body">
              Use AWS profiles, access keys or a role to assume. Accounts are scanned in parallel, four at a time by default.
            </Translate>
          </p>
        </Cell>
        <Cell
          className={styles.span4}
          icon={<IconTag />}
          title={translate({id: 'home.c4.title', message: 'Your tags, your columns'})}
          flag="--tag-mappings"
          link="/docs/user-guides/configuration-examples"
          linkLabel={translate({id: 'home.c4.link', message: 'Map tags to columns'})}
          preview={
            <pre className={styles.snippet} tabIndex={0}>
              <code>{`tag_mappings:
  - tag: "Owner"
    name: "Resource Owner"
  - tag: "CostCenter"
    name: "Cost Center"`}</code>
            </pre>
          }>
          <p>
            <Translate id="home.c4.body">
              Turn the tags your team agreed on into named columns in the default report. Add your own service descriptions too.
            </Translate>
          </p>
        </Cell>
        <Cell
          className={styles.span4}
          icon={<IconHistory />}
          title={translate({id: 'home.c5.title', message: 'What changed since last time'})}
          link="/docs/architecture/state-management"
          linkLabel={translate({id: 'home.c5.link', message: 'How snapshots work'})}
          preview={
            <pre className={styles.snippet} tabIndex={0}>
              <code>{`bom_output/
├─ multi_account_bom_<timestamp>.xlsx
└─ state/
   └─ state_<timestamp>.json`}</code>
            </pre>
          }>
          <p>
            <Translate id="home.c5.body">Each run saves a snapshot. The next run tells you what was added, removed or changed.</Translate>
          </p>
        </Cell>
        <Cell
          className={styles.span6}
          icon={<IconTemplate />}
          title={translate({id: 'home.c6.title', message: 'Reusable templates'})}
          link={TEMPLATES_LINK}
          linkLabel={translate({id: 'home.c6.link', message: 'Browse the templates'})}
          preview={
            <ul className={styles.fileList} aria-label={translate({id: 'home.c6.list', message: 'Built-in templates'})}>
              <li>
                <span>
                  <Translate id="home.c6.layouts">Report layouts</Translate>
                </span>
                <code>standard-bom</code>
                <code>executive-summary</code>
              </li>
              <li>
                <span>
                  <Translate id="home.c6.policies">Tag policies</Translate>
                </span>
                <code>finops-cost-allocation</code>
                <code>security-baseline</code>
              </li>
              <li>
                <span>
                  <Translate id="home.c6.settings">Run settings</Translate>
                </span>
                <code>single-account</code>
                <code>ci-pipeline</code>
              </li>
            </ul>
          }>
          <p>
            <Translate id="home.c6.body" values={{cmd: <code>inventag templates list</code>}}>
              {'Start from eight built-in templates: report layouts, tag policies and run settings. List them with {cmd}, copy one into your project and change only what you need.'}
            </Translate>
          </p>
        </Cell>
        <Cell
          className={styles.span3}
          icon={<IconNetwork />}
          title={translate({id: 'home.c7.title', message: 'Network and security sheets'})}
          flag="--enable-network-analysis"
          link="/docs/architecture/network-analysis"
          linkLabel={translate({id: 'home.c7.link', message: 'Network analysis'})}>
          <p>
            <Translate id="home.c7.body" values={{flag: <code>--enable-security-analysis</code>}}>
              {'Optional sheets for VPCs and subnets, and for security groups with {flag}.'}
            </Translate>
          </p>
        </Cell>
        <Cell
          className={styles.span3}
          icon={<IconCheck />}
          title={translate({id: 'home.c8.title', message: 'Tag policy checks'})}
          link="/docs/architecture/tag-compliance"
          linkLabel={translate({id: 'home.c8.link', message: 'Tag compliance'})}>
          <p>
            <Translate id="home.c8.body">
              Check for required tags and allowed values with a tag-policy template. Results go to a sheet, a Word section and a JSON file.
            </Translate>
          </p>
        </Cell>
      </div>
    </section>
  );
}

const steps = (): [string, string][] => [
  [
    translate({id: 'home.s1.title', message: 'Credentials'}),
    translate({id: 'home.s1.body', message: 'Your default AWS credentials, a named profile, keys from an accounts file, or an assumed role.'}),
  ],
  [
    translate({id: 'home.s2.title', message: 'Discovery'}),
    translate({id: 'home.s2.body', message: 'For each account and region: the Tagging API, per-service read calls and Cost Explorer.'}),
  ],
  [
    translate({id: 'home.s3.title', message: 'Enrichment'}),
    translate({id: 'home.s3.body', message: 'Service attributes, your tag columns and descriptions, optional network and security analysis.'}),
  ],
  [
    translate({id: 'home.s4.title', message: 'Output'}),
    translate({id: 'home.s4.body', message: 'Excel and Word files in bom_output/, plus a snapshot the next run compares against.'}),
  ],
];

function HowItWorks(): ReactNode {
  return (
    <section className={styles.section} aria-labelledby="how-it-works">
      <div className={styles.sectionHead}>
        <p className={styles.eyebrow}>
          <Translate id="home.how.eyebrow">02 · How a run works</Translate>
        </p>
        <h2 id="how-it-works" className={styles.sectionTitle}>
          <Translate id="home.how.title">Four steps, left to right.</Translate>
        </h2>
      </div>
      <ol className={styles.steps}>
        {steps().map(([title, text], i) => (
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
          <p className={styles.eyebrow}>
            <Translate id="home.honest.eyebrow">03 · Before you rely on it</Translate>
          </p>
          <h2 id="before-you-rely" className={styles.sectionTitle}>
            <Translate id="home.honest.title">Plain about the edges.</Translate>
          </h2>
        </div>
        <ul className={styles.honestList}>
          <li>
            <Translate
              id="home.honest.1"
              values={{
                link: (
                  <Link to="/docs/getting-started/status">
                    {translate({id: 'home.honest.1.link', message: 'feature status page'})}
                  </Link>
                ),
              }}>
              {'Some options are not built yet. If you use one, the run stops with a clear “not implemented yet” message instead of ignoring it. The {link} lists what works today.'}
            </Translate>
          </li>
          <li>
            <Translate
              id="home.honest.2"
              values={{
                link: (
                  <Link to="/docs/getting-started/status#costs">
                    {translate({id: 'home.honest.2.link', message: 'notes on cost'})}
                  </Link>
                ),
              }}>
              {'By default, discovery calls Cost Explorer, and AWS charges for each Cost Explorer request. Read the {link} before you scan many accounts.'}
            </Translate>
          </li>
          <li>
            <Translate id="home.honest.3">
              InvenTag has its own discovery code for 46 AWS services and has only been tested against mocked AWS, not a real account.
            </Translate>
          </li>
          <li>
            <Translate id="home.honest.4">
              It gathers evidence, such as a list of resources and how well they are tagged. It does not certify that you meet any compliance standard.
            </Translate>
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
          <Translate id="home.closing.title">Start with one account. It takes about ten minutes.</Translate>
        </h2>
        <div className={styles.actions}>
          <Link className="button button--primary button--lg" to="/docs/getting-started/quick-start">
            <Translate id="home.runQuickStart">Run the quick start</Translate>
            <IconArrow />
          </Link>
          <Link className="button button--secondary button--lg" href={REPO}>
            <Translate id="home.sourceOnGitHub">Source on GitHub</Translate>
          </Link>
        </div>
        <p className={styles.disclaimer}>
          <Translate id="home.disclaimer">
            InvenTag is an independent open-source project. It is not affiliated with, endorsed by, or sponsored by Amazon Web Services.
          </Translate>
        </p>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout title={pageTitle()} description={pageDescription()}>
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
