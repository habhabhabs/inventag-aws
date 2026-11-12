// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

// Import current version from version.json
import { readFileSync } from 'fs';
import { resolve } from 'path';

// Read current version from version.json
const versionData = JSON.parse(readFileSync(resolve('../version.json'), 'utf8'));
const currentVersion = `v${versionData.version}`;

// Code highlighting: the stock Prism themes have token colours below 4.5:1
// (e.g. GitHub's comments at 2.7:1). Swap those colours for accessible ones.
function recolor(theme, map) {
  return {
    ...theme,
    styles: theme.styles.map((s) =>
      s.style && map[s.style.color] ? {...s, style: {...s.style, color: map[s.style.color]}} : s,
    ),
  };
}
const codeLight = recolor(prismThemes.github, {
  '#999988': '#57606a', // comments          2.7 -> 6.0:1 on #f6f8fa
  '#e3116c': '#a3125a', // strings           4.3 -> 7.1:1
  '#36acaa': '#0b7285', // properties, flags 2.6 -> 5.3:1
  '#00a4db': '#0550ae', // keywords          2.7 -> 7.1:1
  '#d73a49': '#b31d28', // functions         4.3 -> 6.3:1
});
const codeDark = recolor(prismThemes.dracula, {
  'rgb(98, 114, 164)': '#a9b4dc', // comments 3.0 -> 6.9:1 on #282a36
});

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'InvenTag',
  tagline: 'AWS resource inventory, tag compliance checks and BOM reports',
  // .ico for older browsers; the SVG and touch icons are added in headTags below
  favicon: 'img/favicon.ico',

  headTags: [
    {tagName: 'link', attributes: {rel: 'icon', type: 'image/svg+xml', href: '/inventag-aws/img/favicon.svg'}},
    {tagName: 'link', attributes: {rel: 'apple-touch-icon', sizes: '180x180', href: '/inventag-aws/img/apple-touch-icon.png'}},
  ],

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://habhabhabs.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/inventag-aws/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'habhabhabs', // Usually your GitHub org/user name.
  projectName: 'inventag-aws', // Usually your repo name.
  deploymentBranch: 'gh-pages', // Branch for GitHub Pages deployment
  trailingSlash: false, // GitHub Pages compatibility

  // 'warn' (not 'ignore') so broken links show up in the build log. Archived
  // versions (versioned_docs/) still contain some old broken links, which is
  // why this is not 'throw'. The current docs are checked strictly by
  // `npm run check:links` (website/scripts/check-links.mjs).
  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',
  onBrokenAnchors: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          path: '../docs', // Single source of truth - read from root-level docs directory
          routeBasePath: 'docs', // Serve docs under /docs path to avoid conflicts with homepage
          sidebarPath: './sidebars.js',
          // Ensure consistent sidebar across all pages
          sidebarCollapsible: true,
          sidebarCollapsed: false,
          // Edit links point to GitHub repository for dual-platform compatibility
          editUrl: 'https://github.com/habhabhabs/inventag-aws/edit/main/docs/',
          showLastUpdateTime: true,
          showLastUpdateAuthor: true,
          // Enhanced GitHub integration
          editCurrentVersion: true,
          // Breadcrumbs for better navigation
          breadcrumbs: true,
          // Include frontmatter for better GitHub compatibility
          include: ['**/*.md', '**/*.mdx'],
          exclude: [
            '**/_*.{js,jsx,ts,tsx,md,mdx}',
            '**/_*/**',
            '**/*.test.{js,jsx,ts,tsx}',
            '**/__tests__/**',
            // Temporarily exclude problematic files during migration
            '**/template-system-summary.md',
            '**/complete-readme-backup.md',
            // Internal status notes and dated reports: kept in the repo, not
            // published (unverifiable numbers, superseded content)
            'DOCUMENTATION_MIGRATION.md',
            'DOCUMENTATION_STATUS_CURRENT.md',
            'ENHANCED_DISCOVERY_FINAL.md',
            'user-guides/production-safety-revision.md',
            'testing/**',
            'assets/readme.md',
          ],
          // Documentation versioning configuration  
          includeCurrentVersion: true,
          lastVersion: 'current',
          // N-1 versioning strategy: only keep previous version in versioned docs  
          // Current version shows actual version number in sidebar and dropdown
          // Previous version (N-1) is automatically managed via versions.json
          versions: {
            current: {
              label: `${currentVersion} (Current)`,
              badge: true,
              path: '/',
            },
          },
          // Force sidebar to show version labels instead of keys
          sidebarCollapsed: false,
          // Version-specific edit URLs
          editLocalizedFiles: false,
          // Version dropdown configuration
          disableVersioning: false
        },
        blog: false, // Disable blog functionality for this documentation site
        theme: {
          customCss: './src/css/custom.css',
        },
        // Google Analytics 4 is loaded only after consent: see
        // src/clientModules/analyticsConsent.js and src/theme/Root.js
      }),
    ],
  ],

  customFields: {
    gaMeasurementId: 'G-CVK8311NYE',
  },
  clientModules: ['./src/clientModules/analyticsConsent.js'],

  // Plugins for enhanced functionality
  plugins: [
    [
      '@easyops-cn/docusaurus-search-local',
      /** @type {any} */
      ({
        // Whether to index docs pages
        indexDocs: true,
        // Whether to index blog posts  
        indexBlog: false,
        // Whether to index static pages
        indexPages: false,
        // Language of the documentation
        language: 'en',
        // Enable search bar keyboard shortcuts
        searchBarShortcut: true,
        searchBarShortcutHint: true,
        // Highlight search terms on target page
        highlightSearchTermsOnTargetPage: true,
        // Search result limits and context - optimized for technical docs
        searchResultLimits: 12,
        searchResultContextMaxLength: 80,
        // Remove default stopwords for better AWS/technical term search
        removeDefaultStopWordFilter: true,
        // Set docs route base path
        docsRouteBasePath: '/',
        // Include more context in search results
        explicitSearchResultPath: true,
      }),
    ],
  ],


  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Enhanced metadata for better SEO and social sharing
      metadata: [
        {name: 'keywords', content: 'aws, inventory, tagging, tag compliance, bill of materials, bom, cli, python, open source'},
        {name: 'description', content: 'InvenTag is an open-source Python CLI that inventories AWS resources across accounts, checks tag compliance and writes Excel/Word bill-of-materials reports.'},
        {property: 'og:image:width', content: '1200'},
        {property: 'og:image:height', content: '630'},
        {property: 'og:image:alt', content: 'InvenTag logo with the text: AWS resource inventory, tag compliance checks and Excel/Word BOM reports.'},
        {name: 'twitter:image:alt', content: 'InvenTag logo with the text: AWS resource inventory, tag compliance checks and Excel/Word BOM reports.'},
      ],
      // Open Graph / Twitter card (PNG: LinkedIn, X and Slack do not render SVG cards).
      // Regenerate with: python3 website/brand/generate_brand_assets.py
      image: 'img/social-card.png',
      navbar: {
        title: 'InvenTag',
        logo: {
          alt: 'InvenTag home',
          // white mark on the blue light-theme navbar, colour mark on the dark navbar
          src: 'img/logo-on-brand.svg',
          srcDark: 'img/logo-dark.svg',
          width: 32,
          height: 32,
        },
        items: [
          {
            to: '/docs/',
            position: 'left',
            label: 'Documentation',
          },
          {
            type: 'docsVersionDropdown',
            position: 'left',
            dropdownActiveClassDisabled: true,
          },
          {
            type: 'search',
            position: 'right',
          },
          {
            href: 'https://github.com/habhabhabs/inventag-aws',
            className: 'header-github-link',
            'aria-label': 'GitHub repository',
            position: 'right',
          },
        ],
        hideOnScroll: true,
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Documentation',
            items: [
              {
                label: 'Getting Started',
                to: '/docs/',
              },
              {
                label: 'User Guides',
                to: '/docs/user-guides/cli-user-guide',
              },
              {
                label: 'Architecture',
                to: '/docs/architecture/core-module-integration',
              },
              {
                label: 'Development',
                to: '/docs/development/CONTRIBUTING',
              },
            ],
          },
          {
            title: 'Community',
            items: [
              {
                label: 'GitHub Repository',
                href: 'https://github.com/habhabhabs/inventag-aws',
              },
              {
                label: 'Issues & Bug Reports',
                href: 'https://github.com/habhabhabs/inventag-aws/issues',
              },
              {
                label: 'Discussions',
                href: 'https://github.com/habhabhabs/inventag-aws/discussions',
              },
            ],
          },
          {
            title: 'Resources',
            items: [
              {
                label: 'Configuration Examples',
                to: '/docs/user-guides/configuration-examples',
              },
              {
                label: 'Contributing Guide',
                to: '/docs/development/CONTRIBUTING',
              },
              {
                label: 'License',
                href: 'https://github.com/habhabhabs/inventag-aws/blob/main/LICENSE',
              },
              {
                label: 'Analytics settings',
                href: '#analytics-settings',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} InvenTag contributors. MIT licence. Built with Docusaurus.<br/>AWS is a trademark of Amazon.com, Inc. or its affiliates. InvenTag is an independent project and is not affiliated with, endorsed by, or sponsored by Amazon Web Services.`,
      },
      prism: {
        theme: codeLight,
        darkTheme: codeDark,
        // Enhanced syntax highlighting for AWS and cloud technologies
        additionalLanguages: [
          'bash',
          'json',
          'yaml',
          'python',
          'javascript',
          'typescript',
          'powershell',
          'ini',
          'toml',
          'sql',
          'graphql',
          'markdown',
          'diff'
        ],
        // Custom syntax highlighting for AWS CLI and cloud commands
        magicComments: [
          {
            className: 'theme-code-block-highlighted-line',
            line: 'highlight-next-line',
            block: {start: 'highlight-start', end: 'highlight-end'},
          },
          {
            className: 'code-block-aws-command',
            line: 'aws-command',
          },
          {
            className: 'code-block-inventag-command',
            line: 'inventag-command',
          },
        ],
      },
      // Enhanced color mode configuration - default to light theme
      colorMode: {
        defaultMode: 'light',
        disableSwitch: false,
        respectPrefersColorScheme: false,  // Force light mode as default
      },
      // Table of contents configuration for better navigation
      tableOfContents: {
        minHeadingLevel: 2,
        maxHeadingLevel: 4,
      },
      // Docs configuration for better GitHub compatibility
      docs: {
        sidebar: {
          hideable: true,
          autoCollapseCategories: true,
        },
      },
    }),
};

export default config;
