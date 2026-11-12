import React from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageHero from '@site/src/components/HomepageHero';
import HomepageFeatures from '@site/src/components/HomepageFeatures';

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title="AWS inventory, tag compliance and BOM reports"
      description="InvenTag is an open-source Python CLI that inventories AWS resources across accounts, checks tag compliance and writes Excel/Word bill-of-materials reports.">
      <HomepageHero />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}