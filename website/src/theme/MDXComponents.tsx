import MDXComponents from '@theme-original/MDXComponents';
import Table from './MDXComponents/Table';

// Default MDX components plus a scroll wrapper for tables.
export default {
  ...MDXComponents,
  table: Table,
};
