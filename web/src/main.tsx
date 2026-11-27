// Copyright (c) 2026 Almoon-D. All rights reserved.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.tsx";
import { Gate } from "./auth/Gate.tsx";
import "./styles.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("index.html has no #root element");
}
createRoot(root).render(
  <StrictMode>
    <Gate>
      <App />
    </Gate>
  </StrictMode>,
);
