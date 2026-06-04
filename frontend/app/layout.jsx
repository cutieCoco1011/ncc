import "./globals.css";

export const metadata = {
  title: "ncc creator",
  description: "Local-first Korean webtoon compiler workflow"
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
