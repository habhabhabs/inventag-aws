/**
 * Consent-gated Google Analytics 4.
 * Nothing is loaded until the visitor chooses "Allow" in the banner
 * (src/theme/Root.js). The choice is kept in localStorage under KEY.
 * The measurement ID comes from customFields.gaMeasurementId.
 */
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';
import siteConfig from '@generated/docusaurus.config';

const KEY = 'inventag-analytics';
const ID = siteConfig.customFields && siteConfig.customFields.gaMeasurementId;
let loaded = false;

export function getChoice() {
  try {
    return localStorage.getItem(KEY); // 'granted' | 'denied' | null
  } catch (e) {
    return 'denied'; // storage blocked: treat as no consent, and don't nag
  }
}

function sendPageView() {
  if (loaded && window.gtag) {
    window.gtag('event', 'page_view', {
      page_location: window.location.href,
      page_title: document.title,
    });
  }
}

function load() {
  if (loaded || !ID) return;
  loaded = true;
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() {
    window.dataLayer.push(arguments); // eslint-disable-line prefer-rest-params
  };
  window.gtag('js', new Date());
  window.gtag('config', ID, {anonymize_ip: true, send_page_view: false});
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${ID}`;
  document.head.appendChild(s);
}

export function setChoice(value) {
  try {
    localStorage.setItem(KEY, value);
  } catch (e) {
    /* storage blocked: the choice lasts for this page only */
  }
  if (value === 'granted') {
    load();
    sendPageView();
  }
}

if (ExecutionEnvironment.canUseDOM && getChoice() === 'granted') {
  load();
}

export function onRouteDidUpdate({location, previousLocation}) {
  if (!previousLocation || location.pathname !== previousLocation.pathname) {
    sendPageView();
  }
}
