import "@fontsource/barlow-condensed/latin-600.css";
import "@fontsource/barlow-condensed/latin-700.css";
import "@fontsource-variable/atkinson-hyperlegible-next/index.css";
import "./theme.css";

import { render } from "preact";

import { App } from "./App";

const root = document.getElementById("app");
if (root) render(<App />, root);
