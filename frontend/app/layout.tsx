import "./globals.css";

export const metadata = {
  title: "AlphaNexus Backtesting Lab",
  description: "Strategy backtesting dashboard for risk and return analysis",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

