import type { Metadata, Viewport } from "next";
import "./globals.css";

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,  // Allow zoom for accessibility
};

export const metadata: Metadata = {
  title: "Tweet-Price Correlation Analyzer",
  description: "Do founder tweets correlate with token price? Analyze the relationship between crypto project founders' tweets and their token's price action across multiple assets.",
  openGraph: {
    title: "Tweet-Price Correlation Analyzer",
    description: "Do founder tweets correlate with token price? Interactive charts and statistical analysis for PUMP, JUP, HYPE, ASTER, and more.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Tweet-Price Correlation Analyzer",
    description: "Do founder tweets correlate with token price? Interactive charts and statistical analysis for PUMP, JUP, HYPE, ASTER, and more.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
