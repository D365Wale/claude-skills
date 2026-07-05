import "./globals.css";

export const metadata = {
  title: "D365 ATLAS",
  description: "AI-powered D365 F&O Integration & Metadata Studio",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <span className="logo">
            D365 <strong>ATLAS</strong>
          </span>
          <nav>
            <a href="/">Metadata Search</a>
            <a href="/xpp">X++ Service Catalog</a>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
