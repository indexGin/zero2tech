import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

import "./css/reset.css";
import "./css/variables.css";
import "./css/layout.css";
import "./css/hero.css";
import "./css/nav.css";
import "./css/cards.css";
import "./css/lab.css";
import "./css/responsive.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
