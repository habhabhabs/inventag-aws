import React, {useEffect, useState, type ReactNode} from 'react';
import {useThemeConfig} from '@docusaurus/theme-common';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useLocation} from '@docusaurus/router';
import FooterLinks from '@theme/Footer/Links';
import FooterLogo from '@theme/Footer/Logo';
import FooterCopyright from '@theme/Footer/Copyright';
import FooterLayout from '@theme/Footer/Layout';

/**
 * GitHub Pages serves one root 404.html for every address, and that file is built
 * in English. On the 404 page under /fr/ (or /es/, /zh-Hans/, /zh-Hant/) the
 * footer would therefore stay English, because the theme reads the footer text
 * of the build's locale. When the locale in the address differs from the build's
 * locale, this footer loads the footer strings of the locale in the address and
 * points the links at that locale. On every normal page the two locales are the
 * same and the footer is the theme's own.
 */
const LOCALES = ['zh-Hans', 'zh-Hant', 'es', 'fr'] as const;
type Messages = Record<string, {message: string}>;
type Bundle = {footer: Messages; code: Messages};

const LOADERS: Record<string, () => Promise<Bundle>> = {
  'zh-Hans': async () => ({
    footer: (await import('@site/i18n/zh-Hans/docusaurus-theme-classic/footer.json')).default,
    code: (await import('@site/i18n/zh-Hans/code.json')).default,
  }),
  'zh-Hant': async () => ({
    footer: (await import('@site/i18n/zh-Hant/docusaurus-theme-classic/footer.json')).default,
    code: (await import('@site/i18n/zh-Hant/code.json')).default,
  }),
  es: async () => ({
    footer: (await import('@site/i18n/es/docusaurus-theme-classic/footer.json')).default,
    code: (await import('@site/i18n/es/code.json')).default,
  }),
  fr: async () => ({
    footer: (await import('@site/i18n/fr/docusaurus-theme-classic/footer.json')).default,
    code: (await import('@site/i18n/fr/code.json')).default,
  }),
};

type Item = {label?: string; to?: string; href?: string; html?: string; [key: string]: unknown};
type Column = {title?: string; items: Item[]; [key: string]: unknown};

function translate(links: Column[], copyright: string | undefined, bundle: Bundle, prefix: string) {
  const {footer, code} = bundle;
  const text = (key: string, fallback: string) => footer[key]?.message || fallback;
  const cookie = code['footer.cookiePreferences']?.message;
  return {
    copyright: copyright ? text('copyright', copyright) : copyright,
    links: links.map((column) => ({
      ...column,
      title: column.title ? text(`link.title.${column.title}`, column.title) : column.title,
      items: column.items.map((item) => {
        if (item.html) {
          return cookie ? {...item, html: item.html.replace(/>[^<>]*<\/button>/, `>${cookie}</button>`)} : item;
        }
        const label = item.label ? text(`link.item.label.${item.label}`, item.label) : item.label;
        if (item.to) {
          // an internal page: the same page in the locale of the address
          const {to, ...rest} = item;
          return {...rest, label, href: `${prefix}${to.replace(/^\//, '')}`};
        }
        return {...item, label};
      }),
    })),
  };
}

function Footer(): ReactNode {
  const {footer} = useThemeConfig();
  const {
    siteConfig: {baseUrl},
    i18n: {currentLocale},
  } = useDocusaurusContext();
  const {pathname} = useLocation();
  const first = (pathname.startsWith(baseUrl) ? pathname.slice(baseUrl.length) : pathname.replace(/^\//, '')).split(
    '/',
  )[0];
  const wanted = (LOCALES as readonly string[]).includes(first) && first !== currentLocale ? first : null;
  const [loaded, setLoaded] = useState<{locale: string; bundle: Bundle} | null>(null);
  useEffect(() => {
    if (!wanted) return;
    let cancelled = false;
    LOADERS[wanted]().then((bundle) => {
      if (!cancelled) setLoaded({locale: wanted, bundle});
    });
    return () => {
      cancelled = true;
    };
  }, [wanted]);

  if (!footer) return null;
  let {copyright, links} = footer;
  if (wanted && loaded && loaded.locale === wanted && links) {
    const translated = translate(links as Column[], copyright, loaded.bundle, `${baseUrl}${wanted}/`);
    copyright = translated.copyright;
    links = translated.links as typeof links;
  }
  const {logo, style} = footer;
  return (
    <FooterLayout
      style={style}
      links={links && links.length > 0 && <FooterLinks links={links} />}
      logo={logo && <FooterLogo logo={logo} />}
      copyright={copyright && <FooterCopyright copyright={copyright} />}
    />
  );
}
export default React.memo(Footer);
