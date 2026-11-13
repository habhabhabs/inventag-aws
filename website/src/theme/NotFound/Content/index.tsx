import React, {useEffect, useState, type ReactNode} from 'react';
import clsx from 'clsx';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useLocation} from '@docusaurus/router';
import Heading from '@theme/Heading';
import type {Props} from '@theme/NotFound/Content';

/**
 * GitHub Pages serves the one root 404.html for every address, in every language,
 * so the page cannot rely on the build's locale. It reads the language from the
 * address (/es/, /fr/, /zh-Hans/, /zh-Hant/) after hydration and shows its own
 * small dictionary. Until then it renders in the build's language.
 */
type Strings = {title: string; body: string; search: string; home: string; quick: string; report: string};
const STRINGS: Record<string, Strings> = {
  en: {
    title: 'Page not found',
    body: 'There is no page at this address. It may have moved, or the link may be wrong.',
    search: 'Search the docs',
    home: 'Docs home',
    quick: 'Quick start',
    report: 'Report a broken link',
  },
  es: {
    title: 'Página no encontrada',
    body: 'No hay ninguna página en esta dirección. Puede que se haya movido o que el enlace sea incorrecto.',
    search: 'Buscar en la documentación',
    home: 'Inicio de la documentación',
    quick: 'Inicio rápido',
    report: 'Informar de un enlace roto',
  },
  fr: {
    title: 'Page introuvable',
    body: 'Il n’y a pas de page à cette adresse. Elle a peut-être été déplacée, ou le lien est erroné.',
    search: 'Rechercher dans la documentation',
    home: 'Accueil de la documentation',
    quick: 'Démarrage rapide',
    report: 'Signaler un lien cassé',
  },
  'zh-Hans': {
    title: '找不到页面',
    body: '这个地址上没有页面。它可能已移动，或者链接有误。',
    search: '搜索文档',
    home: '文档首页',
    quick: '快速开始',
    report: '报告失效链接',
  },
  'zh-Hant': {
    title: '找不到頁面',
    body: '這個網址上沒有頁面。它可能已移動，或是連結有誤。',
    search: '搜尋文件',
    home: '文件首頁',
    quick: '快速開始',
    report: '回報失效連結',
  },
};
const LOCALES = ['zh-Hans', 'zh-Hant', 'es', 'fr'];

export default function NotFoundContent({className}: Props): ReactNode {
  const {
    siteConfig: {baseUrl},
    i18n: {currentLocale},
  } = useDocusaurusContext();
  const {pathname} = useLocation();
  const [locale, setLocale] = useState(currentLocale in STRINGS ? currentLocale : 'en');
  useEffect(() => {
    const rest = pathname.startsWith(baseUrl) ? pathname.slice(baseUrl.length) : pathname.replace(/^\//, '');
    const first = rest.split('/')[0];
    setLocale(LOCALES.includes(first) ? first : 'en');
  }, [pathname, baseUrl]);
  const t = STRINGS[locale] ?? STRINGS.en;
  const prefix = locale === 'en' ? baseUrl : `${baseUrl}${locale}/`;

  // The last address segment, as words, is the first search to try
  const guess = decodeURIComponent(pathname.replace(/\/+$/, '').split('/').pop() ?? '')
    .replace(/\.html?$/, '')
    .replace(/[-_]+/g, ' ')
    .trim();
  const issue =
    'https://github.com/habhabhabs/inventag-aws/issues/new?title=' +
    encodeURIComponent('Broken link') +
    '&body=' +
    encodeURIComponent(`Address: ${typeof window !== 'undefined' ? window.location.href : pathname}`);

  return (
    <main className={clsx('container margin-vert--xl', className)} lang={locale === 'en' ? 'en' : locale}>
      <div className="row">
        <div className="col col--6 col--offset-3 it-nf">
          <Heading as="h1" className="hero__title">
            {t.title}
          </Heading>
          <p>{t.body}</p>
          <p className="it-nf__actions">
            <button
              type="button"
              className="button button--primary"
              onClick={() => window.dispatchEvent(new CustomEvent('inventag:search', {detail: {query: guess}}))}>
              {t.search}
            </button>
            <a className="button button--secondary" href={`${prefix}docs`}>
              {t.home}
            </a>
          </p>
          <p className="it-nf__links">
            <a href={`${prefix}docs/getting-started/quick-start`}>{t.quick}</a>
            {' · '}
            <a href={issue} target="_blank" rel="noopener noreferrer">
              {t.report}
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}
