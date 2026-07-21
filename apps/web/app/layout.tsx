import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CausaOps",
  description: "Find the cause. Verify the fix.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

