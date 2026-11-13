---
title: Readme
---

# Documentation Assets

This directory contains all images, diagrams, and other static assets used in the InvenTag documentation.

## Directory Structure

- `images/` - Screenshots, diagrams, and other images
- `files/` - Downloadable files, templates, and other documents
- `examples/` - Pictures and sample files that
  `scripts/docs/generate_example_outputs.py` writes. Do not edit them by hand.

## Usage Guidelines

### Adding Images

1. Place images in the appropriate subdirectory under `images/`
2. Use descriptive filenames (e.g., `cli-output-example.png`, `architecture-diagram.svg`)
3. Optimize images for web viewing (reasonable file sizes)
4. Use relative paths in markdown: `![Alt text](/img/filename.png)`

### Supported Formats

- **Images**: PNG, JPG, JPEG, GIF, SVG, WebP
- **Documents**: PDF, JSON, YAML, TXT

### Dual Platform Compatibility

All assets in this directory are accessible from both:
- GitHub's markdown viewer (when browsing the repository)
- The Docusaurus documentation site

Use relative paths to ensure compatibility across both platforms.

## Validation

To verify that all assets are accessible from both GitHub and Docusaurus:

1. **GitHub Compatibility**: Browse the documentation on GitHub and verify that:
   - Images display correctly in markdown files
   - Download links work for files in `assets/files/`
   - Relative paths resolve correctly

2. **Docusaurus Compatibility**: Run the local development server and verify that:
   - All images render properly on the documentation site
   - File download links work correctly
   - Navigation and cross-references function as expected

3. **Path Validation**: All asset references should use relative paths from the documentation file location:
   - From `docs/` root: `assets/images/filename.png`
   - From subdirectories: `../assets/images/filename.png`

## Available Assets

### Images
- `inventag-logo-placeholder.svg` - InvenTag project logo

### Files
- `default_excel_template.json` - Default Excel template for BOM reports
- `default_word_template.yaml` - Default Word template for BOM reports
- `accounts-example.json` - Example account configuration
- `service-descriptions-example.yaml` - Example service descriptions
- `tag-mappings-example.yaml` - Example tag mappings

## Examples

The sample-output pictures are inserted by the generator script as
Reference images with markdown syntax, for example `![alt text](../assets/examples/img/<name>.png)`.
between `<!-- BEGIN EXAMPLE OUTPUT: <name> -->` markers. Write other images
and downloads as plain Markdown links relative to the page, for example
`![Alt text](../assets/images/inventag-logo-placeholder.svg)`.
