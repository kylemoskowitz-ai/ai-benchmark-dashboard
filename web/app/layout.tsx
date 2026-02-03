import type { Metadata } from "next";
import { IBM_Plex_Serif, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/Navigation";
import { LastUpdated } from "@/components/LastUpdated";

const ibmPlexSerif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-plex-serif",
  display: "swap",
});

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-plex-sans",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Benchmark Dashboard",
  description: "Tracking frontier AI capabilities across key benchmarks",
  openGraph: {
    title: "AI Benchmark Dashboard",
    description: "Tracking frontier AI capabilities across key benchmarks",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html 
      lang="en" 
      className={`${ibmPlexSerif.variable} ${ibmPlexSans.variable} ${ibmPlexMono.variable}`}
    >
      <body className="font-sans">
        <div className="min-h-screen flex flex-col">
          <Navigation />
          <main className="flex-1">
            {children}
          </main>
          <footer className="border-t border-base-200 py-8 mt-16">
            <div className="container-wide text-center text-body-sm text-base-500">
              <p>Data sourced from official benchmarks, Epoch AI, and community evaluations.</p>
              <p className="mt-2 text-base-400">
                Last updated: <LastUpdated />
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
