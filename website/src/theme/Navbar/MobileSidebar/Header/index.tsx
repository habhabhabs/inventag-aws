import React, {useEffect, useRef, useState, type ReactNode} from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useAlternatePageUtils, useNavbarMobileSidebar} from '@docusaurus/theme-common/internal';
import {mergeSearchStrings, useHistorySelector} from '@docusaurus/theme-common';
import {translate} from '@docusaurus/Translate';
import Link from '@docusaurus/Link';
import {
  useVersions,
  useActiveDocContext,
  useDocsVersionCandidates,
  useDocsPreferredVersion,
} from '@docusaurus/plugin-content-docs/client';
import NavbarColorModeToggle from '@theme/Navbar/ColorModeToggle';
import IconClose from '@theme/Icon/Close';
import IconLanguage from '@theme/Icon/Language';
import NavbarLogo from '@theme/Navbar/Logo';

type Panel = null | 'lang' | 'version';

function CloseButton() {
  const mobileSidebar = useNavbarMobileSidebar();
  return (
    <button
      type="button"
      aria-label={translate({
        id: 'theme.docs.sidebar.closeSidebarButtonAriaLabel',
        message: 'Close navigation bar',
        description: 'The ARIA label for close button of mobile sidebar',
      })}
      className="clean-btn navbar-sidebar__close"
      onClick={() => mobileSidebar.toggle()}>
      <IconClose color="var(--ifm-color-emphasis-600)" />
    </button>
  );
}

/**
 * Language in the phone drawer's header: one button, visible at every drawer
 * level, opens the language list (same page and same section in each language,
 * as the navbar's language menu does).
 */
function LanguageSwitch({open, setPanel}: {open: boolean; setPanel: (p: Panel) => void}): ReactNode {
  const {
    siteConfig,
    i18n: {currentLocale, locales, localeConfigs},
  } = useDocusaurusContext();
  const alternate = useAlternatePageUtils();
  const search = useHistorySelector((h) => h.location.search);
  const hash = useHistorySelector((h) => h.location.hash);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const label = (l: string) => localeConfigs[l]?.label ?? l;

  const href = (locale: string) => {
    const same = localeConfigs[locale]?.url === siteConfig.url;
    const base = alternate.createUrl({locale, fullyQualified: !same});
    return `${base}${mergeSearchStrings([search], 'append')}${hash}`;
  };

  useEffect(() => {
    if (open) panelRef.current?.querySelector<HTMLElement>('[aria-current="true"]')?.focus();
  }, [open]);

  const closePanel = () => {
    setPanel(null);
    buttonRef.current?.focus();
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className="navbar-sidebar__lang"
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={translate({id: 'menu.language', message: 'Language: {language}. Change language'}, {language: label(currentLocale)})}
        onClick={() => (open ? closePanel() : setPanel('lang'))}>
        <IconLanguage />
      </button>
      {open && (
        <div
          className="it-mlang"
          ref={panelRef}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              e.nativeEvent.stopPropagation(); // the drawer stays open; only the list closes
              closePanel();
            }
          }}>
          <ul>
            {locales.map((locale) => (
              <li key={locale}>
                <a
                  className={`it-mlang__link${locale === currentLocale ? ' is-active' : ''}`}
                  href={href(locale)}
                  lang={localeConfigs[locale]?.htmlLang}
                  hrefLang={localeConfigs[locale]?.htmlLang}
                  aria-current={locale === currentLocale ? 'true' : undefined}>
                  {label(locale)}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

/**
 * Version in the phone drawer, directly under the header bar: one row that
 * names the version being read, visible at every drawer level, opens a list of
 * all versions. A choice goes to the same page in that version when it exists,
 * else to that version's start page (the rule of the navbar's version menu).
 */
function VersionSwitch({open, langOpen, setPanel}: {open: boolean; langOpen: boolean; setPanel: (p: Panel) => void}): ReactNode {
  const mobileSidebar = useNavbarMobileSidebar();
  const versions = useVersions(undefined);
  const active = useActiveDocContext(undefined);
  const shown = useDocsVersionCandidates(undefined)[0] ?? versions[0];
  const {savePreferredVersionName} = useDocsPreferredVersion(undefined);
  const search = useHistorySelector((h) => h.location.search);
  const hash = useHistorySelector((h) => h.location.hash);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) panelRef.current?.querySelector<HTMLElement>('[aria-current="true"]')?.focus();
  }, [open]);

  if (versions.length < 2) return null;

  const target = (v: (typeof versions)[number]) => {
    const doc = active.alternateDocVersions[v.name] ?? v.docs.find((d) => d.id === v.mainDocId)!;
    return `${doc.path}${search}${hash}`;
  };
  const closePanel = () => {
    setPanel(null);
    buttonRef.current?.focus();
  };

  return (
    <>
      <div className="navbar-sidebar__version" inert={langOpen}>
        <button
          ref={buttonRef}
          type="button"
          className="navbar-sidebar__ver"
          aria-haspopup="true"
          aria-expanded={open}
          onClick={() => (open ? closePanel() : setPanel('version'))}>
          <span>
            {translate(
              {id: 'theme.docs.versionBadge.label', message: 'Version: {versionLabel}'},
              {versionLabel: shown.label},
            )}
          </span>
          <svg aria-hidden="true" focusable="false" width="16" height="16" viewBox="0 0 24 24" className="navbar-sidebar__ver-caret">
            <path fill="currentColor" d="M7 10l5 5 5-5z" />
          </svg>
        </button>
      </div>
      {open && (
        <div
          className="it-mver"
          ref={panelRef}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault();
              e.nativeEvent.stopPropagation(); // the drawer stays open; only the list closes
              closePanel();
            }
          }}>
          <ul>
            {versions.map((v) => (
              <li key={v.name}>
                <Link
                  className={`it-mlang__link${v === shown ? ' is-active' : ''}`}
                  to={target(v)}
                  aria-current={v === shown ? 'true' : undefined}
                  onClick={() => {
                    savePreferredVersionName(v.name);
                    setPanel(null);
                    mobileSidebar.toggle();
                  }}>
                  {v.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

export default function NavbarMobileSidebarHeader(): ReactNode {
  const [panel, setPanel] = useState<Panel>(null);

  // While a list is open it covers the menu below the header: keep keyboard
  // focus and assistive technology out of the covered menu.
  useEffect(() => {
    const items = document.querySelector('.navbar-sidebar__items');
    items?.toggleAttribute('inert', panel !== null);
    return () => items?.removeAttribute('inert');
  }, [panel]);

  return (
    <>
      <div className="navbar-sidebar__brand">
        <NavbarLogo />
        <NavbarColorModeToggle className="margin-right--md" />
        <LanguageSwitch open={panel === 'lang'} setPanel={setPanel} />
        <CloseButton />
      </div>
      <VersionSwitch open={panel === 'version'} langOpen={panel === 'lang'} setPanel={setPanel} />
    </>
  );
}
