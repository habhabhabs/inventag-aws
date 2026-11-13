import React, {type ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import IconHome from '@theme/Icon/Home';

import styles from './styles.module.css';

/**
 * Inside the docs the house icon goes to the documentation start page
 * ("InvenTag documentation"), not to the marketing landing page. The site
 * logo in the navbar still goes to the landing page.
 */
export default function HomeBreadcrumbItem(): ReactNode {
  const docsHref = useBaseUrl('/docs/');

  return (
    <li className="breadcrumbs__item">
      <Link
        aria-label="InvenTag documentation"
        className="breadcrumbs__link"
        href={docsHref}>
        <IconHome className={styles.breadcrumbHomeIcon} />
      </Link>
    </li>
  );
}
