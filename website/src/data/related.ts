/**
 * Curated "where next" tiles shown at the bottom of a docs page. The key is a
 * doc id (its path under docs/ without the extension); each value lists other
 * doc ids, in the order to show them. Title and description come from the
 * target page, so they never drift. Keep each list to 2 to 4 pages.
 */
export const RELATED: Record<string, {ids: string[]; icons?: string[]}> = {
  index: {ids: ['getting-started/quick-start', 'getting-started/introduction', 'examples/index']},
  'getting-started/introduction': {
    ids: ['getting-started/installation', 'getting-started/status', 'getting-started/quick-start'],
    icons: ['download', 'list', 'rocket'],
  },
  'getting-started/installation': {
    ids: ['getting-started/quick-start', 'guides/read-only-access', 'guides/troubleshooting'],
    icons: ['rocket', 'shield', 'help'],
  },
  'getting-started/quick-start': {
    ids: ['guides/run-a-scan', 'templates/index', 'examples/index', 'guides/troubleshooting'],
    icons: ['terminal', 'layers', 'file', 'help'],
  },
  'getting-started/status': {
    ids: ['reference/cli', 'guides/troubleshooting', 'getting-started/quick-start'],
  },
  'guides/read-only-access': {
    ids: ['reference/iam-permissions', 'guides/scan-multiple-accounts', 'guides/run-in-ci'],
    icons: ['key', 'building', 'play'],
  },
  'guides/run-a-scan': {
    ids: ['guides/scan-multiple-accounts', 'guides/check-tag-compliance', 'reference/outputs', 'reference/cli'],
    icons: ['building', 'tag', 'file', 'terminal'],
  },
  'guides/scan-multiple-accounts': {
    ids: ['examples/accounts-setup', 'guides/read-only-access', 'reference/configuration-files'],
    icons: ['building', 'shield', 'sliders'],
  },
  'guides/check-tag-compliance': {
    ids: ['examples/tag-policy-in-ci', 'templates/catalogue', 'examples/finops-cost-allocation'],
    icons: ['play', 'layers', 'tag'],
  },
  'guides/track-changes': {
    ids: ['guides/run-in-ci', 'reference/outputs', 'examples/scheduled-s3-upload'],
    icons: ['play', 'file', 'clock'],
  },
  'guides/run-in-ci': {
    ids: ['guides/read-only-access', 'examples/tag-policy-in-ci', 'guides/track-changes'],
    icons: ['key', 'tag', 'clock'],
  },
  'guides/network-and-security-analysis': {
    ids: ['reference/outputs', 'examples/security-review', 'reference/iam-permissions'],
    icons: ['file', 'shield', 'key'],
  },
  'guides/troubleshooting': {
    ids: ['reference/iam-permissions', 'guides/read-only-access', 'reference/cli'],
    icons: ['key', 'shield', 'terminal'],
  },
  'templates/index': {
    ids: ['templates/catalogue', 'templates/adapt-a-template', 'templates/reference'],
    icons: ['layers', 'code', 'book'],
  },
  'templates/catalogue': {
    ids: ['templates/adapt-a-template', 'examples/branded-executive-report', 'templates/reference'],
    icons: ['code', 'file', 'book'],
  },
  'templates/adapt-a-template': {
    ids: ['templates/layout-flags', 'templates/reference', 'examples/custom-columns'],
    icons: ['sliders', 'book', 'file'],
  },
  'templates/layout-flags': {
    ids: ['templates/reference', 'examples/custom-columns', 'examples/branded-executive-report'],
  },
  'templates/reference': {
    ids: ['templates/adapt-a-template', 'reference/configuration-files', 'templates/catalogue'],
  },
  'examples/index': {
    ids: ['getting-started/quick-start', 'templates/catalogue', 'guides/run-in-ci'],
    icons: ['rocket', 'layers', 'play'],
  },
  'examples/quick-audit': {
    ids: ['examples/security-review', 'examples/custom-columns', 'guides/run-a-scan'],
  },
  'examples/accounts-setup': {
    ids: ['guides/scan-multiple-accounts', 'guides/read-only-access', 'examples/scheduled-s3-upload'],
  },
  'examples/tag-policy-in-ci': {
    ids: ['guides/check-tag-compliance', 'guides/run-in-ci', 'examples/finops-cost-allocation'],
  },
  'examples/finops-cost-allocation': {
    ids: ['guides/check-tag-compliance', 'examples/security-review', 'examples/custom-columns'],
  },
  'examples/security-review': {
    ids: ['guides/network-and-security-analysis', 'examples/finops-cost-allocation', 'guides/check-tag-compliance'],
  },
  'examples/branded-executive-report': {
    ids: ['templates/layout-flags', 'templates/catalogue', 'examples/custom-columns'],
  },
  'examples/custom-columns': {
    ids: ['templates/layout-flags', 'examples/branded-executive-report', 'templates/reference'],
  },
  'examples/scheduled-s3-upload': {
    ids: ['guides/run-in-ci', 'guides/track-changes', 'reference/iam-permissions'],
  },
  'reference/cli': {
    ids: ['reference/outputs', 'reference/configuration-files', 'guides/run-a-scan'],
  },
  'reference/outputs': {
    ids: ['reference/cli', 'guides/track-changes', 'templates/catalogue'],
  },
  'reference/configuration-files': {
    ids: ['reference/cli', 'guides/scan-multiple-accounts', 'templates/reference'],
  },
  'reference/iam-permissions': {
    ids: ['guides/read-only-access', 'guides/troubleshooting', 'security/index'],
    icons: ['shield', 'help', 'key'],
  },
  'reference/glossary': {
    ids: ['getting-started/introduction', 'reference/cli', 'getting-started/quick-start'],
  },
  'security/index': {
    ids: ['guides/read-only-access', 'reference/iam-permissions', 'getting-started/status'],
  },
  'development/architecture': {
    ids: ['development/CONTRIBUTING', 'reference/cli', 'getting-started/status'],
  },
  'development/CONTRIBUTING': {
    ids: ['development/architecture', 'getting-started/status', 'reference/cli'],
  },
};
