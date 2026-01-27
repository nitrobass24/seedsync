# SeedSync Docs Website

Static documentation site for the SeedSync project, built with Docusaurus and deployed to Cloudflare Workers.

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

This project deploys to Cloudflare Workers using Wrangler and `wrangler.toml`.

```bash
npm run deploy
```

For CI/CD, see `.github/workflows/deploy.yml`.
