import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AULA F87 Controller",
  description: "WebHID keyboard lighting controller for AULA F87",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
