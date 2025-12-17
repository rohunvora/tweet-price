import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Does Alon Tweet = $PUMP Pump?",
  description: "Analyzing the correlation between @a1lon9's tweets and $PUMP token price. See the data for yourself.",
  openGraph: {
    title: "Does Alon Tweet = $PUMP Pump?",
    description: "When Alon tweets, $PUMP averages +1.26%. When silent, -1.46%. See the data.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Does Alon Tweet = $PUMP Pump?",
    description: "When Alon tweets, $PUMP averages +1.26%. When silent, -1.46%. See the data.",
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
