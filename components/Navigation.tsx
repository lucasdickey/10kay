'use client';

import { SignInButton, SignUpButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { Disclosure } from "@headlessui/react";
import { HeaderSearch } from "./HeaderSearch";

export function Navigation() {
  return (
    <Disclosure as="nav" className="bg-white">
      {({ open }) => (
        <>
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-6">
              <Link href="/" className="flex items-center gap-3">
                <img src="/logo.png" alt="10KAY Logo" className="w-12 h-12" />
                <div>
                  <h1 className="text-4xl font-bold text-gray-900">10KAY</h1>
                </div>
              </Link>
            </div>

            {/* Desktop Navigation */}
            <div className="hidden lg:flex items-center gap-4">
              {/* Header Search */}
              <HeaderSearch />

              {/* Companies Link */}
              <Link
                href="/companies"
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
              >
                Companies
              </Link>

              <SignedOut>
                <SignInButton mode="modal">
                  <button className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors">
                    Sign In
                  </button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <button className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors">
                    Sign Up
                  </button>
                </SignUpButton>
              </SignedOut>

              <SignedIn>
                <Link
                  href="/dashboard"
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
                >
                  Dashboard
                </Link>
                <UserButton
                  afterSignOutUrl="/"
                  appearance={{
                    elements: {
                      avatarBox: "w-10 h-10"
                    }
                  }}
                />
              </SignedIn>
            </div>

            {/* Mobile menu button */}
            <div className="lg:hidden">
              <Disclosure.Button className="inline-flex items-center justify-center p-2 rounded-md text-gray-700 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500">
                <span className="sr-only">Open main menu</span>
                {open ? (
                  <svg
                    className="block h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                ) : (
                  <svg
                    className="block h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth="1.5"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
                    />
                  </svg>
                )}
              </Disclosure.Button>
            </div>
          </div>

          {/* Mobile menu */}
          <Disclosure.Panel className="lg:hidden">
            <div className="px-2 pt-2 pb-3 space-y-3 border-t mt-4">
              {/* Mobile Search */}
              <div className="px-3 py-2">
                <HeaderSearch />
              </div>

              {/* Mobile Companies Link */}
              <Link
                href="/companies"
                className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
              >
                Companies
              </Link>

              {/* Mobile Auth Buttons - Signed Out */}
              <SignedOut>
                <div className="space-y-2">
                  <SignInButton mode="modal">
                    <button className="w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50">
                      Sign In
                    </button>
                  </SignInButton>
                  <SignUpButton mode="modal">
                    <button className="w-full text-left px-3 py-2 rounded-md text-base font-medium text-white bg-blue-600 hover:bg-blue-700">
                      Sign Up
                    </button>
                  </SignUpButton>
                </div>
              </SignedOut>

              {/* Mobile Auth - Signed In */}
              <SignedIn>
                <Link
                  href="/dashboard"
                  className="block px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
                >
                  Dashboard
                </Link>
                <div className="px-3 py-2">
                  <UserButton
                    afterSignOutUrl="/"
                    appearance={{
                      elements: {
                        avatarBox: "w-10 h-10"
                      }
                    }}
                  />
                </div>
              </SignedIn>
            </div>
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
