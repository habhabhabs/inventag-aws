// Docusaurus configuration for the InvenTag site.
// See https://docusaurus.io/docs/api/docusaurus-config
// This runs in Node.js: no browser APIs or JSX here.

import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import type {Config, Plugin} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import {inventagLight, inventagDark} from './src/theme-config/prism';

// version.json at the repo root is bumped by the release workflow.
const versionData = JSON.parse(readFileSync(resolve('../version.json'), 'utf8')) as {version: string};
const currentVersion = `v${versionData.version}`;

// Archived versions (versions.json) are snapshots: kept online for people on
// older releases, but marked noindex so search engines send readers to the
// current docs instead of near-duplicate old pages.
const archivedVersions = JSON.parse(readFileSync(resolve('./versions.json'), 'utf8')) as string[];

const SITE_URL = 'https://habhabhabs.github.io';
const BASE_URL = '/inventag-aws/';
const DESCRIPTION =
  'InvenTag is an open-source Python CLI that lists the resources in your AWS accounts, ' +
  'shows how they are tagged and writes Excel or Word reports.';
const SOCIAL_ALT =
  'InvenTag: list what runs in your AWS accounts, check the tags, hand over an Excel or Word report.';

// Fail the build on broken links in the homepage and the current docs.
// Archived versions only warn (they are snapshots and are not edited).
// Docusaurus' own onBrokenLinks is site-wide, so the strict check lives here.
function brokenLinksGate(): Plugin {
  return {
    name: 'inventag-broken-links-gate',
    async postBuild({outDir}) {
      const {checkLinks, printReport} = await import('./scripts/check-links.mjs');
      const result = checkLinks(outDir);
      printReport(result, outDir);
      if (result.errors.length) {
        throw new Error(`${result.errors.length} broken link(s) in the homepage or current docs (see above).`);
      }
    },
  };
}

const config: Config = {
  title: 'InvenTag',
  tagline: 'See what runs in your AWS accounts, check the tags, hand over the report.',
  favicon: 'img/favicon.ico',

  url: SITE_URL,
  baseUrl: BASE_URL,
  organizationName: 'habhabhabs',
  projectName: 'inventag-aws',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  future: {
    v4: true,
  },

  // Site-wide setting: archived versions still contain old broken links.
  // The current docs are checked strictly by brokenLinksGate() above.
  onBrokenLinks: 'warn',
  onBrokenAnchors: 'warn',
  markdown: {
    format: 'detect', // .md is CommonMark (allows <!-- comments -->), .mdx is MDX
    hooks: {
      onBrokenMarkdownLinks: ({sourceFilePath, url}) => {
        // ../docs/ is the current version; versioned_docs/ are archives.
        if (sourceFilePath.startsWith('../docs/')) {
          throw new Error(`Broken Markdown link in current docs: ${sourceFilePath} -> ${url}`);
        }
        console.warn(`[archived docs] broken Markdown link: ${sourceFilePath} -> ${url}`);
      },
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  // A fixed storage namespace keeps the theme key ('theme-inventag') stable for the headTags script below.
  storage: {type: 'localStorage', namespace: 'inventag'},

  headTags: [
    {
      tagName: 'script',
      attributes: {},
      innerHTML:
        "(function(){try{if(!localStorage.getItem('theme-inventag')){var d=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';localStorage.setItem('theme-inventag',d);document.documentElement.setAttribute('data-theme',d);document.documentElement.setAttribute('data-theme-choice',d)}}catch(e){}})()",
    },
    // favicon.ico comes from `favicon` above; these add the scalable and touch icons
    {tagName: 'link', attributes: {rel: 'icon', type: 'image/svg+xml', href: `${BASE_URL}img/favicon.svg`}},
    {tagName: 'link', attributes: {rel: 'apple-touch-icon', sizes: '180x180', href: `${BASE_URL}img/apple-touch-icon.png`}},
    {tagName: 'link', attributes: {rel: 'manifest', href: `${BASE_URL}site.webmanifest`}},
    {tagName: 'meta', attributes: {name: 'theme-color', media: '(prefers-color-scheme: light)', content: '#F9F8F6'}},
    {tagName: 'meta', attributes: {name: 'theme-color', media: '(prefers-color-scheme: dark)', content: '#111110'}},
    // Without JavaScript, long code blocks cannot be expanded, so show them in full
    {tagName: 'noscript', attributes: {}, innerHTML: '<style>.code-collapsed{max-height:none!important}.code-collapsed::after{display:none}</style>'},
    // Self-hosted fonts (website/static/fonts). Preload the two faces every page uses.
    {
      tagName: 'link',
      attributes: {
        rel: 'preload',
        href: `${BASE_URL}fonts/instrument-sans-latin-wght-normal.woff2`,
        as: 'font',
        type: 'font/woff2',
        crossorigin: 'anonymous',
      },
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'preload',
        href: `${BASE_URL}fonts/jetbrains-mono-latin-wght-normal.woff2`,
        as: 'font',
        type: 'font/woff2',
        crossorigin: 'anonymous',
      },
    },
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          path: '../docs', // single source of truth: the repo-level docs/ directory
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
          sidebarCollapsible: true,
          sidebarCollapsed: false,
          editUrl: 'https://github.com/habhabhabs/inventag-aws/edit/main/docs/',
          editCurrentVersion: true,
          editLocalizedFiles: false,
          showLastUpdateTime: true,
          showLastUpdateAuthor: false,
          breadcrumbs: true,
          include: ['**/*.md', '**/*.mdx'],
          exclude: [
            '**/_*.{js,jsx,ts,tsx,md,mdx}',
            '**/_*/**',
            '**/*.test.{js,jsx,ts,tsx}',
            '**/__tests__/**',
            '**/template-system-summary.md',
            '**/complete-readme-backup.md',
            // Internal status notes and dated reports: kept in the repo, not published
            'DOCUMENTATION_MIGRATION.md',
            'DOCUMENTATION_STATUS_CURRENT.md',
            'ENHANCED_DISCOVERY_FINAL.md',
            'user-guides/production-safety-revision.md',
            'testing/**',
            'assets/readme.md',
          ],
          // Versioning: current docs at /docs, archived versions from versions.json
          includeCurrentVersion: true,
          lastVersion: 'current',
          disableVersioning: false,
          versions: {
            current: {
              label: `${currentVersion} (Current)`,
              badge: true,
              path: '/',
            },
            ...Object.fromEntries(archivedVersions.map((v) => [v, {noIndex: true}])),
          },
        },
        blog: false,
        theme: {
          customCss: ['./src/css/custom.css', './src/css/docs-ui.css'],
        },
        sitemap: {
          lastmod: 'date',
          changefreq: null,
          priority: null,
          ignorePatterns: [`${BASE_URL}search`, `${BASE_URL}search/**`],
          filename: 'sitemap.xml',
        },
        // Google Analytics 4 is loaded only after consent: see
        // src/clientModules/analyticsConsent.ts and src/theme/Root.tsx
      } satisfies Preset.Options,
    ],
  ],

  customFields: {
    gaMeasurementId: 'G-CVK8311NYE',
  },
  clientModules: ['./src/clientModules/analyticsConsent.ts', './src/clientModules/a11yPatches.js'],

  plugins: [
    [
      '@easyops-cn/docusaurus-search-local',
      {
        indexDocs: true,
        indexBlog: false,
        indexPages: false,
        language: 'en',
        searchBarShortcut: true,
        searchBarShortcutHint: true,
        highlightSearchTermsOnTargetPage: true,
        searchResultLimits: 12,
        searchResultContextMaxLength: 80,
        removeDefaultStopWordFilter: true,
        docsRouteBasePath: '/docs',
        explicitSearchResultPath: true,
      },
    ],
    brokenLinksGate,
  ],

  themeConfig: {
    metadata: [
      {name: 'description', content: DESCRIPTION},
      {name: 'keywords', content: 'aws, inventory, tagging, tag policy, bill of materials, bom, cli, python, open source'},
      {property: 'og:type', content: 'website'},
      {property: 'og:site_name', content: 'InvenTag'},
      {property: 'og:locale', content: 'en_GB'},
      {property: 'og:image:type', content: 'image/png'},
      {property: 'og:image:width', content: '1200'},
      {property: 'og:image:height', content: '630'},
      {property: 'og:image:alt', content: SOCIAL_ALT},
      {name: 'twitter:image:alt', content: SOCIAL_ALT},
    ],
    // Open Graph / Twitter card (PNG, 1200x630). Regenerate: npm run brand
    image: 'img/social-card.png',
    colorMode: {
      defaultMode: 'light',
      disableSwitch: false,
      // Two states only (light, dark). The first visit follows the system setting
      // once (see the headTags script); after that the button decides.
      respectPrefersColorScheme: false,
    },
    navbar: {
      // The logo is the lockup (mark + outlined "InvenTag" wordmark), so there is no live title text.
      // Light and dark files come from website/brand (npm run brand).
      hideOnScroll: false,
      logo: {
        alt: 'InvenTag',
        src: 'img/logo-wordmark.svg',
        srcDark: 'img/logo-wordmark-dark.svg',
        width: 138,
        height: 40,
      },
      items: [
        {type: 'doc', docId: 'index', label: 'Docs', position: 'left', className: 'nav-ico nav-ico-docs'},
        {to: '/docs/getting-started/quick-start', label: 'Quick start', position: 'left', className: 'nav-ico nav-ico-start'},
        {to: '/docs/reference/cli', label: 'CLI reference', position: 'left', className: 'nav-ico nav-ico-cli'},
        {type: 'docsVersionDropdown', position: 'right', dropdownActiveClassDisabled: true},
        {type: 'search', position: 'right'},
        {
          href: 'https://github.com/habhabhabs/inventag-aws',
          position: 'right',
          className: 'header-github-link',
          'aria-label': 'InvenTag on GitHub',
        },
      ],
    },
    footer: {
      style: 'light',
      links: [
        {
          title: 'Start here',
          items: [
            {label: 'Overview', to: '/docs'},
            {label: 'Introduction', to: '/docs/getting-started/introduction'},
            {label: 'Quick start', to: '/docs/getting-started/quick-start'},
            {label: 'What works today', to: '/docs/getting-started/status'},
          ],
        },
        {
          title: 'Guides',
          items: [
            {label: 'CLI reference', to: '/docs/reference/cli'},
            {label: 'Account setup', to: '/docs/examples/accounts-setup'},
            {label: 'Configuration examples', to: '/docs/templates/'},
            {label: 'Permissions and safety', to: '/docs/user-guides/production-safety'},
          ],
        },
        {
          title: 'Project',
          items: [
            {label: 'Install from PyPI', href: 'https://pypi.org/project/inventag-aws/'},
            {label: 'Source on GitHub', href: 'https://github.com/habhabhabs/inventag-aws'},
            {label: 'Report an issue', href: 'https://github.com/habhabhabs/inventag-aws/issues'},
            {label: 'Discussions', href: 'https://github.com/habhabhabs/inventag-aws/discussions'},
            {label: 'Contributing', to: '/docs/development/CONTRIBUTING'},
            {label: 'MIT licence', href: 'https://github.com/habhabhabs/inventag-aws/blob/main/LICENSE'},
            {
              // a button, not a #fragment link: it reopens the cookie banner (src/theme/Root.tsx)
              html: '<button type="button" class="footer__link-item footer__button" data-cookie-preferences>Cookie preferences</button>',
            },
            {label: 'Privacy and cookies', to: '/privacy'},
          ],
        },
      ],
      copyright:
        `© ${new Date().getFullYear()} InvenTag contributors. Released under the MIT licence.<br/>` +
        'AWS is a trademark of Amazon.com, Inc. or its affiliates. InvenTag is an independent project ' +
        'and is not affiliated with, endorsed by, or sponsored by Amazon Web Services.',
    },
    prism: {
      theme: inventagLight,
      darkTheme: inventagDark,
      additionalLanguages: ['bash', 'json', 'yaml', 'python', 'powershell', 'ini', 'toml', 'diff', 'groovy', 'docker'],
      magicComments: [
        {
          className: 'theme-code-block-highlighted-line',
          line: 'highlight-next-line',
          block: {start: 'highlight-start', end: 'highlight-end'},
        },
      ],
    },
    tableOfContents: {
      minHeadingLevel: 2,
      maxHeadingLevel: 3,
    },
    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: true,
      },
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
