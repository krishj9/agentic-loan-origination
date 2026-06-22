import { createBrowserRouter, RouterProvider } from "react-router-dom";

/**
 * Placeholder shell for Phase 0.
 *
 * Full route definitions and feature views are added in Phase 5 (UI/Auth).
 * The router structure is established here so subsequent phases can extend it
 * without restructuring the app entry point.
 */

const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <main
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100dvh",
          fontFamily: "system-ui, sans-serif",
          gap: "1rem",
          padding: "2rem",
        }}
      >
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, margin: 0 }}>
          Consumer Loan Origination AI
        </h1>
        <p style={{ color: "#6b7280", margin: 0 }}>
          Phase 0 — Bootstrap scaffold. UI implemented in Phase 5.
        </p>
      </main>
    ),
  },
]);

export default function App(): React.JSX.Element {
  return <RouterProvider router={router} />;
}
