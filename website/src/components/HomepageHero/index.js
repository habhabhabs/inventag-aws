import React, {useState} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './styles.module.css';

// version.json lives at the repo root and is bumped by the release workflow.
// The build fails loudly if it is missing, which is what we want.
let versionInfo;
try {
  versionInfo = require('../../../../version.json');
} catch (error) {
  throw new Error('version.json not found - ensure main branch version.json is updated before building docs');
}

const COMMANDS = [
  'git clone https://github.com/habhabhabs/inventag-aws.git',
  'cd inventag-aws && pip install -r requirements.txt',
  './inventag.sh --create-excel --verbose',
];

function CopyButton({text}) {
  const [status, setStatus] = useState('');
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setStatus('Copied');
    } catch (e) {
      setStatus('Copy failed: select the text instead');
    }
    setTimeout(() => setStatus(''), 2500);
  };
  return (
    <>
      <button type="button" className={styles.copyButton} onClick={copy} aria-label="Copy the three commands">
        {status === 'Copied' ? 'copied' : 'copy'}
      </button>
      <span className={styles.srOnly} role="status" aria-live="polite">{status}</span>
    </>
  );
}

function HomepageHero() {
  const mark = useBaseUrl('/img/logo-on-brand.svg');
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <div className={styles.heroContent}>
          <div className={styles.heroText}>
            <p className={styles.kicker}>
              <span aria-hidden="true">// </span>open-source CLI · MIT · v{versionInfo.version}
            </p>
            <h1 className={clsx('hero__title', styles.heroTitle)}>
              <img src={mark} alt="" width="64" height="64" className={styles.heroMark} />
              InvenTag
            </h1>
            <p className={styles.heroSubtitle}>
              Find out what is actually running in your AWS accounts, check it is tagged
              the way you agreed, and hand over an Excel or Word bill of materials.
            </p>
            <ul className={styles.heroFacts}>
              <li>Discovery through the Resource Groups Tagging API, service List/Describe/Get calls and Cost Explorer</li>
              <li>One account or many: profiles, access keys or an assumed cross-account role</li>
              <li>Snapshots between runs, so the next report shows what changed</li>
            </ul>
            <div className={styles.buttons}>
              <Link className={clsx('button button--lg', styles.pillPrimary)} to="/docs/getting-started/quick-start">
                Quick start
              </Link>
              <Link className={clsx('button button--lg', styles.pillGhost)} to="/docs/getting-started/introduction">
                What it does
              </Link>
              <Link className={clsx('button button--lg', styles.pillGhost)} href="https://github.com/habhabhabs/inventag-aws">
                GitHub
              </Link>
            </div>
          </div>

          <div className={styles.heroVisual}>
            <div className={styles.terminal} role="group" aria-label="Try it">
              <div className={styles.terminalBar}>
                <span className={styles.terminalTitle}>try it</span>
                <CopyButton text={COMMANDS.join('\n')} />
              </div>
              <pre className={styles.terminalBody}>
                {COMMANDS.map((c) => (
                  <code key={c} className={styles.terminalLine}>
                    <span className={styles.prompt} aria-hidden="true">$ </span>{c}
                  </code>
                ))}
              </pre>
              <p className={styles.terminalNote}>
                Uses your current AWS credentials. Report lands in <code>bom_output/</code>.
                Cost Explorer requests are billed by AWS.
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default HomepageHero;
