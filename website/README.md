# SeedSync Docs Website

Static documentation site for the SeedSync project, built with Docusaurus and deployed to GitHub Pages.

## Requirements

- Node.js 22+
- npm

## Install

```bash
npm install
```

## Local development

```bash
npm start
```

## Build

```bash
npm run build
```

## Deploy

Deployment is automated: the `docs-pages.yml` GitHub Actions workflow builds
the site and publishes it to GitHub Pages when changes under `website/` are
pushed to `master`.
