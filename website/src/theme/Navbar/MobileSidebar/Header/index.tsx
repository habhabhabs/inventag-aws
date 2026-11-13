import React, {useEffect, useRef, useState, type ReactNode} from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useAlternatePageUtils, useNavbarMobileSidebar} from '@docusaurus/theme-common/internal';
import {mergeSearchStrings, useHistorySelector} from '@docusaurus/theme-common';
import {translate} from '@docusaurus/Translate';
import NavbarColorModeToggle from '@theme/Navbar/ColorModeToggle';
import IconClose from '@theme/Icon/Close';
import IconLanguage from '@theme/Icon/Language';
import NavbarLogo from '@theme/Navbar/Logo';

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
function LanguageSwitch(): ReactNode {
  const {
    siteConfig,
    i18n: {currentLocale, locales, localeConfigs},
  } = useDocusaurusContext();
  const alternate = useAlternatePageUtils();
  const search = useHistorySelector((h) => h.location.search);
  const hash = useHistorySelector((h) => h.location.hash);
  const [open, setOpen] = useState(false);
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
    setOpen(false);
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
        onClick={() => (open ? closePanel() : setOpen(true))}>
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

export default function NavbarMobileSidebarHeader(): ReactNode {
  return (
    <div className="navbar-sidebar__brand">
      <NavbarLogo />
      <NavbarColorModeToggle className="margin-right--md" />
      <LanguageSwitch />
      <CloseButton />
    </div>
  );
}
