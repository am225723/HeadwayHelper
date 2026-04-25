import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Clinical AI Webapp",
  description: "Clinical documentation, Drive automation, and billing review"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
