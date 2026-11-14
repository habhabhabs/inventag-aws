import React, {createContext, useContext, type ReactNode} from 'react';
import {Context as DocusaurusContext} from '@docusaurus/core/lib/client/docusaurusContext';
import codeTranslations from '@generated/codeTranslations';

/**
 * GitHub Pages serves one root 404.html (built in English) for every address.
 * Under /fr/, /es/, /zh-Hans/ or /zh-Hant/ the page must still speak that
 * language. This module reads the locale from the address and loads the
 * translation files the real locale builds already use (code.json and
 * docusaurus-theme-classic/navbar.json). It keeps no second copy of the texts.
 */
export const LOCALES = ['zh-Hans', 'zh-Hant', 'es', 'fr'] as const;
export type Messages = Record<string, {message: string}>;
export type Bundle = {code: Messages; navbar: Messages};

const LOADERS: Record<string, () => Promise<Bundle>> = {
  'zh-Hans': async () => ({
    code: (await import('@site/i18n/zh-Hans/code.json')).default,
    navbar: (await import('@site/i18n/zh-Hans/docusaurus-theme-classic/navbar.json')).default,
  }),
  'zh-Hant': async () => ({
    code: (await import('@site/i18n/zh-Hant/code.json')).default,
    navbar: (await import('@site/i18n/zh-Hant/docusaurus-theme-classic/navbar.json')).default,
  }),
  es: async () => ({
    code: (await import('@site/i18n/es/code.json')).default,
    navbar: (await import('@site/i18n/es/docusaurus-theme-classic/navbar.json')).default,
  }),
  fr: async () => ({
    code: (await import('@site/i18n/fr/code.json')).default,
    navbar: (await import('@site/i18n/fr/docusaurus-theme-classic/navbar.json')).default,
  }),
};

export function loadBundle(locale: string): Promise<Bundle> {
  return LOADERS[locale]();
}

/** The non-English locale named in the address, when it differs from the build's locale. */
export function localeInAddress(pathname: string, baseUrl: string, currentLocale: string): string | null {
  const rest = pathname.startsWith(baseUrl) ? pathname.slice(baseUrl.length) : pathname.replace(/^\//, '');
  const first = rest.split('/')[0];
  return (LOCALES as readonly string[]).includes(first) && first !== currentLocale ? first : null;
}

// The theme's translate() reads one object built for the build's locale. While the
// address names another locale, its entries are replaced by that locale's code.json
// (so the theme's own labels follow too: colour toggle, menu button), and put back
// when the visitor leaves.
const originals = new Map<string, string | undefined>();
const dictionary = codeTranslations as Record<string, string>;

export function applyCodeMessages(messages: Messages): void {
  for (const [id, entry] of Object.entries(messages)) {
    if (!entry?.message) continue;
    if (!originals.has(id)) originals.set(id, dictionary[id]);
    dictionary[id] = entry.message;
  }
}

export function restoreCodeMessages(): void {
  originals.forEach((value, id) => {
    if (value === undefined) delete dictionary[id];
    else dictionary[id] = value;
  });
  originals.clear();
}

/** Set by Root once the files of the address's locale are loaded; null on every normal page. */
export type AddressLocale = {locale: string; navbar: Messages} | null;
export const AddressLocaleContext = createContext<AddressLocale>(null);
export const useAddressLocale = (): AddressLocale => useContext(AddressLocaleContext);

/**
 * Draws its children in a context that names the address's language as the current
 * locale, with the base URL and the locale list the real locale builds have. The
 * theme's language menu, built on that context, then shows the right language as
 * current and links to the same address in the other languages (/es/..., not
 * /es/fr/...). Outside such a 404 page it passes the children through.
 */
export function AddressLocaleScope({children}: {children: ReactNode}): ReactNode {
  const address = useAddressLocale();
  const context = useContext(DocusaurusContext);
  if (!address) return <>{children}</>;
  const {siteConfig, i18n} = context;
  const root = siteConfig.baseUrl;
  const localeConfigs = Object.fromEntries(
    Object.entries(i18n.localeConfigs).map(([locale, config]) => [
      locale,
      {...config, baseUrl: locale === i18n.defaultLocale ? root : `${root}${locale}/`},
    ]),
  );
  return (
    <DocusaurusContext.Provider
      value={{
        ...context,
        siteConfig: {...siteConfig, baseUrl: `${root}${address.locale}/`},
        i18n: {...i18n, currentLocale: address.locale, localeConfigs},
      }}>
      {children}
    </DocusaurusContext.Provider>
  );
}
