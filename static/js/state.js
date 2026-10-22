// Shared client state; views read from here and main.js refreshes it.
export const state = {
  admin: false,
  publicMode: true,
  mfa: false,
  items: [],
  alerts: [],
  sources: {},
  candidates: [],
  loaded: false,
};
