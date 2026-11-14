import React, {type ReactNode} from 'react';
import NavbarItem from '@theme-original/NavbarItem';
import type {Props} from '@theme/NavbarItem';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useAddressLocale} from '@site/src/address/addressLocale';

/**
 * Navbar labels and links of the 404 page under /fr/, /es/, /zh-Hans/, /zh-Hant/.
 * That page is the English build's 404.html (see src/address/addressLocale.tsx). Once
 * Root has loaded the navbar.json of the address's language, the labels are read
 * from it and the internal links point at that language's routes as plain links
 * (those routes do not exist in the English build, so a client-side jump would
 * only show this 404 page again). On every other page nothing changes.
 */
export default function NavbarItemWrapper(props: Props): ReactNode {
  const address = useAddressLocale();
  const {
    siteConfig: {baseUrl},
  } = useDocusaurusContext();
  const item = props as Record<string, unknown>;
  if (!address) return <NavbarItem {...props} />;

  const prefix = `${baseUrl}${address.locale}/`;
  const label =
    typeof item.label === 'string' ? (address.navbar[`item.label.${item.label}`]?.message ?? item.label) : item.label;
  const plain = {target: '_self', autoAddBaseUrl: false};

  if (item.type === 'doc') {
    // the docs home (docId "index") of that language
    const {type, docId, docsPluginId, ...rest} = item;
    return <NavbarItem {...(rest as object)} {...plain} label={label as string} to={`pathname://${prefix}docs`} />;
  }
  if ((!item.type || item.type === 'default') && typeof item.to === 'string' && item.to.startsWith('/')) {
    // either a route written in the config ("/docs/reference/cli") or a route that already carries
    // the base URL (the entries of the version menu, "/inventag-aws/docs/1.1.3")
    const route = item.to.startsWith(baseUrl) ? item.to.slice(baseUrl.length) : item.to.slice(1);
    return <NavbarItem {...props} {...plain} label={label as string} to={`pathname://${prefix}${route}`} />;
  }
  return <NavbarItem {...props} {...(label !== item.label ? {label: label as string} : {})} />;
}
