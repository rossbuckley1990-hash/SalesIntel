import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ds: {
          "canvas": "var(--ds-canvas)",
          "surface": "var(--ds-surface)",
          "subtle": "var(--ds-subtle)",
          "hover": "var(--ds-hover)",
          "border": "var(--ds-border)",
          "border-strong": "var(--ds-border-strong)",
          "ink": "var(--ds-ink)",
          "ink-2": "var(--ds-ink-2)",
          "muted": "var(--ds-muted)",
          "faint": "var(--ds-faint)",
          "brand": "var(--ds-brand)",
          "brand-hover": "var(--ds-brand-hover)",
          "brand-soft": "var(--ds-brand-soft)",
          "brand-line": "var(--ds-brand-line)",
          "green": "var(--ds-green)",
          "green-soft": "var(--ds-green-soft)",
          "green-line": "var(--ds-green-line)",
          "amber": "var(--ds-amber)",
          "amber-soft": "var(--ds-amber-soft)",
          "amber-line": "var(--ds-amber-line)",
          "red": "var(--ds-red)",
          "red-soft": "var(--ds-red-soft)",
          "red-line": "var(--ds-red-line)",
          "blue": "var(--ds-blue)",
          "blue-soft": "var(--ds-blue-soft)",
          "blue-line": "var(--ds-blue-line)",
          "violet": "var(--ds-violet)",
          "violet-soft": "var(--ds-violet-soft)",
          "violet-line": "var(--ds-violet-line)",
        },
        ink: "#080d10",
        mist: "#10171b",
        line: "rgba(255, 255, 255, 0.1)",
        mitie: {
          green: "#087f5b",
          teal: "#0f766e",
          lime: "#7cb342",
        },
      },
      boxShadow: {
        "ds-xs": "var(--ds-shadow-xs)",
        "ds-sm": "var(--ds-shadow-sm)",
        "ds-lg": "var(--ds-shadow-lg)",
        panel: "0 20px 70px rgba(0, 0, 0, 0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
