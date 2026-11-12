/**
 * Consent-gated Google Analytics 4 ("basic" Consent Mode v2).
 *
 * Nothing from Google is requested until the visitor chooses "Allow" in the
 * banner (src/theme/Root.tsx). The choice is kept in localStorage under KEY,
 * because Consent Mode does not store choices itself.
 *
 * When the visitor allows analytics, the order follows Google's tag guidance
 * (developers.google.com/tag-platform/devguides/consent):
 *   1. define dataLayer/gtag and set consent defaults (everything denied)
 *   2. update analytics_storage to granted (the ad signals stay denied: the
 *      site shows no ads and never asks for ad consent)
 *   3. load gtag.js, then `js` and `config`
 * If the visitor later withdraws, consent is updated to denied, page views
 * stop and the _ga cookies are removed.
 */
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';
import siteConfig from '@generated/docusaurus.config';
import type {ClientModule} from '@docusaurus/types';

type Choice = 'granted' | 'denied';

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

const KEY = 'inventag-analytics';
const ID = (siteConfig.customFields?.gaMeasurementId as string | undefined) ?? '';
let loaded = false;
let granted = false;

export function getChoice(): Choice | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'granted' || v === 'denied' ? v : null;
  } catch {
    return 'denied'; // storage blocked: treat as no consent, and don't nag
  }
}

// gtag.js reads the `arguments` object, not an array, so keep the classic form.
function gtag(..._args: unknown[]): void {
  // eslint-disable-next-line prefer-rest-params
  (window.dataLayer = window.dataLayer || []).push(arguments);
}

function load(): void {
  if (loaded || !ID) return;
  loaded = true;
  window.gtag = gtag;
  gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: 'denied',
  });
  gtag('consent', 'update', {analytics_storage: 'granted'});
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(ID)}`;
  document.head.appendChild(s);
  gtag('js', new Date());
  gtag('config', ID, {send_page_view: false});
}

function sendPageView(): void {
  if (loaded && granted) {
    gtag('event', 'page_view', {
      page_location: window.location.href,
      page_title: document.title,
    });
  }
}

function clearAnalyticsCookies(): void {
  const host = window.location.hostname;
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim();
    if (name === '_ga' || name.startsWith('_ga_')) {
      for (const domain of ['', `; domain=${host}`, `; domain=.${host}`]) {
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domain}`;
      }
    }
  }
}

export function setChoice(value: Choice): void {
  try {
    localStorage.setItem(KEY, value);
  } catch {
    /* storage blocked: the choice lasts for this page only */
  }
  if (value === 'granted') {
    granted = true;
    if (loaded) gtag('consent', 'update', {analytics_storage: 'granted'});
    load();
    sendPageView();
  } else {
    granted = false;
    if (loaded) gtag('consent', 'update', {analytics_storage: 'denied'});
    clearAnalyticsCookies();
  }
}

if (ExecutionEnvironment.canUseDOM && getChoice() === 'granted') {
  granted = true;
  load();
}

export const onRouteDidUpdate: ClientModule['onRouteDidUpdate'] = ({location, previousLocation}) => {
  if (!previousLocation || location.pathname !== previousLocation.pathname) {
    sendPageView();
  }
};
