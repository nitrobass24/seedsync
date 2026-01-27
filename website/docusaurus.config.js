// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// There are various equivalent ways to declare your Docusaurus config.
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'SeedSync',
  tagline: 'Fast seedbox sync with a clean web UI',
  favicon: 'img/favicon.png',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: process.env.DOCS_SITE_URL || 'https://nitrobass24.com',
  // Set the /<baseUrl>/ pathname under which your site is served
  // Default is the Cloudflare subpath; override for GitHub Pages via env.
  baseUrl: process.env.DOCS_BASE_URL || '/seedsync/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'nitrobass24', // GitHub org/user name.
  projectName: 'seedsync-website', // Repo name.

  onBrokenLinks: 'throw',

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
          sidebarPath: './sidebars.js',
          routeBasePath: '/', // Serve docs at the site root.
          editUrl:
            'https://github.com/nitrobass24/seedsync-website/tree/main/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      // Replace with your project's social card
      image: 'img/logo.png',
      colorMode: {
        defaultMode: 'light',
        disableSwitch: true,
        respectPrefersColorScheme: false,
      },
      navbar: {
        title: 'SeedSync',
        logo: {
          alt: 'SeedSync Logo',
          src: 'img/logo.png',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'docs',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://github.com/nitrobass24/seedsync',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'light',
        links: [
          {
            title: 'Docs',
            items: [
              {label: 'Installation', to: '/installation'},
              {label: 'Usage', to: '/usage'},
              {label: 'Configuration', to: '/configuration'},
            ],
          },
          {
            title: 'Project',
            items: [
              {
                label: 'SeedSync Repo',
                href: 'https://github.com/nitrobass24/seedsync',
              },
              {
                label: 'Docs Repo',
                href: 'https://github.com/nitrobass24/seedsync-website',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} SeedSync.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
      },
    }),
};

export default config;
