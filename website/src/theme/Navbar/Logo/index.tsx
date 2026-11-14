import React, {type ReactNode} from 'react';
import Logo from '@theme/Logo';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useAddressLocale} from '@site/src/address/addressLocale';

/**
 * The theme's navbar logo. On the 404 page under /fr/ (and the other languages)
 * it links to the home page of that language, as a plain link, because that
 * home page is not a route of the English build that serves this 404 page.
 */
export default function NavbarLogo(): ReactNode {
  const address = useAddressLocale();
  const {
    siteConfig: {baseUrl},
  } = useDocusaurusContext();
  return (
    <Logo
      className="navbar__brand"
      imageClassName="navbar__logo"
      titleClassName="navbar__title text--truncate"
      {...(address ? {to: `pathname://${baseUrl}${address.locale}/`, target: '_self'} : {})}
    />
  );
}
