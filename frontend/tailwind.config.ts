import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17201b",
        paper: "#f7f5ef",
        cream: "#fbfaf6",
        moss: "#315f4c",
        sage: "#eaf2ed",
        clay: "#c96f55",
        amber: "#a46b1f",
        line: "#ddd8cc",
        muted: "#766f64"
      },
      boxShadow: {
        soft: "0 18px 45px rgba(23, 32, 27, 0.10)",
        card: "0 10px 28px rgba(23, 32, 27, 0.07)"
      }
    }
  },
  plugins: []
};

export default config;
