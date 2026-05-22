import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'LOUDmusic Audio Analysis',
  description: 'Audio and Spotify intelligence for independent artist campaigns.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
