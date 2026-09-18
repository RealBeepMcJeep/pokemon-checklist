import { render } from "preact";
import { App } from "./App";
import { startSync, stopSync } from "./sync/engine";
import { watchAuth } from "./sync/firebase";
import { firstIncompleteLocation } from "./domain";
import {
  activeEncounters,
  focusedLocation,
  initializeState,
  mode,
  showNotice,
  speciesStatus,
  watchOtherTabs,
} from "./state";
import "./styles/themes.css";
import "./styles/app.css";
import "./styles/responsive.css";

initializeState();
watchOtherTabs();
// Sign-in is what turns sync on, and it is the only thing in the app that may
// touch the network. Signed out this fires once with no user, does nothing, and
// the app behaves exactly as the offline-only build always has.
watchAuth((user, allowed) => {
  if (!user) {
    stopSync();
    return;
  }
  if (!allowed) {
    stopSync();
    showNotice(
      `${user.email ?? "That account"} is not on the list for the shared checklist.`,
      "error",
    );
    return;
  }
  void startSync({ uid: user.uid, email: user.email });
});
document.documentElement.dataset.mode = mode.value;
focusedLocation.value =
  firstIncompleteLocation(activeEncounters.value, speciesStatus)?.id || null;

render(<App />, document.getElementById("app")!);
