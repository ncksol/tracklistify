'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';

export default function Navigation() {
  const pathname = usePathname();

  const isActive = (path: string) => pathname === path;

  return (
    <nav className="sticky top-0 z-50 bg-carbon border-b border-carbon">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link href="/" className="flex items-center gap-2 transition-opacity hover:opacity-80">
              <Image
                src="/logo-icon.png"
                alt=""
                width={32}
                height={32}
                unoptimized
                className="rounded"
              />
              <span className="text-lg font-semibold text-sand">Tracklistify</span>
            </Link>
            <Link
              href="/history"
              className={`text-sm transition-colors ${
                isActive('/history')
                  ? 'text-saffron font-semibold'
                  : 'text-sand-light hover:text-saffron'
              }`}
            >
              History
            </Link>
            <Link
              href="/settings"
              className={`text-sm transition-colors ${
                isActive('/settings')
                  ? 'text-saffron font-semibold'
                  : 'text-sand-light hover:text-saffron'
              }`}
            >
              Settings
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
