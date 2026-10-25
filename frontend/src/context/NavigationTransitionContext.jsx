import { createContext, useContext, useEffect } from "react";
import { useLocation } from "react-router-dom";

const NavigationTransitionContext = createContext({ generation: 0, reportReady: () => {} });

export function NavigationTransitionProvider({ value, children }) {
  return <NavigationTransitionContext.Provider value={value}>{children}</NavigationTransitionContext.Provider>;
}

export function usePageTransitionReady(ready) {
  const { pathname } = useLocation();
  const { generation, reportReady } = useContext(NavigationTransitionContext);
  useEffect(() => {
    if (ready) reportReady(pathname, generation);
  }, [pathname, generation, ready, reportReady]);
}
