import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App.js";
import { AuthProvider } from "./app/AuthContext.js";

const root = document.getElementById("root");
if (!root) throw new Error("React root element is missing");

createRoot(root).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
