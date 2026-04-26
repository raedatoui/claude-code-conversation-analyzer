import { Geist, Geist_Mono } from "next/font/google";
import { AppProvider } from "@/context/AppContext";
import type { Metadata } from "next";
import "./globals.css";

const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
});

const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
});

export const metadata: Metadata = {
    title: "Claude Code Conversation Analyzer",
    description: "Claude Code conversation quality and cost analysis",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body
                className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-background text-text-primary font-sans antialiased`}
            >
                <AppProvider>{children}</AppProvider>
            </body>
        </html>
    );
}
