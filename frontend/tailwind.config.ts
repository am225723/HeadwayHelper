import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17201b",
        paper: "#f7f5ef",
        moss: "#3f6f5a",
        clinic: "#d86041",
        line: "#d8d4c8"
      },
      boxShadow: {
        soft: "0 18px 45px rgba(23, 32, 27, 0.12)"
      }
    }
  },
  plugins: []
};

export default config;
