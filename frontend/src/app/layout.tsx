import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { initializeMonitoring } from '@/lib/monitoring';
import Navigation from '@/components/Navigation';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'Tracklistify - Identify Tracks in DJ Sets',
  description: 'Identify tracks in YouTube DJ sets using audio fingerprinting',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Initialize Application Insights monitoring (only if connection string is set)
  initializeMonitoring();

  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased bg-brick-light`}>
        <Navigation />
        {children}
      </body>
    </html>
  );
}
