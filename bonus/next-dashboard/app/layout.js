import "./globals.css";

export const metadata = {
  title: "Indus Weave Recruitment Funnel",
  description: "Recruitment funnel dashboard for Indus Weave Textiles",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
