// Kept apart from preferences.tsx (a client module) because the
// root layouts, which are server components, call this.

export const LANGUAGE_KEY = "jsm.language";
export const THEME_KEY = "jsm.theme";

/**
 * Runs in <head> before the first paint, so a returning visitor
 * does not see the default language direction or theme flash by.
 */
export function preferencesScript(themable = true): string {
  return `(function(){try{var d=document.documentElement,s=window.localStorage;
var l=s.getItem(${JSON.stringify(LANGUAGE_KEY)});
if(l==="en"){d.lang="en";d.dir="ltr";}
var t=${themable ? `s.getItem(${JSON.stringify(THEME_KEY)})` : `"light"`};
if(t==="system"){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}
d.dataset.theme=t==="dark"?"dark":"light";}catch(e){}})();`;
}
